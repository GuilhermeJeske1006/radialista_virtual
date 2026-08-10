
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


def test_gerar_radialista_ia(client, account, auth_headers, monkeypatch):
    monkeypatch.setattr(
        "app.config.router.gerar_configuracao_ia",
        lambda descricao: (
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


def test_gerar_radialista_ia_falha_do_llm_devolve_502(client, account, auth_headers, monkeypatch):
    def _falha(descricao):
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

    def _gerar(descricao):
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
