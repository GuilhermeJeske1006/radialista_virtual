"""Caracterização de POST /live/{rid}/programas/{pid}/proxima (F3, C1 da auditoria §6).

Retrato completo de cada cenário: o texto inteiro do system e da mensagem de toda chamada ao LLM, a
resposta (sem `criado_em` e sem o token aleatório do pedido), o Redis depois da chamada, as linhas do banco
que a rota grava e a sequência de sorteios do módulo `random`. Gravado no código anterior à extração de
`gerar_proxima_fala` (docs/melhoria-radio/f3/auditoria.md §5.9): mover código não pode mudar nada daqui.

Caracterização permanente (decisão D6): uma frente que muda texto de prompt de propósito regrava com
`ATUALIZAR_GOLDEN=1 pytest tests/test_live_proxima_caracterizacao.py` e revisa o diff no mesmo commit.
Campos de resposta com valor nulo ficam fora do retrato: campo opcional novo e nulo não muda nada.
Os dublês trocam funções pelo nome em app.live.router, como os outros testes da rota.
"""

import dataclasses
import datetime
import json
import os
import pathlib
import random
import re
import sys
from typing import Any, Callable

import pytest
from freezegun import freeze_time

from app.live.music import MusicaEncontrada
from app.models.fila_ao_vivo import FilaAoVivo
from app.models.musica_historico import MusicaHistorico
from app.models.noticia_historico import NoticiaHistorico
from app.models.patrocinador import Patrocinador
from app.models.programa import Programa
from app.models.programa_radialista import ProgramaRadialista
from app.models.radio_config import RadioConfig
from app.models.tema_historico import TemaHistorico

DIR_GOLDEN = pathlib.Path(__file__).resolve().parent / "fixtures" / "caracterizacao_proxima"
ATUALIZAR = os.environ.get("ATUALIZAR_GOLDEN") == "1"
AGORA_UTC = "2026-08-10 15:00:00"  # 12:00 em São Paulo, dentro do programa 10:00-14:00

FAIXA = MusicaEncontrada(video_id="faixa001", titulo="Estrada Aberta", canal="Banda Horizonte",
                         duracao_segundos=200, descricao="Gravada em 2019 num sítio do interior.")
FAIXA_GENERICA = MusicaEncontrada(video_id="faixa002", titulo="Varanda Azul", canal="Trio Maré",
                                  duracao_segundos=190)
CITADA = MusicaEncontrada(video_id="cit001", titulo="Outra Citada", canal="Banda Y", duracao_segundos=180)


@dataclasses.dataclass
class Cenario:
    nome: str
    corpo: dict
    respostas: list[str] = dataclasses.field(default_factory=lambda: ["Seguimos juntos nesta tarde de rádio."])
    agora: str = AGORA_UTC
    semente: int = 11
    # Valores impostos aos primeiros random.random() (o resto sai da semente): liga os ramos sorteados.
    random_forcado: tuple[float, ...] = ()
    preparar: Callable[..., None] | None = None
    buscar: Callable[..., Any] | None = None
    citadas: list[str] = dataclasses.field(default_factory=list)
    fio: str = ""


# ---------------------------------------------------------------------------------------------
# Preparação dos cenários
# ---------------------------------------------------------------------------------------------

def _pedido(db, radialista, tipo, nome, mensagem, **extra):
    pedido = FilaAoVivo(radio_config_id=radialista.id, telefone=extra.pop("telefone", "5511999990001"), nome=nome,
                        tipo=tipo, mensagem_usuario=mensagem, **extra)
    db.add(pedido)
    db.commit()
    return pedido


def _p_assunto(db, account, radialista, programa, mp):
    programa.estrutura_blocos = ["comentario"]
    programa.ia_pode_adicionar_blocos = False
    programa.assuntos_ao_vivo = ["Feira de domingo", "Horta no quintal"]


def _p_quadro(db, account, radialista, programa, mp):
    programa.estrutura_blocos = ["Quadro da Receita"]
    programa.ia_pode_adicionar_blocos = False
    programa.quadros_fixos = {"Quadro da Receita": ["bolo de fubá cremoso", "pão de queijo de frigideira"]}
    mp.setattr("app.live.router.classificar_categoria_bloco", lambda tipo: "comentario")


