import json
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest

from app.config.redis_client import redis_client
from app.models.fonte_noticia import FonteNoticia
from app.models.programa import Programa
from app.models.radio_config import RadioConfig
from app.news import descoberta

URL = "https://jornal.example.com/cidade/noticia"
PERFIL = descoberta.PerfilFontes(
    nome="Jornal da manhã", descricao="Serviços e notícias locais", perfil="jornalismo",
    publico_alvo="Moradores da região", tipos_noticias=["trânsito"],
    topicos_permitidos=["educação"], topicos_proibidos=["fofoca"],
    instrucoes_pesquisa="Priorize fontes oficiais",
)


def _resposta(fontes=None, urls=None, stop_reason="end_turn"):
    return NS(stop_reason=stop_reason, content=[
        NS(type="web_search_tool_result", content=[NS(url=u) for u in (urls or [URL])]),
        NS(type="text", text=json.dumps({"fontes": fontes if fontes is not None else [
            {"nome": "Jornal local", "url": URL, "motivo": "Cobre serviços da cidade"},
        ]})),
    ])


def test_descoberta_considera_radio_cidade_publico_e_restricoes(account, monkeypatch):
    account.cidade, account.tipo_radio = "Blumenau, SC", "popular"
    chamada = Mock(return_value=_resposta())
    monkeypatch.setattr(descoberta, "criar_mensagem", chamada)
    resultado = descoberta.descobrir_fontes(PERFIL, account)
    assert resultado.status == "ok"
    assert resultado.fontes[0].dominio == "jornal.example.com"
    args = chamada.call_args.kwargs
    briefing = json.loads(args["messages"][0]["content"])
    assert briefing["radio"]["cidade"] == "Blumenau, SC"
    assert briefing["radio"]["tipo"] == "popular"
    assert briefing["programa"] == PERFIL.model_dump()
    assert args["tools"] == [{"type": "web_search_20250305", "name": "web_search", "max_uses": 3}]


def test_descoberta_descarta_url_inventada_ou_insegura_e_deduplica_dominio(account, monkeypatch):
    urls = [URL, "https://www.jornal.example.com/outra", "javascript:alert(1)", "https://user:senha@portal.com"]
    fontes = [{"nome": "Portal", "url": u, "motivo": "Local"} for u in [*urls, "https://inventado.com/feed"]]
    monkeypatch.setattr(descoberta, "criar_mensagem", Mock(return_value=_resposta(fontes, urls)))
    resultado = descoberta.descobrir_fontes(PERFIL, account)
    assert [f.url for f in resultado.fontes] == [URL]


def test_sem_busca_real_nao_aceita_sites_sugeridos_de_memoria(account, monkeypatch):
    resposta = _resposta()
    resposta.content = resposta.content[1:]
    monkeypatch.setattr(descoberta, "criar_mensagem", Mock(return_value=resposta))
    assert descoberta.descobrir_fontes(PERFIL, account).status == "sem_resultados"


def test_texto_introdutorio_antes_da_busca_nao_descarta_os_links(account, monkeypatch):
    resposta = _resposta()
    resposta.content.insert(0, NS(type="text", text="Vou pesquisar fontes para esse programa."))
    monkeypatch.setattr(descoberta, "criar_mensagem", Mock(return_value=resposta))
    resultado = descoberta.descobrir_fontes(PERFIL, account)
    assert resultado.status == "ok"
    assert resultado.fontes[0].url == URL


def _resposta_citada(url=URL):
    return NS(stop_reason="end_turn", content=[
        NS(type="text", text="Vou pesquisar fontes da região."),
        NS(type="web_search_tool_result", content=[NS(url=URL)]),
        NS(type="text", text="Jornal local — Cobre serviços públicos e notícias da cidade.", citations=[
            NS(type="web_search_result_location", url=url, title="Notícias da cidade"),
        ]),
    ])


def test_resposta_citada_sem_json_produz_fontes_confirmadas(account, monkeypatch):
    chamada = Mock(return_value=_resposta_citada())
    monkeypatch.setattr(descoberta, "criar_mensagem", chamada)
    resultado = descoberta.descobrir_fontes(PERFIL, account)
    assert resultado.status == "ok"
    assert resultado.fontes[0].model_dump() == {
        "nome": "Jornal local", "dominio": "jornal.example.com", "url": URL,
        "motivo": "Cobre serviços públicos e notícias da cidade.",
    }
    assert "Não escreva JSON" in chamada.call_args.kwargs["system"]


