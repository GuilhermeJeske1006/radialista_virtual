"""Contrato do formato do programa e gerador por IA (F6, I8, I10 e U12 da auditoria §8; D14, D15).

- `ProgramaRequest.perfil_programacao` aceita `padrao`, os ids implementados e os aliases; o resto é 422 em
  português. A resposta ecoa o valor gravado (o alias continua alias) e não valida: um valor fora do catálogo
  gravado direto no banco não derruba a leitura.
- `GET /config/formatos` lista o catálogo, inclusive os formatos ainda não implementados.
- O gerador por IA oferece os formatos implementados; formato futuro ou inventado vira `padrao` com o campo em
  `campos_corrigidos`. Nenhuma chamada real ao LLM: as funções do gerador são trocadas por nome.
"""

import pytest

from app.live.formatos import FORMATOS
from app.tts.voices import VOZES_DISPONIVEIS

IMPLEMENTADOS = [chave for chave, formato in FORMATOS.items() if formato.implementado]
ACEITOS = [*IMPLEMENTADOS, *(a for chave in IMPLEMENTADOS for a in FORMATOS[chave].aliases)]
CAMPOS_FORMATO = {"id", "nome", "promessa", "conteudo", "conducao", "unidade_principal", "roteiro_padrao",
                  "relogio_padrao", "ia_pode_adicionar_blocos", "participacao", "temas_revisao", "reorientacao_s",
                  "aliases", "implementado", "requer"}


def _payload(**kwargs):
    padrao = dict(nome="Programa Teste", descricao="", dias_semana=[], horario_inicio="10:00:00",
                  horario_fim="12:00:00", ativo=True, tom="animado")
    padrao.update(kwargs)
    return padrao


@pytest.fixture
def programa_url(client, account, auth_headers):
    headers = auth_headers(account.id)
    radialista = client.post("/config/radialistas", json={"nome_locutor": "Caio Ventania", "personalidade": "",
                                                          "timezone": "America/Sao_Paulo"}, headers=headers).json()
    criado = client.post(f"/config/radialistas/{radialista['id']}/programas", json=_payload(), headers=headers)
    assert criado.status_code == 201
    return f"/config/programas/{criado.json()['id']}", headers


# ---------------------------------------------------------------------------------------------------------
# I8: contrato
# ---------------------------------------------------------------------------------------------------------

def test_i8_aceitos_sao_os_implementados_e_os_aliases():
    assert set(ACEITOS) == {"padrao", "musical_adulto", "musical_companhia", "popular_sertanejo", "variedades_leves"}


@pytest.mark.parametrize("valor", ACEITOS)
def test_i8_put_e_get_ecoam_o_valor_gravado(client, programa_url, valor):
    url, headers = programa_url
    resposta = client.put(url, json=_payload(perfil_programacao=valor), headers=headers)
    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["perfil_programacao"] == valor
    assert client.get(url, headers=headers).json()["perfil_programacao"] == valor


@pytest.mark.parametrize("valor", ["hits", "jornalistico", "inexistente", "MUSICAL_ADULTO", ""])
def test_i8_formato_futuro_ou_desconhecido_da_422_em_portugues(client, programa_url, valor):
    url, headers = programa_url
    client.put(url, json=_payload(perfil_programacao="musical_companhia"), headers=headers)
    resposta = client.put(url, json=_payload(perfil_programacao=valor), headers=headers)
    assert resposta.status_code == 422
    mensagens = [erro["msg"] for erro in resposta.json()["detail"]]
    assert any(m.startswith("Formato desconhecido ou ainda não disponível") for m in mensagens), mensagens
    assert client.get(url, headers=headers).json()["perfil_programacao"] == "musical_companhia"


def test_i8_post_sem_o_campo_cria_padrao(client, account, auth_headers):
    headers = auth_headers(account.id)
    radialista = client.post("/config/radialistas", json={"nome_locutor": "Lia Serena", "personalidade": "",
                                                          "timezone": "America/Sao_Paulo"}, headers=headers).json()
    criado = client.post(f"/config/radialistas/{radialista['id']}/programas", json=_payload(), headers=headers)
    assert criado.json()["perfil_programacao"] == "padrao"


