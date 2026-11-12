"""Dublês da simulação: LLM, música, notícia, clima e TTS (docs/melhoria-radio/f0/auditoria.md §5.3).

TTS: sem dublê de voz (padrão da função simular), o TTS fica desligado e a fala dura palavras ÷ wpm. Com
DubleTTS (F2), o sintetizador devolve um mp3 silencioso com a duração de uma voz a `wpm_real`
palavras/min, o /tts mede esse áudio e o backend calibra o ritmo da voz, sem rede.

Dois mecanismos aplicados juntos:
- por nome, em app.live.router.<nome> (padrão dos testes atuais);
- por identidade: todo atributo de módulo app.* que *seja* a função original é trocado. Isso continua
  valendo quando a F3 mover chamadas para outros módulos.

O dublê do LLM lê do prompt só o tipo do bloco, o pedido de revisão, o limite de palavras e a meta
de duração do bloco (formato musical e relógio da hora). A faixa
confirmada e o pedido da chamada chegam por canal lateral (EstadoChamada), porque as frentes
seguintes reescrevem os prompts. RNG próprio: mexer no dublê não muda a sequência aleatória do backend.

Importa app.*: só carregue este módulo depois de preparar o ambiente (scripts/simulacao/ambiente.py).
"""

import contextlib
import dataclasses
import hashlib
import importlib
import io
import json
import math
import random
import re
import sys
from collections import Counter
from typing import Any, Callable, Iterator
from unittest import mock

from app.config.settings import settings
from app.live.formato import contar_palavras, orcamento_fala
from app.live.music import MusicaEncontrada, titulo_ja_tocado
from app.live.orcamento import contar_pausas, palavras_faladas, wpm_padrao
from app.util.texto import sem_acento

from scripts.simulacao import banco_falas
from scripts.simulacao.fixtures import Catalogo, Faixa, FixturePrograma

# Lidos da mensagem/prompt do /proxima (router.py: "Tipo do próximo bloco", revisão por orçamento e
# por repetição). Tudo o mais vem do canal lateral.
TIPO_BLOCO_RE = re.compile(r"Tipo do próximo bloco: (.+)\.")
LIMITE_REVISAO_RE = re.compile(r"Reescreva com no máximo (\d+) palavras")
# Meta de duração do bloco no prompt (formato musical e relógio da hora, F1): mínimo, máximo, palavras.
META_BLOCO_RE = re.compile(r"(\d+) a (\d+) segundos, no máximo (\d+) palavras")
MARCA_REVISAO_PARECIDA = "ficou muito parecida"
# Revisão em que o motivo é a duração estimada (F2), não só o limite de palavras.
MARCA_REVISAO_DURACAO = "ultrapassou o tempo de locução"

_BASES_CATEGORIA = (
    "musica", "noticia", "escalada", "servico", "plantao", "reporter",
    "chamada_ouvinte", "abertura", "comentario", "encerramento",
)


