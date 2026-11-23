"""F8, passos 2 e 3: repetição por estrutura no prompt e reorientação periódica com memória, como exceção às regras
de não repetir. Nada disso faz chamada extra ao LLM: só muda o que vai no prompt."""

import datetime

import pytest
from freezegun import freeze_time

from app.live.formatos import POPULAR_SERTANEJO, SECAO_REORIENTACAO, linhas_do_formato, reorienta
from app.live.memoria import abertura_repetida, fala_semelhante_no_historico, textos_do_historico
from app.models.programa import Programa
from app.models.radio_config import RadioConfig
from tests.test_live_router import _url_proxima

AGORA = datetime.datetime(2026, 8, 10, 15, 0, tzinfo=datetime.timezone.utc)  # 12:00 local, programa 10-14
NOMES = ("Tarde Sertaneja", "Rádio Serra")


# ----------------------------------------------------------------------------------------------- puras

def test_textos_do_historico_tira_tipo_sufixo_de_musica_e_blocos_sem_locucao():
    historico = [
        "abertura: Bom dia, gente! Tudo certo?",
        "musica:  [Música(s) tocada(s) nesse bloco: Estrada - Banda]",
        "vinheta: Rádio Serra, a sua companhia.",
        "patrocinador: Compre na Loja X.",
        "comentario: Boa tarde, pessoal. Hoje tem feira. [Música(s) tocada(s) nesse bloco: A - B]",
    ]
    assert textos_do_historico(historico) == ["Bom dia, gente! Tudo certo?", "Boa tarde, pessoal. Hoje tem feira."]


@pytest.mark.parametrize("textos,esperado", [
    (["Bom dia, gente!", "Boa tarde, pessoal. Hoje tem feira."], "saudacao"),
    (["Hoje tem feira.", "Seguimos com a gente.", "Seguimos aqui na tarde."], "retomada"),
    (["Bom dia, gente!", "Hoje tem feira."], None),
    (["Bom dia, gente!"], None),
    (["A feira abriu.", "A chuva parou."], None),  # "outra" não é estrutura reconhecida
])
def test_abertura_repetida_nas_duas_ultimas_falas(textos, esperado):
    assert abertura_repetida(textos) == esperado


def test_reorientacao_nao_conta_como_repeticao_na_similaridade():
    anterior = "Você está no Tarde Sertaneja, na Rádio Serra. Bom te ter aqui comigo."
    fala = "Você está no Tarde Sertaneja, na Rádio Serra. Que bom te ter com a gente."
    assert fala_semelhante_no_historico(fala, [anterior]) == anterior
    assert fala_semelhante_no_historico(fala, [anterior], ignorar=lambda frase: reorienta(frase, NOMES)) is None


def test_reorientacao_vencida_pede_a_reorientacao_em_qualquer_bloco_do_formato():
    sem = linhas_do_formato(POPULAR_SERTANEJO, programa="Tarde", tipo="comentario", primeira=False)
    com = linhas_do_formato(POPULAR_SERTANEJO, programa="Tarde", tipo="comentario", primeira=False,
                            reorientacao_vencida=True)
    assert SECAO_REORIENTACAO not in sem
    assert com == [*sem, SECAO_REORIENTACAO]
    assert linhas_do_formato("padrao", programa="Tarde", tipo="comentario", primeira=False,
                             reorientacao_vencida=True) == []


# ------------------------------------------------------------------------------------------ pelo /proxima

@pytest.fixture()
def programa_popular(db_session, account):
    radio_config = RadioConfig(account_id=account.id, timezone="America/Sao_Paulo")
    db_session.add(radio_config)
    db_session.commit()
    programa = Programa(radio_config_id=radio_config.id, nome="Tarde Sertaneja", horario_inicio=datetime.time(10, 0),
                        horario_fim=datetime.time(14, 0), estrutura_blocos=["comentario"],
                        perfil_programacao="popular_sertanejo", ia_pode_adicionar_blocos=False)
    db_session.add(programa)
    db_session.commit()
    return radio_config, programa