def test_citacao_inventada_fora_dos_resultados_nunca_vira_fonte(account, monkeypatch):
    monkeypatch.setattr(descoberta, "criar_mensagem", Mock(return_value=_resposta_citada("https://inventado.example.com")))
    assert descoberta.descobrir_fontes(PERFIL, account).fontes == []


def test_busca_parcial_com_limite_excedido_preserva_fontes_citadas(account, monkeypatch, caplog):
    resposta = _resposta_citada()
    resposta.content.insert(2, NS(type="web_search_tool_result", content=NS(error_code="max_uses_exceeded")))
    monkeypatch.setattr(descoberta, "criar_mensagem", Mock(return_value=resposta))
    with caplog.at_level("INFO", logger="radialista.news.descoberta"):
        resultado = descoberta.descobrir_fontes(PERFIL, account)
    assert resultado.status == "ok"
    assert resultado.fontes[0].url == URL
    assert "max_uses_exceeded" in caplog.text


def test_json_com_texto_antes_e_depois_nao_descarta_fontes(account, monkeypatch):
    resposta = _resposta()
    resposta.content[-1].text = "Sites encontrados:\n```json\n" + resposta.content[-1].text + "\n```\nConfira a seleção."
    monkeypatch.setattr(descoberta, "criar_mensagem", Mock(return_value=resposta))
    assert descoberta.descobrir_fontes(PERFIL, account).fontes[0].url == URL


def test_sem_fontes_confirmadas_nao_e_tratado_como_indisponibilidade(account, monkeypatch):
    resposta = _resposta_citada()
    resposta.content[-1] = NS(type="text", text="SEM_FONTES")
    monkeypatch.setattr(descoberta, "criar_mensagem", Mock(return_value=resposta))
    assert descoberta.descobrir_fontes(PERFIL, account).status == "sem_resultados"


def test_erro_da_ferramenta_com_http_200_tem_diagnostico_e_nao_inventa_fontes(account, monkeypatch, caplog):
    resposta = NS(stop_reason="end_turn", content=[
        NS(type="web_search_tool_result", content=NS(error_code="unavailable")),
        NS(type="text", text="A pesquisa não pôde ser concluída."),
    ])
    monkeypatch.setattr(descoberta, "criar_mensagem", Mock(return_value=resposta))
    with caplog.at_level("INFO", logger="radialista.news.descoberta"):
        resultado = descoberta.descobrir_fontes(PERFIL, account)
    assert resultado.status == "indisponivel"
    assert resultado.fontes == []
    assert "unavailable" in caplog.text


def test_continua_pause_turn_preservando_resultados(account, monkeypatch):
    primeira = _resposta(stop_reason="pause_turn")
    segunda = _resposta()
    segunda.content = segunda.content[1:]
    chamada = Mock(side_effect=[primeira, segunda])
    monkeypatch.setattr(descoberta, "criar_mensagem", chamada)
    assert descoberta.descobrir_fontes(PERFIL, account).fontes[0].url == URL
    assert chamada.call_count == 2
    assert chamada.call_args.kwargs["messages"][-1]["content"] == primeira.content


def test_cache_depende_de_perfil_cidade_e_conta(account, account_factory, monkeypatch):
    chamada = Mock(return_value=_resposta())
    monkeypatch.setattr(descoberta, "criar_mensagem", chamada)
    for _ in range(2):
        descoberta.descobrir_fontes(PERFIL, account)
    assert chamada.call_count == 1
    assert redis_client.ttl(redis_client.keys("fontes:descoberta:*")[0]) == 3600
    descoberta.descobrir_fontes(PERFIL.model_copy(update={"perfil": "esportivo"}), account)
    account.cidade = "Outra cidade"
    descoberta.descobrir_fontes(PERFIL, account)
    outra = account_factory(email="outra@example.com", cidade=account.cidade)
    descoberta.descobrir_fontes(PERFIL, outra)
    assert chamada.call_count == 4