def _p_callback(db, account, radialista, programa, mp):
    programa.estrutura_blocos = ["comentario"]
    programa.ia_pode_adicionar_blocos = False
    outro = Programa(radio_config_id=radialista.id, nome="Manhã Viva", horario_inicio=datetime.time(6, 0),
                     horario_fim=datetime.time(9, 0), estrutura_blocos=[])
    db.add(outro)
    db.flush()
    ontem = datetime.datetime(2026, 8, 9, 12, 0, tzinfo=datetime.timezone.utc)
    db.add_all([TemaHistorico(programa_id=outro.id, tema="preço do tomate", criado_em=ontem),
                TemaHistorico(programa_id=outro.id, tema="festa junina", criado_em=ontem)])
    from app.config.redis_client import redis_client
    redis_client.lpush(f"temas_comentados:{programa.id}", "chuva da semana")


def _p_citada(db, account, radialista, programa, mp):
    pass


def _p_legado_musica(db, account, radialista, programa, mp):
    _pedido(db, radialista, "musica", "Joana", "toca Estrada Aberta", musica_query="Estrada Aberta",
            natureza="pedido_musica")


def _p_novo_musica(db, account, radialista, programa, mp):
    from app.whatsapp.atendimento import ocorrencia

    account.atendimento_ouvinte_ativo = True
    _pedido(db, radialista, "musica", "Joana", "toca Estrada Aberta pra minha mãe", musica_query="Estrada Aberta",
            natureza="pedido_musica", programa_id=programa.id, transmissao=ocorrencia(programa, radialista.timezone),
            estado="em_fila", texto_autorizado="Pediu Estrada Aberta para a mãe, que faz aniversário hoje.")


def _p_sem_resultado(db, account, radialista, programa, mp):
    _pedido(db, radialista, "musica", "Joana", "toca Canção Que Não Existe", musica_query="Canção Que Não Existe",
            natureza="pedido_musica")


def _p_abraco(db, account, radialista, programa, mp):
    _pedido(db, radialista, "abraco", "Seu Valdir", "manda um abraço pro pessoal da oficina, que tá sem café",
            natureza="reacao_engracada")


def _p_sorteio(db, account, radialista, programa, mp):
    _pedido(db, radialista, "sorteio", "Lúcia", "quero participar do sorteio", natureza="participacao_sorteio")


def _p_recorrente(db, account, radialista, programa, mp):
    agora = datetime.datetime.now(datetime.timezone.utc)
    _pedido(db, radialista, "musica", "Seu Valdir", "toca uma moda", atendido=True,
            atendido_em=agora - datetime.timedelta(minutes=30), criado_em=agora - datetime.timedelta(minutes=30))
    _pedido(db, radialista, "abraco", "Seu Valdir", "voltei pra mandar outro abraço", natureza="recado_comum",
            criado_em=agora)


def _p_recorrente_dias(db, account, radialista, programa, mp):
    agora = datetime.datetime.now(datetime.timezone.utc)
    _pedido(db, radialista, "abraco", "Seu Valdir", "abraço de semana passada", atendido=True,
            atendido_em=agora - datetime.timedelta(days=3), criado_em=agora - datetime.timedelta(days=3))
    _pedido(db, radialista, "abraco", "Seu Valdir", "voltei depois de uns dias", natureza="pergunta",
            criado_em=agora)


def _p_pedido_recente(db, account, radialista, programa, mp):
    programa.estrutura_blocos = ["comentario"]
    programa.ia_pode_adicionar_blocos = False
    _pedido(db, radialista, "musica", "Rita", "toca Varanda Azul", musica_query="Varanda Azul",
            criado_em=datetime.datetime.now(datetime.timezone.utc))