def test_i8_rota_de_formatos_lista_o_catalogo(client, account, auth_headers):
    assert client.get("/config/formatos").status_code == 401
    resposta = client.get("/config/formatos", headers=auth_headers(account.id))
    assert resposta.status_code == 200
    formatos = {f["id"]: f for f in resposta.json()}
    assert list(formatos) == list(FORMATOS)
    for formato in formatos.values():
        assert set(formato) == CAMPOS_FORMATO
    assert {chave for chave, f in formatos.items() if f["implementado"]} == set(IMPLEMENTADOS)
    musical = formatos["musical_adulto"]
    assert musical["aliases"] == ["musical_companhia"] and musical["relogio_padrao"] == "A"
    assert musical["ia_pode_adicionar_blocos"] is False and musical["reorientacao_s"] == 900
    assert musical["roteiro_padrao"] == list(FORMATOS["musical_adulto"].roteiro_padrao)
    assert formatos["padrao"]["ia_pode_adicionar_blocos"] is True
    popular, variedades = formatos["popular_sertanejo"], formatos["variedades_leves"]
    assert (popular["relogio_padrao"], popular["reorientacao_s"], popular["implementado"]) == ("A", 1200, True)
    assert (variedades["relogio_padrao"], variedades["reorientacao_s"], variedades["implementado"]) == ("C", 900, True)
    assert popular["ia_pode_adicionar_blocos"] is True and variedades["ia_pode_adicionar_blocos"] is True
    assert "F5" in formatos["jornalistico"]["requer"] and formatos["jornalistico"]["implementado"] is False


# ---------------------------------------------------------------------------------------------------------
# I10: leitura tolerante (o validador da requisição não vale na resposta)
# ---------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("gravado", ["hits", "valor_de_outra_versao"])
def test_i10_valor_fora_do_catalogo_no_banco_responde_200(client, db_session, programa_url, gravado):
    from app.models.programa import Programa

    url, headers = programa_url
    programa = db_session.get(Programa, int(url.rsplit("/", 1)[1]))
    programa.perfil_programacao = gravado
    db_session.commit()
    lista = client.get("/config/programas", headers=headers)
    assert lista.status_code == 200
    assert [p["perfil_programacao"] for p in lista.json()] == [gravado]
    assert client.get(url, headers=headers).json()["perfil_programacao"] == gravado


# ---------------------------------------------------------------------------------------------------------
# U12: gerador por IA
# ---------------------------------------------------------------------------------------------------------

def test_u12_prompt_do_gerador_lista_os_formatos_implementados():
    from app.llm import config_generator as g

    prompts = [g._montar_system_prompt_completo(), g._montar_system_prompt_programa("Caio", "calmo"),
               g._montar_system_prompt_ajuste_programa(), g._montar_system_prompt_ajuste_completo()]
    for prompt in prompts:
        assert ('"perfil_programacao": "padrao" ou "musical_adulto" ou "popular_sertanejo" ou "variedades_leves"'
                in prompt)
        for chave in IMPLEMENTADOS:
            assert f"'{chave}'" in prompt, chave
        assert "musical_companhia" not in prompt
        for futuro in ("'hits'", "'noturno'", "'jornalistico'", "'morning'"):
            assert futuro not in prompt
    assert set(g._USO_FORMATO_NO_GERADOR) == set(IMPLEMENTADOS)


def test_u12_tipo_radio_sugere_o_formato_como_dica():
    from app.llm import config_generator as g

    assert "Formato sugerido para este tipo de rádio (dica, não regra): 'musical_adulto'" in \
        g._montar_system_prompt_completo(tipo_radio="mpb_variedades")
    assert "Formato sugerido" not in g._montar_system_prompt_completo(tipo_radio="jornalismo_noticia")
    for tipo_radio in ("sertaneja", "popular_mix"):
        assert "Formato sugerido para este tipo de rádio (dica, não regra): 'popular_sertanejo'" in \
            g._montar_system_prompt_completo(tipo_radio=tipo_radio)
    for chave in g._FORMATO_SUGERIDO_POR_TIPO_RADIO.values():
        assert FORMATOS[chave].implementado


