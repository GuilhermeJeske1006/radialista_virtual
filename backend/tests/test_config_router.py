
import datetime

from app.tts.voices import VOZES_DISPONIVEIS


def _criar_radialista(client, auth_headers, account_id, nome="Ze do Radio"):
    return client.post(
        "/config/radialistas",
        json={"nome_locutor": nome, "personalidade": "", "timezone": "America/Sao_Paulo"},
        headers=auth_headers(account_id),
    )


def _programa_payload(**kwargs):
    padrao = dict(
        nome="Programa Teste",
        descricao="",
        dias_semana=[],
        horario_inicio="10:00:00",
        horario_fim="12:00:00",
        ativo=True,
        tom="animado",
    )
    padrao.update(kwargs)
    return padrao


def test_obter_e_atualizar_dados_da_radio(client, account, auth_headers):
    resposta = client.put(
        "/config/radio",
        json={"nome_radio": "Radio Top", "slogan": "A melhor", "cidade": "Porto Alegre"},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 200
    assert resposta.json()["nome_radio"] == "Radio Top"

    obtido = client.get("/config/radio", headers=auth_headers(account.id))
    assert obtido.json()["nome_radio"] == "Radio Top"


def test_tipos_radio_endpoint_retorna_catalogo(client):
    resposta = client.get("/config/tipos-radio")
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert len(corpo) > 0
    assert {"value", "label"} <= corpo[0].keys()
    assert any(t["value"] == "sertaneja" for t in corpo)


def test_atualizar_radio_salva_tipo_radio(client, account, auth_headers):
    resposta = client.put(
        "/config/radio", json={"tipo_radio": "gospel"}, headers=auth_headers(account.id)
    )
    assert resposta.status_code == 200
    assert resposta.json()["tipo_radio"] == "gospel"


def test_atualizar_radio_com_tipo_invalido_falha_400(client, account, auth_headers):
    resposta = client.put(
        "/config/radio", json={"tipo_radio": "nao-existe"}, headers=auth_headers(account.id)
    )
    assert resposta.status_code == 400


def test_criar_radialista(client, account, auth_headers):
    resposta = _criar_radialista(client, auth_headers, account.id)
    assert resposta.status_code == 201
    assert resposta.json()["nome_locutor"] == "Ze do Radio"


def test_criar_radialista_com_voz_invalida_falha(client, account, auth_headers):
    resposta = client.post(
        "/config/radialistas",
        json={"nome_locutor": "Ze", "voz_id": "voz-invalida"},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 400


def test_criar_radialista_respeita_limite_do_plano(client, account, auth_headers):
    assert account.plano == "starter"  # limite de 1 agente
    primeiro = _criar_radialista(client, auth_headers, account.id, nome="Primeiro")
    assert primeiro.status_code == 201

    segundo = _criar_radialista(client, auth_headers, account.id, nome="Segundo")
    assert segundo.status_code == 402


def test_listar_radialistas(client, account, auth_headers):
    _criar_radialista(client, auth_headers, account.id)
    resposta = client.get("/config/radialistas", headers=auth_headers(account.id))
    assert resposta.status_code == 200
    assert len(resposta.json()) == 1


def test_obter_radialista_de_outra_conta_falha(client, account_factory, auth_headers):
    dono = account_factory(email="dono@a.com")
    outro = account_factory(email="outro@a.com")
    criado = _criar_radialista(client, auth_headers, dono.id).json()

    resposta = client.get(f"/config/radialistas/{criado['id']}", headers=auth_headers(outro.id))
    assert resposta.status_code == 404


def test_atualizar_radialista(client, account, auth_headers):
    criado = _criar_radialista(client, auth_headers, account.id).json()
    resposta = client.put(
        f"/config/radialistas/{criado['id']}",
        json={"nome_locutor": "Novo Nome", "timezone": "America/Sao_Paulo"},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 200
    assert resposta.json()["nome_locutor"] == "Novo Nome"


def test_excluir_radialista(client, account, auth_headers):
    criado = _criar_radialista(client, auth_headers, account.id).json()
    resposta = client.delete(f"/config/radialistas/{criado['id']}", headers=auth_headers(account.id))
    assert resposta.status_code == 204

    listagem = client.get("/config/radialistas", headers=auth_headers(account.id)).json()
    assert listagem == []


def test_criar_programa(client, account, auth_headers):
    radialista = _criar_radialista(client, auth_headers, account.id).json()
    resposta = client.post(
        f"/config/radialistas/{radialista['id']}/programas",
        json=_programa_payload(),
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 201
    assert resposta.json()["nome"] == "Programa Teste"


def test_criar_programa_com_conflito_de_horario_falha(client, account, auth_headers):
    radialista = _criar_radialista(client, auth_headers, account.id).json()
    client.post(
        f"/config/radialistas/{radialista['id']}/programas",
        json=_programa_payload(nome="Programa 1", horario_inicio="10:00:00", horario_fim="12:00:00"),
        headers=auth_headers(account.id),
    )
    resposta = client.post(
        f"/config/radialistas/{radialista['id']}/programas",
        json=_programa_payload(nome="Programa 2", horario_inicio="11:00:00", horario_fim="13:00:00"),
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 409


def test_criar_programa_sem_conflito_de_horario_funciona(client, account, auth_headers):
    radialista = _criar_radialista(client, auth_headers, account.id).json()
    client.post(
        f"/config/radialistas/{radialista['id']}/programas",
        json=_programa_payload(nome="Programa 1", horario_inicio="10:00:00", horario_fim="12:00:00"),
        headers=auth_headers(account.id),
    )
    resposta = client.post(
        f"/config/radialistas/{radialista['id']}/programas",
        json=_programa_payload(nome="Programa 2", horario_inicio="12:00:00", horario_fim="14:00:00"),
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 201


def test_listar_programas(client, account, auth_headers):
    radialista = _criar_radialista(client, auth_headers, account.id).json()
    client.post(
        f"/config/radialistas/{radialista['id']}/programas",
        json=_programa_payload(),
        headers=auth_headers(account.id),
    )
    resposta = client.get(
        f"/config/radialistas/{radialista['id']}/programas", headers=auth_headers(account.id)
    )
    assert resposta.status_code == 200
    assert len(resposta.json()) == 1


def test_atualizar_programa(client, account, auth_headers):
    radialista = _criar_radialista(client, auth_headers, account.id).json()
    programa = client.post(
        f"/config/radialistas/{radialista['id']}/programas",
        json=_programa_payload(),
        headers=auth_headers(account.id),
    ).json()

    resposta = client.put(
        f"/config/programas/{programa['id']}",
        json=_programa_payload(nome="Programa Renomeado"),
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 200
    assert resposta.json()["nome"] == "Programa Renomeado"


def test_criar_programa_com_publico_alvo_e_densidade_assunto(client, account, auth_headers):
    """Ver Fase A/H do plano-assuntos.md -- campos opcionais, default preserva comportamento
    anterior a eles existirem (publico_alvo vazio, densidade_assunto 'leve')."""
    radialista = _criar_radialista(client, auth_headers, account.id).json()

    resposta_default = client.post(
        f"/config/radialistas/{radialista['id']}/programas",
        json=_programa_payload(nome="Programa Sem Publico Alvo"),
        headers=auth_headers(account.id),
    )
    assert resposta_default.status_code == 201
    assert resposta_default.json()["publico_alvo"] == ""
    assert resposta_default.json()["densidade_assunto"] == "leve"

    resposta = client.post(
        f"/config/radialistas/{radialista['id']}/programas",
        json=_programa_payload(
            nome="Programa Com Publico Alvo",
            horario_inicio="14:00:00", horario_fim="16:00:00",
            publico_alvo="trabalhador rural que sai de casa as cinco",
            densidade_assunto="informado",
        ),
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 201
    assert resposta.json()["publico_alvo"] == "trabalhador rural que sai de casa as cinco"
    assert resposta.json()["densidade_assunto"] == "informado"


def test_atualizar_programa_nao_conflita_consigo_mesmo(client, account, auth_headers):
    radialista = _criar_radialista(client, auth_headers, account.id).json()
    programa = client.post(
        f"/config/radialistas/{radialista['id']}/programas",
        json=_programa_payload(),
        headers=auth_headers(account.id),
    ).json()

    resposta = client.put(
        f"/config/programas/{programa['id']}",
        json=_programa_payload(nome="Mesmo horario"),
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 200


def test_excluir_programa(client, account, auth_headers):
    radialista = _criar_radialista(client, auth_headers, account.id).json()
    programa = client.post(
        f"/config/radialistas/{radialista['id']}/programas",
        json=_programa_payload(),
        headers=auth_headers(account.id),
    ).json()

    resposta = client.delete(f"/config/programas/{programa['id']}", headers=auth_headers(account.id))
    assert resposta.status_code == 204


def test_excluir_programa_com_assunto_casado_e_historico_de_noticia(client, account, auth_headers, db_session):
    """Bug real achado testando o fluxo ao vivo do banco de assuntos (ver plano-assuntos.md):
    AssuntoPrograma/NoticiaHistorico tem FK pra programas.id sem ON DELETE CASCADE -- excluir um
    programa que ja' tem assunto casado ou historico de noticia estourava ForeignKeyViolation
    (500) em vez de 204."""
    from app.models.assunto import Assunto
    from app.models.assunto_programa import AssuntoPrograma
    from app.models.noticia import Noticia
    from app.models.noticia_historico import NoticiaHistorico

    radialista = _criar_radialista(client, auth_headers, account.id).json()
    programa = client.post(
        f"/config/radialistas/{radialista['id']}/programas",
        json=_programa_payload(),
        headers=auth_headers(account.id),
    ).json()

    assunto = Assunto(account_id=account.id, origem="reserva", titulo="X", gancho="Y", fatos=[], tags=[])
    db_session.add(assunto)
    db_session.flush()
    db_session.add(AssuntoPrograma(assunto_id=assunto.id, programa_id=programa["id"], score=5.0, ponte="", eixos_sugeridos=[]))

    noticia = Noticia(
        account_id=account.id, fonte_nome="Fonte", titulo="Titulo", url="https://x.com/n", url_hash="hash-x",
        publicado_em=datetime.datetime.now(datetime.timezone.utc),
    )
    db_session.add(noticia)
    db_session.flush()
    db_session.add(NoticiaHistorico(programa_id=programa["id"], noticia_id=noticia.id, angulo="fato", fala="fala"))
    db_session.commit()

    resposta = client.delete(f"/config/programas/{programa['id']}", headers=auth_headers(account.id))
    assert resposta.status_code == 204


def test_gerar_radialista_ia(client, account, auth_headers, monkeypatch):
    monkeypatch.setattr(
        "app.config.router.gerar_configuracao_ia",
        lambda descricao, tipo_radio=None, account=None, roster_existente=None: (
            {
                "nome_locutor": "IA Radialista",
                "personalidade": "animado",
                "voz_id": VOZES_DISPONIVEIS[0]["voz_id"],
                "timezone": "America/Sao_Paulo",
            },
            {
                "nome": "Programa IA",
                "tom": "animado",
                "horario_inicio": "08:00:00",
                "horario_fim": "10:00:00",
            },
        ),
    )
    resposta = client.post(
        "/config/radialistas/gerar-ia", json={"descricao": "radio animada"}, headers=auth_headers(account.id)
    )
    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["radialista"]["nome_locutor"] == "IA Radialista"
    assert corpo["programa"]["nome"] == "Programa IA"


def test_gerar_radialista_ia_sem_descricao_usa_tipo_radio(client, account, auth_headers, monkeypatch, db_session):
    account.tipo_radio = "sertaneja"
    db_session.commit()

    chamadas = []

    def _gerar(descricao, tipo_radio=None, account=None, roster_existente=None):
        chamadas.append((descricao, tipo_radio))
        return (
            {
                "nome_locutor": "IA Radialista",
                "personalidade": "animado",
                "voz_id": VOZES_DISPONIVEIS[0]["voz_id"],
                "timezone": "America/Sao_Paulo",
            },
            {"nome": "Programa IA", "tom": "animado", "horario_inicio": "08:00:00", "horario_fim": "10:00:00"},
        )

    monkeypatch.setattr("app.config.router.gerar_configuracao_ia", _gerar)
    resposta = client.post(
        "/config/radialistas/gerar-ia", json={}, headers=auth_headers(account.id)
    )
    assert resposta.status_code == 201
    assert chamadas == [("", "sertaneja")]


def test_gerar_radialista_ia_falha_sem_tipo_e_sem_descricao(client, account, auth_headers):
    assert account.tipo_radio == ""
    resposta = client.post(
        "/config/radialistas/gerar-ia", json={"descricao": "  "}, headers=auth_headers(account.id)
    )
    assert resposta.status_code == 400


def test_gerar_radialista_ia_falha_do_llm_devolve_502(client, account, auth_headers, monkeypatch):
    def _falha(descricao, tipo_radio=None, account=None, roster_existente=None):
        raise ValueError("LLM nao respondeu")

    monkeypatch.setattr("app.config.router.gerar_configuracao_ia", _falha)
    resposta = client.post(
        "/config/radialistas/gerar-ia", json={"descricao": "radio animada"}, headers=auth_headers(account.id)
    )
    assert resposta.status_code == 502


def test_gerar_radialista_ia_respeita_rate_limit(client, account_factory, auth_headers, monkeypatch):
    account = account_factory(email="growth@a.com", plano="growth")
    # Sem limite de agentes nem conflito de horario no meio do caminho -- isola o rate limit em si.
    monkeypatch.setattr("app.config.router.limite_agentes_efetivo", lambda acc: 999)

    def _gerar(descricao, tipo_radio=None, account=None, roster_existente=None):
        i = int(descricao)
        return (
            {
                "nome_locutor": f"IA{i}",
                "personalidade": "",
                "voz_id": VOZES_DISPONIVEIS[0]["voz_id"],
                "timezone": "America/Sao_Paulo",
            },
            {"nome": f"P{i}", "tom": "x", "horario_inicio": f"{i:02d}:00:00", "horario_fim": f"{i:02d}:30:00"},
        )

    monkeypatch.setattr("app.config.router.gerar_configuracao_ia", _gerar)

    for i in range(5):
        resposta = client.post(
            "/config/radialistas/gerar-ia", json={"descricao": str(i)}, headers=auth_headers(account.id)
        )
        assert resposta.status_code == 201

    bloqueado = client.post(
        "/config/radialistas/gerar-ia", json={"descricao": "5"}, headers=auth_headers(account.id)
    )
    assert bloqueado.status_code == 429


def test_cota_nao_e_consumida_quando_a_geracao_falha(client, account, auth_headers, monkeypatch):
    """Falha do LLM (ValueError) nao pode contar pro limite de 5/hora -- so' tentativa que
    de fato gerou algo consome cota (ver Fase 2/6 do plano de melhoria)."""
    monkeypatch.setattr("app.config.router.limite_agentes_efetivo", lambda acc: 999)

    def _falha(descricao, tipo_radio=None, account=None, roster_existente=None):
        raise ValueError("LLM nao respondeu")

    monkeypatch.setattr("app.config.router.gerar_configuracao_ia", _falha)
    for _ in range(6):
        resposta = client.post(
            "/config/radialistas/gerar-ia", json={"descricao": "x"}, headers=auth_headers(account.id)
        )
        assert resposta.status_code == 502

    monkeypatch.setattr(
        "app.config.router.gerar_configuracao_ia",
        lambda descricao, tipo_radio=None, account=None, roster_existente=None: (
            {
                "nome_locutor": "IA",
                "personalidade": "",
                "voz_id": VOZES_DISPONIVEIS[0]["voz_id"],
                "timezone": "America/Sao_Paulo",
            },
            {"nome": "P", "tom": "x", "horario_inicio": "08:00:00", "horario_fim": "09:00:00"},
        ),
    )
    resposta = client.post(
        "/config/radialistas/gerar-ia", json={"descricao": "x"}, headers=auth_headers(account.id)
    )
    assert resposta.status_code == 201


def test_preview_nao_grava_nada_nem_consome_slot_de_agente(client, account, auth_headers, db_session, monkeypatch):
    monkeypatch.setattr("app.config.router.limite_agentes_efetivo", lambda acc: 0)  # ja no limite
    monkeypatch.setattr(
        "app.config.router.gerar_configuracao_ia",
        lambda descricao, tipo_radio=None, account=None, roster_existente=None: (
            {
                "nome_locutor": "IA Radialista",
                "personalidade": "animado",
                "voz_id": VOZES_DISPONIVEIS[0]["voz_id"],
                "timezone": "America/Sao_Paulo",
            },
            {"nome": "Programa IA", "tom": "animado", "horario_inicio": "08:00:00", "horario_fim": "10:00:00"},
        ),
    )
    resposta = client.post(
        "/config/radialistas/gerar-ia/preview", json={"descricao": "radio animada"}, headers=auth_headers(account.id)
    )
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["radialista"]["nome_locutor"] == "IA Radialista"
    assert corpo["programa"]["nome"] == "Programa IA"
    assert corpo["campos_corrigidos"] == []
    assert corpo["avisos"] == []

    from app.models.radio_config import RadioConfig

    assert db_session.query(RadioConfig).count() == 0


def test_preview_avisa_conflito_de_horario_sem_bloquear(client, account, auth_headers, monkeypatch):
    """Preview so' AVISA de conflito de horario (ver Fase 5) -- ao contrario de criar_programa,
    que da 409 -- porque o cliente ainda vai revisar/ajustar antes de confirmar."""
    existente = _criar_radialista(client, auth_headers, account.id, nome="Ze").json()
    client.post(
        f"/config/radialistas/{existente['id']}/programas",
        json=_programa_payload(nome="Programa Existente", horario_inicio="08:00:00", horario_fim="10:00:00"),
        headers=auth_headers(account.id),
    )

    monkeypatch.setattr(
        "app.config.router.gerar_programa_ia",
        lambda *a, **k: {"nome": "Novo", "tom": "x", "horario_inicio": "09:00:00", "horario_fim": "11:00:00"},
    )
    resposta = client.post(
        f"/config/radialistas/{existente['id']}/programas/gerar-ia/preview",
        json={"descricao": "x"},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert any("Programa Existente" in a for a in corpo["avisos"])


def test_preview_avisa_generos_musicais_sem_bloco_de_musica(client, account, auth_headers, monkeypatch):
    radialista = _criar_radialista(client, auth_headers, account.id).json()
    monkeypatch.setattr(
        "app.config.router.gerar_programa_ia",
        lambda *a, **k: {
            "nome": "Novo",
            "tom": "x",
            "horario_inicio": "09:00:00",
            "horario_fim": "11:00:00",
            "generos_musicais": ["sertanejo"],
            "estrutura_blocos": ["abertura", "comentario"],
        },
    )
    resposta = client.post(
        f"/config/radialistas/{radialista['id']}/programas/gerar-ia/preview",
        json={"descricao": "x"},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert any("bloco de música" in a for a in corpo["avisos"])


def test_preview_avisa_voz_ja_usada_por_outro_radialista(client, account, auth_headers, monkeypatch):
    outro = _criar_radialista(client, auth_headers, account.id, nome="Ja Existe").json()
    client.put(
        f"/config/radialistas/{outro['id']}",
        json={
            "nome_locutor": outro["nome_locutor"],
            "personalidade": "x",
            "voz_id": VOZES_DISPONIVEIS[0]["voz_id"],
            "timezone": "America/Sao_Paulo",
        },
        headers=auth_headers(account.id),
    )
    monkeypatch.setattr(
        "app.config.router.gerar_configuracao_ia",
        lambda descricao, tipo_radio=None, account=None, roster_existente=None: (
            {
                "nome_locutor": "Novo",
                "personalidade": "x",
                "voz_id": VOZES_DISPONIVEIS[0]["voz_id"],
                "timezone": "America/Sao_Paulo",
            },
            {"nome": "P", "tom": "x", "horario_inicio": "08:00:00", "horario_fim": "09:00:00"},
        ),
    )
    resposta = client.post(
        "/config/radialistas/gerar-ia/preview", json={"descricao": "x"}, headers=auth_headers(account.id)
    )
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert any("Ja Existe" in a for a in corpo["avisos"])


def test_validation_error_dispara_reparo_unico_e_nao_loop(client, account, auth_headers, monkeypatch):
    chamadas_reparo = []

    monkeypatch.setattr(
        "app.config.router.gerar_configuracao_ia",
        lambda descricao, tipo_radio=None, account=None, roster_existente=None: (
            {
                "nome_locutor": "IA Radialista",
                "personalidade": "animado",
                "voz_id": VOZES_DISPONIVEIS[0]["voz_id"],
                "timezone": "America/Sao_Paulo",
            },
            {"nome": "Programa IA", "horario_inicio": "08:00:00", "horario_fim": "10:00:00"},  # falta 'tom'
        ),
    )

    def _reparar(tipo_radio, account, roster_existente, dados_radialista, dados_programa, erros):
        chamadas_reparo.append(erros)
        return dados_radialista, {**dados_programa, "tom": "animado"}

    monkeypatch.setattr("app.config.router.reparar_configuracao_ia", _reparar)

    resposta = client.post(
        "/config/radialistas/gerar-ia", json={"descricao": "radio animada"}, headers=auth_headers(account.id)
    )
    assert resposta.status_code == 201
    assert resposta.json()["programa"]["tom"] == "animado"
    assert len(chamadas_reparo) == 1


def test_reparo_falho_devolve_proposta_parcial_com_campos_marcados(client, account, auth_headers, monkeypatch):
    monkeypatch.setattr(
        "app.config.router.gerar_configuracao_ia",
        lambda descricao, tipo_radio=None, account=None, roster_existente=None: (
            {
                "nome_locutor": "IA Radialista",
                "personalidade": "animado",
                "voz_id": VOZES_DISPONIVEIS[0]["voz_id"],
                "timezone": "America/Sao_Paulo",
            },
            {"nome": "Programa IA", "horario_inicio": "08:00:00", "horario_fim": "10:00:00"},  # falta 'tom'
        ),
    )

    def _reparo_falha(tipo_radio, account, roster_existente, dados_radialista, dados_programa, erros):
        raise ValueError("reparo tambem falhou")

    monkeypatch.setattr("app.config.router.reparar_configuracao_ia", _reparo_falha)

    resposta = client.post(
        "/config/radialistas/gerar-ia/preview", json={"descricao": "radio animada"}, headers=auth_headers(account.id)
    )
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["programa"]["tom"] == "neutro"
    assert "tom" in corpo["campos_corrigidos"]


def test_commit_radialista_ia_reaproveita_placeholder(client, account, auth_headers, db_session):
    """POST /gerar-ia/commit (usado depois da tela de revisao do preview) tem que respeitar a
    MESMA logica de reaproveitamento de placeholder do endpoint atomico -- sem chamar LLM."""
    placeholder = _criar_radialista(client, auth_headers, account.id, nome="Programa Principal").json()
    client.post(
        f"/config/radialistas/{placeholder['id']}/programas",
        json=_programa_payload(nome="Programa Principal", dias_semana=[], horario_inicio="00:00:00", horario_fim="23:59:00"),
        headers=auth_headers(account.id),
    )
    assert placeholder["voz_id"] is None

    resposta = client.post(
        "/config/radialistas/gerar-ia/commit",
        json={
            "radialista": {
                "nome_locutor": "Ze Revisado",
                "personalidade": "animado",
                "voz_id": VOZES_DISPONIVEIS[0]["voz_id"],
                "timezone": "America/Sao_Paulo",
            },
            "programa": _programa_payload(nome="Programa Revisado"),
        },
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["radialista"]["id"] == placeholder["id"]
    assert corpo["radialista"]["nome_locutor"] == "Ze Revisado"

    todos_radialistas = client.get("/config/radialistas", headers=auth_headers(account.id)).json()
    assert len(todos_radialistas) == 1


def test_commit_radialista_ia_respeita_limite_de_agentes(client, account, auth_headers, monkeypatch):
    configurado = _criar_radialista(client, auth_headers, account.id).json()
    client.put(
        f"/config/radialistas/{configurado['id']}",
        json={
            "nome_locutor": configurado["nome_locutor"],
            "personalidade": "",
            "voz_id": VOZES_DISPONIVEIS[0]["voz_id"],
            "timezone": "America/Sao_Paulo",
        },
        headers=auth_headers(account.id),
    )
    monkeypatch.setattr("app.config.router.limite_agentes_efetivo", lambda acc: 1)

    resposta = client.post(
        "/config/radialistas/gerar-ia/commit",
        json={
            "radialista": {
                "nome_locutor": "Novo",
                "personalidade": "",
                "voz_id": VOZES_DISPONIVEIS[0]["voz_id"],
                "timezone": "America/Sao_Paulo",
            },
            "programa": _programa_payload(),
        },
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 402


def test_preview_devolve_geracao_id_e_commit_marca_aceita(client, account, auth_headers, db_session, monkeypatch):
    """Ver Fase 10 do plano de melhoria: preview registra a proposta e devolve geracao_id;
    commit, quando recebe esse id de volta, marca a geracao como aceita com o payload final."""
    from app.models.geracao_ia import GeracaoIA

    monkeypatch.setattr(
        "app.config.router.gerar_configuracao_ia",
        lambda descricao, tipo_radio=None, account=None, roster_existente=None: (
            {
                "nome_locutor": "IA",
                "personalidade": "animado",
                "voz_id": VOZES_DISPONIVEIS[0]["voz_id"],
                "timezone": "America/Sao_Paulo",
            },
            {"nome": "P", "tom": "x", "horario_inicio": "08:00:00", "horario_fim": "09:00:00"},
        ),
    )
    preview = client.post(
        "/config/radialistas/gerar-ia/preview", json={"descricao": "x"}, headers=auth_headers(account.id)
    ).json()
    geracao_id = preview["geracao_id"]
    assert geracao_id is not None

    registro = db_session.query(GeracaoIA).filter_by(id=geracao_id).first()
    assert registro is not None
    assert registro.aceita is False
    assert registro.proposta_final is None

    resposta = client.post(
        "/config/radialistas/gerar-ia/commit",
        json={"radialista": preview["radialista"], "programa": preview["programa"], "geracao_id": geracao_id},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 201

    db_session.refresh(registro)
    assert registro.aceita is True
    assert registro.proposta_final["radialista"]["nome_locutor"] == "IA"


def test_refinar_persona_troca_so_persona_mantendo_programa(client, account, auth_headers, monkeypatch):
    monkeypatch.setattr(
        "app.config.router.gerar_persona_ia",
        lambda descricao, tipo_radio=None, account=None, roster_existente=None: {
            "nome_locutor": "Nome Novo",
            "personalidade": "outra",
            "voz_id": VOZES_DISPONIVEIS[1]["voz_id"],
            "timezone": "America/Sao_Paulo",
        },
    )
    resposta = client.post(
        "/config/radialistas/gerar-ia/refinar",
        json={
            "escopo": "persona",
            "radialista": {
                "nome_locutor": "Nome Antigo",
                "personalidade": "x",
                "voz_id": VOZES_DISPONIVEIS[0]["voz_id"],
                "timezone": "America/Sao_Paulo",
            },
            "programa": _programa_payload(nome="Programa Mantido"),
        },
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["radialista"]["nome_locutor"] == "Nome Novo"
    assert corpo["programa"]["nome"] == "Programa Mantido"


def test_refinar_programa_troca_so_programa_mantendo_persona(client, account, auth_headers, monkeypatch):
    monkeypatch.setattr(
        "app.config.router.gerar_programa_ia",
        lambda *a, **k: {"nome": "Grade Nova", "tom": "x", "horario_inicio": "08:00:00", "horario_fim": "09:00:00"},
    )
    resposta = client.post(
        "/config/radialistas/gerar-ia/refinar",
        json={
            "escopo": "programa",
            "radialista": {
                "nome_locutor": "Nome Mantido",
                "personalidade": "x",
                "voz_id": VOZES_DISPONIVEIS[0]["voz_id"],
                "timezone": "America/Sao_Paulo",
            },
            "programa": _programa_payload(nome="Grade Antiga"),
        },
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["radialista"]["nome_locutor"] == "Nome Mantido"
    assert corpo["programa"]["nome"] == "Grade Nova"


def test_refinar_ajuste_aplica_instrucao(client, account, auth_headers, monkeypatch):
    chamadas = []

    def _ajustar(instrucao, radialista_atual, programa_atual, tipo_radio=None, account=None):
        chamadas.append(instrucao)
        return radialista_atual, {**programa_atual, "tom": "mais serio"}

    monkeypatch.setattr("app.config.router.ajustar_configuracao_ia", _ajustar)
    resposta = client.post(
        "/config/radialistas/gerar-ia/refinar",
        json={
            "escopo": "ajuste",
            "instrucao": "deixa mais serio",
            "radialista": {
                "nome_locutor": "N",
                "personalidade": "x",
                "voz_id": VOZES_DISPONIVEIS[0]["voz_id"],
                "timezone": "America/Sao_Paulo",
            },
            "programa": _programa_payload(tom="animado"),
        },
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 200
    assert resposta.json()["programa"]["tom"] == "mais serio"
    assert chamadas == ["deixa mais serio"]


def test_ajustar_programa_ia_preview_exige_instrucao(client, account, auth_headers):
    resposta = client.post(
        "/config/programas/gerar-ia/ajustar",
        json={"instrucao": "  ", "programa": _programa_payload()},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 400


def test_ajustar_programa_ia_preview_aplica_instrucao_sem_gravar(client, account, auth_headers, db_session, monkeypatch):
    monkeypatch.setattr(
        "app.config.router.ajustar_programa_ia",
        lambda instrucao, programa_atual, tipo_radio=None, account=None: {**programa_atual, "tom": "calmo"},
    )
    resposta = client.post(
        "/config/programas/gerar-ia/ajustar",
        json={"instrucao": "deixa mais calmo", "programa": _programa_payload(tom="animado")},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 200
    assert resposta.json()["programa"]["tom"] == "calmo"

    from app.models.programa import Programa

    assert db_session.query(Programa).count() == 0


def test_gerar_radialista_ia_reaproveita_placeholder_do_cadastro(client, account, auth_headers, db_session, monkeypatch):
    """Conta nova (plano starter, limite=1 agente) ja' vem com o radialista+programa padrao
    criados no /auth/register (ver app/auth/router.py::registrar) -- sem voz definida ainda.
    Gerar com IA nesse momento nao pode bater o limite de agentes tentando criar um SEGUNDO
    radialista; tem que preencher o placeholder existente."""
    placeholder = _criar_radialista(client, auth_headers, account.id, nome="Programa Principal").json()
    programa_padrao = client.post(
        f"/config/radialistas/{placeholder['id']}/programas",
        json=_programa_payload(nome="Programa Principal", dias_semana=[], horario_inicio="00:00:00", horario_fim="23:59:00"),
        headers=auth_headers(account.id),
    ).json()
    assert placeholder["voz_id"] is None

    monkeypatch.setattr(
        "app.config.router.gerar_configuracao_ia",
        lambda descricao, tipo_radio=None, account=None, roster_existente=None: (
            {
                "nome_locutor": "Ze Gerado",
                "personalidade": "animado",
                "voz_id": VOZES_DISPONIVEIS[0]["voz_id"],
                "timezone": "America/Sao_Paulo",
            },
            {"nome": "Programa Gerado", "tom": "animado", "horario_inicio": "08:00:00", "horario_fim": "10:00:00"},
        ),
    )

    resposta = client.post(
        "/config/radialistas/gerar-ia", json={"descricao": "radio sertaneja"}, headers=auth_headers(account.id)
    )
    assert resposta.status_code == 201
    corpo = resposta.json()

    # reaproveitou o MESMO radialista e o MESMO programa (nao criou um segundo agente)
    assert corpo["radialista"]["id"] == placeholder["id"]
    assert corpo["programa"]["id"] == programa_padrao["id"]
    assert corpo["radialista"]["nome_locutor"] == "Ze Gerado"
    assert corpo["programa"]["nome"] == "Programa Gerado"

    todos_radialistas = client.get("/config/radialistas", headers=auth_headers(account.id)).json()
    assert len(todos_radialistas) == 1
    todos_programas = client.get(
        f"/config/radialistas/{placeholder['id']}/programas", headers=auth_headers(account.id)
    ).json()
    assert len(todos_programas) == 1


def test_gerar_radialista_ia_com_radialista_ja_configurado_respeita_limite(client, account, auth_headers, monkeypatch):
    """Se o (unico) radialista da conta JA tem voz definida, ele nao e' um placeholder --
    gerar de novo tenta criar um segundo agente e deve respeitar o limite do plano normalmente."""
    configurado = _criar_radialista(client, auth_headers, account.id).json()
    client.put(
        f"/config/radialistas/{configurado['id']}",
        json={
            "nome_locutor": configurado["nome_locutor"],
            "personalidade": "",
            "voz_id": VOZES_DISPONIVEIS[0]["voz_id"],
            "timezone": "America/Sao_Paulo",
        },
        headers=auth_headers(account.id),
    )

    monkeypatch.setattr(
        "app.config.router.gerar_configuracao_ia",
        lambda descricao, tipo_radio=None, account=None, roster_existente=None: (
            {
                "nome_locutor": "IA Radialista",
                "personalidade": "animado",
                "voz_id": VOZES_DISPONIVEIS[0]["voz_id"],
                "timezone": "America/Sao_Paulo",
            },
            {"nome": "Programa IA", "tom": "animado", "horario_inicio": "08:00:00", "horario_fim": "10:00:00"},
        ),
    )
    resposta = client.post(
        "/config/radialistas/gerar-ia", json={"descricao": "radio animada"}, headers=auth_headers(account.id)
    )
    assert resposta.status_code == 402


def test_radialistas_do_programa_inclui_dono(client, account, auth_headers):
    radialista = _criar_radialista(client, auth_headers, account.id).json()
    programa = client.post(
        f"/config/radialistas/{radialista['id']}/programas",
        json=_programa_payload(),
        headers=auth_headers(account.id),
    ).json()

    resposta = client.get(
        f"/config/programas/{programa['id']}/radialistas", headers=auth_headers(account.id)
    )
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert len(corpo) == 1
    assert corpo[0]["e_dono"] is True


def test_adicionar_co_apresentador_ao_programa(client, account_factory, auth_headers):
    account = account_factory(email="growth@a.com", plano="growth")
    dono = _criar_radialista(client, auth_headers, account.id, nome="Dono").json()
    convidado = _criar_radialista(client, auth_headers, account.id, nome="Convidado").json()
    programa = client.post(
        f"/config/radialistas/{dono['id']}/programas",
        json=_programa_payload(),
        headers=auth_headers(account.id),
    ).json()

    resposta = client.put(
        f"/config/programas/{programa['id']}/radialistas/{convidado['id']}",
        json={"papel": "Comentarista", "comportamento": "sempre engracado"},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 200
    assert resposta.json()["papel"] == "Comentarista"

    roster = client.get(
        f"/config/programas/{programa['id']}/radialistas", headers=auth_headers(account.id)
    ).json()
    assert len(roster) == 2


def test_nao_pode_remover_dono_do_programa(client, account, auth_headers):
    radialista = _criar_radialista(client, auth_headers, account.id).json()
    programa = client.post(
        f"/config/radialistas/{radialista['id']}/programas",
        json=_programa_payload(),
        headers=auth_headers(account.id),
    ).json()

    resposta = client.delete(
        f"/config/programas/{programa['id']}/radialistas/{radialista['id']}",
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 400


def test_remover_co_apresentador_do_programa(client, account_factory, auth_headers):
    account = account_factory(email="growth@a.com", plano="growth")
    dono = _criar_radialista(client, auth_headers, account.id, nome="Dono").json()
    convidado = _criar_radialista(client, auth_headers, account.id, nome="Convidado").json()
    programa = client.post(
        f"/config/radialistas/{dono['id']}/programas",
        json=_programa_payload(),
        headers=auth_headers(account.id),
    ).json()
    client.put(
        f"/config/programas/{programa['id']}/radialistas/{convidado['id']}",
        json={"papel": "Comentarista", "comportamento": ""},
        headers=auth_headers(account.id),
    )

    resposta = client.delete(
        f"/config/programas/{programa['id']}/radialistas/{convidado['id']}",
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 204

    roster = client.get(
        f"/config/programas/{programa['id']}/radialistas", headers=auth_headers(account.id)
    ).json()
    assert len(roster) == 1


def test_limite_radialistas_por_programa_do_plano_starter(client, account, auth_headers):
    # starter permite so' 1 agente no total, entao nao ha nem como criar um segundo radialista
    # pra tentar adicionar como co-apresentador -- confirma que a criacao ja e' barrada antes.
    _criar_radialista(client, auth_headers, account.id, nome="Unico")
    segundo = _criar_radialista(client, auth_headers, account.id, nome="Segundo")
    assert segundo.status_code == 402


def test_perfil_musical_persiste_e_rejeita_valor_desconhecido(client, account, auth_headers):
    radialista = _criar_radialista(client, auth_headers, account.id).json()
    headers = auth_headers(account.id)
    criado = client.post(f"/config/radialistas/{radialista['id']}/programas",
                         json=_programa_payload(perfil_programacao="musical_companhia"), headers=headers)
    assert criado.status_code == 201
    url = f"/config/programas/{criado.json()['id']}"
    assert client.get(url, headers=headers).json()["perfil_programacao"] == "musical_companhia"
    invalido = client.put(url, json=_programa_payload(perfil_programacao="inexistente"), headers=headers)
    assert invalido.status_code == 422
    assert client.get(url, headers=headers).json()["perfil_programacao"] == "musical_companhia"
    padrao = client.put(url, json=_programa_payload(perfil_programacao="padrao"), headers=headers)
    assert padrao.json()["perfil_programacao"] == "padrao"