def _pauta(noticia_id=7, angulo="fato", titulo="Ponte da Rua Nova é liberada"):
    from app.news.pauta import NoticiaPauta

    return NoticiaPauta(
        noticia_id=noticia_id, titulo=titulo, resumo="A prefeitura liberou o tráfego na ponte depois da obra.",
        fonte_nome="Prefeitura", fonte_tipo="oficial", url="https://exemplo.invalid/ponte", categoria="cidade",
        publicado_em=datetime.datetime(2026, 8, 10, 13, 0, tzinfo=datetime.timezone.utc), angulo=angulo,
        aberturas_usadas=[], detalhes={"servico": "Desvio pela Rua Velha até as dezoito horas."},
    )


def _p_noticia(db, account, radialista, programa, mp):
    programa.tipos_noticias = ["cidade"]
    mp.setattr("app.live.router.proxima_noticia", lambda db, programa, account: _pauta())


def _p_escalada(db, account, radialista, programa, mp):
    programa.estrutura_blocos = ["escalada"]
    programa.ia_pode_adicionar_blocos = False
    programa.tipos_noticias = ["cidade"]
    mp.setattr("app.live.router.proximas_noticias", lambda db, programa, account, limite=3: [
        _pauta(7), _pauta(8, titulo="Feira do livro começa na praça")])


def _p_correcao(db, account, radialista, programa, mp):
    from app.news.pauta import ANGULO_CORRECAO

    programa.tipos_noticias = ["cidade"]
    mp.setattr("app.live.router.correcao_pendente", lambda db, programa: _pauta(9, angulo=ANGULO_CORRECAO))


def _p_pesquisa(db, account, radialista, programa, mp):
    from app.llm.noticias import FonteNoticia, PesquisaNoticias

    programa.pode_pesquisar = True
    mp.setattr("app.live.router.proxima_noticia", lambda db, programa, account: None)
    mp.setattr("app.live.router.pesquisar_noticias", lambda p, a, **kw: PesquisaNoticias(
        status="ok", texto="Segundo a Defesa Civil, a chuva da madrugada derrubou duas árvores no centro.",
        fontes=[FonteNoticia(titulo="Jornal da Cidade", url="https://exemplo.invalid/chuva")],
        consultado_em=datetime.datetime(2026, 8, 10, 14, 50, tzinfo=datetime.timezone.utc)))


def _p_encerramento(db, account, radialista, programa, mp):
    from app.config.redis_client import redis_client
    redis_client.set(f"fio_condutor:{programa.id}", "será que hoje bate recorde de calor?")


def _p_musical(db, account, radialista, programa, mp):
    programa.perfil_programacao = "musical_companhia"


def _p_musical_pedido(db, account, radialista, programa, mp):
    programa.perfil_programacao = "musical_companhia"
    _p_legado_musica(db, account, radialista, programa, mp)


def _p_relogio(preset, *executadas):
    def preparar(db, account, radialista, programa, mp):
        from app.live.relogio import PRESETS

        patrocinadores = [Patrocinador(account_id=account.id, nome=n, texto=f"{n}, perto de você.", ativo=True,
                                       tipo_conteudo="audio", audio_path=f"p/{n}.mp3", duracao_segundos=d)
                          for n, d in (("Loja Um", 30), ("Loja Dois", 20))]
        db.add_all(patrocinadores)
        db.flush()
        programa.horario_inicio, programa.horario_fim = datetime.time(12, 0), datetime.time(13, 0)
        programa.ia_pode_adicionar_blocos = False
        programa.estrutura_blocos = ["comentario", *[f"patrocinador:{p.id}" for p in patrocinadores]]
        programa.relogio_hora = PRESETS[preset].model_dump()
        db.commit()
        from app.live import relogio as r

        instante = datetime.datetime(2026, 11, 10, 12, 0, tzinfo=datetime.timezone(datetime.timedelta(hours=-3)))
        r.marcar_executada(programa.id, r.ocorrencia_em(programa, radialista.timezone, instante),
                           "0:0:fala:abertura", *executadas)
    return preparar


def _promessa_aberta(db, programa, ocorrencia, chave, *, posicao=None, texto="Mais tarde a gente lê os recados."):
    from app.live import promessas as p
    from app.live import promessas_repo

    evento = p.EventoAgendado(chave=chave, tipo="participacao", rotulo="Retorno e participação", posicao=posicao)
    promessas_repo.registrar(db, programa=programa, ocorrencia=ocorrencia, request_id="anterior",
                             itens=[(p.detectar(texto)[0], evento)])


