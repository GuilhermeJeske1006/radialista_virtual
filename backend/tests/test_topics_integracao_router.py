import datetime

import pytest
from freezegun import freeze_time

from app.live.music import MusicaEncontrada
from app.models.assunto import Assunto
from app.models.assunto_programa import AssuntoPrograma
from app.models.programa import Programa
from app.models.radio_config import RadioConfig
from app.topics.pauta_conversa import registrar_assunto_usado

AGORA_UTC = "2026-08-10 15:00:00"  # 12:00 local, dentro de um programa 10:00-14:00


@pytest.fixture()
def radialista_e_programa(db_session, account):
    radio_config = RadioConfig(account_id=account.id, timezone="America/Sao_Paulo")
    db_session.add(radio_config)
    db_session.commit()
    programa = Programa(
        radio_config_id=radio_config.id, nome="Programa Principal",
        horario_inicio=datetime.time(10, 0), horario_fim=datetime.time(14, 0),
        estrutura_blocos=[],
    )
    db_session.add(programa)
    db_session.commit()
    db_session.refresh(radio_config)
    db_session.refresh(programa)
    return radio_config, programa


def _url_proxima(radialista_id, programa_id):
    return f"/live/{radialista_id}/programas/{programa_id}/proxima"


def _casar_assunto(db_session, account, programa, *, eixos_sugeridos=None):
    assunto = Assunto(
        account_id=account.id, origem="noticia", titulo="Chuva forte a tarde",
        gancho="Defesa Civil confirma chuva forte pra tarde, risco de alagamento.",
        fatos=["Defesa Civil confirmou chuva forte a tarde"], tags=["servico", "transito"], peso_base=5.0,
    )
    db_session.add(assunto)
    db_session.flush()
    ap = AssuntoPrograma(
        assunto_id=assunto.id, programa_id=programa.id, score=8.0,
        ponte="publico deste programa trabalha na rua e sai cedo",
        eixos_sugeridos=eixos_sugeridos if eixos_sugeridos is not None else ["fato", "impacto", "servico"],
    )
    db_session.add(ap)
    db_session.commit()
    return assunto, ap


@freeze_time(AGORA_UTC)
def test_comentario_recebe_assunto_casado_com_o_programa(client, account, auth_headers, radialista_e_programa, db_session, monkeypatch):
    radio_config, programa = radialista_e_programa
    assunto, _ap = _casar_assunto(db_session, account, programa)

    prompts = []
    monkeypatch.setattr("app.live.router.gerar_resposta", lambda system, msg: prompts.append(system) or "Comentario com o assunto casado.")
    monkeypatch.setattr("app.live.router.classificar_tema_fala", lambda texto: "")

    resposta = client.post(
        _url_proxima(radio_config.id, programa.id),
        json={"historico": [], "total_falas": 3},
        headers=auth_headers(account.id),
    )

    assert resposta.status_code == 200
    assert resposta.json()["tipo"] == "comentario"
    assert "PAUTA DESTE ASSUNTO" in prompts[0]
    assert assunto.gancho in prompts[0]
    assert "publico deste programa trabalha na rua" in prompts[0]

    from app.config.redis_client import redis_client
    historico = redis_client.lrange(f"assuntos_usados:{programa.id}", 0, -1)
    assert len(historico) == 1
    assert historico[0].startswith(f"{assunto.id}|")


