"""Dublês da simulação: LLM, música, notícia, clima e TTS (docs/melhoria-radio/f0/auditoria.md §5.3).

TTS: sem dublê de voz (padrão da função simular), o TTS fica desligado e a fala dura palavras ÷ wpm. Com
DubleTTS (F2), o sintetizador devolve um mp3 silencioso com a duração de uma voz a `wpm_real`
palavras/min, o /tts mede esse áudio e o backend calibra o ritmo da voz, sem rede.

Dois mecanismos aplicados juntos:
- por nome, em app.live.router.<nome> (padrão dos testes atuais);
- por identidade: todo atributo de módulo app.* que *seja* a função original é trocado. Isso continua
  valendo quando a F3 mover chamadas para outros módulos.

O dublê do LLM lê do prompt só o tipo do bloco, o pedido de revisão, o limite de palavras, a meta
de duração do bloco (formato musical e relógio da hora) e, desde a F5, o bloco de dados da mensagem (para o modo
`duble_usa_dados` e para medir se texto externo da fixture apareceu fora dele). Desde a F6, por canal lateral, se
o system de cada bloco de fala tinha a direção do formato que o backend resolve para o programa (ou a de outro
formato); o texto continua do banco, igual para todo formato (fato 7 da auditoria da F6). A faixa
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
from app.live.formato import contar_palavras
from app.live.formatos import FORMATOS, unidade as unidade_do_formato
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
# F5: cabeçalho do bloco de dados da mensagem (app.dados.fontes.CABECALHO_BLOCO).
CABECALHO_DADOS = "Dados de referência deste bloco ("
# Tipos de dado que o dublê "obediente" cita (duble_usa_dados) e as injeções de dado (F5).
TIPOS_CITAVEIS = ("clima", "noticia", "servico", "transito", "aviso", "agenda", "esporte", "correcao")
INJECOES_DADO = ("dado_sem_fonte", "dado_vencido")
# F6: injeções de coerência com o formato que só acrescentam a frase da fixture (convite, tema que exige revisão).
INJECOES_FRASE_F6 = ("convite", "tema_revisao")
# H0: vazamento, sinal de IA e bordão, também só a frase da fixture (copiada do corpus de humanização).
INJECOES_FRASE_H0 = ("vazamento", "sinal_ia", "bordao")

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
        # F5: o bloco de dados que cada bloco recebeu e as frases legítimas (com dado) que o dublê disse nele.
        self.blocos_dados: dict[int, list[dict]] = {}
        self.legitimas: dict[int, list[str]] = {}
        self._externos = _textos_externos(fixture)
        # F6, canal lateral: por bloco de fala, o system tinha a direção do formato que o backend resolve para o
        # programa? E a de outro formato? (como os contadores de injeção da F5)
        self.formato_esperado = fixture.formato_backend
        self.instrucao_por_bloco: dict[int, tuple[bool, bool]] = {}
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
            self._registrar_instrucao(system_prompt or "")
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

        debate = next((i for i in self.fixture.injecoes if i.fala == self._fala_n and i.tipo == "debate_longo"), None)
        if debate is not None:
            # F6: uma frase corrida de `segundos`, em toda tentativa (nem a reescrita nem o encurtamento por frases
            # resolvem): mede o aviso fora_da_unidade, que não corta nada (D21).
            self.contadores["injecao_debate_longo"] += 1
            texto = _debate_longo(round(self.wpm * debate.segundos / 60))
            self.temas[texto] = "debate_longo"
            return texto

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

            elif injecao.tipo in INJECOES_DADO:
                extras.append(injecao.frase)
                self.contadores["injecao_dado"] += 1
            elif injecao.tipo == "obedece_injecao":
                extras.append(injecao.frase)
                self.contadores["injecao_obedece"] += 1
            elif injecao.tipo in INJECOES_FRASE_F6 + INJECOES_FRASE_H0:
                extras.append(injecao.frase)
                self.contadores[f"injecao_{injecao.tipo}"] += 1

        dados = self._ler_dados(system_prompt or "", mensagem or "")
        if self.fixture.duble_usa_dados and categoria not in ("musica", "encerramento"):
            legitima = _frase_com_dado(dados)
            if legitima:
                extras.insert(0, legitima)
                self.legitimas.setdefault(self.estado.bloco_n, [])
                if legitima not in self.legitimas[self.estado.bloco_n]:
                    self.legitimas[self.estado.bloco_n].append(legitima)
                self.contadores["frases_com_dado"] += 1

        palavras_extras = sum(contar_palavras(e) for e in extras)
        evitar = MARCA_REVISAO_PARECIDA in (system_prompt or "")
        texto, tema = self._montar(modelo, max(1, alvo - palavras_extras), max(1, teto - palavras_extras),
                                   espacos, evitar)
        if extras:
            texto = " ".join([texto, *extras])
        self.temas[texto] = tema
        return texto

    def _ler_dados(self, system: str, mensagem: str) -> list[dict]:
        """O bloco de dados da mensagem (F5) e, de passagem, se texto externo da fixture apareceu fora dele."""
        linhas = mensagem.split("\n")
        inicio = next((i for i, linha in enumerate(linhas) if linha.startswith(CABECALHO_DADOS)), None)
        dados: list[dict] = []
        fora = mensagem
        if inicio is not None:
            fim = next((i for i in range(inicio + 1, len(linhas)) if linhas[i].endswith("]")), inicio)
            bloco = "\n".join(linhas[inicio + 1:fim + 1])
            try:
                dados = json.loads(bloco)
            except ValueError:
                self.contadores["bloco_dados_invalido"] += 1
            fora = "\n".join(linhas[:inicio] + linhas[fim + 1:])
            self.blocos_dados[self.estado.bloco_n] = dados
        if any(t in system for t in self._externos):
            self.contadores["injecao_no_system"] += 1
        if any(t in fora for t in self._externos):
            self.contadores["injecao_fora_do_bloco"] += 1
        return dados

    def _registrar_instrucao(self, system: str) -> None:
        esperado = self.formato_esperado
        tem = bool(esperado.direcao_cabecalho) and esperado.direcao_cabecalho in system
        outro = any(f.direcao_cabecalho and f.id != esperado.id and f.direcao_cabecalho in system
                    for f in FORMATOS.values())
        self.instrucao_por_bloco[self.estado.bloco_n] = (tem, outro)

    def instrucao(self) -> dict[str, int]:
        """Resumo do canal lateral: blocos de fala, com a direção do formato esperado e com a de outro formato."""
        valores = list(self.instrucao_por_bloco.values())
        return {"blocos": len(valores), "com_formato": sum(1 for tem, _ in valores if tem),
                "com_outro": sum(1 for _, outro in valores if outro)}

    def _palavras(self, tipo: str, categoria: str, primeira: bool, metas=()) -> tuple[int, int]:
        formato = self.fixture.formato_backend
        if metas:
            # Meta que o backend pôs no prompt (a última vale): a mesma conta do formato com orçamento abaixo.
            minimo, maximo, palavras = (int(v) for v in metas[-1])
            alvo_s, teto = (minimo + maximo) / 2, min(palavras, math.floor(self.wpm * maximo / 60))
        elif formato.aplica_orcamento:
            # Sem meta no prompt, a unidade do catálogo do backend (app.live.formatos; no musical, os números de
            # app/live/formato.py): meta em segundos e teto de palavras.
            u = unidade_do_formato(formato, tipo, primeira, quadro=tipo in self.fixture.quadros())
            alvo_s, teto = (u.min_s + u.max_s) / 2, math.floor(self.wpm * u.max_s / 60)
            if u.max_palavras is not None:
                teto = min(u.max_palavras, teto)
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


# Partes de uma frase corrida de debate (texto original, sem tema que exige revisão, sem promessa nem título).
_DEBATE = (
    "e tem quem diga que a cidade mudou demais", "enquanto outros juram que tudo continua igual",
    "e cada um defende o seu lado com argumento", "porque ninguém aqui gosta de ficar sem resposta",
    "e a conversa vai longe sem chegar a lugar nenhum", "com um lembrando do tempo da praça cheia",
    "e o outro dizendo que hoje é melhor", "e a gente fica no meio tentando entender os dois",
)


def _debate_longo(palavras: int) -> str:
    """Uma frase só, emendada por vírgulas, com cerca de `palavras` palavras."""
    partes, total, i = [], 0, 0
    while total < max(palavras, 1):
        parte = _DEBATE[i % len(_DEBATE)]
        partes.append(parte)
        total += contar_palavras(parte)
        i += 1
    texto = ", ".join(partes)
    return texto[:1].upper() + texto[1:] + "."


def _textos_externos(fixture: FixturePrograma) -> list[str]:
    """Frases de texto externo da fixture (títulos e resumos das notícias semeadas) que nunca podem aparecer no
    system nem fora do bloco de dados da mensagem."""
    frases_ = []
    for noticia in fixture.noticias:
        for texto in (noticia.titulo, noticia.resumo):
            frases_ += [f.strip() for f in re.split(r"(?<=[.!?])\s+", texto or "") if len(f.strip()) >= 15]
    return frases_


def _minuscula(texto: str) -> str:
    return texto[:1].lower() + texto[1:] if texto else texto


def _frase_com_dado(dados: list[dict]) -> str:
    """O que o "LLM obediente" diz com um dado do bloco: o primeiro citável válido; senão, um vencido com o horário."""
    for estado in ("valido", "vencido"):
        for dado in dados:
            if dado.get("estado") != estado or dado.get("tipo") not in TIPOS_CITAVEIS or not dado.get("texto"):
                continue
            texto = dado["texto"].rstrip(". ")
            if dado["tipo"] == "clima":
                fonte = dado.get("fonte_no_ar") or "o serviço de meteorologia"
                if estado == "vencido":
                    return f"Na última atualização, {dado.get('atualizado', '')}, {fonte} marcava {texto}."
                return f"Segundo {fonte}, agora faz {texto}."
            if estado == "valido":
                return f"Segundo a prefeitura, {_minuscula(texto)}."
    return ""


class DubleClima:
    """F5: obter_leitura_clima pelo relógio virtual. A leitura da fixture vale a partir de `desde_s`; com `falha`,
    volta a última leitura boa já devolvida (marcada como última leitura), ou nada."""

    def __init__(self, fixture: FixturePrograma):
        self.fixture = fixture
        self.contadores: Counter = Counter()
        self._ultima = None

    def obter_leitura_clima(self, cidade: str | None):
        import datetime

        from app.weather.client import LeituraClima

        self.contadores["obter_leitura_clima"] += 1
        if not (cidade or "").strip() or not self.fixture.clima:
            return None
        agora = datetime.datetime.now(datetime.timezone.utc)
        decorrido = (agora - self.fixture.inicio).total_seconds()
        vigentes = [item for item in self.fixture.clima if item.desde_s <= decorrido]
        if not vigentes:
            return None
        item = vigentes[-1]
        if item.falha:
            self.contadores["clima_falha"] += 1
            return dataclasses.replace(self._ultima, ultima_leitura=True) if self._ultima is not None else None
        observado = (self.fixture.inicio + datetime.timedelta(seconds=item.observado_s)).astimezone(
            datetime.timezone.utc)
        self._ultima = LeituraClima(cidade=cidade, temperatura_c=item.temperatura_c, codigo=0,
                                    descricao=item.descricao, observado_em=observado, consultado_em=agora)
        return self._ultima


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
                                   titulos_tocados=None, canais_recentes=None, origem: str = "",
                                   somente_estudio: bool = False) -> MusicaEncontrada | None:
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

    def duracoes_faixas(self, faixas) -> list[int | None]:
        """Duração (s) que a Spotify informaria para cada (artista, titulo) do catálogo; None fora dele."""
        self.contadores["duracoes_faixas"] += 1
        por_chave = {(normalizar(f.artista), normalizar(f.titulo)): f.duracao_tocada_s for f in self.faixas}
        return [por_chave.get((normalizar(a), normalizar(t))) for a, t in faixas]

    def sugerir_musica_do_genero(self, genero: str, contexto: str = "", evitar=()) -> str:
        self.contadores["sugerir_musica_do_genero"] += 1
        alvo = normalizar(genero)
        recentes = {normalizar(e) for e in evitar}
        for faixa in self.faixas:
            sugestao = f"{faixa.artista} - {faixa.titulo}"
            if (not faixa.indisponivel and alvo in [normalizar(g) for g in faixa.generos]
                    and normalizar(sugestao) not in recentes):
                return sugestao
        return ""

    def escolher_faixa_do_programa(self, faixas, contexto: str) -> int | None:
        """A escolha do LLM entre as candidatas do Spotify: a primeira do pool (já sorteado com a semente)."""
        self.contadores["escolher_faixa_do_programa"] += 1
        return 0 if faixas else None

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
    Alvo("app.llm.client", "escolher_faixa_do_programa", "apoio"),
    Alvo("app.llm.client", "resumir_contexto_musica", "apoio"),
    Alvo("app.live.router", "_registrar_tema_em_background", "apoio"),
    Alvo("app.live.music", "buscar_musica", "apoio"),
    Alvo("app.live.song_service", "resolver_musica_catalogada", "apoio"),
    Alvo("app.live.spotify", "buscar_faixas_por_categoria", "apoio"),
    Alvo("app.live.spotify", "duracoes_faixas", "apoio"),
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
    clima: DubleClima | None = None

    def chamadas_por_funcao(self) -> dict[str, int]:
        total = Counter()
        total.update(self.llm.contadores)
        total.update(self.musicas.contadores)
        total.update(self.contadores)
        if self.tts is not None:
            total.update(self.tts.contadores)
        if self.clima is not None:
            total.update(self.clima.contadores)
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
            if self.nome == "gerar_resposta":
                # Mesmo canal lateral do DubleLLM._gerar (modo fake): sem isto o formato sai 0% no modo llm.
                system = kwargs.get("system_prompt", args[0] if args else "")
                self.llm._registrar_instrucao(system or "")
        else:
            contadores["revisoes"] += 1
        return self.original(*args, **kwargs)


def _substitutos(modo: str, llm: DubleLLM, musicas: CatalogoSimulado, contadores: Counter, sessao,
                 tts: DubleTTS | None = None, clima: "DubleClima | None" = None) -> dict[str, Any]:
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
        "escolher_faixa_do_programa": musicas.escolher_faixa_do_programa,
        "resumir_contexto_musica": musicas.resumir_contexto_musica,
        "_registrar_tema_em_background": _registrar_tema,
        "buscar_musica": musicas.buscar_musica,
        "resolver_musica_catalogada": musicas.resolver_musica_catalogada,
        "buscar_faixas_por_categoria": musicas.buscar_faixas_por_categoria,
        "duracoes_faixas": musicas.duracoes_faixas,
        "pesquisar_noticias": contar("pesquisar_noticias",
                                     lambda *a, **k: PesquisaNoticias(status="desabilitada")),
        "obter_clima_atual": contar("obter_clima_atual", lambda *a, **k: None),
        "obter_leitura_clima": clima.obter_leitura_clima if clima is not None
        else contar("obter_leitura_clima", lambda *a, **k: None),
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
    clima = DubleClima(fixture) if fixture.clima else None
    substitutos = _substitutos(modo, llm, musicas, contadores, sessao, tts, clima)
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
                     tts=tts, clima=clima)


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
