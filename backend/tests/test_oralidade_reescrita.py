"""Reescrita opcional de oralidade (F7): o aviso entra na reescrita única, sem chamada extra ao LLM.

`settings.oralidade_modo`: "desligado" (padrão, nada muda), "avisar" (só registra) e "reescrever" (a instrução
vai na mesma reescrita que já existe; no máximo duas chamadas por fala).
"""

from app.config.settings import settings
from app.live.geracao import gerar_fala
from app.live.oralidade import instrucao_de_oralidade
from app.live.prompt_emissao import montar_prompt
from tests.test_live_formatos_prompt import contexto

FALA_COM_AVISO = (
    "Hoje eu queria conversar com você sobre a importância de organizar a rotina da casa de um jeito que funcione "
    "para todo mundo que mora junto e que respeite o tempo de cada pessoa da família."
)
FALA_LIMPA = "Bom dia, gente. Vamos seguir com a música."


class PortaFalsa:
    """Responde em sequência e grava as chamadas (system, mensagem) feitas ao LLM."""

    def __init__(self, *respostas: str):
        self.respostas = list(respostas)
        self.chamadas: list[tuple[str, str]] = []

    def gerar_resposta(self, system, mensagem):
        self.chamadas.append((system, mensagem))
        return self.respostas[len(self.chamadas) - 1]


def _rodar(monkeypatch, modo: str, *respostas: str):
    monkeypatch.setattr(settings, "oralidade_modo", modo)
    ctx = contexto("padrao", "comentario")
    porta = PortaFalsa(*respostas)
    resultado = gerar_fala(ctx, montar_prompt(ctx), porta)
    return resultado, porta


def test_modo_desligado_uma_chamada_e_fala_intocada(monkeypatch):
    resultado, porta = _rodar(monkeypatch, "desligado", FALA_COM_AVISO)
    assert len(porta.chamadas) == 1
    assert resultado.fala == FALA_COM_AVISO
    assert resultado.revisada is False


def test_modo_avisar_so_registra_sem_reescrever(monkeypatch):
    resultado, porta = _rodar(monkeypatch, "avisar", FALA_COM_AVISO)
    assert len(porta.chamadas) == 1
    assert resultado.fala == FALA_COM_AVISO
    assert resultado.revisada is False


def test_modo_reescrever_usa_a_reescrita_unica_com_a_instrucao(monkeypatch):
    resultado, porta = _rodar(monkeypatch, "reescrever", FALA_COM_AVISO, FALA_LIMPA)
    assert len(porta.chamadas) == 2
    system_revisao, mensagem_revisao = porta.chamadas[1]
    assert "Oralidade:" in system_revisao
    assert "Quebre as frases longas" in system_revisao
    assert resultado.revisada is True
    assert resultado.fala == FALA_LIMPA


def test_modo_reescrever_fala_limpa_nao_gasta_chamada_extra(monkeypatch):
    resultado, porta = _rodar(monkeypatch, "reescrever", FALA_LIMPA)
    assert len(porta.chamadas) == 1
    assert resultado.revisada is False


def test_modo_reescrever_nunca_faz_terceira_chamada(monkeypatch):
    # A reescrita também tem aviso: o limite de duas chamadas por fala continua valendo.
    resultado, porta = _rodar(monkeypatch, "reescrever", FALA_COM_AVISO, FALA_COM_AVISO)
    assert len(porta.chamadas) == 2
    assert resultado.fala == FALA_COM_AVISO


def test_instrucao_vazia_sem_avisos():
    assert instrucao_de_oralidade([]) == ""


def test_instrucao_sem_repeticao_e_com_o_trecho_da_sigla():
    from app.live.oralidade import Aviso

    texto = instrucao_de_oralidade([
        Aviso("sigla_sem_expansao", "CRAS"),
        Aviso("sigla_sem_expansao", "CRAS"),
        Aviso("burocratico", "municipalidade"),
    ])
    assert texto.startswith("Oralidade: ")
    assert texto.count("CRAS") == 1
    assert "municipalidade" in texto