def _p_retorno_com_promessa(com_pedido: bool):
    """F4: relógio A no retorno de 27:00, com a promessa aberta para ele (cumpre com pedido, contingência sem)."""
    def preparar(db, account, radialista, programa, mp):
        _p_relogio("A", "0:40", "0:720")(db, account, radialista, programa, mp)
        from app.live import relogio as r

        instante = datetime.datetime(2026, 11, 10, 12, 0, tzinfo=datetime.timezone(datetime.timedelta(hours=-3)))
        ocorrencia = r.ocorrencia_em(programa, radialista.timezone, instante)
        ids = [int(t.split(":")[1]) for t in programa.estrutura_blocos if t.startswith("patrocinador:")]
        r.marcar_executada(programa.id, ocorrencia, *(f"0:1440:patrocinador:{i}" for i in ids))
        _promessa_aberta(db, programa, ocorrencia.chave, "etapa:0:1620")
        if com_pedido:
            _p_abraco(db, account, radialista, programa, mp)
    return preparar


def _p_promessa_vencida_sem_relogio(db, account, radialista, programa, mp):
    """F4: sem relógio, a posição prometida (chamada de ouvinte na 2) passou: contingência no comentário."""
    from app.live.contexto import chave_ocorrencia

    programa.estrutura_blocos = ["abertura", "musica", "chamada_ouvinte", "comentario", "musica", "comentario"]
    programa.ia_pode_adicionar_blocos = False
    db.commit()
    ocorrencia = chave_ocorrencia(programa, radialista.timezone, datetime.datetime.now(datetime.timezone.utc))
    _promessa_aberta(db, programa, ocorrencia, "roteiro:2", posicao=2)


def _p_multivoz(db, account, radialista, programa, mp):
    programa.estrutura_blocos = ["comentario"]
    programa.ia_pode_adicionar_blocos = False
    convidada = RadioConfig(account_id=account.id, nome_locutor="Maria", timezone=radialista.timezone)
    db.add(convidada)
    db.flush()
    db.add(ProgramaRadialista(programa_id=programa.id, radio_config_id=convidada.id, papel="Co-apresentadora"))


def _p_tags(db, account, radialista, programa, mp):
    programa.estrutura_blocos = ["comentario"]
    programa.ia_pode_adicionar_blocos = False
    mp.setattr("app.live.router.settings.elevenlabs_model", "eleven_v3")


def _buscar_pedido_sem_resultado(query, **kw):
    return None if "Não Existe" in query else FAIXA_GENERICA


def _buscar_com_citada(query, **kw):
    return CITADA if "Outra Citada" in query else FAIXA


def _buscar_nada(query, **kw):
    return None


HIST_MUSICA = ["musica: Que tarde bonita! [Música(s) tocada(s) nesse bloco: Rio de Prata - Dupla Serra]"]
HIST_COMENTARIO = ["comentario: Falávamos do trânsito na avenida principal."]
LONGA = " ".join(["Uma frase comprida de propósito, para passar do tempo do bloco sem dó."] * 8)