def test_nova_tentativa_solicitada_no_painel_nao_reutiliza_falha_em_cache(client, account, auth_headers, monkeypatch):
    chamada = Mock(side_effect=[RuntimeError("rede"), _resposta_citada()])
    monkeypatch.setattr(descoberta, "criar_mensagem", chamada)
    headers = auth_headers(account.id)
    primeira = client.post("/config/programas/fontes/descobrir", json=PERFIL.model_dump(), headers=headers)
    assert primeira.json()["status"] == "indisponivel"
    segunda = client.post("/config/programas/fontes/descobrir", json={**PERFIL.model_dump(), "atualizar": True}, headers=headers)
    assert segunda.json()["status"] == "ok"
    assert segunda.json()["fontes"][0]["url"] == URL
    assert chamada.call_count == 2


def test_falha_na_atualizacao_preserva_fontes_confirmadas_sem_renovar_cache(account, monkeypatch):
    chamada = Mock(side_effect=[_resposta_citada(), RuntimeError("rede")])
    monkeypatch.setattr(descoberta, "criar_mensagem", chamada)
    primeira = descoberta.descobrir_fontes(PERFIL, account)
    chave = redis_client.keys("fontes:descoberta:*")[0]
    redis_client.expire(chave, 123)
    segunda = descoberta.descobrir_fontes(PERFIL, account, atualizar=True)
    assert segunda == primeira
    assert segunda.status == "ok"
    assert chamada.call_count == 2
    assert 0 < redis_client.ttl(chave) <= 123


@pytest.mark.parametrize("resposta", [RuntimeError("rede"), NS(stop_reason="end_turn", content=[NS(type="text", text="JSON inválido")])])
def test_falha_da_busca_e_tolerada_e_tem_cache_curto(account, monkeypatch, resposta):
    chamada = Mock(side_effect=resposta) if isinstance(resposta, Exception) else Mock(return_value=resposta)
    monkeypatch.setattr(descoberta, "criar_mensagem", chamada)
    for _ in range(2):
        assert descoberta.descobrir_fontes(PERFIL, account).status == "indisponivel"
    assert chamada.call_count == 1
    assert redis_client.ttl(redis_client.keys("fontes:descoberta:*")[0]) == 60


def test_descoberta_requer_login(client):
    assert client.post("/config/programas/fontes/descobrir", json=PERFIL.model_dump()).status_code == 401


def test_descoberta_nao_grava_antes_de_salvar_e_fontes_persistem_no_programa(
    client, account, auth_headers, db_session, monkeypatch,
):
    monkeypatch.setattr(descoberta, "criar_mensagem", Mock(return_value=_resposta()))
    headers = auth_headers(account.id)
    resposta = client.post("/config/programas/fontes/descobrir", json=PERFIL.model_dump(), headers=headers)
    assert resposta.status_code == 200
    assert db_session.query(Programa).count() == 0
    assert db_session.query(FonteNoticia).count() == 0
    radialista = RadioConfig(account_id=account.id)
    db_session.add(radialista)
    db_session.commit()
    urls = [f["url"] for f in resposta.json()["fontes"]]
    criado = client.post(f"/config/radialistas/{radialista.id}/programas", json={
        **PERFIL.model_dump(), "horario_inicio": "08:00", "horario_fim": "09:00", "tom": "informativo",
        "fontes_noticias": urls, "fontes_pesquisa": urls, "pode_pesquisar": True,
    }, headers=headers)
    assert criado.status_code == 201
    salvo = client.get(f'/config/programas/{criado.json()["id"]}', headers=headers).json()
    assert salvo["fontes_noticias"] == urls
    assert salvo["fontes_pesquisa"] == urls
    assert salvo["pode_pesquisar"] is True
    outro = client.post(f"/config/radialistas/{radialista.id}/programas", json={
        "nome": "Outro programa", "horario_inicio": "09:00", "horario_fim": "10:00", "tom": "leve",
        "fontes_noticias": ["https://outro.example.com/noticias"],
        "fontes_pesquisa": ["https://outro.example.com/agenda"],
    }, headers=headers)
    assert outro.status_code == 201
    reaberto = client.get(f'/config/programas/{criado.json()["id"]}', headers=headers).json()
    assert reaberto["fontes_noticias"] == reaberto["fontes_pesquisa"] == urls