def _gerar(monkeypatch, perfil_programacao):
    def gerar(descricao, tipo_radio=None, account=None, roster_existente=None):
        return ({"nome_locutor": "Caio Ventania", "personalidade": "calmo", "voz_id": VOZES_DISPONIVEIS[0]["voz_id"],
                 "timezone": "America/Sao_Paulo"},
                {"nome": "Tarde Serena", "tom": "calmo", "horario_inicio": "14:00:00", "horario_fim": "16:00:00",
                 "perfil_programacao": perfil_programacao})

    def reparo_falha(*args, **kwargs):
        raise ValueError("reparo indisponível no teste")

    monkeypatch.setattr("app.config.router.gerar_configuracao_ia", gerar)
    monkeypatch.setattr("app.config.router.reparar_configuracao_ia", reparo_falha)


def test_u12_uso_de_cada_formato_no_gerador():
    from app.llm import config_generator as g

    assert "jornalismo" in g._USO_FORMATO_NO_GERADOR["padrao"] and "variedades" not in g._USO_FORMATO_NO_GERADOR["padrao"]
    assert "recados" in g._USO_FORMATO_NO_GERADOR["popular_sertanejo"]
    assert "quadro fixo" in g._USO_FORMATO_NO_GERADOR["variedades_leves"]


def test_u12_exemplo_sertanejo_usa_o_formato_popular():
    from app.llm.exemplos_config import _EXEMPLOS

    formatos = {e["saida"]["nome"]: e["saida"]["perfil_programacao"] for e in _EXEMPLOS}
    # Sertanejo vira popular; o radiojornal e o noturno continuam padrao (ainda sem formato próprio, D13).
    assert formatos == {"Trilha da Madrugada": "popular_sertanejo", "Jornal do Meio-Dia": "padrao",
                        "Boa Noite, Coracao": "padrao"}
    for exemplo in _EXEMPLOS:
        assert exemplo["saida"]["perfil_programacao"] in FORMATOS and \
            FORMATOS[exemplo["saida"]["perfil_programacao"]].implementado


@pytest.mark.parametrize("valor", ["musical_companhia", "musical_adulto", "popular_sertanejo", "variedades_leves"])
def test_u12_llm_devolvendo_formato_aceito_grava_sem_correcao(client, account, auth_headers, monkeypatch, valor):
    _gerar(monkeypatch, valor)
    resposta = client.post("/config/radialistas/gerar-ia/preview", json={"descricao": "tarde musical calma"},
                           headers=auth_headers(account.id))
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["programa"]["perfil_programacao"] == valor and corpo["campos_corrigidos"] == []


@pytest.mark.parametrize("valor", ["hits", "sertanejo_raiz"])
def test_u12_formato_futuro_ou_inventado_vira_padrao_marcado(client, account, auth_headers, monkeypatch, valor):
    _gerar(monkeypatch, valor)
    resposta = client.post("/config/radialistas/gerar-ia/preview", json={"descricao": "tarde musical calma"},
                           headers=auth_headers(account.id))
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["programa"]["perfil_programacao"] == "padrao"
    assert "perfil_programacao" in corpo["campos_corrigidos"]


def test_i8_commit_de_programa_gerado_com_formato_canonico(client, account, auth_headers):
    resposta = client.post(
        "/config/radialistas/gerar-ia/commit",
        json={"radialista": {"nome_locutor": "Caio Ventania", "personalidade": "calmo",
                             "voz_id": VOZES_DISPONIVEIS[0]["voz_id"], "timezone": "America/Sao_Paulo"},
              "programa": _payload(nome="Tarde Serena", perfil_programacao="musical_adulto")},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 201, resposta.text
    programas = client.get("/config/programas", headers=auth_headers(account.id)).json()
    assert [p["perfil_programacao"] for p in programas] == ["musical_adulto"]