CENARIOS = [
    Cenario("comentario_assunto_sugerido", {"total_falas": 3, "historico": HIST_MUSICA}, preparar=_p_assunto),
    Cenario("comentario_quadro_fixo", {"total_falas": 3, "historico": HIST_MUSICA}, preparar=_p_quadro),
    Cenario("comentario_callback_tema", {"total_falas": 3, "historico": HIST_MUSICA}, preparar=_p_callback,
            random_forcado=(0.01, 0.01, 0.01, 0.01, 0.01)),
    Cenario("musica_com_faixa", {"total_falas": 1, "historico": HIST_COMENTARIO},
            respostas=["Agora vem Estrada Aberta, com Banda Horizonte."]),
    Cenario("musica_sem_faixa", {"total_falas": 1, "historico": HIST_COMENTARIO}, buscar=_buscar_nada,
            respostas=["Seguimos com o papo, já já tem mais rádio."]),
    Cenario("musica_com_citada", {"total_falas": 1, "historico": HIST_COMENTARIO}, preparar=_p_citada,
            buscar=_buscar_com_citada, citadas=["Banda Y - Outra Citada"],
            respostas=["Agora vem Estrada Aberta, com Banda Horizonte, e depois Outra Citada."]),
    Cenario("pedido_legado", {"total_falas": 1, "historico": HIST_COMENTARIO}, preparar=_p_legado_musica,
            respostas=["A Joana pediu, e toca agora Estrada Aberta, com Banda Horizonte."]),
    Cenario("pedido_novo_texto_autorizado", {"total_falas": 1, "historico": HIST_COMENTARIO},
            preparar=_p_novo_musica, respostas=["A Joana pediu Estrada Aberta para a mãe, parabéns!"]),
    Cenario("pedido_sem_resultado", {"total_falas": 1, "historico": HIST_COMENTARIO}, preparar=_p_sem_resultado,
            buscar=_buscar_pedido_sem_resultado,
            respostas=["Joana, não achei a sua, mas vem Varanda Azul, com Trio Maré."]),
    Cenario("chamada_abraco", {"total_falas": 5, "historico": HIST_MUSICA}, preparar=_p_abraco,
            respostas=["Seu Valdir, café na oficina é coisa séria, abraço pra turma!"]),
    Cenario("chamada_sorteio", {"total_falas": 5, "historico": HIST_MUSICA}, preparar=_p_sorteio,
            respostas=["Lúcia, recebemos o seu contato, obrigado."]),
    Cenario("chamada_recorrente", {"total_falas": 5, "historico": HIST_MUSICA}, preparar=_p_recorrente,
            respostas=["Seu Valdir de novo por aqui, outro abraço!"]),
    Cenario("chamada_recorrente_dias", {"total_falas": 5, "historico": HIST_MUSICA}, preparar=_p_recorrente_dias,
            respostas=["Seu Valdir, você de novo por aqui, que bom."]),
    Cenario("comentario_pedido_recente", {"total_falas": 3, "historico": HIST_MUSICA}, preparar=_p_pedido_recente),
    Cenario("noticia_pauta_com_retry", {"total_falas": 4, "historico": HIST_COMENTARIO}, preparar=_p_noticia,
            respostas=["A ponte da Rua Nova foi liberada nesta tarde.",
                       "Segundo a prefeitura, a ponte da Rua Nova foi liberada nesta tarde."]),
    Cenario("escalada", {"total_falas": 1, "historico": HIST_COMENTARIO}, preparar=_p_escalada,
            respostas=["Ponte liberada. Feira do livro começa na praça."]),
    Cenario("noticia_correcao", {"total_falas": 4, "historico": HIST_COMENTARIO}, preparar=_p_correcao,
            respostas=["Segundo a prefeitura, corrigindo a informação: a ponte foi liberada às catorze horas."]),
    Cenario("noticia_pesquisa_ok", {"total_falas": 4, "historico": HIST_COMENTARIO}, preparar=_p_pesquisa,
            respostas=["Segundo a Defesa Civil, a chuva derrubou duas árvores no centro."]),
    Cenario("abertura_primeira", {"total_falas": 0, "historico": []}, fio="será que hoje bate recorde de calor?",
            respostas=["Boa tarde! Será que hoje bate recorde de calor?"]),
    Cenario("encerramento_fio", {"total_falas": 9, "historico": HIST_MUSICA}, agora="2026-08-10 16:58:00",
            preparar=_p_encerramento, respostas=["Obrigado pela companhia, até amanhã."]),
    Cenario("musical_retomada_com_excesso", {"total_falas": 6, "historico": HIST_MUSICA}, preparar=_p_musical,
            respostas=[LONGA, "Você está na rádio, seguimos juntos."]),
    Cenario("musical_identificacao", {"total_falas": 3, "historico": HIST_MUSICA}, preparar=_p_musical,
            respostas=["Você ouve a rádio da cidade."]),
    Cenario("musical_musica_pedido", {"total_falas": 1, "historico": HIST_MUSICA}, preparar=_p_musical_pedido,
            respostas=["A Joana pediu Estrada Aberta, com Banda Horizonte."]),
    Cenario("relogio_a_link", {"total_falas": 3, "historico": HIST_MUSICA,
                               "inicio_previsto": "2026-11-10T12:12:30-03:00"},
            agora="2026-11-10 15:12:20", preparar=_p_relogio("A", "0:40"), respostas=["Seguimos com você nesta tarde."]),
    Cenario("relogio_c_fechamento_curto", {"total_falas": 3, "historico": HIST_COMENTARIO,
                                           "inicio_previsto": "2026-11-10T12:15:48-03:00"},
            agora="2026-11-10 15:15:00", preparar=_p_relogio("C"), respostas=["Fica a dica: devagar se vai longe."]),
    Cenario("relogio_a_encerramento", {"total_falas": 20, "historico": HIST_MUSICA,
                                       "inicio_previsto": "2026-11-10T12:59:35-03:00"},
            agora="2026-11-10 15:52:00", preparar=_p_relogio("A"), respostas=["Obrigado pela companhia nesta tarde."]),
    # F4: promessa aberta cumprida, com contingência e vencida (sem relógio). Gravados no commit do cumprimento.
    Cenario("relogio_a_retorno_cumpre", {"total_falas": 6, "historico": ["patrocinador: Loja Dois, perto de você."],
                                         "inicio_previsto": "2026-11-10T12:27:00-03:00"},
            agora="2026-11-10 15:26:50", preparar=_p_retorno_com_promessa(True),
            respostas=["Seu Valdir, café na oficina é coisa séria, abraço pra turma!"]),
    Cenario("relogio_a_retorno_contingencia", {"total_falas": 6,
                                               "historico": ["patrocinador: Loja Dois, perto de você."],
                                               "inicio_previsto": "2026-11-10T12:27:00-03:00"},
            agora="2026-11-10 15:26:50", preparar=_p_retorno_com_promessa(False),
            respostas=["O WhatsApp da Rádio Teste está aberto para o seu recado."]),
    Cenario("promessa_vencida_sem_relogio", {"total_falas": 3, "historico": HIST_COMENTARIO},
            preparar=_p_promessa_vencida_sem_relogio,
            respostas=["Repara como cada família tem um jeito próprio de arrumar a mesa no domingo."]),
    Cenario("multivoz", {"total_falas": 3, "historico": HIST_MUSICA}, preparar=_p_multivoz,
            respostas=[json.dumps({"linhas": [
                {"locutor": "Ze do Radio", "texto": "Maria, você viu a feira de domingo?"},
                {"locutor": "Maria", "texto": "Vi sim, estava cheia de gente."}]}, ensure_ascii=False)]),
    Cenario("voz_com_tags_v3", {"total_falas": 3, "historico": HIST_MUSICA}, preparar=_p_tags,
            respostas=["[calm] Que tarde boa para conversar."]),
]


