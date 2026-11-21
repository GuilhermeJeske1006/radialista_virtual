"""Peças de reserva aprovadas (F11 item 3): aprovação explícita, desaprovação ao editar, escolha sem repetir."""

import pytest

from app.live.pecas_reserva import TIPOS_CONTINGENCIA, aprovar, escolher_reserva, normalizar_pecas
from tests.test_config_relogio import _criar_programa


def test_peca_nova_nasce_nao_aprovada():
    pecas = normalizar_pecas([{"tipo": "convidado", "texto": "O convidado não pôde vir; seguimos com a música."}])
    assert pecas[0]["aprovada"] is False
    assert pecas[0]["id"] == 1


def test_tipo_fora_do_contrato_recusado():
    with pytest.raises(ValueError):
        normalizar_pecas([{"tipo": "outro", "texto": "x"}])


def test_peca_sem_texto_recusada():
    with pytest.raises(ValueError):
        normalizar_pecas([{"tipo": "fonte", "texto": "   "}])


def test_editar_texto_desaprova_a_peca():
    atuais = [{"id": 1, "tipo": "fonte", "texto": "Texto antigo.", "aprovada": True}]
    trocadas = normalizar_pecas([{"id": 1, "tipo": "fonte", "texto": "Texto novo."}], atuais=atuais)
    assert trocadas[0]["aprovada"] is False


def test_manter_texto_preserva_aprovacao():
    atuais = [{"id": 1, "tipo": "fonte", "texto": "Mesmo texto.", "aprovada": True}]
    mantidas = normalizar_pecas([{"id": 1, "tipo": "fonte", "texto": "Mesmo texto."}], atuais=atuais)
    assert mantidas[0]["aprovada"] is True


def test_aprovar_marca_so_a_peca_pedida():
    pecas = normalizar_pecas([{"tipo": "audio", "texto": "a"}, {"tipo": "audio", "texto": "b"}])
    aprovar(pecas, 2)
    assert [p["aprovada"] for p in pecas] == [False, True]
    assert aprovar(pecas, 99) is None


def test_escolher_so_entre_aprovadas_do_tipo_e_sem_repetir():
    pecas = normalizar_pecas([
        {"tipo": "estouro", "texto": "1"}, {"tipo": "estouro", "texto": "2"}, {"tipo": "fonte", "texto": "3"},
    ])
    aprovar(pecas, 1)
    aprovar(pecas, 2)
    aprovar(pecas, 3)
    assert escolher_reserva(pecas, "estouro")["id"] == 1
    assert escolher_reserva(pecas, "estouro", ja_usadas={1})["id"] == 2
    assert escolher_reserva(pecas, "estouro", ja_usadas={1, 2}) is None


def test_sem_peca_aprovada_nao_ha_reserva():
    pecas = normalizar_pecas([{"tipo": "convidado", "texto": "x"}])
    assert escolher_reserva(pecas, "convidado") is None


def test_todos_os_tipos_de_contingencia_existem():
    assert TIPOS_CONTINGENCIA == ("convidado", "fonte", "pedido", "audio", "estouro")


def test_api_salva_aprova_e_lista(client, account, auth_headers):
    _, programa = _criar_programa(client, auth_headers, account.id)
    url = f"/config/programas/{programa['id']}/pecas-reserva"
    salvo = client.put(url, json=[{"tipo": "convidado", "texto": "Seguimos sem o convidado."}],
                       headers=auth_headers(account.id))
    assert salvo.status_code == 200
    peca_id = salvo.json()[0]["id"]
    aprovado = client.post(f"{url}/{peca_id}/aprovar", headers=auth_headers(account.id))
    assert aprovado.status_code == 200
    assert aprovado.json()["aprovada"] is True
    lido = client.get(url, headers=auth_headers(account.id)).json()
    assert lido[0]["aprovada"] is True


def test_api_aprovar_peca_inexistente_404(client, account, auth_headers):
    _, programa = _criar_programa(client, auth_headers, account.id)
    resposta = client.post(f"/config/programas/{programa['id']}/pecas-reserva/99/aprovar",
                           headers=auth_headers(account.id))
    assert resposta.status_code == 404


def test_api_tipo_invalido_400(client, account, auth_headers):
    _, programa = _criar_programa(client, auth_headers, account.id)
    resposta = client.put(f"/config/programas/{programa['id']}/pecas-reserva",
                          json=[{"tipo": "xyz", "texto": "x"}], headers=auth_headers(account.id))
    assert resposta.status_code == 400
