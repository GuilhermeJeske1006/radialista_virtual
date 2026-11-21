"""API de configuração do relógio da hora (F1): presets, PUT/DELETE /programas/{id}/relogio.

Casos A1-A8 de docs/melhoria-radio/f1/auditoria.md §6. O relógio fica fora de ProgramaRequest (D6):
nenhum caminho de escrita existente consegue apagá-lo.
"""

from app.live.relogio import PRESETS
from app.models.programa import Programa
from app.tts.voices import VOZES_DISPONIVEIS


def _programa_payload(**kwargs):
    padrao = dict(nome="Programa Teste", descricao="", dias_semana=[], horario_inicio="10:00:00",
                  horario_fim="12:00:00", ativo=True, tom="animado")
    return {**padrao, **kwargs}


def _criar_programa(client, auth_headers, account_id):
    radialista = client.post("/config/radialistas", json={"nome_locutor": "Zé", "personalidade": "",
                                                           "timezone": "America/Sao_Paulo"},
                             headers=auth_headers(account_id)).json()
    resposta = client.post(f"/config/radialistas/{radialista['id']}/programas", json=_programa_payload(),
                           headers=auth_headers(account_id))
    assert resposta.status_code == 201
    return radialista, resposta.json()


def _relogio_a():
    return PRESETS["A"].model_dump(mode="json")


def test_a1_presets_somam_uma_hora(client, account, auth_headers):
    resposta = client.get("/config/relogios/presets", headers=auth_headers(account.id))
    assert resposta.status_code == 200
    presets = resposta.json()
    assert [p["id"] for p in presets] == ["A", "B", "C"]
    for preset in presets:
        assert sum(e["duracao_s"] for e in preset["relogio"]["eventos"]) == 3600
        assert sum(preset["totais"].values()) == 3600
    assert presets[0]["totais"] == {"musica_s": 3015, "fala_s": 225, "intervalo_s": 360}


def test_a2_a6_a8_gravar_ler_e_remover(client, account, auth_headers):
    _, programa = _criar_programa(client, auth_headers, account.id)
    assert programa["relogio_hora"] is None  # A8: nasce sem relógio

    gravado = client.put(f"/config/programas/{programa['id']}/relogio", json=_relogio_a(),
                         headers=auth_headers(account.id))
    assert gravado.status_code == 200
    assert gravado.json()["relogio_hora"]["preset"] == "A"
    lido = client.get(f"/config/programas/{programa['id']}", headers=auth_headers(account.id)).json()
    assert len(lido["relogio_hora"]["eventos"]) == 12

    removido = client.delete(f"/config/programas/{programa['id']}/relogio", headers=auth_headers(account.id))
    assert removido.status_code == 200 and removido.json()["relogio_hora"] is None
    lido = client.get(f"/config/programas/{programa['id']}", headers=auth_headers(account.id)).json()
    assert lido["relogio_hora"] is None


def test_a3_relogio_invalido_da_422_em_portugues_e_nao_grava(client, account, auth_headers):
    _, programa = _criar_programa(client, auth_headers, account.id)
    relogio = _relogio_a()
    relogio["eventos"][-1]["duracao_s"] = 29
    resposta = client.put(f"/config/programas/{programa['id']}/relogio", json=relogio,
                          headers=auth_headers(account.id))
    assert resposta.status_code == 422
    assert "precisa somar exatamente 60:00" in resposta.json()["detail"]
    lido = client.get(f"/config/programas/{programa['id']}", headers=auth_headers(account.id)).json()
    assert lido["relogio_hora"] is None


def test_a4_put_do_programa_completo_preserva_o_relogio(client, account, auth_headers):
    _, programa = _criar_programa(client, auth_headers, account.id)
    client.put(f"/config/programas/{programa['id']}/relogio", json=_relogio_a(), headers=auth_headers(account.id))
    # Sem o campo e ecoando o campo (o painel devolve tudo o que veio no GET).
    sem_campo = client.put(f"/config/programas/{programa['id']}", json=_programa_payload(tom="sereno"),
                           headers=auth_headers(account.id))
    assert sem_campo.status_code == 200 and sem_campo.json()["relogio_hora"]["preset"] == "A"
    eco = {**sem_campo.json(), "relogio_hora": None, "tom": "alegre"}
    eco.pop("id"), eco.pop("radio_config_id")
    ecoado = client.put(f"/config/programas/{programa['id']}", json=eco, headers=auth_headers(account.id))
    assert ecoado.status_code == 200
    assert ecoado.json()["tom"] == "alegre" and ecoado.json()["relogio_hora"]["preset"] == "A"


def test_a5_commit_de_programa_gerado_por_ia_preserva_o_relogio(client, account, auth_headers, db_session):
    """O caminho que regrava o programa existente com setattr em laço (radialista placeholder)."""
    radialista, programa = _criar_programa(client, auth_headers, account.id)
    client.put(f"/config/programas/{programa['id']}/relogio", json=_relogio_a(), headers=auth_headers(account.id))
    resposta = client.post(
        "/config/radialistas/gerar-ia/commit",
        json={"radialista": {"nome_locutor": "IA", "personalidade": "", "voz_id": VOZES_DISPONIVEIS[0]["voz_id"],
                             "timezone": "America/Sao_Paulo"},
              "programa": _programa_payload(nome="Programa Refeito")},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 201, resposta.text
    assert resposta.json()["programa"]["id"] == programa["id"]
    db_session.expire_all()
    salvo = db_session.get(Programa, programa["id"])
    assert salvo.nome == "Programa Refeito" and salvo.relogio_hora["preset"] == "A"


def test_a7_programa_de_outra_conta_da_404(client, account, account_factory, auth_headers):
    _, programa = _criar_programa(client, auth_headers, account.id)
    outra = account_factory(email="outra@conta.com")
    for metodo in ("put", "delete"):
        kwargs = {"json": _relogio_a()} if metodo == "put" else {}
        resposta = getattr(client, metodo)(f"/config/programas/{programa['id']}/relogio",
                                           headers=auth_headers(outra.id), **kwargs)
        assert resposta.status_code == 404


def test_leitura_tolerante_de_relogio_invalido_no_banco(client, account, auth_headers, db_session):
    _, programa = _criar_programa(client, auth_headers, account.id)
    linha = db_session.get(Programa, programa["id"])
    linha.relogio_hora = {"eventos": [{"inicio_s": 0, "duracao_s": 5, "tipo": "musica", "natureza": "ajustavel"}]}
    db_session.commit()
    resposta = client.get(f"/config/programas/{programa['id']}", headers=auth_headers(account.id))
    assert resposta.status_code == 200 and resposta.json()["relogio_hora"] is None