# ---------------------------------------------------------------------------------------------
# Execução e retrato
# ---------------------------------------------------------------------------------------------

class _RandomGravado(random.Random):
    """RNG próprio do cenário, com a semente dele, que registra cada sorteio. Entra no lugar do módulo `random`
    em todo módulo app.* (como scripts/simulacao/ambiente.py::rng_isolado): outra thread do processo que use o
    random global (o flush de logs do Sentry, na suíte inteira) não muda a sequência do cenário."""

    def __init__(self, semente: int, forcado: tuple[float, ...]):
        self._interno = True
        super().__init__(semente)
        self.forcado = list(forcado)
        self.registro: list = []
        self._interno = False

    def random(self):
        if self._interno:
            return super().random()
        valor = self.forcado.pop(0) if self.forcado else super().random()
        self.registro.append(["random", round(valor, 6)])
        return valor

    def _por_dentro(self, funcao, *args, **kwargs):
        self._interno = True
        try:
            return funcao(*args, **kwargs)
        finally:
            self._interno = False

    def randint(self, a, b):
        valor = self._por_dentro(super().randint, a, b)
        self.registro.append(["randint", [a, b], valor])
        return valor

    def choice(self, seq):
        valor = self._por_dentro(super().choice, seq)
        self.registro.append(["choice", len(seq), str(valor)[:60]])
        return valor

    def choices(self, population, weights=None, *, cum_weights=None, k=1):
        valor = self._por_dentro(super().choices, population, weights=weights, cum_weights=cum_weights, k=k)
        self.registro.append(["choices", len(population), [str(v)[:60] for v in valor]])
        return valor

    def shuffle(self, x):
        self._por_dentro(super().shuffle, x)
        self.registro.append(["shuffle", len(x)])

    def instalar(self, mp) -> None:
        for nome, modulo in list(sys.modules.items()):
            if modulo is not None and (nome == "app" or nome.startswith("app.")) \
                    and getattr(modulo, "random", None) is random:
                mp.setattr(modulo, "random", self)


