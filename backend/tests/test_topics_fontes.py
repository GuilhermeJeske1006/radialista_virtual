import datetime

import pytest

from app.models.assunto import Assunto
from app.models.fila_ao_vivo import FilaAoVivo
from app.models.musica import Musica
from app.models.musica_historico import MusicaHistorico
from app.models.noticia import Noticia
from app.models.programa import Programa
from app.models.radio_config import RadioConfig
from app.topics.fontes.de_efemeride import derivar_de_efemeride
from app.topics.fontes.de_musica import derivar_de_musica
from app.topics.fontes.de_noticia import derivar_de_noticia
from app.topics.fontes.de_ouvinte import derivar_de_ouvinte


@pytest.fixture()
def radio_config(db_session, account):
    radio_config = RadioConfig(account_id=account.id, timezone="America/Sao_Paulo")
    db_session.add(radio_config)
    db_session.commit()
    return radio_config


@pytest.fixture()
def programa(db_session, radio_config):
    programa = Programa(
        radio_config_id=radio_config.id, nome="Programa",
        horario_inicio=datetime.time(6, 0), horario_fim=datetime.time(9, 0),
    )
    db_session.add(programa)
    db_session.commit()
    db_session.refresh(programa)
    return programa


def _noticia(db_session, account, **kwargs):
    base = dict(
        account_id=account.id, fonte_nome="Prefeitura", fonte_tipo="oficial",
        titulo="Rua interditada apos obra", resumo="Trecho fechado ate sexta.",
        url="https://x.com/n", url_hash="hash-noticia",
        publicado_em=datetime.datetime.now(datetime.timezone.utc), categoria="transito", score=80.0,
    )
    base.update(kwargs)
    noticia = Noticia(**base)
    db_session.add(noticia)
    db_session.commit()
    db_session.refresh(noticia)
    return noticia


# --------------------------------------------------------------------------- de_noticia


def test_de_noticia_deriva_e_persiste_ganchos(db_session, account, monkeypatch):
    resposta = (
        '[{"titulo": "Quem trabalha na rua", "gancho": "leva capa hoje", '
        '"fatos": ["obra fecha a rua ate sexta"], "tags": ["servico"], "pergunta_ouvinte": ""}]'
    )
    monkeypatch.setattr("app.topics.derivador.gerar_classificacao", lambda system, msg, **_: resposta)
    noticia = _noticia(db_session, account)

    assuntos = derivar_de_noticia(db_session, noticia, account)

    assert len(assuntos) == 1
    assert assuntos[0].origem == "noticia"
    assert assuntos[0].origem_ref_id == noticia.id
    assert assuntos[0].validade_ate is not None


def test_de_noticia_nao_deriva_duas_vezes_a_mesma_noticia(db_session, account, monkeypatch):
    chamadas = []

    def _fake(system, msg, **_):
        chamadas.append(1)
        return '[{"titulo": "T", "gancho": "G", "fatos": [], "tags": []}]'
    monkeypatch.setattr("app.topics.derivador.gerar_classificacao", _fake)
    noticia = _noticia(db_session, account)

    derivar_de_noticia(db_session, noticia, account)
    segunda = derivar_de_noticia(db_session, noticia, account)

    assert segunda == []
    assert len(chamadas) == 1


# --------------------------------------------------------------------------- de_musica


def _musica(db_session, **kwargs):
    base = dict(
        titulo="Cancao Boa", artista="Artista X", titulo_normalizado="cancao boa", artista_normalizado="artista x",
        youtube_video_id="abc123",
        youtube_metadados={"descricao": "musica sobre saudade do interior", "tags": ["sertanejo"], "ano": "2010"},
    )
    base.update(kwargs)
    musica = Musica(**base)
    db_session.add(musica)
    db_session.commit()
    db_session.refresh(musica)
    return musica


def test_de_musica_deriva_contexto_real(db_session, account, programa, monkeypatch):
    musica = _musica(db_session)
    historico = MusicaHistorico(
        programa_id=programa.id, song_id=musica.id, video_id="abc123", titulo=musica.titulo,
        canal=musica.artista, query="cancao boa artista x", query_normalizada="cancao boa artista x", origem="auto",
    )
    db_session.add(historico)
    db_session.commit()
    monkeypatch.setattr(
        "app.topics.fontes.de_musica.resumir_contexto_musica",
        lambda **kwargs: "Cancao boa fala sobre saudade do interior, lancada em 2010.",
    )

    assunto = derivar_de_musica(db_session, historico, account.id)

    assert assunto is not None
    assert assunto.origem == "musica"
    assert assunto.validade_ate is None