def _proxima(client, account, auth_headers, radio_config, programa, monkeypatch, fala, historico):
    prompts: list[str] = []
    monkeypatch.setattr("app.live.router.classificar_tema_fala", lambda texto: "")
    monkeypatch.setattr("app.live.router.gerar_resposta", lambda system, msg: prompts.append(system) or fala)
    resposta = client.post(_url_proxima(radio_config.id, programa.id),
                           json={"historico": historico, "total_falas": len(historico)},
                           headers=auth_headers(account.id))
    assert resposta.status_code == 200, resposta.text
    return prompts[0]


HISTORICO = ["abertura: Você está no Tarde Sertaneja. Começamos agora.", "comentario: A feira abriu cedo hoje."]


@pytest.mark.parametrize("minutos_desde,pede", [(5, False), (25, True)])
def test_proxima_pede_reorientacao_quando_passa_do_intervalo_do_formato(
    client, account, auth_headers, programa_popular, monkeypatch, minutos_desde, pede
):
    from app.live.router import _registrar_reorientacao

    radio_config, programa = programa_popular  # popular: reorientacao_s = 1200
    _registrar_reorientacao(programa.id, AGORA - datetime.timedelta(minutes=minutos_desde))
    with freeze_time(AGORA):
        system = _proxima(client, account, auth_headers, radio_config, programa, monkeypatch,
                          "A chuva deu uma trégua na serra.", HISTORICO)
    assert (SECAO_REORIENTACAO in system) is pede


def test_fala_que_reorienta_vira_a_ultima_reorientacao(client, account, auth_headers, programa_popular,
                                                        monkeypatch):
    from app.live.router import _registrar_reorientacao, _ultima_reorientacao

    radio_config, programa = programa_popular
    _registrar_reorientacao(programa.id, AGORA - datetime.timedelta(minutes=30))
    with freeze_time(AGORA):
        _proxima(client, account, auth_headers, radio_config, programa, monkeypatch,
                 "Você está no Tarde Sertaneja. A chuva deu uma trégua na serra hoje.", HISTORICO)
        # lida dentro do freeze: a chave tem TTL de sessão (6 h) contado no relógio congelado
        assert _ultima_reorientacao(programa.id) == AGORA


def test_fala_sem_reorientacao_nao_mexe_na_memoria(client, account, auth_headers, programa_popular, monkeypatch):
    from app.live.router import _registrar_reorientacao, _ultima_reorientacao

    radio_config, programa = programa_popular
    antes = AGORA - datetime.timedelta(minutes=10)
    _registrar_reorientacao(programa.id, antes)
    with freeze_time(AGORA):
        _proxima(client, account, auth_headers, radio_config, programa, monkeypatch,
                 "A chuva deu uma trégua na serra hoje à tarde.", HISTORICO)
        assert _ultima_reorientacao(programa.id) == antes


def test_proxima_avisa_estrutura_de_abertura_repetida(client, account, auth_headers, programa_popular, monkeypatch):
    radio_config, programa = programa_popular
    historico = ["comentario: Boa tarde, pessoal! A feira abriu.", "comentario: Oi, gente. A chuva parou."]
    with freeze_time(AGORA):
        system = _proxima(client, account, auth_headers, radio_config, programa, monkeypatch,
                          "A praça encheu de gente hoje.", historico)
    assert "As duas últimas falas abriram com saudação" in system


def test_reorientacao_pedida_libera_abertura_de_identificacao_repetida(
    client, account, auth_headers, programa_popular, monkeypatch
):
    """Exceção da F8: quando a reorientação é pedida, abrir identificando o programa não conta como repetição."""
    from app.live.router import _registrar_reorientacao

    radio_config, programa = programa_popular
    _registrar_reorientacao(programa.id, AGORA - datetime.timedelta(minutes=25))
    historico = ["comentario: Você está no Tarde Sertaneja. A feira abriu.",
                 "comentario: Você está ouvindo a Rádio Serra. A chuva parou."]
    with freeze_time(AGORA):
        system = _proxima(client, account, auth_headers, radio_config, programa, monkeypatch,
                          "A praça encheu de gente hoje.", historico)
    assert SECAO_REORIENTACAO in system
    assert "As duas últimas falas abriram com" not in system