@freeze_time(AGORA_UTC)
def test_cascata_esgotada_troca_o_bloco_e_nunca_gera_fala_vazia(client, account, auth_headers, radialista_e_programa, db_session, monkeypatch):
    """ADR item 6, degrau 4: pipeline ativo pra este programa (ja' existe casamento) mas
    esgotado nesta sessao (unico eixo sugerido ja' foi usado) e sem assuntos_ao_vivo manual --
    o bloco de comentario vira musica em vez de gerar fala livre/vazia."""
    radio_config, programa = radialista_e_programa
    assunto, _ap = _casar_assunto(db_session, account, programa, eixos_sugeridos=["fato"])
    registrar_assunto_usado(programa.id, radio_config.id, assunto.id, eixo="fato", origem="noticia", tag_principal="servico")

    # Bloco de musica ainda chama gerar_resposta (fala de introducao da faixa, ver
    # test_gerar_proxima_fala_bloco_musica_inclui_dados_da_musica em test_live_router.py) -- o
    # que este teste garante e' que o bloco deixou de ser "comentario" (que geraria fala livre
    # sem pauta nenhuma) e virou "musica" com a faixa de verdade.
    monkeypatch.setattr("app.live.router.gerar_resposta", lambda system, msg: "Vamos ouvir essa!")
    monkeypatch.setattr(
        "app.live.router.buscar_musica",
        lambda query, **kwargs: MusicaEncontrada(video_id="abc123", titulo="Musica Generica", canal="Canal X"),
    )

    resposta = client.post(
        _url_proxima(radio_config.id, programa.id),
        json={"historico": [], "total_falas": 3},
        headers=auth_headers(account.id),
    )

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["tipo"] == "musica"
    assert corpo["video_id"] == "abc123"


@freeze_time(AGORA_UTC)
def test_pipeline_nunca_rodou_mantem_geracao_livre_sem_regressao(client, account, auth_headers, radialista_e_programa, monkeypatch):
    """Conta nova / pipeline ainda nao rodou (nenhum AssuntoPrograma pra este programa) -- NAO
    deve cascatear pra musica, senao toda conta nova perderia o bloco de comentario ate' o
    worker rodar por uma semana. Mantem o comportamento anterior a este plano."""
    radio_config, programa = radialista_e_programa
    monkeypatch.setattr("app.live.router.gerar_resposta", lambda system, msg: "comentario livre de sempre")
    monkeypatch.setattr("app.live.router.classificar_tema_fala", lambda texto: "")

    resposta = client.post(
        _url_proxima(radio_config.id, programa.id),
        json={"historico": [], "total_falas": 3},
        headers=auth_headers(account.id),
    )

    assert resposta.status_code == 200
    assert resposta.json()["tipo"] == "comentario"


@freeze_time(AGORA_UTC)
def test_musica_puxa_assunto_do_comentario_seguinte(client, account, auth_headers, radialista_e_programa, monkeypatch):
    """Fase G: contexto real da musica que acabou de tocar (sem chamada de LLM extra -- reaproveita
    o que ja' foi computado pra anunciar a faixa) vira pauta do bloco de comentario logo depois."""
    radio_config, programa = radialista_e_programa
    monkeypatch.setattr(
        "app.live.router.buscar_musica",
        lambda query, **kwargs: MusicaEncontrada(
            video_id="abc123", titulo="Musica Teste", canal="Canal Teste",
            descricao="Uma composicao sobre a vida no interior", tags=["sertanejo raiz"], ano="1998",
        ),
    )
    monkeypatch.setattr(
        "app.live.router.resumir_contexto_musica",
        lambda titulo, canal, descricao, tags, ano: "Fala sobre a vida no interior, de 1998.",
    )
    monkeypatch.setattr("app.live.router.classificar_tema_fala", lambda texto: "")

    prompts = []
    monkeypatch.setattr("app.live.router.gerar_resposta", lambda system, msg: prompts.append(system) or "Vamos ouvir essa!")

    # total_falas=1 -> bloco "musica" no roteiro padrao.
    resposta_musica = client.post(
        _url_proxima(radio_config.id, programa.id),
        json={"historico": ["abertura: oi"], "total_falas": 1},
        headers=auth_headers(account.id),
    )
    assert resposta_musica.status_code == 200
    assert resposta_musica.json()["tipo"] == "musica"

    # total_falas=3 -> bloco "comentario" no roteiro padrao, logo em seguida.
    resposta_comentario = client.post(
        _url_proxima(radio_config.id, programa.id),
        json={"historico": [], "total_falas": 3},
        headers=auth_headers(account.id),
    )
    assert resposta_comentario.status_code == 200
    assert resposta_comentario.json()["tipo"] == "comentario"
    assert "Fala sobre a vida no interior, de 1998." in prompts[1]
    assert "PAUTA DESTE ASSUNTO" in prompts[1]
    assert "EIXO DESTE BLOCO: MEMORIA" in prompts[1]