def normalizar(texto: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", sem_acento((texto or "").lower())).strip()


def categoria_do_tipo(tipo: str) -> str:
    """Categoria do bloco pelas mesmas regras de prefixo do backend (sem chamar classificação)."""
    bruto = sem_acento((tipo or "").strip().lower())
    if bruto.startswith(("vinheta:", "patrocinador:")):
        return bruto.split(":", 1)[0]
    if bruto in ("retomada", "identificacao"):
        return "abertura"
    for base in _BASES_CATEGORIA:
        if bruto == base or bruto.startswith((f"{base} ", f"{base}_")):
            return base
    return bruto


@dataclasses.dataclass
class EstadoChamada:
    """Canal lateral entre o simulador e os dublês, zerado antes de cada POST /proxima."""

    chamada_id: int = 0
    bloco_n: int = 0
    total_falas: int = 0
    retrato_pedidos: dict[int, str] = dataclasses.field(default_factory=dict)
    faixa: Faixa | None = None

    def nova_chamada(self, bloco_n: int, total_falas: int, retrato_pedidos: dict[int, str] | None = None) -> None:
        self.chamada_id += 1
        self.bloco_n = bloco_n
        self.total_falas = total_falas
        self.retrato_pedidos = dict(retrato_pedidos or {})
        self.faixa = None

    def registrar_faixa(self, faixa: Faixa) -> None:
        self.faixa = faixa


class _Espacos(dict):
    def __missing__(self, chave: str) -> str:
        return ""


def _preencher(modelo: str, espacos: dict[str, str]) -> str:
    return re.sub(r"\s+([,.;:!?])", r"\1", modelo.format_map(_Espacos(espacos))).strip()


class DubleLLM:
    """Substitui gerar_resposta/gerar_dialogo_multivoz e as classificações auxiliares."""

    def __init__(self, fixture: FixturePrograma, estado: EstadoChamada, wpm: float | None = None, semente: int = 7,
                 sessao=None):
        self.fixture = fixture
        self.estado = estado
        # Sem ritmo explícito, o padrão do backend (mesma origem de app.live.orcamento).
        self.wpm = wpm if wpm is not None else wpm_padrao(settings.elevenlabs_model)
        self.sessao = sessao
        self.rng = random.Random(f"duble-llm:{semente}")
        self.contadores: Counter = Counter()
        self.temas: dict[str, str] = {}
        self._chamada_vista: int | None = None
        self._fala_n = 0
        self._tentativa = 0
        self._ultimos_indices: dict[tuple[str, str], int] = {}
        self._uso_meios: Counter = Counter()
        self._espacos_base = {
            "radio": fixture.conta.nome_radio,
            "programa": str(fixture.programa.get("nome", "")),
            "locutor": fixture.radialista.nome_locutor,
        }

    # --- funções do app.llm.client -------------------------------------------------------------

    def gerar_resposta(self, system_prompt: str, mensagem_usuario: str) -> str:
        self.contadores["gerar_resposta"] += 1
        return self._gerar(system_prompt, mensagem_usuario)

    def gerar_dialogo_multivoz(self, system_prompt: str, mensagem_usuario: str) -> str:
        self.contadores["gerar_dialogo_multivoz"] += 1
        texto = self._gerar(system_prompt, mensagem_usuario)
        linha = {"locutor": self.fixture.radialista.nome_locutor, "texto": texto}
        return json.dumps({"linhas": [linha]}, ensure_ascii=False)

    def classificar_tema_fala(self, texto: str) -> str:
        self.contadores["classificar_tema_fala"] += 1
        return self.temas.get(texto) or " ".join(normalizar(texto).split()[:4])

    def classificar_fio_condutor(self, texto: str) -> str:
        self.contadores["classificar_fio_condutor"] += 1
        return ""

    def classificar_tom_fala(self, texto: str, tipo_bloco: str | None = None) -> str:
        self.contadores["classificar_tom_fala"] += 1
        return "neutro"

    def classificar_categoria_bloco(self, nome_bloco: str) -> str:
        self.contadores["classificar_categoria_bloco"] += 1
        categoria = categoria_do_tipo(nome_bloco)
        return categoria if categoria in _BASES_CATEGORIA else "comentario"

    def itens_fora_do_genero(self, itens: list[str], generos: list[str]) -> set[int]:
        self.contadores["itens_fora_do_genero"] += 1
        return set()

    # --- geração ---------------------------------------------------------------------------------

    def _gerar(self, system_prompt: str, mensagem: str) -> str:
        achado = TIPO_BLOCO_RE.search(mensagem or "")
        if achado:
            self.contadores["tipo_reconhecido"] += 1
            tipo = achado.group(1).strip()
        else:
            self.contadores["tipo_nao_reconhecido"] += 1
            tipo = "padrao"

        if self.estado.chamada_id != self._chamada_vista:
            self._chamada_vista = self.estado.chamada_id
            self._fala_n += 1
            self._tentativa = 0
            self.contadores["falas"] += 1
        else:
            self._tentativa += 1
            self.contadores["revisoes"] += 1
            if MARCA_REVISAO_DURACAO in (system_prompt or ""):
                self.contadores["revisoes_duracao"] += 1

        categoria = categoria_do_tipo(tipo)
        primeira = self.estado.total_falas == 0
        pedido = self._pedido_da_chamada()
        faixa = self.estado.faixa if categoria == "musica" else None
        if categoria == "musica":
            self.contadores["blocos_musica_llm"] += 1
            if faixa is not None:
                self.contadores["faixa_reconhecida"] += 1

        modelo = self._modelo(tipo, categoria, primeira, pedido, faixa)
        espacos = {
            **self._espacos_base,
            "quadro": self.fixture.rotulos_quadros.get(tipo, "quadro"),
            "nome": getattr(pedido, "nome", "") or "um ouvinte",
            "titulo": faixa.titulo if faixa else "",
            "artista": faixa.artista if faixa else "",
        }

        alvo, teto = self._palavras(tipo, categoria, primeira, META_BLOCO_RE.findall(system_prompt or ""))
        limite = LIMITE_REVISAO_RE.search(system_prompt or "")
        persistente = next((i for i in self.fixture.injecoes
                            if i.fala == self._fala_n and i.tipo == "excesso_persistente"), None)
        if persistente is not None:
            # Ignora o limite da reescrita também: o backend precisa encurtar sem uma terceira chamada.
            alvo = teto = round(alvo * persistente.fator)
            self.contadores["injecao_excesso_persistente"] += 1
        elif limite:
            teto = min(teto, int(limite.group(1)))
            alvo = min(alvo, teto)

        extras: list[str] = []
        for injecao in (i for i in self.fixture.injecoes if i.fala == self._fala_n):
            if injecao.tipo == "excesso" and self._tentativa == 0 and not limite:
                alvo = round(alvo * injecao.fator)
                teto = alvo
                self.contadores["injecao_excesso"] += 1
            elif injecao.tipo == "promessa":
                extras.append(injecao.frase)
                self.contadores["injecao_promessa"] += 1
            elif injecao.tipo == "cita_musica":
                extras.append(banco_falas.INJECAO_CITA_MUSICA.format(titulo=injecao.titulo, artista=injecao.artista))
                self.contadores["injecao_cita_musica"] += 1
            elif injecao.tipo == "cita_ouvinte":
                extras.append(banco_falas.INJECAO_CITA_OUVINTE.format(nome=injecao.nome))
                self.contadores["injecao_cita_ouvinte"] += 1

        palavras_extras = sum(contar_palavras(e) for e in extras)
        evitar = MARCA_REVISAO_PARECIDA in (system_prompt or "")
        texto, tema = self._montar(modelo, max(1, alvo - palavras_extras), max(1, teto - palavras_extras),
                                   espacos, evitar)
        if extras:
            texto = " ".join([texto, *extras])
        self.temas[texto] = tema
        return texto

    def _palavras(self, tipo: str, categoria: str, primeira: bool, metas=()) -> tuple[int, int]:
        if metas:
            # Meta que o backend pôs no prompt (a última vale): a mesma conta do formato musical abaixo.
            minimo, maximo, palavras = (int(v) for v in metas[-1])
            alvo_s, teto = (minimo + maximo) / 2, min(palavras, math.floor(self.wpm * maximo / 60))
        elif self.fixture.formato_musical:
            # Mesma função do backend (app/live/formato.py): meta em segundos e teto de palavras.
            minimo, maximo, palavras = orcamento_fala(tipo, primeira)
            alvo_s, teto = (minimo + maximo) / 2, min(palavras, math.floor(self.wpm * maximo / 60))
        else:
            orcamento = self.fixture.orcamento_para(tipo, categoria)
            alvo_s, teto = orcamento.alvo_s(), math.floor(self.wpm * orcamento.max / 60)
        return min(round(self.wpm * alvo_s / 60), teto), teto

    def _modelo(self, tipo: str, categoria: str, primeira: bool, pedido, faixa: Faixa | None) -> str:
        if categoria == "musica":
            if faixa is None:
                return "musica_sem_faixa"
            if pedido is not None and pedido.tipo == "musica":
                return "musica_pedido" if _pedido_bate(pedido, faixa) else "musica_pedido_substituta"
            return "musica"
        if categoria == "chamada_ouvinte":
            if pedido is None:
                return "chamada_convite"
            return "chamada_sorteio" if pedido.tipo == "sorteio" else "chamada_pedido"
        if categoria == "abertura":
            bruto = normalizar(tipo)
            if bruto == "identificacao":
                return "identificacao"
            if bruto == "retomada" or (self.fixture.formato_musical and not primeira):
                return "retomada"
            return "abertura" if primeira else "reabertura"
        if categoria == "comentario":
            return "quadro" if tipo in (self.fixture.programa.get("quadros_fixos") or {}) else "comentario"
        if categoria == "encerramento":
            return "encerramento"
        return "reabertura"

    def _escolher(self, modelo: str, parte: str, opcoes: list[str], evitar: bool,
                  cabe: Callable[[str], bool] = lambda _: True) -> str:
        """Sorteia uma variante (com o RNG do dublê) entre as que cabem; na revisão por repetição, troca."""
        indices = [i for i, opcao in enumerate(opcoes) if cabe(opcao)] or [
            min(range(len(opcoes)), key=lambda i: contar_palavras(opcoes[i]))
        ]
        anterior = self._ultimos_indices.get((modelo, parte))
        if evitar and anterior in indices and len(indices) > 1:
            indices.remove(anterior)
        indice = self.rng.choice(indices)
        self._ultimos_indices[(modelo, parte)] = indice
        return opcoes[indice]

    def _montar(self, modelo: str, alvo: int, teto: int, espacos: dict[str, str], evitar: bool) -> tuple[str, str]:
        banco = banco_falas.BANCO[modelo]

        def palavras(modelo_frase: str) -> int:
            return contar_palavras(_preencher(modelo_frase, espacos))

        # Abertura e gancho carregam o essencial (nome, faixa, identificação): escolhe variantes que cabem
        # juntas no teto antes de pensar em frases de meio e fechamento.
        abertura = _preencher(self._escolher(modelo, "aberturas", banco["aberturas"], evitar,
                                             lambda a: palavras(a) + 1 <= teto), espacos)
        restante = teto - contar_palavras(abertura)
        gancho = _preencher(self._escolher(modelo, "ganchos", banco["ganchos"], evitar,
                                           lambda g: palavras(g) <= restante), espacos)
        fechamento = _preencher(self._escolher(modelo, "fechamentos", banco["fechamentos"], evitar), espacos)
        frases = [f for f in (abertura, gancho) if f]
        total = sum(contar_palavras(f) for f in frases)
        reserva = contar_palavras(fechamento)

        # Frases do próprio tema primeiro, genéricas depois; cada uma no máximo uma vez por fala e, entre
        # falas, as menos usadas antes (sem isso o banco pequeno faz o backend pedir revisão por repetição).
        meios: list[tuple[str, str]] = []
        for conjunto in (banco["meios"], banco.get("meios_extra", [])):
            embaralhadas = list(conjunto)
            self.rng.shuffle(embaralhadas)
            embaralhadas.sort(key=lambda m: self._uso_meios[m])
            meios += [(m, _preencher(m, espacos)) for m in embaralhadas]
        for modelo_frase, meio in meios:
            if meio not in frases and total + contar_palavras(meio) + reserva <= alvo:
                frases.append(meio)
                total += contar_palavras(meio)
                self._uso_meios[modelo_frase] += 1
        if fechamento and total + reserva <= teto:
            frases.append(fechamento)
            total += reserva
        while total > teto and len(frases) > 1:
            total -= contar_palavras(frases.pop())
        if total > teto:
            frases = [" ".join(frases[0].split()[:teto]).rstrip(",;:.") + "."]
        tema = f"{modelo}: {' '.join(normalizar(gancho or abertura).split()[:4])}"
        return " ".join(frases), tema

    def _pedido_da_chamada(self):
        """Pedido que mudou para selecionado/historico_legado nesta chamada (retrato tirado antes do POST)."""
        if self.sessao is None:
            return None
        from app.models.fila_ao_vivo import FilaAoVivo

        linhas = (
            self.sessao.query(FilaAoVivo)
            .filter(FilaAoVivo.estado.in_(("selecionado", "historico_legado")))
            .order_by(FilaAoVivo.id.asc())
            .all()
        )
        for pedido in linhas:
            if self.estado.retrato_pedidos.get(pedido.id) != pedido.estado:
                return pedido
        return None


class DubleTTS:
    """Sintetizador falso (F2): mp3 silencioso com a duração de uma voz a `wpm_real` palavras/min (palavras
    faladas, como a estimativa do backend) mais as pausas explícitas, via pydub e ffmpeg, sem rede. O mesmo
    texto dá os mesmos bytes, como o cache de TTS; textos diferentes, bytes diferentes (tag com o hash)."""

    def __init__(self, wpm_real: float, pausa_s: float | None = None):
        if wpm_real <= 0:
            raise ValueError("wpm_real deve ser maior que zero")
        self.wpm_real = wpm_real
        self.pausa_s = settings.fala_pausa_explicita_s if pausa_s is None else pausa_s
        self.contadores: Counter = Counter()
        self._audios: dict[str, bytes] = {}

    def duracao_s(self, texto: str) -> float:
        return palavras_faladas(texto) * 60 / self.wpm_real + contar_pausas(texto) * self.pausa_s

    def _mp3(self, texto: str) -> bytes:
        if texto not in self._audios:
            from pydub import AudioSegment

            buffer = io.BytesIO()
            AudioSegment.silent(duration=round(self.duracao_s(texto) * 1000), frame_rate=16000).export(
                buffer, format="mp3", tags={"comment": hashlib.sha1(texto.encode()).hexdigest()[:16]})
            self._audios[texto] = buffer.getvalue()
        return self._audios[texto]

    def sintetizar_audio(self, texto: str, voice_id: str | None = None, **_opcoes) -> bytes:
        self.contadores["sintetizar_audio"] += 1
        self.contadores["caracteres_tts"] += len(texto)
        return self._mp3(texto)

    def sintetizar_audio_stream(self, texto: str, voice_id: str | None = None, **_opcoes) -> Iterator[bytes]:
        self.contadores["sintetizar_audio"] += 1
        self.contadores["caracteres_tts"] += len(texto)
        yield self._mp3(texto)


def _pedido_bate(pedido, faixa: Faixa) -> bool:
    tokens = set(normalizar(pedido.musica_query or pedido.mensagem_usuario or "").split())
    return bool(tokens) and tokens <= set(normalizar(f"{faixa.titulo} {faixa.artista}").split())


class CatalogoSimulado:
    """Busca de música sobre o catálogo fictício da fixture: primeira faixa livre na ordem do catálogo."""

    def __init__(self, catalogo: Catalogo, estado: EstadoChamada, extras: list[tuple[str, str]] | None = None):
        self.faixas = list(catalogo.faixas)
        self.estado = estado
        # Títulos citáveis fora do catálogo (injeções): o extrator os reconhece, a busca nunca os acha.
        self.extras = list(extras or [])
        self.contadores: Counter = Counter()

    def _livre(self, faixa: Faixa, bloqueados, evitar_video_ids, titulos_tocados) -> bool:
        if faixa.indisponivel or faixa.video_id in (evitar_video_ids or ()):
            return False
        if titulo_ja_tocado(faixa.titulo, set(titulos_tocados or ())):
            return False
        texto = normalizar(f"{faixa.artista} {faixa.titulo}")
        return not any(normalizar(b) and normalizar(b) in texto for b in (bloqueados or []))

    def _encontrada(self, faixa: Faixa) -> MusicaEncontrada:
        self.estado.registrar_faixa(faixa)
        self.contadores["faixas_devolvidas"] += 1
        return MusicaEncontrada(
            video_id=faixa.video_id, titulo=faixa.titulo, canal=faixa.artista, inicio_segundos=0,
            fim_segundos=faixa.fim_s, duracao_segundos=faixa.duracao_s, descricao=faixa.contexto,
        )

    def buscar_musica(self, query: str, genero: str | None = None, bloqueados=None, evitar_video_ids=None,
                      titulos_tocados=None, canais_recentes=None, **_opcoes) -> MusicaEncontrada | None:
        self.contadores["buscar_musica"] += 1
        from app.live.router import QUERY_MUSICA_GENERICA

        consulta = normalizar(query)
        if consulta == normalizar(QUERY_MUSICA_GENERICA):
            candidatas = self.faixas
        elif genero and consulta == f"{normalizar(genero)} musica":
            candidatas = [f for f in self.faixas if normalizar(genero) in [normalizar(g) for g in f.generos]]
        else:
            tokens = set(consulta.split())
            candidatas = [f for f in self.faixas if tokens and tokens <= set(normalizar(f"{f.titulo} {f.artista}").split())]
        # Como app.live.music.buscar_musica: duracao_max_segundos é preferência (faixa mais longa só se não
        # houver outra), nunca bloqueio. O padrão do backend (8 min) não exclui nada do catálogo fictício.
        duracao_max = _opcoes.get("duracao_max_segundos")
        livres = [f for f in candidatas if self._livre(f, bloqueados, evitar_video_ids, titulos_tocados)]
        preferidas = [f for f in livres if duracao_max is None or f.duracao_tocada_s <= duracao_max]
        if preferidas or livres:
            return self._encontrada((preferidas or livres)[0])
        return None

    def resolver_musica_catalogada(self, db, titulo: str, artista: str, bloqueados=None, evitar_video_ids=None,
                                   titulos_tocados=None, canais_recentes=None, origem: str = "") -> MusicaEncontrada | None:
        self.contadores["resolver_musica_catalogada"] += 1
        for faixa in self.faixas:
            if normalizar(faixa.titulo) == normalizar(titulo) and normalizar(faixa.artista) == normalizar(artista):
                return self._encontrada(faixa) if self._livre(faixa, bloqueados, evitar_video_ids, titulos_tocados) else None
        return None

    def buscar_faixas_por_categoria(self, genero: str, excluir_titulos=None) -> list[tuple[str, str]]:
        self.contadores["buscar_faixas_por_categoria"] += 1
        alvo = normalizar(genero)
        return [
            (f.artista, f.titulo) for f in self.faixas
            if not f.indisponivel and alvo in [normalizar(g) for g in f.generos]
            and not titulo_ja_tocado(f.titulo, set(excluir_titulos or ()))
        ]

    def sugerir_musica_do_genero(self, genero: str) -> str:
        self.contadores["sugerir_musica_do_genero"] += 1
        alvo = normalizar(genero)
        for faixa in self.faixas:
            if not faixa.indisponivel and alvo in [normalizar(g) for g in faixa.generos]:
                return f"{faixa.artista} - {faixa.titulo}"
        return ""

    def resumir_contexto_musica(self, titulo: str, canal: str, descricao: str, tags, ano) -> str:
        self.contadores["resumir_contexto_musica"] += 1
        return descricao or ""

    def citaveis(self) -> list[tuple[str, str]]:
        """(título, artista) de tudo que pode ser citado numa fala: catálogo inteiro e injeções."""
        vistos, itens = set(), []
        for titulo, artista in [(f.titulo, f.artista) for f in self.faixas] + self.extras:
            chave = (normalizar(titulo), normalizar(artista))
            if chave not in vistos:
                vistos.add(chave)
                itens.append((titulo, artista))
        return itens

    def extrair_musicas_citadas(self, fala: str, ja_tocadas: list[str] | None = None) -> list[str]:
        self.contadores["extrair_musicas_citadas"] += 1
        ignorar = {normalizar(item.rsplit(" - ", 1)[0]) for item in (ja_tocadas or [])}
        texto = f" {normalizar(fala)} "
        achadas = []
        for titulo, artista in self.citaveis():
            chave = normalizar(titulo)
            posicao = texto.find(f" {chave} ")
            if chave and posicao >= 0 and chave not in ignorar:
                achadas.append((posicao, f"{artista} - {titulo}"))
        return [rotulo for _, rotulo in sorted(achadas)]


@dataclasses.dataclass(frozen=True)
class Alvo:
    modulo: str
    nome: str
    # texto: só no modo fake | apoio: todos os modos | tts: fake e llm (o modo completo usa o real)
    grupo: str
    por_nome: tuple[str, ...] = ("app.live.router",)


ALVOS: tuple[Alvo, ...] = (
    Alvo("app.llm.client", "gerar_resposta", "texto"),
    Alvo("app.llm.client", "gerar_dialogo_multivoz", "texto"),
    Alvo("app.llm.client", "classificar_fio_condutor", "apoio"),
    Alvo("app.llm.client", "classificar_categoria_bloco", "apoio"),
    Alvo("app.llm.client", "classificar_tema_fala", "apoio"),
    Alvo("app.llm.client", "classificar_tom_fala", "apoio"),
    Alvo("app.llm.client", "extrair_musicas_citadas", "apoio"),
    Alvo("app.llm.client", "itens_fora_do_genero", "apoio", ("app.live.router", "app.live.spotify")),
    Alvo("app.llm.client", "sugerir_musica_do_genero", "apoio"),
    Alvo("app.llm.client", "resumir_contexto_musica", "apoio"),
    Alvo("app.live.router", "_registrar_tema_em_background", "apoio"),
    Alvo("app.live.music", "buscar_musica", "apoio"),
    Alvo("app.live.song_service", "resolver_musica_catalogada", "apoio"),
    Alvo("app.live.spotify", "buscar_faixas_por_categoria", "apoio"),
    Alvo("app.llm.noticias", "pesquisar_noticias", "apoio"),
    Alvo("app.weather.client", "obter_clima_atual", "apoio", ("app.llm.prompt_builder",)),
    Alvo("app.weather.client", "obter_leitura_clima", "apoio"),
    Alvo("app.tts.client", "tts_habilitado", "tts"),
    Alvo("app.tts.client", "sintetizar_audio", "tts"),
    Alvo("app.tts.client", "sintetizar_audio_stream", "tts"),
    Alvo("app.postprod.client", "processar_audio", "tts"),
    Alvo("app.tts.client", "obter_metadados_voz", "tts", ("app.tts.profiles",)),
)


@dataclasses.dataclass
class Dubles:
    estado: EstadoChamada
    llm: DubleLLM
    musicas: CatalogoSimulado
    contadores: Counter
    substituidos: list[str]
    tts: DubleTTS | None = None

    def chamadas_por_funcao(self) -> dict[str, int]:
        total = Counter()
        total.update(self.llm.contadores)
        total.update(self.musicas.contadores)
        total.update(self.contadores)
        if self.tts is not None:
            total.update(self.tts.contadores)
        return dict(sorted(total.items()))


class _EspiaoTexto:
    """Modos pagos: chama o LLM real, mas conta falas e revisões como o dublê."""

    def __init__(self, original: Callable, nome: str, llm: DubleLLM):
        self.original, self.nome, self.llm = original, nome, llm

    def __call__(self, *args, **kwargs):
        contadores, estado = self.llm.contadores, self.llm.estado
        contadores[self.nome] += 1
        if estado.chamada_id != self.llm._chamada_vista:
            self.llm._chamada_vista = estado.chamada_id
            contadores["falas"] += 1
        else:
            contadores["revisoes"] += 1
        return self.original(*args, **kwargs)


def _substitutos(modo: str, llm: DubleLLM, musicas: CatalogoSimulado, contadores: Counter, sessao,
                 tts: DubleTTS | None = None) -> dict[str, Any]:
    from app.llm.noticias import PesquisaNoticias

    def contar(nome: str, valor_ou_funcao):
        def _f(*args, **kwargs):
            contadores[nome] += 1
            return valor_ou_funcao(*args, **kwargs) if callable(valor_ou_funcao) else valor_ou_funcao
        return _f

    def _tts_desligado(*args, **kwargs):
        contadores["sintetizar_audio_bloqueado"] += 1
        raise RuntimeError("TTS desligado na simulação (modo fake/llm)")

    def _registrar_tema(programa_id: int, texto: str) -> None:
        """Versão síncrona de _registrar_tema_em_background: sem thread solta, na sessão da simulação."""
        contadores["registrar_tema"] += 1
        tema = llm.classificar_tema_fala(texto)
        if not tema:
            return
        from app.live import router

        router._registrar_tema(programa_id, tema)
        if sessao is not None:
            router._registrar_tema_persistente(sessao, programa_id, tema)

    return {
        "gerar_resposta": llm.gerar_resposta,
        "gerar_dialogo_multivoz": llm.gerar_dialogo_multivoz,
        "classificar_fio_condutor": llm.classificar_fio_condutor,
        "classificar_categoria_bloco": llm.classificar_categoria_bloco,
        "classificar_tema_fala": llm.classificar_tema_fala,
        "classificar_tom_fala": llm.classificar_tom_fala,
        "extrair_musicas_citadas": musicas.extrair_musicas_citadas,
        "itens_fora_do_genero": llm.itens_fora_do_genero,
        "sugerir_musica_do_genero": musicas.sugerir_musica_do_genero,
        "resumir_contexto_musica": musicas.resumir_contexto_musica,
        "_registrar_tema_em_background": _registrar_tema,
        "buscar_musica": musicas.buscar_musica,
        "resolver_musica_catalogada": musicas.resolver_musica_catalogada,
        "buscar_faixas_por_categoria": musicas.buscar_faixas_por_categoria,
        "pesquisar_noticias": contar("pesquisar_noticias",
                                     lambda *a, **k: PesquisaNoticias(status="desabilitada")),
        "obter_clima_atual": contar("obter_clima_atual", lambda *a, **k: None),
        "obter_leitura_clima": contar("obter_leitura_clima", lambda *a, **k: None),
        "tts_habilitado": contar("tts_habilitado", lambda *a, **k: tts is not None),
        "sintetizar_audio": tts.sintetizar_audio if tts is not None else _tts_desligado,
        "sintetizar_audio_stream": tts.sintetizar_audio_stream if tts is not None else _tts_desligado,
        "processar_audio": contar("processar_audio", lambda audio, *a, **k: audio),
        "obter_metadados_voz": contar("obter_metadados_voz", lambda *a, **k: None),
    }


def _modulos_app() -> Iterator[tuple[str, Any]]:
    for nome, modulo in list(sys.modules.items()):
        if modulo is not None and (nome == "app" or nome.startswith("app.")):
            yield nome, modulo


@contextlib.contextmanager
def aplicar_dubles(fixture: FixturePrograma, catalogo: Catalogo, modo: str = "fake", sessao=None,
                   estado: EstadoChamada | None = None, wpm: float | None = None, semente: int = 7,
                   tts_wpm_real: float | None = None) -> Iterator[Dubles]:
    """`tts_wpm_real` liga o DubleTTS (modos fake e llm); None mantém o TTS desligado (linha de base)."""
    estado = estado or EstadoChamada()
    llm = DubleLLM(fixture, estado, wpm=wpm, semente=semente, sessao=sessao)
    extras = [(i.titulo, i.artista) for i in fixture.injecoes if i.tipo == "cita_musica" and i.titulo]
    musicas = CatalogoSimulado(catalogo, estado, extras=extras)
    contadores: Counter = Counter()
    tts = DubleTTS(tts_wpm_real) if tts_wpm_real is not None and modo != "completo" else None
    substitutos = _substitutos(modo, llm, musicas, contadores, sessao, tts)
    substituidos: list[str] = []

    with contextlib.ExitStack() as pilha:
        for alvo in ALVOS:
            original = getattr(importlib.import_module(alvo.modulo), alvo.nome)
            if alvo.grupo == "texto" and modo != "fake":
                novo = _EspiaoTexto(original, alvo.nome, llm)
            elif alvo.grupo == "tts" and modo == "completo":
                continue
            else:
                novo = substitutos[alvo.nome]
            for nome_modulo in alvo.por_nome:
                modulo = sys.modules.get(nome_modulo) or importlib.import_module(nome_modulo)
                if hasattr(modulo, alvo.nome):
                    pilha.enter_context(mock.patch.object(modulo, alvo.nome, novo))
                    substituidos.append(f"{nome_modulo}.{alvo.nome}")
            for nome_modulo, modulo in _modulos_app():
                for atributo, valor in list(vars(modulo).items()):
                    if valor is original:
                        pilha.enter_context(mock.patch.object(modulo, atributo, novo))
                        substituidos.append(f"{nome_modulo}.{atributo}")

        noticias = importlib.import_module("app.llm.noticias")

        def _criar_mensagem_noticia(**kwargs):
            contadores["noticias_client_create"] += 1
            from types import SimpleNamespace
            return SimpleNamespace(stop_reason="end_turn", content=[])

        pilha.enter_context(mock.patch.object(noticias._client.messages, "create", _criar_mensagem_noticia))
        yield Dubles(estado=estado, llm=llm, musicas=musicas, contadores=contadores, substituidos=substituidos,
                     tts=tts)


class BloqueioRede:
    """Modo fake: qualquer tentativa de abrir conexão de rede é contada e falha."""

    def __init__(self):
        self.tentativas = 0
        self.destinos: list[str] = []
        self._originais: tuple | None = None

    def _registrar(self, destino) -> None:
        self.tentativas += 1
        self.destinos.append(str(destino)[:120])

    def __enter__(self) -> "BloqueioRede":
        import socket

        originais = (socket.getaddrinfo, socket.create_connection, socket.socket.connect, socket.socket.connect_ex)
        self._originais = originais
        bloqueio = self

        def getaddrinfo(host, *args, **kwargs):
            bloqueio._registrar(host)
            raise OSError("rede bloqueada na simulação (modo fake)")

        def create_connection(endereco, *args, **kwargs):
            bloqueio._registrar(endereco)
            raise OSError("rede bloqueada na simulação (modo fake)")

        def connect(sock, endereco):
            if getattr(socket, "AF_UNIX", None) is not None and sock.family == socket.AF_UNIX:
                return originais[2](sock, endereco)
            bloqueio._registrar(endereco)
            raise OSError("rede bloqueada na simulação (modo fake)")

        def connect_ex(sock, endereco):
            if getattr(socket, "AF_UNIX", None) is not None and sock.family == socket.AF_UNIX:
                return originais[3](sock, endereco)
            bloqueio._registrar(endereco)
            raise OSError("rede bloqueada na simulação (modo fake)")

        socket.getaddrinfo = getaddrinfo
        socket.create_connection = create_connection
        socket.socket.connect = connect
        socket.socket.connect_ex = connect_ex
        return self

    def __exit__(self, *exc) -> None:
        import socket

        assert self._originais is not None
        socket.getaddrinfo, socket.create_connection, socket.socket.connect, socket.socket.connect_ex = self._originais