def test_de_musica_inclui_genero_do_programa_na_tag(db_session, account, programa, monkeypatch):
    """Bug real achado testando o fluxo ao vivo: sem o genero do programa onde a musica tocou,
    o gancho so' carregava tag generica (musica/memoria/afeto) e nunca casava com o filtro por
    genero de nenhum programa -- uma faixa sertaneja nunca virava assunto do proprio programa
    sertanejo que a tocou."""
    programa.generos_musicais = ["Sertanejo Raiz", "Sertanejo Universitário"]
    db_session.commit()
    musica = _musica(db_session)
    historico = MusicaHistorico(
        programa_id=programa.id, song_id=musica.id, video_id="abc123", titulo=musica.titulo,
        canal=musica.artista, query="cancao boa artista x", query_normalizada="cancao boa artista x", origem="auto",
    )
    db_session.add(historico)
    db_session.commit()
    monkeypatch.setattr("app.topics.fontes.de_musica.resumir_contexto_musica", lambda **kwargs: "contexto real")

    assunto = derivar_de_musica(db_session, historico, account.id)

    assert assunto is not None
    assert "sertanejo raiz" in assunto.tags
    assert "sertanejo universitário" in assunto.tags


def test_de_musica_contexto_insuficiente_nao_gera_assunto(db_session, account, programa, monkeypatch):
    musica = _musica(db_session)
    historico = MusicaHistorico(
        programa_id=programa.id, song_id=musica.id, video_id="abc123", titulo=musica.titulo,
        canal=musica.artista, query="q", query_normalizada="q", origem="auto",
    )
    db_session.add(historico)
    db_session.commit()
    monkeypatch.setattr("app.topics.fontes.de_musica.resumir_contexto_musica", lambda **kwargs: "")

    assert derivar_de_musica(db_session, historico, account.id) is None


# --------------------------------------------------------------------------- de_efemeride


def test_de_efemeride_gera_gancho_quando_anos_suficientes(db_session, account):
    ano_atual = datetime.datetime.now(datetime.timezone.utc).year
    musica = _musica(db_session, youtube_metadados={"ano": str(ano_atual - 20)})

    assunto = derivar_de_efemeride(db_session, musica, account.id)

    assert assunto is not None
    assert "20 anos" in assunto.titulo


def test_de_efemeride_ignora_lancamento_recente_demais(db_session, account):
    ano_atual = datetime.datetime.now(datetime.timezone.utc).year
    musica = _musica(db_session, youtube_metadados={"ano": str(ano_atual - 1)})

    assert derivar_de_efemeride(db_session, musica, account.id) is None


def test_de_efemeride_inclui_genero_extra_na_tag(db_session, account):
    ano_atual = datetime.datetime.now(datetime.timezone.utc).year
    musica = _musica(db_session, youtube_metadados={"ano": str(ano_atual - 20)})

    assunto = derivar_de_efemeride(db_session, musica, account.id, generos_extra=["Sertanejo Raiz"])

    assert assunto is not None
    assert "sertanejo raiz" in assunto.tags


def test_de_efemeride_nao_deriva_duas_vezes_no_mesmo_ano(db_session, account):
    ano_atual = datetime.datetime.now(datetime.timezone.utc).year
    musica = _musica(db_session, youtube_metadados={"ano": str(ano_atual - 20)})

    primeiro = derivar_de_efemeride(db_session, musica, account.id)
    segundo = derivar_de_efemeride(db_session, musica, account.id)

    assert primeiro is not None
    assert segundo is None


# --------------------------------------------------------------------------- de_ouvinte


def test_pedido_recorrente_de_ouvinte_vira_pauta_de_comentario(db_session, account, radio_config, programa):
    for _ in range(3):
        db_session.add(MusicaHistorico(
            programa_id=programa.id, video_id="v1", titulo="Musica Pedida", canal="Artista Y",
            query="musica pedida artista y", query_normalizada="musica pedida artista y", origem="pedido_ouvinte",
        ))
    db_session.commit()

    assuntos = derivar_de_ouvinte(db_session, radio_config.id, account.id)

    assert len(assuntos) == 1
    assert assuntos[0].origem == "ouvinte"
    assert "musica pedida artista y" in assuntos[0].gancho.lower()


def test_pedido_isolado_nao_vira_pauta(db_session, account, radio_config, programa):
    db_session.add(MusicaHistorico(
        programa_id=programa.id, video_id="v1", titulo="Musica Pedida", canal="Artista Y",
        query="musica pedida artista y", query_normalizada="musica pedida artista y", origem="pedido_ouvinte",
    ))
    db_session.commit()

    assert derivar_de_ouvinte(db_session, radio_config.id, account.id) == []