def _retrato_redis() -> dict:
    from app.config.redis_client import redis_client

    retrato = {}
    for chave in sorted(redis_client.keys("*")):
        tipo = redis_client.type(chave)
        if tipo == "string":
            # O request_id (uuid4) do orçamento pendente da F2 muda a cada chamada.
            valor = re.sub(r'"request_id": "[0-9a-f]+"', '"request_id": "<id>"', redis_client.get(chave))
        elif tipo == "list":
            valor = redis_client.lrange(chave, 0, -1)
        elif tipo == "set":
            valor = sorted(redis_client.smembers(chave))
        elif tipo == "hash":
            valor = dict(sorted(redis_client.hgetall(chave).items()))
        elif tipo == "zset":
            valor = redis_client.zrange(chave, 0, -1, withscores=True)
        else:
            valor = f"<{tipo}>"
        retrato[chave] = valor
    return retrato


def _retrato_banco(db) -> dict:
    db.expire_all()
    return {
        "musica_historico": [[m.video_id, m.titulo, m.origem, m.query] for m in
                             db.query(MusicaHistorico).order_by(MusicaHistorico.id).all()],
        "fila": [[p.id, p.tipo, p.estado, p.atendido, p.motivo] for p in
                 db.query(FilaAoVivo).order_by(FilaAoVivo.id).all()],
        "noticia_historico": [[n.noticia_id, n.angulo, n.fala] for n in
                              db.query(NoticiaHistorico).order_by(NoticiaHistorico.id).all()],
        "temas": db.query(TemaHistorico).count(),
    }


def _sem_nulos(valor):
    if isinstance(valor, dict):
        return {k: _sem_nulos(v) for k, v in valor.items() if v is not None}
    if isinstance(valor, list):
        return [_sem_nulos(v) for v in valor]
    return valor


def _resposta(dados: dict) -> dict:
    dados = {k: v for k, v in dados.items() if k != "criado_em"}
    if dados.get("pedido_token"):
        dados["pedido_token"] = "<token>"
    return _sem_nulos(dados)