@pytest.mark.parametrize("com_radialista,preview", [(False, False), (False, True), (True, False), (True, True)])
def test_geracao_ja_devolve_links_nos_dois_campos_e_os_vincula_ao_programa_e_radio(
    client, account, account_factory, auth_headers, db_session, monkeypatch, com_radialista, preview,
):
    programa_gerado = {**PERFIL.model_dump(), "tom": "informativo", "horario_inicio": "08:00", "horario_fim": "09:00"}
    radialista_gerado = {"nome_locutor": "Apresentador", "personalidade": "Informativo"}
    monkeypatch.setattr("app.config.router.gerar_configuracao_ia", lambda *args: (radialista_gerado, programa_gerado))
    monkeypatch.setattr("app.config.router.gerar_programa_ia", lambda *args: programa_gerado)
    chamada = Mock(return_value=_resposta())
    monkeypatch.setattr(descoberta, "criar_mensagem", chamada)
    headers = auth_headers(account.id)
    if com_radialista:
        path = "/config/radialistas/gerar-ia"
    else:
        radialista = RadioConfig(account_id=account.id, nome_locutor="Apresentador")
        db_session.add(radialista)
        db_session.commit()
        path = f"/config/radialistas/{radialista.id}/programas/gerar-ia"
    if preview:
        path += "/preview"
    resposta = client.post(path, json={"descricao": "Jornal local"}, headers=headers)
    assert resposta.status_code == (200 if preview else 201)
    corpo = resposta.json()
    programa = corpo["programa"] if preview or com_radialista else corpo
    assert programa["fontes_noticias"] == [URL]
    assert programa["fontes_pesquisa"] == [URL]
    assert programa["pode_pesquisar"] is True
    if preview:
        assert db_session.query(Programa).count() == 0
        if com_radialista:
            criado = client.post("/config/radialistas/gerar-ia/commit", json={
                "radialista": corpo["radialista"], "programa": programa,
            }, headers=headers)
            assert criado.status_code == 201
            programa = criado.json()["programa"]
        else:
            criado = client.post(f"/config/radialistas/{radialista.id}/programas", json=programa, headers=headers)
            assert criado.status_code == 201
            programa = criado.json()
    assert chamada.call_count == 1  # O salvamento não redescobre nem troca a seleção revisada.
    salvo = db_session.get(Programa, programa["id"])
    assert db_session.get(RadioConfig, salvo.radio_config_id).account_id == account.id
    assert salvo.fontes_noticias == salvo.fontes_pesquisa == [URL]
    reaberto = client.get(f"/config/programas/{salvo.id}", headers=headers).json()
    assert reaberto["fontes_noticias"] == reaberto["fontes_pesquisa"] == [URL]
    outra = account_factory(email="outra-radio@example.com")
    outros_headers = auth_headers(outra.id)
    assert client.get(f"/config/programas/{salvo.id}", headers=outros_headers).status_code == 404
    assert client.put(f"/config/programas/{salvo.id}", json=programa, headers=outros_headers).status_code == 404
    assert client.get("/config/programas", headers=outros_headers).json() == []


def test_geracao_sem_noticias_traz_links_para_pesquisa_externa(account, monkeypatch):
    from app.config.router import ProgramaRequest

    programa = ProgramaRequest(nome="Cultura", tom="leve", horario_inicio="08:00", horario_fim="09:00", dose_noticia="nenhuma")
    monkeypatch.setattr(descoberta, "criar_mensagem", Mock(return_value=_resposta()))
    resultado = descoberta.preencher_fontes_programa(programa, account)
    assert resultado.fontes_noticias == []
    assert resultado.fontes_pesquisa == [URL]
    assert resultado.pode_pesquisar is True


def test_rate_limit_e_isolado_por_conta(client, account, account_factory, auth_headers, monkeypatch):
    chamada = Mock(return_value=descoberta.DescobertaFontes(status="sem_resultados"))
    monkeypatch.setattr("app.config.router.descobrir_fontes", chamada)
    for _ in range(30):
        assert client.post("/config/programas/fontes/descobrir", json=PERFIL.model_dump(), headers=auth_headers(account.id)).status_code == 200
    assert client.post("/config/programas/fontes/descobrir", json=PERFIL.model_dump(), headers=auth_headers(account.id)).status_code == 429
    outra = account_factory(email="outra@example.com")
    assert client.post("/config/programas/fontes/descobrir", json=PERFIL.model_dump(), headers=auth_headers(outra.id)).status_code == 200
    assert chamada.call_count == 31