def _rodar(cenario: Cenario, client, account, auth_headers, db_session, monkeypatch) -> dict:
    from app.config.redis_client import redis_client

    radialista = RadioConfig(account_id=account.id, timezone="America/Sao_Paulo", nome_locutor="Ze do Radio")
    db_session.add(radialista)
    account.nome_radio = "Rádio Teste"
    account.cidade = "Campo Alegre"
    db_session.commit()
    programa = Programa(radio_config_id=radialista.id, nome="Tarde Viva", horario_inicio=datetime.time(10, 0),
                        horario_fim=datetime.time(14, 0), estrutura_blocos=[])
    db_session.add(programa)
    db_session.commit()

    chamadas: list[dict] = []
    respostas = list(cenario.respostas)

    def _llm(funcao):
        def gerar(system, mensagem):
            chamadas.append({"funcao": funcao, "system": system.split("\n"), "mensagem": mensagem.split("\n")})
            return respostas[min(len(chamadas), len(respostas)) - 1]
        return gerar

    buscas: list[str] = []
    buscar = cenario.buscar or (lambda query, **kw: FAIXA)

    def _buscar(query, **kw):
        buscas.append(query)
        return buscar(query, **kw)

    temas_bg: list[str] = []
    monkeypatch.setattr("app.live.router.gerar_resposta", _llm("gerar_resposta"))
    monkeypatch.setattr("app.live.router.gerar_dialogo_multivoz", _llm("gerar_dialogo_multivoz"))
    monkeypatch.setattr("app.live.router.buscar_musica", _buscar)
    monkeypatch.setattr("app.live.router.resolver_musica_catalogada", lambda *a, **k: None)
    monkeypatch.setattr("app.live.router.extrair_musicas_citadas",
                        lambda fala, ja_tocadas=None: list(cenario.citadas))
    monkeypatch.setattr("app.live.router.classificar_fio_condutor", lambda fala: cenario.fio)
    monkeypatch.setattr("app.live.router.classificar_categoria_bloco", lambda tipo: "comentario")
    monkeypatch.setattr("app.live.router.resumir_contexto_musica",
                        lambda titulo, canal, descricao, tags, ano: f"Contexto: {descricao}" if descricao else "")
    monkeypatch.setattr("app.live.router._registrar_tema_em_background", lambda pid, texto: temas_bg.append(texto))
    monkeypatch.setattr("app.live.router.sugerir_musica_do_genero", lambda genero: "")
    monkeypatch.setattr("app.live.router.buscar_faixas_por_categoria", lambda genero, excluir_titulos=None: [])
    monkeypatch.setattr("app.llm.prompt_builder.obter_clima_atual", lambda cidade: None)

    espiao = _RandomGravado(cenario.semente, cenario.random_forcado)
    with freeze_time(cenario.agora):
        redis_client.flushall()
        if cenario.preparar is not None:
            cenario.preparar(db_session, account, radialista, programa, monkeypatch)
        db_session.commit()
        espiao.instalar(monkeypatch)
        corpo = {"incluir_audio": False, **cenario.corpo}
        resposta = client.post(f"/live/{radialista.id}/programas/{programa.id}/proxima", json=corpo,
                               headers=auth_headers(account.id))
        # Dentro do freeze_time: as chaves têm TTL e, no relógio real, já teriam expirado.
        redis_depois, banco_depois = _retrato_redis(), _retrato_banco(db_session)
    assert resposta.status_code == 200, resposta.text
    return {
        "cenario": cenario.nome,
        "chamadas_llm": chamadas,
        "resposta": _resposta(resposta.json()),
        "redis": redis_depois,
        "banco": banco_depois,
        "random": espiao.registro,
        "buscas_musica": buscas,
        "temas_em_background": temas_bg,
    }


@pytest.mark.parametrize("cenario", CENARIOS, ids=[c.nome for c in CENARIOS])
def test_caracterizacao_proxima(cenario, client, account, auth_headers, db_session, monkeypatch):
    retrato = json.loads(json.dumps(_rodar(cenario, client, account, auth_headers, db_session, monkeypatch),
                                    ensure_ascii=False, default=str))
    caminho = DIR_GOLDEN / f"{cenario.nome}.json"
    if ATUALIZAR or not caminho.exists():
        if not ATUALIZAR:
            pytest.fail(f"golden ausente: {caminho.name} (rode com ATUALIZAR_GOLDEN=1)")
        DIR_GOLDEN.mkdir(parents=True, exist_ok=True)
        caminho.write_text(json.dumps(retrato, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                           encoding="utf-8")
        return
    esperado = json.loads(caminho.read_text(encoding="utf-8"))
    for parte in ("chamadas_llm", "resposta", "redis", "banco", "random", "buscas_musica", "temas_em_background"):
        assert retrato[parte] == esperado[parte], f"{cenario.nome}: '{parte}' mudou"


def test_cenarios_cobrem_os_ramos_da_auditoria():
    """Os ramos que a extração mais arrisca: sorteios forçados, retry, relógio, pedido novo e multivoz."""
    nomes = {c.nome for c in CENARIOS}
    assert len(CENARIOS) >= 20
    for esperado in ("comentario_callback_tema", "noticia_pauta_com_retry", "musical_retomada_com_excesso",
                     "relogio_a_link", "relogio_c_fechamento_curto", "pedido_novo_texto_autorizado", "multivoz",
                     "voz_com_tags_v3", "chamada_recorrente_dias", "comentario_pedido_recente"):
        assert esperado in nomes
