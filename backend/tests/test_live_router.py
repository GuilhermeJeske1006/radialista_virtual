import datetime
import json

import httpx
import pytest
from freezegun import freeze_time

from app.live.music import MusicaEncontrada, _titulo_normalizado
from app.live.router import (
    _aberturas_e_fechamentos,
    _categoria_bloco,
    _escolher_query_musica,
    _primeira_frase,
    _registrar_fala_gerada,
    _registrar_historico_persistente,
    _ultima_frase,
    _tom_sintese_do_bloco,
)
from app.models.biblioteca_audio import BibliotecaAudioItem
from app.models.fila_ao_vivo import FilaAoVivo
from app.models.musica import Musica
from app.models.musica_historico import MusicaHistorico
from app.models.patrocinador import Patrocinador
from app.models.programa import Programa
from app.models.programa_radialista import ProgramaRadialista
from app.models.radio_config import RadioConfig
from app.models.tema_historico import TemaHistorico

AGORA_UTC = "2026-08-10 15:00:00"  # 12:00 local, dentro de um programa 10:00-14:00


@pytest.fixture()
def radialista_e_programa(db_session, account):
    radio_config = RadioConfig(account_id=account.id, timezone="America/Sao_Paulo")
    db_session.add(radio_config)
    db_session.commit()
    programa = Programa(
        radio_config_id=radio_config.id,
        nome="Programa Principal",
        horario_inicio=datetime.time(10, 0),
        horario_fim=datetime.time(14, 0),
        estrutura_blocos=[],
    )
    db_session.add(programa)
    db_session.commit()
    db_session.refresh(radio_config)
    db_session.refresh(programa)
    return radio_config, programa


def _url_proxima(radialista_id, programa_id):
    return f"/live/{radialista_id}/programas/{programa_id}/proxima"


@pytest.mark.parametrize("bloco", [
    "noticia_local", "noticia_brasil", "Notícia regional", "agenda cultural", "boletim regional",
])
def test_bloco_jornalistico_reconhecido_sem_classificacao_remota(monkeypatch, bloco):
    def nao_classificar(*args):
        raise AssertionError("Bloco jornalístico conhecido não precisa de classificação remota")
    monkeypatch.setattr("app.live.router.classificar_categoria_bloco", nao_classificar)
    assert _categoria_bloco(bloco) == "noticia"


@pytest.mark.parametrize("bloco", ["manchetes", "manchete", "Manchetes do dia"])
def test_bloco_de_manchete_reconhecido_como_escalada(monkeypatch, bloco):
    monkeypatch.setattr(
        "app.live.router.classificar_categoria_bloco",
        lambda *a: (_ for _ in ()).throw(AssertionError("não precisa de classificação remota")),
    )
    assert _categoria_bloco(bloco) == "escalada"


@pytest.mark.parametrize("bloco", ["giro", "giro de noticias", "giro_rapido"])
def test_bloco_de_giro_reconhecido_como_giro(monkeypatch, bloco):
    monkeypatch.setattr(
        "app.live.router.classificar_categoria_bloco",
        lambda *a: (_ for _ in ()).throw(AssertionError("não precisa de classificação remota")),
    )
    assert _categoria_bloco(bloco) == "giro"


@pytest.mark.parametrize("bloco", ["tempo_e_transito", "previsao do tempo", "utilidade_publica", "cotações"])
def test_bloco_de_utilidade_publica_reconhecido_como_servico(monkeypatch, bloco):
    monkeypatch.setattr(
        "app.live.router.classificar_categoria_bloco",
        lambda *a: (_ for _ in ()).throw(AssertionError("não precisa de classificação remota")),
    )
    assert _categoria_bloco(bloco) == "servico"


@pytest.mark.parametrize("bloco", ["plantao", "plantao_urgente"])
def test_bloco_de_plantao_reconhecido_como_plantao(monkeypatch, bloco):
    monkeypatch.setattr(
        "app.live.router.classificar_categoria_bloco",
        lambda *a: (_ for _ in ()).throw(AssertionError("não precisa de classificação remota")),
    )
    assert _categoria_bloco(bloco) == "plantao"


@freeze_time(AGORA_UTC)
def test_bloco_jornalistico_explicito_com_pesquisa_desligada_informa_status(
    client, account, auth_headers, radialista_e_programa, db_session, monkeypatch
):
    radialista, programa = radialista_e_programa
    programa.estrutura_blocos = ["noticia_local"]
    programa.ia_pode_adicionar_blocos = False
    db_session.commit()
    prompts = []
    monkeypatch.setattr("app.live.router.gerar_resposta", lambda system, msg: prompts.append(system) or "Seguimos no ar.")
    resposta = client.post(
        _url_proxima(radialista.id, programa.id), json={"total_falas": 1, "incluir_audio": False},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 200
    assert resposta.json()["tipo"] == "noticia_local"
    assert resposta.json()["pesquisa_noticias"]["status"] == "desabilitada"
    assert "Não há notícias verificadas" in prompts[0]


@pytest.mark.parametrize("dupla", [False, True])
@freeze_time(AGORA_UTC)
def test_noticia_pesquisada_chega_a_locucao_e_retorna_fontes(
    client, account, auth_headers, radialista_e_programa, db_session, monkeypatch, dupla
):
    from app.llm.noticias import FonteNoticia, PesquisaNoticias

    radialista, programa = radialista_e_programa
    programa.pode_pesquisar = True
    programa.estrutura_blocos = ["noticia"]
    programa.ia_pode_adicionar_blocos = False
    if dupla:
        convidado = RadioConfig(account_id=account.id, nome_locutor="Maria")
        db_session.add(convidado)
        db_session.flush()
        db_session.add(ProgramaRadialista(programa_id=programa.id, radio_config_id=convidado.id))
    db_session.commit()

    apuracao = PesquisaNoticias(
        status="ok", texto="Prefeitura anunciou nova escola nesta segunda-feira.",
        fontes=[FonteNoticia(titulo="Jornal da Cidade", url="https://jornal.example.com/escola")],
        consultado_em=datetime.datetime.now(datetime.timezone.utc),
    )
    consultas = []
    def pesquisar(p, a, **kwargs):
        consultas.append((p.id, a.id, kwargs))
        return apuracao
    monkeypatch.setattr("app.live.router.pesquisar_noticias", pesquisar)
    prompts = []
    fala = "Segundo o Jornal da Cidade, a prefeitura anunciou uma nova escola."
    monkeypatch.setattr("app.live.router.gerar_resposta", lambda system, msg: prompts.append(system) or fala)
    monkeypatch.setattr(
        "app.live.router.gerar_configuracao",
        lambda system, msg: prompts.append(system) or json.dumps({"linhas": [
            {"locutor": radialista.nome_locutor, "texto": fala},
            {"locutor": "Maria", "texto": "A medida amplia o acesso à educação."},
        ]}),
    )
    resposta = client.post(
        _url_proxima(radialista.id, programa.id),
        json={"historico": [], "total_falas": 1, "incluir_audio": False},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 200
    assert len(consultas) == 1
    assert consultas[0][:2] == (programa.id, account.id)
    assert "APURAÇÃO JORNALÍSTICA" in prompts[0]
    assert apuracao.texto in prompts[0]
    assert "em vez de forçar a notícia pesada" not in prompts[0]
    assert resposta.json()["pesquisa_noticias"]["fontes"][0]["url"] == apuracao.fontes[0].url
    assert bool(resposta.json()["falas"]) == dupla


@freeze_time(AGORA_UTC)
def test_gerar_proxima_fala_primeira_e_abertura(client, account, auth_headers, radialista_e_programa, monkeypatch):
    radio_config, programa = radialista_e_programa
    monkeypatch.setattr("app.live.router.gerar_resposta", lambda system, msg: "E ai galera, tudo bem?")

    resposta = client.post(
        _url_proxima(radio_config.id, programa.id),
        json={"historico": [], "total_falas": 0},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["tipo"] == "abertura"
    assert corpo["fala"] == "E ai galera, tudo bem?"
    assert corpo["programa_atual"] == "Programa Principal"


@freeze_time(AGORA_UTC)
def test_gerar_proxima_fala_radialista_inexistente_404(client, account, auth_headers, radialista_e_programa):
    _, programa = radialista_e_programa
    resposta = client.post(
        _url_proxima(999999, programa.id), json={"historico": []}, headers=auth_headers(account.id)
    )
    assert resposta.status_code == 404


@freeze_time(AGORA_UTC)
def test_gerar_proxima_fala_programa_inexistente_404(client, account, auth_headers, radialista_e_programa):
    radio_config, _ = radialista_e_programa
    resposta = client.post(
        _url_proxima(radio_config.id, 999999), json={"historico": []}, headers=auth_headers(account.id)
    )
    assert resposta.status_code == 404


@freeze_time(AGORA_UTC)
def test_gerar_proxima_fala_bloco_musica_inclui_dados_da_musica(
    client, account, auth_headers, radialista_e_programa, monkeypatch
):
    radio_config, programa = radialista_e_programa
    monkeypatch.setattr("app.live.router.gerar_resposta", lambda system, msg: "Vamos ouvir essa!")
    monkeypatch.setattr(
        "app.live.router.buscar_musica",
        lambda query, **kwargs: MusicaEncontrada(video_id="abc123", titulo="Musica Teste", canal="Canal Teste"),
    )

    # total_falas=1 -> proximo bloco do roteiro padrao apos abertura(0) e' "musica" (indice 0 do roteiro).
    resposta = client.post(
        _url_proxima(radio_config.id, programa.id),
        json={"historico": ["abertura: oi"], "total_falas": 1},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["tipo"] == "musica"
    assert corpo["video_id"] == "abc123"
    assert corpo["titulo_musica"] == "Musica Teste"


@freeze_time(AGORA_UTC)
def test_gerar_proxima_fala_patrocinador_nao_passa_pelo_llm(
    client, account, auth_headers, radialista_e_programa, db_session, monkeypatch
):
    radio_config, programa = radialista_e_programa
    patrocinador = Patrocinador(account_id=account.id, nome="Loja X", tipo_conteudo="texto", texto="Visite a loja X!")
    db_session.add(patrocinador)
    db_session.flush()
    programa.estrutura_blocos = [f"patrocinador:{patrocinador.id}"]
    db_session.commit()

    chamou_llm = []
    monkeypatch.setattr(
        "app.live.router.gerar_resposta", lambda system, msg: chamou_llm.append(1) or "nunca deveria chegar aqui"
    )

    resposta = client.post(
        _url_proxima(radio_config.id, programa.id),
        json={"historico": [], "total_falas": 0},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["tipo"] == "patrocinador"
    assert corpo["fala"] == "Visite a loja X!"
    assert corpo["patrocinador_id"] == patrocinador.id
    assert chamou_llm == []


@freeze_time(AGORA_UTC)
def test_gerar_proxima_fala_patrocinador_desativado_cai_para_comentario(
    client, account, auth_headers, radialista_e_programa, db_session, monkeypatch
):
    radio_config, programa = radialista_e_programa
    patrocinador = Patrocinador(
        account_id=account.id, nome="Loja X", tipo_conteudo="texto", texto="Visite!", ativo=False
    )
    db_session.add(patrocinador)
    db_session.flush()
    programa.estrutura_blocos = [f"patrocinador:{patrocinador.id}"]
    db_session.commit()

    monkeypatch.setattr("app.live.router.gerar_resposta", lambda system, msg: "comentario generico")

    resposta = client.post(
        _url_proxima(radio_config.id, programa.id),
        json={"historico": [], "total_falas": 0},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 200
    assert resposta.json()["tipo"] == "comentario"


@freeze_time(AGORA_UTC)
def test_gerar_proxima_fala_vinheta_nao_passa_pelo_llm(
    client, account, auth_headers, radialista_e_programa, db_session, monkeypatch
):
    radio_config, programa = radialista_e_programa
    vinheta = BibliotecaAudioItem(
        account_id=account.id, nome="Vinheta QA", audio_path="biblioteca_audio/1/x.mp3", audio_nome_original="x.mp3"
    )
    db_session.add(vinheta)
    db_session.flush()
    programa.estrutura_blocos = [f"vinheta:{vinheta.id}"]
    db_session.commit()

    chamou_llm = []
    monkeypatch.setattr(
        "app.live.router.gerar_resposta", lambda system, msg: chamou_llm.append(1) or "nunca deveria chegar aqui"
    )

    resposta = client.post(
        _url_proxima(radio_config.id, programa.id),
        json={"historico": [], "total_falas": 0},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["tipo"] == "vinheta"
    assert corpo["fala"] == ""
    assert corpo["vinheta_id"] == vinheta.id
    assert chamou_llm == []


@freeze_time(AGORA_UTC)
def test_gerar_proxima_fala_vinheta_desativada_cai_para_comentario(
    client, account, auth_headers, radialista_e_programa, db_session, monkeypatch
):
    radio_config, programa = radialista_e_programa
    vinheta = BibliotecaAudioItem(
        account_id=account.id,
        nome="Vinheta QA",
        audio_path="biblioteca_audio/1/x.mp3",
        audio_nome_original="x.mp3",
        ativo=False,
    )
    db_session.add(vinheta)
    db_session.flush()
    programa.estrutura_blocos = [f"vinheta:{vinheta.id}"]
    db_session.commit()

    monkeypatch.setattr("app.live.router.gerar_resposta", lambda system, msg: "comentario generico")

    resposta = client.post(
        _url_proxima(radio_config.id, programa.id),
        json={"historico": [], "total_falas": 0},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 200
    assert resposta.json()["tipo"] == "comentario"


@freeze_time("2026-08-10 16:58:00")  # 13:58 local -- 2 min antes do fim (14:00)
def test_gerar_proxima_fala_perto_do_fim_vira_encerramento(
    client, account, auth_headers, radialista_e_programa, monkeypatch
):
    radio_config, programa = radialista_e_programa
    monkeypatch.setattr("app.live.router.gerar_resposta", lambda system, msg: "Foi um prazer, ate mais!")

    resposta = client.post(
        _url_proxima(radio_config.id, programa.id),
        json={"historico": [], "total_falas": 3},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 200
    assert resposta.json()["tipo"] == "encerramento"


@freeze_time(AGORA_UTC)
def test_gerar_proxima_fala_multi_voz_gera_dialogo(
    client, account_factory, auth_headers, db_session, monkeypatch
):
    account = account_factory(email="growth@a.com", plano="growth")
    dono = RadioConfig(account_id=account.id, nome_locutor="Ze", timezone="America/Sao_Paulo")
    convidado = RadioConfig(account_id=account.id, nome_locutor="Maria", timezone="America/Sao_Paulo")
    db_session.add_all([dono, convidado])
    db_session.commit()

    programa = Programa(
        radio_config_id=dono.id,
        nome="Programa Duplo",
        horario_inicio=datetime.time(10, 0),
        horario_fim=datetime.time(14, 0),
    )
    db_session.add(programa)
    db_session.commit()
    db_session.add(ProgramaRadialista(programa_id=programa.id, radio_config_id=convidado.id))
    db_session.commit()

    resposta_llm = json.dumps(
        {
            "linhas": [
                {"locutor": "Ze", "texto": "E ai Maria, bora comecar o programa?"},
                {"locutor": "Maria", "texto": "Bora sim, ja to na sintonia!"},
            ]
        }
    )
    monkeypatch.setattr("app.live.router.gerar_configuracao", lambda system, msg: resposta_llm)

    resposta = client.post(
        _url_proxima(dono.id, programa.id),
        json={"historico": [], "total_falas": 0},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["falas"] is not None
    assert len(corpo["falas"]) == 2
    assert corpo["falas"][0]["nome_locutor"] == "Ze"
    assert corpo["falas"][1]["nome_locutor"] == "Maria"


@freeze_time(AGORA_UTC)
def test_musica_de_fundo_endpoint(client, account, auth_headers, radialista_e_programa, monkeypatch):
    radio_config, programa = radialista_e_programa
    monkeypatch.setattr(
        "app.live.router.buscar_musica_fundo",
        lambda generos, bloqueados=None, musica_escolhida=None: MusicaEncontrada(
            video_id="bg1", titulo="Fundo", canal="Canal"
        ),
    )
    resposta = client.get(
        f"/live/{radio_config.id}/programas/{programa.id}/musica-fundo", headers=auth_headers(account.id)
    )
    assert resposta.status_code == 200
    assert resposta.json()["video_id"] == "bg1"


@freeze_time(AGORA_UTC)
def test_musica_de_fundo_sem_resultado_404(client, account, auth_headers, radialista_e_programa, monkeypatch):
    radio_config, programa = radialista_e_programa
    monkeypatch.setattr(
        "app.live.router.buscar_musica_fundo", lambda generos, bloqueados=None, musica_escolhida=None: None
    )
    resposta = client.get(
        f"/live/{radio_config.id}/programas/{programa.id}/musica-fundo", headers=auth_headers(account.id)
    )
    assert resposta.status_code == 404


@freeze_time(AGORA_UTC)
def test_musica_de_fundo_usa_escolha_do_programa(
    client, account, auth_headers, radialista_e_programa, db_session, monkeypatch
):
    radio_config, programa = radialista_e_programa
    programa.musica_fundo_escolhida = "Lofi Chill Beats - Instrumental"
    db_session.add(programa)
    db_session.commit()

    chamadas = []

    def fake_buscar_musica_fundo(generos, bloqueados=None, musica_escolhida=None):
        chamadas.append(musica_escolhida)
        return MusicaEncontrada(video_id="bg2", titulo="Fundo escolhido", canal="Canal")

    monkeypatch.setattr("app.live.router.buscar_musica_fundo", fake_buscar_musica_fundo)
    resposta = client.get(
        f"/live/{radio_config.id}/programas/{programa.id}/musica-fundo", headers=auth_headers(account.id)
    )
    assert resposta.status_code == 200
    assert resposta.json()["video_id"] == "bg2"
    assert chamadas == ["Lofi Chill Beats - Instrumental"]


def test_tts_endpoint_nao_habilitado_503(client, account, auth_headers, radialista_e_programa):
    radio_config, _ = radialista_e_programa
    resposta = client.post(
        f"/live/{radio_config.id}/tts", json={"texto": "ola"}, headers=auth_headers(account.id)
    )
    assert resposta.status_code == 503


def test_tts_endpoint_com_sucesso(client, account, auth_headers, radialista_e_programa, monkeypatch):
    radio_config, _ = radialista_e_programa
    monkeypatch.setattr("app.live.router.tts_habilitado", lambda voz_id=None: True)
    monkeypatch.setattr("app.live.router.classificar_tom_fala", lambda texto, tipo: "neutro")
    monkeypatch.setattr(
        "app.live.router.sintetizar_audio_stream",
        lambda texto, voz_id, tipo_bloco=None, tom=None, eh_clonada=False, texto_anterior=None: iter([b"audio-bytes"]),
    )

    resposta = client.post(
        f"/live/{radio_config.id}/tts", json={"texto": "ola ouvintes"}, headers=auth_headers(account.id)
    )
    assert resposta.status_code == 200
    assert resposta.content == b"audio-bytes"


def test_tom_integrado_usa_direcao_editorial_do_bloco():
    assert _tom_sintese_do_bloco("abertura") == "energico"
    assert _tom_sintese_do_bloco("comentario") == "calmo"
    assert _tom_sintese_do_bloco("quadro livre") == "neutro"


@freeze_time(AGORA_UTC)
def test_proxima_informa_falha_de_audio_sem_forcar_segunda_sintese(
    client, account, auth_headers, radialista_e_programa, monkeypatch
):
    """O frontend usa esse estado para manter a cama musical, sem repetir TTS e sem recorrer
    a voz generica do navegador."""
    radio_config, programa = radialista_e_programa
    monkeypatch.setattr("app.live.router.gerar_resposta", lambda system, msg: "Bom dia, ouvintes.")
    monkeypatch.setattr("app.live.router.tts_habilitado", lambda voz_id=None: True)
    monkeypatch.setattr("app.live.router.classificar_tom_fala", lambda texto, tipo: "neutro")

    def falhar_tts(*args, **kwargs):
        raise RuntimeError("provedor indisponivel")

    monkeypatch.setattr("app.live.router.sintetizar_audio", falhar_tts)

    resposta = client.post(
        _url_proxima(radio_config.id, programa.id),
        json={"historico": [], "total_falas": 0},
        headers=auth_headers(account.id),
    )

    assert resposta.status_code == 200
    assert resposta.json()["audio_status"] == "falhou"
    assert resposta.json()["audio_erro"] == "RuntimeError"
    assert resposta.json()["audio_base64"] is None


@freeze_time(AGORA_UTC)
@pytest.mark.parametrize("habilitado,estado", [(True, "pendente"), (False, "indisponivel")])
def test_proxima_pode_entregar_texto_sem_esperar_voz(
    client, account, auth_headers, radialista_e_programa, monkeypatch, habilitado, estado
):
    from app.live.router import _ultimo_tom

    radio_config, programa = radialista_e_programa
    monkeypatch.setattr("app.live.router.gerar_resposta", lambda *args: "Bom dia, ouvintes!")
    monkeypatch.setattr("app.live.router.tts_habilitado", lambda *args: habilitado)

    def nao_deve_processar(*args, **kwargs):
        pytest.fail("A resposta de texto não deve esperar síntese ou pós-produção")

    monkeypatch.setattr("app.live.router.sintetizar_audio", nao_deve_processar)
    monkeypatch.setattr("app.live.router.processar_audio", nao_deve_processar)
    resposta = client.post(_url_proxima(radio_config.id, programa.id),
                           json={"total_falas": 0, "incluir_audio": False, "perfil_pos_producao": "radio_fm"},
                           headers=auth_headers(account.id))
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["fala"] == "Bom dia, ouvintes!"
    assert corpo["audio_status"] == estado
    assert corpo["audio_base64"] is None
    assert corpo["tom"] == "energico"
    assert _ultimo_tom(programa.id) == "energico"


def test_tts_antecipado_preserva_tom_do_texto_sem_sobrescrever_bloco_seguinte(
    client, account, auth_headers, radialista_e_programa, monkeypatch
):
    from app.live.router import _registrar_ultimo_tom, _ultimo_tom

    radio_config, programa = radialista_e_programa
    _registrar_ultimo_tom(programa.id, "energico")
    monkeypatch.setattr("app.live.router.tts_habilitado", lambda *args: True)
    monkeypatch.setattr("app.live.router.classificar_tom_fala", lambda *args: pytest.fail("Tom já definido na escrita"))
    chamadas = []

    def sintetizar(texto, voz_id, **kwargs):
        chamadas.append(kwargs)
        return b"voz original"

    monkeypatch.setattr("app.live.router.sintetizar_audio", sintetizar)
    monkeypatch.setattr("app.live.router.processar_audio", lambda audio, perfil: audio + b" tratado")
    resposta = client.post(f"/live/{radio_config.id}/tts", headers=auth_headers(account.id),
                           json={"texto": "Vamos com calma.", "tom": "calmo", "tipo": "comentario",
                                 "programa_id": programa.id, "perfil_pos_producao": "radio_fm"})
    assert resposta.status_code == 200
    assert resposta.content == b"voz original tratado"
    assert chamadas[0]["tom"] == "calmo"
    assert _ultimo_tom(programa.id) == "energico"


def test_tts_endpoint_com_programa_id_registra_ultimo_tom(
    client, account, auth_headers, radialista_e_programa, monkeypatch
):
    """Tom classificado na sintese de audio (ver classificar_tom_fala) precisa ficar disponivel
    pra proxima chamada de gerar_proxima_fala usar na transicao de humor (ver _ultimo_tom)."""
    from app.live.router import _ultimo_tom

    radio_config, programa = radialista_e_programa
    monkeypatch.setattr("app.live.router.tts_habilitado", lambda voz_id=None: True)
    monkeypatch.setattr("app.live.router.classificar_tom_fala", lambda texto, tipo: "energico")
    monkeypatch.setattr(
        "app.live.router.sintetizar_audio_stream",
        lambda texto, voz_id, tipo_bloco=None, tom=None, eh_clonada=False, texto_anterior=None: iter([b"audio-bytes"]),
    )

    resposta = client.post(
        f"/live/{radio_config.id}/tts",
        json={"texto": "ola ouvintes", "programa_id": programa.id},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 200
    assert _ultimo_tom(programa.id) == "energico"


def test_tts_endpoint_sem_programa_id_nao_registra_tom(
    client, account, auth_headers, radialista_e_programa, monkeypatch
):
    from app.live.router import _ultimo_tom

    radio_config, programa = radialista_e_programa
    monkeypatch.setattr("app.live.router.tts_habilitado", lambda voz_id=None: True)
    monkeypatch.setattr("app.live.router.classificar_tom_fala", lambda texto, tipo: "energico")
    monkeypatch.setattr(
        "app.live.router.sintetizar_audio_stream",
        lambda texto, voz_id, tipo_bloco=None, tom=None, eh_clonada=False, texto_anterior=None: iter([b"audio-bytes"]),
    )

    resposta = client.post(
        f"/live/{radio_config.id}/tts", json={"texto": "ola ouvintes"}, headers=auth_headers(account.id)
    )
    assert resposta.status_code == 200
    assert _ultimo_tom(programa.id) is None


@freeze_time(AGORA_UTC)
def test_prompt_avisa_transicao_de_humor_com_tom_anterior_registrado(
    client, account, auth_headers, radialista_e_programa, monkeypatch
):
    from app.live.router import _registrar_ultimo_tom

    radio_config, programa = radialista_e_programa
    _registrar_ultimo_tom(programa.id, "energico")

    prompts = []
    monkeypatch.setattr(
        "app.live.router.gerar_resposta", lambda system, msg: prompts.append(system) or "Vamos seguir com calma."
    )

    resposta = client.post(
        _url_proxima(radio_config.id, programa.id),
        json={"historico": [], "total_falas": 3},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 200
    assert "tom energico" in prompts[0]


@freeze_time(AGORA_UTC)
def test_prompt_sem_tom_anterior_nao_menciona_transicao_de_humor(
    client, account, auth_headers, radialista_e_programa, monkeypatch
):
    radio_config, programa = radialista_e_programa

    prompts = []
    monkeypatch.setattr(
        "app.live.router.gerar_resposta", lambda system, msg: prompts.append(system) or "Vamos seguir."
    )

    resposta = client.post(
        _url_proxima(radio_config.id, programa.id),
        json={"historico": [], "total_falas": 3},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 200
    assert "transição de humor" not in prompts[0]


@freeze_time(AGORA_UTC)
def test_prompt_oferece_expressao_regional_quando_configurada(
    client, account, auth_headers, radialista_e_programa, monkeypatch, db_session
):
    radio_config, programa = radialista_e_programa
    account.conhecimento_local = {"expressoes_regionais": ["oxente"]}
    db_session.commit()

    prompts = []
    monkeypatch.setattr(
        "app.live.router.gerar_resposta", lambda system, msg: prompts.append(system) or "Bora."
    )

    resposta = client.post(
        _url_proxima(radio_config.id, programa.id),
        json={"historico": [], "total_falas": 3},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 200
    assert "oxente" in prompts[0]


def test_tts_endpoint_com_voz_invalida_400(client, account, auth_headers, radialista_e_programa):
    radio_config, _ = radialista_e_programa
    resposta = client.post(
        f"/live/{radio_config.id}/tts",
        json={"texto": "ola", "voz_id": "voz-invalida"},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 400


def test_tts_endpoint_com_perfil_pos_producao(client, account, auth_headers, radialista_e_programa, monkeypatch):
    radio_config, _ = radialista_e_programa
    monkeypatch.setattr("app.live.router.tts_habilitado", lambda voz_id=None: True)
    monkeypatch.setattr("app.live.router.classificar_tom_fala", lambda texto, tipo: "neutro")
    monkeypatch.setattr(
        "app.live.router.sintetizar_audio", lambda texto, voz_id, tipo_bloco=None, tom=None, eh_clonada=False, texto_anterior=None: b"audio-cru"
    )
    monkeypatch.setattr(
        "app.live.router.processar_audio",
        lambda audio, perfil: audio + b"-processado:" + perfil.encode(),
    )

    resposta = client.post(
        f"/live/{radio_config.id}/tts",
        json={"texto": "ola ouvintes", "perfil_pos_producao": "alfa_fm"},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 200
    assert resposta.content == b"audio-cru-processado:alfa_fm"


def test_tts_endpoint_com_perfil_pos_producao_invalido_422(
    client, account, auth_headers, radialista_e_programa, monkeypatch
):
    radio_config, _ = radialista_e_programa
    monkeypatch.setattr("app.live.router.tts_habilitado", lambda voz_id=None: True)
    monkeypatch.setattr("app.live.router.classificar_tom_fala", lambda texto, tipo: "neutro")
    monkeypatch.setattr(
        "app.live.router.sintetizar_audio", lambda texto, voz_id, tipo_bloco=None, tom=None, eh_clonada=False, texto_anterior=None: b"audio-cru"
    )

    resposta = client.post(
        f"/live/{radio_config.id}/tts",
        json={"texto": "ola", "perfil_pos_producao": "perfil-que-nao-existe"},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 422


def test_tts_endpoint_usa_streaming_sem_perfil_pos_producao(
    client, account, auth_headers, radialista_e_programa, monkeypatch
):
    """Sem perfil_pos_producao (caminho default), /tts deve chamar sintetizar_audio_stream (ver
    Plano B.4) em vez do sintetizar_audio buffered -- e' o que corta a cauda de latencia em
    blocos de fala mais longos."""
    radio_config, _ = radialista_e_programa
    monkeypatch.setattr("app.live.router.tts_habilitado", lambda voz_id=None: True)
    monkeypatch.setattr("app.live.router.classificar_tom_fala", lambda texto, tipo: "neutro")

    def _stream_falso(*args, **kwargs):
        raise AssertionError("sintetizar_audio nao deveria ser chamado quando streaming esta disponivel")

    monkeypatch.setattr("app.live.router.sintetizar_audio", _stream_falso)
    monkeypatch.setattr(
        "app.live.router.sintetizar_audio_stream",
        lambda texto, voz_id, tipo_bloco=None, tom=None, eh_clonada=False, texto_anterior=None: iter(
            [b"parte1", b"parte2"]
        ),
    )

    resposta = client.post(
        f"/live/{radio_config.id}/tts", json={"texto": "ola ouvintes"}, headers=auth_headers(account.id)
    )
    assert resposta.status_code == 200
    assert resposta.content == b"parte1parte2"


def test_tts_endpoint_falha_de_streaming_retorna_502(client, account, auth_headers, radialista_e_programa, monkeypatch):
    """Erro na sintese antes do primeiro chunk (ver sintetizar_audio_stream) ainda precisa virar
    502 normal -- e' so' depois do primeiro chunk que a resposta ja comprometeu o status 200."""
    radio_config, _ = radialista_e_programa
    monkeypatch.setattr("app.live.router.tts_habilitado", lambda voz_id=None: True)
    monkeypatch.setattr("app.live.router.classificar_tom_fala", lambda texto, tipo: "neutro")

    def _stream_com_erro(*args, **kwargs):
        raise httpx.ConnectError("timeout")
        yield b""  # torna a funcao um gerador -- nunca alcancado

    monkeypatch.setattr("app.live.router.sintetizar_audio_stream", _stream_com_erro)

    resposta = client.post(
        f"/live/{radio_config.id}/tts", json={"texto": "ola ouvintes"}, headers=auth_headers(account.id)
    )
    assert resposta.status_code == 502


@freeze_time(AGORA_UTC)
def test_convite_chamada_ouvinte_varia_entre_falas(
    client, account, auth_headers, radialista_e_programa, monkeypatch
):
    """Fase 1 do anti-repeticao: o convite generico de chamada_ouvinte roda por um pool de
    variacoes (round-robin no Redis), nao fica preso na mesma frase toda vez."""
    radio_config, programa = radialista_e_programa
    prompts = []

    def _fake_gerar_resposta(system, msg):
        prompts.append(system)
        return "Bora mandar recado no zap"

    monkeypatch.setattr("app.live.router.gerar_resposta", _fake_gerar_resposta)

    for total_falas in (5, 10, 15):
        resposta = client.post(
            _url_proxima(radio_config.id, programa.id),
            json={"historico": [], "total_falas": total_falas},
            headers=auth_headers(account.id),
        )
        assert resposta.status_code == 200
        assert resposta.json()["tipo"] == "chamada_ouvinte"

    convites = [
        next(linha for linha in prompt.split("\n") if linha.startswith("Quando o bloco for chamada_ouvinte"))
        for prompt in prompts
    ]
    assert len(set(convites)) == 3


@freeze_time(AGORA_UTC)
def test_historico_de_temas_injetado_no_proximo_comentario(
    client, account, auth_headers, radialista_e_programa, monkeypatch
):
    """Fase 2 do anti-repeticao: tema de comentario/noticia fica registrado na sessao inteira
    (nao so nas ultimas falas do historico enviado pelo frontend) e volta pro prompt."""
    radio_config, programa = radialista_e_programa
    monkeypatch.setattr("app.live.router.classificar_tema_fala", lambda texto: "transito na cidade")

    prompts = []

    def _fake_gerar_resposta(system, msg):
        prompts.append(system)
        return "comentario generico sobre a cidade hoje de manha"

    monkeypatch.setattr("app.live.router.gerar_resposta", _fake_gerar_resposta)

    # total_falas=3 e total_falas=8 caem os dois no bloco "comentario" do roteiro padrao.
    for total_falas in (3, 8):
        resposta = client.post(
            _url_proxima(radio_config.id, programa.id),
            json={"historico": [], "total_falas": total_falas},
            headers=auth_headers(account.id),
        )
        assert resposta.status_code == 200
        assert resposta.json()["tipo"] == "comentario"

    assert "transito na cidade" not in prompts[0]
    assert "Temas de comentário/notícia já abordados nesta transmissão" in prompts[1]
    assert "transito na cidade" in prompts[1]


@freeze_time(AGORA_UTC)
def test_fala_muito_parecida_com_historico_e_regenerada(
    client, account, auth_headers, radialista_e_programa, monkeypatch
):
    """Fase 3 do anti-repeticao: rede de seguranca em runtime -- fala quase igual a uma fala
    recente do mesmo tipo de bloco (mesmo fora da janela de 8 falas do historico enviado pelo
    frontend) dispara uma unica regeneracao."""
    radio_config, programa = radialista_e_programa
    monkeypatch.setattr("app.live.router.classificar_tema_fala", lambda texto: "")

    texto_repetido = "hoje o transito da cidade esta terrivel de novo por causa da chuva forte"
    texto_novo = "vamos falar sobre a nova praca que abriu ali no bairro central"
    respostas = iter([texto_repetido, texto_repetido, texto_novo])
    chamadas = []

    def _fake_gerar_resposta(system, msg):
        chamadas.append(1)
        return next(respostas)

    monkeypatch.setattr("app.live.router.gerar_resposta", _fake_gerar_resposta)

    # total_falas=3 e total_falas=8 caem os dois no bloco "comentario" do roteiro padrao --
    # a primeira chamada registra texto_repetido no historico da sessao pra essa categoria.
    r1 = client.post(
        _url_proxima(radio_config.id, programa.id),
        json={"historico": [], "total_falas": 3},
        headers=auth_headers(account.id),
    )
    assert r1.status_code == 200
    assert r1.json()["tipo"] == "comentario"
    assert r1.json()["fala"] == texto_repetido

    r2 = client.post(
        _url_proxima(radio_config.id, programa.id),
        json={"historico": [], "total_falas": 8},
        headers=auth_headers(account.id),
    )
    assert r2.status_code == 200
    assert r2.json()["tipo"] == "comentario"
    assert r2.json()["fala"] == texto_novo
    assert len(chamadas) == 3  # 1 pra r1, 2 pra r2 (tentativa original + retry apos deteccao)


@freeze_time(AGORA_UTC)
def test_bloco_customizado_com_genero_proprio_ignora_musicas_permitidas(
    client, account, auth_headers, radialista_e_programa, db_session, monkeypatch
):
    """Bug corrigido: bloco customizado com genero proprio (ex.: 'Musica Xote') tinha
    prioridade MENOR que musicas_permitidas generico da radio -- na pratica, um bloco de
    xote acabava buscando a lista fixa de musicas da radio em vez do estilo do proprio
    bloco. O rotulo do bloco tem que vencer, e o genero pedido tem que ir como filtro pra
    busca (ver genero= em buscar_musica), pra nao vazar pra genero vizinho (chamame)."""
    radio_config, programa = radialista_e_programa
    programa.estrutura_blocos = ["Musica Xote"]
    programa.musicas_permitidas = ["Alguma Musica Generica Da Radio"]
    db_session.commit()

    monkeypatch.setattr("app.live.router.gerar_resposta", lambda system, msg: "Vamos de xote!")

    capturado = {}

    def _fake_buscar_musica(query, **kwargs):
        capturado["query"] = query
        capturado["genero"] = kwargs.get("genero")
        return MusicaEncontrada(video_id="id1", titulo="Xote Bom", canal="Canal Xote")

    monkeypatch.setattr("app.live.router.buscar_musica", _fake_buscar_musica)

    resposta = client.post(
        _url_proxima(radio_config.id, programa.id),
        json={"historico": [], "total_falas": 0},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 200
    assert capturado["genero"] == "Xote"
    assert "xote" in capturado["query"].lower()
    assert capturado["query"] != "Alguma Musica Generica Da Radio"

    registro = db_session.query(MusicaHistorico).filter_by(programa_id=programa.id).one()
    assert registro.origem == "auto"
    assert registro.video_id == "id1"


@freeze_time(AGORA_UTC)
def test_busca_automatica_sem_resultado_cai_pro_fallback_generico(
    client, account, auth_headers, radialista_e_programa, db_session, monkeypatch
):
    """Bug corrigido: bloco de musica automatico (sem pedido do ouvinte) fazia uma unica
    tentativa de busca -- se a query curada/gerada nao achasse nada, `musica` ficava None e o
    locutor recebia instrucao pra anunciar um genero/artista mesmo sem nada pra tocar de
    verdade (fala anunciava musica que nunca disparava). Agora cai pra uma busca generica de
    ultimo recurso antes de desistir de vez."""
    radio_config, programa = radialista_e_programa
    programa.musicas_permitidas = ["Musica Bem Especifica Que Nao Existe"]
    db_session.commit()

    monkeypatch.setattr("app.live.router.gerar_resposta", lambda system, msg: "Vamos ouvir uma boa!")

    def _fake_buscar_musica(query, **kwargs):
        if query == "musica instrumental":
            return MusicaEncontrada(video_id="id-fallback", titulo="Instrumental Generica", canal="Canal Z")
        return None

    monkeypatch.setattr("app.live.router.buscar_musica", _fake_buscar_musica)

    # total_falas=1 -> proximo bloco do roteiro padrao apos abertura(0) e' "musica".
    resposta = client.post(
        _url_proxima(radio_config.id, programa.id),
        json={"historico": ["abertura: oi"], "total_falas": 1},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["tipo"] == "musica"
    assert corpo["video_id"] == "id-fallback"
    assert corpo["titulo_musica"] == "Instrumental Generica"

    registro = db_session.query(MusicaHistorico).filter_by(programa_id=programa.id).one()
    assert registro.origem == "auto"
    assert registro.query_normalizada == "musica instrumental"


@freeze_time(AGORA_UTC)
def test_pedido_musica_via_whatsapp_registra_historico_persistente(
    client, account, auth_headers, radialista_e_programa, db_session, monkeypatch
):
    """Pedido real do ouvinte via WhatsApp precisa ficar registrado no historico persistente
    (origem='pedido_ouvinte') -- e' a partir dai que o sistema aprende o que o publico mais
    pede (ver _pedidos_publico_mais_frequentes)."""
    radio_config, programa = radialista_e_programa
    pedido = FilaAoVivo(
        radio_config_id=radio_config.id,
        telefone="5511999999999",
        nome="Ouvinte Teste",
        tipo="musica",
        mensagem_usuario="toca uma sofrencia",
        musica_query="Sofrencia Boa",
    )
    db_session.add(pedido)
    db_session.commit()

    monkeypatch.setattr("app.live.router.gerar_resposta", lambda system, msg: "Aqui vai seu pedido!")
    monkeypatch.setattr(
        "app.live.router.buscar_musica",
        lambda query, **kwargs: MusicaEncontrada(video_id="id-pedido", titulo="Sofrencia Boa", canal="Canal X"),
    )

    resposta = client.post(
        _url_proxima(radio_config.id, programa.id),
        json={"historico": ["abertura: oi"], "total_falas": 1},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 200
    assert resposta.json()["tipo"] == "musica"

    registro = db_session.query(MusicaHistorico).filter_by(programa_id=programa.id).one()
    assert registro.origem == "pedido_ouvinte"
    assert registro.video_id == "id-pedido"
    assert registro.query_normalizada == "sofrencia boa"


@freeze_time(AGORA_UTC)
def test_pedido_musica_sem_resultado_cai_para_escolha_automatica(
    client, account, auth_headers, radialista_e_programa, db_session, monkeypatch
):
    """Bug corrigido: quando a busca pela musica pedida nao achava nada, `_proximo_pedido_fila`
    ja tinha marcado o pedido como atendido e `musica` ficava None -- o bloco caia no anuncio
    generico "nao encontrei nada", nenhuma faixa tocava, e o pedido do ouvinte sumia pra sempre.
    Agora tem que cair pra escolha automatica e ainda tocar alguma coisa nesse bloco."""
    radio_config, programa = radialista_e_programa
    pedido = FilaAoVivo(
        radio_config_id=radio_config.id,
        telefone="5511999999999",
        nome="Ouvinte Teste",
        tipo="musica",
        mensagem_usuario="toca uma musica que nao existe no youtube",
        musica_query="Musica Inexistente XYZ",
    )
    db_session.add(pedido)
    db_session.commit()

    monkeypatch.setattr("app.live.router.gerar_resposta", lambda system, msg: "Não achei, mas toca essa!")

    def _fake_buscar_musica(query, **kwargs):
        if query == "Musica Inexistente XYZ":
            return None
        return MusicaEncontrada(video_id="id-auto", titulo="Musica Automatica", canal="Canal Y")

    monkeypatch.setattr("app.live.router.buscar_musica", _fake_buscar_musica)
    monkeypatch.setattr(
        "app.live.router._buscar_musica_para_bloco",
        lambda db, programa, tipo=None: MusicaEncontrada(video_id="id-auto", titulo="Musica Automatica", canal="Canal Y"),
    )

    resposta = client.post(
        _url_proxima(radio_config.id, programa.id),
        json={"historico": ["abertura: oi"], "total_falas": 1},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["tipo"] == "musica"
    # continua tocando alguma coisa (fallback automatico), em vez de video_id/titulo vazios.
    assert corpo["video_id"] == "id-auto"
    assert corpo["titulo_musica"] == "Musica Automatica"

    # pedido segue marcado como atendido (nao entra em loop tentando pra sempre uma busca que
    # nunca vai achar nada), mas nao fica registrado como pedido_ouvinte bem-sucedido.
    db_session.refresh(pedido)
    assert pedido.atendido is True
    assert db_session.query(MusicaHistorico).filter_by(programa_id=programa.id, origem="pedido_ouvinte").count() == 0


def test_escolher_query_musica_pondera_posicao_admin_e_pedidos_publico(
    db_session, radialista_e_programa, monkeypatch
):
    """Musica ponderada: posicao na lista curada pelo admin e frequencia de pedido real do
    publico (persistido em MusicaHistorico) entram no mesmo pool de candidatos, com pesos
    diferentes (ver _PESO_POSICAO_ADMIN/_PESO_PEDIDO_PUBLICO)."""
    _, programa = radialista_e_programa
    programa.musicas_permitidas = ["Musica A", "Musica B"]
    db_session.commit()

    for _ in range(5):
        _registrar_historico_persistente(
            db_session,
            programa.id,
            MusicaEncontrada(video_id="x", titulo="t", canal="c"),
            "Sofrencia Pedida",
            origem="pedido_ouvinte",
        )
    _registrar_historico_persistente(
        db_session,
        programa.id,
        MusicaEncontrada(video_id="y", titulo="t2", canal="c2"),
        "Musica C",
        origem="pedido_ouvinte",
    )

    capturado = {}

    def _fake_choices(population, weights, k):
        capturado["population"] = list(population)
        capturado["weights"] = list(weights)
        return [population[0]]

    monkeypatch.setattr("app.live.router.random.choices", _fake_choices)

    query, genero, musica_catalogada = _escolher_query_musica(db_session, programa)

    assert genero is None
    assert musica_catalogada is None
    assert "Musica A" in capturado["population"]
    assert "Musica B" in capturado["population"]
    assert "sofrencia pedida" in capturado["population"]
    indice_sofrencia = capturado["population"].index("sofrencia pedida")
    indice_musica_c = capturado["population"].index("musica c")
    assert capturado["weights"][indice_sofrencia] > capturado["weights"][indice_musica_c]


def test_escolher_query_musica_pula_candidato_ja_tocado_na_sessao(
    db_session, radialista_e_programa, monkeypatch
):
    """Item da curadoria do admin (ou pedido mais frequente) que ja tocou nesta sessao (ver
    titulos_tocados) nao entra no sorteio -- sem isso o peso maior da 1a posicao da lista (ver
    _PESO_POSICAO_ADMIN) insiste em reoferecer a mesma musica ja tocada, que so' vai ser
    bloqueada depois (ver _via_catalogo/buscar_musica) e cair no fallback generico 'musica
    instrumental' em vez de seguir pra proxima musica da curadoria."""
    _, programa = radialista_e_programa
    programa.musicas_permitidas = ["Jorge & Mateus - Propaganda", "Outra Dupla - Segunda Musica"]
    db_session.commit()

    for _ in range(5):
        _registrar_historico_persistente(
            db_session,
            programa.id,
            MusicaEncontrada(video_id="x", titulo="t", canal="c"),
            "Terceira Dupla - Pedido Popular",
            origem="pedido_ouvinte",
        )

    capturado = {}

    def _fake_choices(population, weights, k):
        capturado["population"] = list(population)
        return [population[0]]

    monkeypatch.setattr("app.live.router.random.choices", _fake_choices)

    titulos_tocados = {_titulo_normalizado("Propaganda"), _titulo_normalizado("Pedido Popular")}
    query, genero, musica_catalogada = _escolher_query_musica(
        db_session, programa, set(), titulos_tocados, {}
    )

    assert "Jorge & Mateus - Propaganda" not in capturado["population"]
    assert "terceira dupla - pedido popular" not in capturado["population"]
    assert "Outra Dupla - Segunda Musica" in capturado["population"]
    assert query == capturado["population"][0]


def test_escolher_query_musica_sem_curadoria_cai_pro_genero_da_radio(db_session, radialista_e_programa):
    _, programa = radialista_e_programa
    programa.musicas_permitidas = []
    programa.generos_musicais = ["Sertanejo"]
    db_session.commit()

    query, genero, musica_catalogada = _escolher_query_musica(db_session, programa)
    assert genero == "Sertanejo"
    assert query == "Sertanejo musica"
    assert musica_catalogada is None


def test_escolher_query_musica_sugestao_llm_cataloga_e_reutiliza_youtube(
    db_session, radialista_e_programa, monkeypatch
):
    """Sugestao da LLM no formato 'Artista - Musica' (ver dividir_artista_titulo em
    app.live.song_service) e' catalogada na 1a chamada e persiste o youtube_video_id
    resolvido; numa 2a chamada, o catalogo evita repetir a busca no YouTube."""
    _, programa = radialista_e_programa
    programa.musicas_permitidas = []
    programa.generos_musicais = ["Sertanejo"]
    db_session.commit()

    monkeypatch.setattr("app.live.router.sugerir_musica_do_genero", lambda genero: "Jorge & Mateus - Propaganda")
    monkeypatch.setattr("app.live.song_service.obter_fim_seguro", lambda video_id, duracao: None)

    chamadas = []

    def _fake_buscar_musica(query, **kwargs):
        chamadas.append(query)
        return MusicaEncontrada(video_id="abc123", titulo="Propaganda", canal="Jorge e Mateus Oficial", duracao_segundos=200)

    monkeypatch.setattr("app.live.song_service.buscar_musica", _fake_buscar_musica)

    query1, genero1, musica1 = _escolher_query_musica(db_session, programa, set(), set(), {})
    assert genero1 is None
    assert musica1 is not None
    assert musica1.video_id == "abc123"
    assert musica1.musica_catalogada_id is not None
    assert len(chamadas) == 1
    assert db_session.query(Musica).count() == 1

    _registrar_historico_persistente(db_session, programa.id, musica1, query1, origem="auto")
    historico = db_session.query(MusicaHistorico).filter_by(programa_id=programa.id).one()
    assert historico.song_id == musica1.musica_catalogada_id

    query2, genero2, musica2 = _escolher_query_musica(db_session, programa, set(), set(), {})
    assert musica2 is not None
    assert musica2.video_id == "abc123"
    assert len(chamadas) == 1  # nao repetiu a busca no YouTube
    assert db_session.query(Musica).count() == 1  # nao duplicou a Musica catalogada

    # ja tocada nesta sessao -- catalogo devolve None em vez de reaproveitar de novo.
    query3, genero3, musica3 = _escolher_query_musica(db_session, programa, {"abc123"}, set(), {})
    assert musica3 is None
    assert len(chamadas) == 1


def test_escolher_query_musica_curadoria_no_formato_artista_titulo_usa_catalogo(
    db_session, radialista_e_programa, monkeypatch
):
    """musicas_permitidas e' texto livre digitado pelo admin -- quando o admin ja escreveu no
    formato 'Artista - Titulo', a entrada tambem passa pelo catalogo persistente (mesma logica
    da sugestao da LLM), sem exigir mudanca na tela de configuracao nem no formato salvo."""
    _, programa = radialista_e_programa
    programa.musicas_permitidas = ["Jorge & Mateus - Propaganda"]
    db_session.commit()

    monkeypatch.setattr("app.live.song_service.obter_fim_seguro", lambda video_id, duracao: None)

    chamadas = []
    monkeypatch.setattr(
        "app.live.song_service.buscar_musica",
        lambda query, **kwargs: chamadas.append(query)
        or MusicaEncontrada(video_id="xyz789", titulo="Propaganda", canal="Jorge e Mateus Oficial"),
    )

    query1, genero1, musica1 = _escolher_query_musica(db_session, programa, set(), set(), {})
    assert genero1 is None
    assert musica1 is not None
    assert musica1.video_id == "xyz789"
    assert len(chamadas) == 1

    query2, genero2, musica2 = _escolher_query_musica(db_session, programa, set(), set(), {})
    assert musica2 is not None
    assert musica2.video_id == "xyz789"
    assert len(chamadas) == 1  # nao repetiu a busca no YouTube


def test_escolher_query_musica_curadoria_texto_livre_ignora_catalogo(
    db_session, radialista_e_programa
):
    """Entrada de musicas_permitidas sem o formato 'Artista - Titulo' (texto livre comum)
    continua caindo direto pra busca por query, sem tentar catalogar."""
    _, programa = radialista_e_programa
    programa.musicas_permitidas = ["Alguma Musica Generica Da Radio"]
    db_session.commit()

    query, genero, musica_catalogada = _escolher_query_musica(db_session, programa, set(), set(), {})
    assert query == "Alguma Musica Generica Da Radio"
    assert musica_catalogada is None
    assert db_session.query(Musica).count() == 0


def test_escolher_query_musica_curadoria_admin_grava_confianca_alta(
    db_session, radialista_e_programa, monkeypatch
):
    """Entrada de musicas_permitidas no formato 'Artista - Titulo' e' curadoria humana do admin
    -- catalogada com confianca alta (ver _confianca_da_origem em app.live.song_service)."""
    _, programa = radialista_e_programa
    programa.musicas_permitidas = ["Jorge & Mateus - Propaganda"]
    db_session.commit()

    monkeypatch.setattr("app.live.song_service.obter_fim_seguro", lambda video_id, duracao: None)
    monkeypatch.setattr(
        "app.live.song_service.buscar_musica",
        lambda query, **kwargs: MusicaEncontrada(video_id="xyz789", titulo="Propaganda", canal="Jorge e Mateus Oficial"),
    )

    _escolher_query_musica(db_session, programa, set(), set(), {})

    musica_db = db_session.query(Musica).filter_by(youtube_video_id="xyz789").one()
    assert musica_db.confianca == "alta"
    assert musica_db.status == "resolvida"


def test_escolher_query_musica_sugestao_llm_grava_confianca_baixa(
    db_session, radialista_e_programa, monkeypatch
):
    """Sugestao de texto livre da LLM (sem lista Spotify disponivel pro genero) e' catalogada
    com confianca baixa -- pode ter 'inventado' uma combinacao artista+musica inexistente."""
    _, programa = radialista_e_programa
    programa.musicas_permitidas = []
    programa.generos_musicais = ["Sertanejo"]
    db_session.commit()

    monkeypatch.setattr("app.live.router.sugerir_musica_do_genero", lambda genero: "Jorge & Mateus - Propaganda")
    monkeypatch.setattr("app.live.song_service.obter_fim_seguro", lambda video_id, duracao: None)
    monkeypatch.setattr(
        "app.live.song_service.buscar_musica",
        lambda query, **kwargs: MusicaEncontrada(video_id="abc123", titulo="Propaganda", canal="Jorge e Mateus Oficial"),
    )

    _escolher_query_musica(db_session, programa, set(), set(), {})

    musica_db = db_session.query(Musica).filter_by(youtube_video_id="abc123").one()
    assert musica_db.confianca == "baixa"


def test_escolher_query_musica_usa_lista_spotify_quando_disponivel(
    db_session, radialista_e_programa, monkeypatch
):
    """Genero configurado com lista Spotify cacheada disponivel: escolhe uma faixa dela em vez
    de pedir sugestao de texto livre pra LLM (ver _escolher_query_musica em app.live.router)."""
    _, programa = radialista_e_programa
    programa.musicas_permitidas = []
    programa.generos_musicais = ["Sertanejo"]
    db_session.commit()

    monkeypatch.setattr(
        "app.live.router.buscar_faixas_por_categoria",
        lambda genero, excluir_titulos=None: [("Jorge & Mateus", "Propaganda")],
    )
    chamou_llm = {"sim": False}
    monkeypatch.setattr(
        "app.live.router.sugerir_musica_do_genero",
        lambda genero: chamou_llm.__setitem__("sim", True) or "",
    )
    monkeypatch.setattr("app.live.song_service.obter_fim_seguro", lambda video_id, duracao: None)
    monkeypatch.setattr(
        "app.live.song_service.buscar_musica",
        lambda query, **kwargs: MusicaEncontrada(video_id="sp1", titulo="Propaganda", canal="Jorge e Mateus Oficial"),
    )

    query, genero, musica = _escolher_query_musica(db_session, programa, set(), set(), {})

    assert query == "Jorge & Mateus - Propaganda"
    assert musica is not None
    assert musica.video_id == "sp1"
    assert chamou_llm["sim"] is False

    musica_db = db_session.query(Musica).filter_by(youtube_video_id="sp1").one()
    assert musica_db.confianca == "alta"


def test_buscar_musica_para_bloco_usa_fallback_curado_quando_tudo_falha(
    db_session, radialista_e_programa, monkeypatch
):
    """Quando nem a query especifica nem o retry generico ('musica instrumental') acham nada no
    YouTube, o bloco nao fica vazio de cara -- primeiro tenta, uma a uma, faixas da lista
    Spotify cacheada por genero (ver _fallback_curado_genero em app.live.router)."""
    _, programa = radialista_e_programa
    programa.musicas_permitidas = []
    programa.generos_musicais = ["Sertanejo"]
    db_session.commit()

    chamadas_spotify = {"n": 0}

    def _fake_faixas(genero, excluir_titulos=None):
        chamadas_spotify["n"] += 1
        if chamadas_spotify["n"] == 1:
            # 1a chamada vem da escolha normal do bloco -- lista vazia, cai pro generico.
            return []
        # 2a chamada em diante vem do fallback curado, depois de tudo o resto falhar.
        return [("Jorge & Mateus", "Propaganda"), ("Gusttavo Lima", "Balada")]

    monkeypatch.setattr("app.live.router.buscar_faixas_por_categoria", _fake_faixas)
    monkeypatch.setattr("app.live.router.sugerir_musica_do_genero", lambda genero: "")
    monkeypatch.setattr("app.live.router.buscar_musica", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.live.song_service.obter_fim_seguro", lambda video_id, duracao: None)
    monkeypatch.setattr(
        "app.live.song_service.buscar_musica",
        lambda query, **kwargs: MusicaEncontrada(video_id="fb1", titulo="Propaganda", canal="Jorge e Mateus Oficial"),
    )

    from app.live.router import _buscar_musica_para_bloco

    musica = _buscar_musica_para_bloco(db_session, programa)

    assert musica is not None
    assert musica.video_id == "fb1"

    musica_db = db_session.query(Musica).filter_by(youtube_video_id="fb1").one()
    assert musica_db.confianca == "alta"
    assert musica_db.status == "resolvida"

    historico = db_session.query(MusicaHistorico).filter_by(programa_id=programa.id).one()
    assert historico.video_id == "fb1"


def test_buscar_musica_para_bloco_sem_generos_nao_tem_fallback_curado(
    db_session, radialista_e_programa, monkeypatch
):
    """Radio sem genero configurado nao tem lista Spotify nenhuma pra' tentar -- fallback curado
    devolve None direto, sem quebrar o bloco (continua vazio, mesmo comportamento de antes)."""
    _, programa = radialista_e_programa
    programa.musicas_permitidas = []
    programa.generos_musicais = []
    db_session.commit()

    monkeypatch.setattr("app.live.router.buscar_musica", lambda *args, **kwargs: None)

    from app.live.router import _buscar_musica_para_bloco

    assert _buscar_musica_para_bloco(db_session, programa) is None


@freeze_time(AGORA_UTC)
def test_prompt_v3_inclui_instrucao_de_tags_em_comentario(
    client, account, auth_headers, radialista_e_programa, monkeypatch
):
    """eleven_v3 aceita tag de direcao vocal inline (ver _TAGS_V3_PERMITIDAS em app.tts.client) --
    o prompt precisa instruir o LLM a usar essa tag so quando o modelo ativo for o v3."""
    monkeypatch.setattr("app.live.router.settings.elevenlabs_model", "eleven_v3")
    radio_config, programa = radialista_e_programa

    prompts = []
    monkeypatch.setattr(
        "app.live.router.gerar_resposta", lambda system, msg: prompts.append(system) or "Que dia otimo!"
    )

    # total_falas=3 -> roteiro padrao cai em "comentario" (indice 2).
    resposta = client.post(
        _url_proxima(radio_config.id, programa.id),
        json={"historico": [], "total_falas": 3},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 200
    assert resposta.json()["tipo"] == "comentario"
    assert "[excited]" in prompts[0]


@freeze_time(AGORA_UTC)
def test_prompt_v3_omite_instrucao_de_tags_em_noticia(
    client, account, auth_headers, radialista_e_programa, db_session, monkeypatch
):
    """Notícia pede tom sereno e informativo -- tag de emoção (ver _PROSODIA_BLOCO) não faz
    sentido nesse bloco, então a instrução nem é oferecida ao LLM."""
    monkeypatch.setattr("app.live.router.settings.elevenlabs_model", "eleven_v3")
    radio_config, programa = radialista_e_programa
    programa.pode_pesquisar = True
    db_session.commit()

    prompts = []
    monkeypatch.setattr(
        "app.live.router.gerar_resposta", lambda system, msg: prompts.append(system) or "O tempo segue firme."
    )

    # total_falas=4 -> roteiro padrao cai em "noticia" (indice 3).
    resposta = client.post(
        _url_proxima(radio_config.id, programa.id),
        json={"historico": [], "total_falas": 4},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 200
    assert resposta.json()["tipo"] == "noticia"
    assert "[excited]" not in prompts[0]


@freeze_time(AGORA_UTC)
def test_prompt_v2_omite_instrucao_de_tags(client, account, auth_headers, radialista_e_programa, monkeypatch):
    """Tag inline e' recurso especifico do eleven_v3 -- outro modelo nem recebe a instrucao."""
    monkeypatch.setattr("app.live.router.settings.elevenlabs_model", "eleven_multilingual_v2")
    radio_config, programa = radialista_e_programa

    prompts = []
    monkeypatch.setattr(
        "app.live.router.gerar_resposta", lambda system, msg: prompts.append(system) or "Que dia otimo!"
    )

    resposta = client.post(
        _url_proxima(radio_config.id, programa.id),
        json={"historico": [], "total_falas": 3},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 200
    assert "[excited]" not in prompts[0]


def test_primeira_frase_e_ultima_frase_ignoram_tag_v3():
    texto = "[excited] Bom dia, ouvintes! Hoje o dia promete. [calm] Vamos com calma no comeco."
    assert _primeira_frase(texto) == "Bom dia, ouvintes!"
    assert _ultima_frase(texto) == "Vamos com calma no comeco."


def test_primeira_frase_e_ultima_frase_fala_de_uma_frase_so():
    texto = "Fala unica sem ponto final no meio"
    assert _primeira_frase(texto) == texto
    assert _ultima_frase(texto) == texto


def test_aberturas_e_fechamentos_extrai_das_falas_recentes():
    historico = [
        "Fechou por aqui, ate a proxima! Foi bom demais.",
        "E ai, galera! Bora de novo com tudo.",
    ]
    aberturas, fechamentos = _aberturas_e_fechamentos(historico)
    assert aberturas == ["Fechou por aqui, ate a proxima!", "E ai, galera!"]
    assert fechamentos == ["Foi bom demais.", "Bora de novo com tudo."]


def test_aberturas_e_fechamentos_fala_de_uma_frase_nao_duplica_no_fechamento():
    aberturas, fechamentos = _aberturas_e_fechamentos(["Fala curta e unica"])
    assert aberturas == ["Fala curta e unica"]
    assert fechamentos == []


@freeze_time(AGORA_UTC)
def test_prompt_avisa_abertura_e_fechamento_ja_usados_no_mesmo_tipo_de_bloco(
    client, account, auth_headers, radialista_e_programa, monkeypatch
):
    radio_config, programa = radialista_e_programa
    _registrar_fala_gerada(
        programa.id, "comentario", "Vamos falar de futebol hoje! Foi um jogo daqueles, viu."
    )

    prompts = []
    monkeypatch.setattr(
        "app.live.router.gerar_resposta", lambda system, msg: prompts.append(system) or "Outro assunto qualquer."
    )

    # total_falas=3 -> roteiro padrao cai em "comentario" (indice 2).
    resposta = client.post(
        _url_proxima(radio_config.id, programa.id),
        json={"historico": [], "total_falas": 3},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 200
    assert resposta.json()["tipo"] == "comentario"
    assert "Vamos falar de futebol hoje!" in prompts[0]
    assert "Foi um jogo daqueles, viu." in prompts[0]


@freeze_time(AGORA_UTC)
def test_prompt_comentario_oferece_marcadores_de_fala_natural(
    client, account, auth_headers, radialista_e_programa, monkeypatch
):
    radio_config, programa = radialista_e_programa
    prompts = []
    monkeypatch.setattr(
        "app.live.router.gerar_resposta", lambda system, msg: prompts.append(system) or "Que dia bom."
    )

    # total_falas=3 -> roteiro padrao cai em "comentario" (indice 2).
    resposta = client.post(
        _url_proxima(radio_config.id, programa.id),
        json={"historico": [], "total_falas": 3},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 200
    assert "autocorreção leve" in prompts[0]
    assert "hesitação pontual" in prompts[0]


@freeze_time(AGORA_UTC)
def test_prompt_noticia_proibe_marcadores_de_fala_natural(
    client, account, auth_headers, radialista_e_programa, db_session, monkeypatch
):
    radio_config, programa = radialista_e_programa
    programa.pode_pesquisar = True
    db_session.commit()

    prompts = []
    monkeypatch.setattr(
        "app.live.router.gerar_resposta", lambda system, msg: prompts.append(system) or "O tempo segue firme."
    )

    # total_falas=4 -> roteiro padrao cai em "noticia" (indice 3).
    resposta = client.post(
        _url_proxima(radio_config.id, programa.id),
        json={"historico": [], "total_falas": 4},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 200
    assert resposta.json()["tipo"] == "noticia"
    assert "autocorreção leve" not in prompts[0]
    assert "nada de maneirismo" in prompts[0]


@freeze_time(AGORA_UTC)
def test_bloco_musica_injeta_contexto_real_no_prompt(
    client, account, auth_headers, radialista_e_programa, monkeypatch
):
    """O locutor precisa de contexto real da musica (nao so titulo/canal) antes de falar dela --
    ver _contexto_musica/resumir_contexto_musica."""
    radio_config, programa = radialista_e_programa
    monkeypatch.setattr(
        "app.live.router.buscar_musica",
        lambda query, **kwargs: MusicaEncontrada(
            video_id="abc123",
            titulo="Musica Teste",
            canal="Canal Teste",
            descricao="Uma composicao sobre a vida no interior",
            tags=["sertanejo raiz"],
            ano="1998",
        ),
    )
    monkeypatch.setattr(
        "app.live.router.resumir_contexto_musica",
        lambda titulo, canal, descricao, tags, ano: "Fala sobre a vida no interior, de 1998.",
    )

    prompts = []

    def _fake_gerar_resposta(system, msg):
        prompts.append(system)
        return "Vamos ouvir essa!"

    monkeypatch.setattr("app.live.router.gerar_resposta", _fake_gerar_resposta)

    resposta = client.post(
        _url_proxima(radio_config.id, programa.id),
        json={"historico": ["abertura: oi"], "total_falas": 1},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 200
    assert resposta.json()["tipo"] == "musica"
    assert "Fala sobre a vida no interior, de 1998." in prompts[0]


@freeze_time(AGORA_UTC)
def test_bloco_musica_sem_metadados_nao_chama_llm_de_contexto(
    client, account, auth_headers, radialista_e_programa, monkeypatch
):
    """Sem descricao/tags/ano nenhum, nao vale a pena gastar chamada de LLM so' pra ouvir
    'insuficiente' -- ver guard em _contexto_musica."""
    radio_config, programa = radialista_e_programa
    monkeypatch.setattr(
        "app.live.router.buscar_musica",
        lambda query, **kwargs: MusicaEncontrada(video_id="abc123", titulo="Musica Teste", canal="Canal Teste"),
    )

    chamou_contexto = []
    monkeypatch.setattr(
        "app.live.router.resumir_contexto_musica",
        lambda *a, **k: chamou_contexto.append(1) or "nunca deveria chegar aqui",
    )
    monkeypatch.setattr("app.live.router.gerar_resposta", lambda system, msg: "Vamos ouvir essa!")

    resposta = client.post(
        _url_proxima(radio_config.id, programa.id),
        json={"historico": ["abertura: oi"], "total_falas": 1},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 200
    assert chamou_contexto == []


@freeze_time(AGORA_UTC)
def test_fluxo_completo_musica_via_spotify_end_to_end(
    client, account, auth_headers, db_session, radialista_e_programa, monkeypatch
):
    """Fluxo inteiro da Fase 0-2 (plano de qualidade na busca de musica), do endpoint HTTP ate
    o catalogo persistido: radio com genero configurado -> lista Spotify cacheada fornece uma
    faixa oficial -> YouTube resolve o video -> resposta ao vivo devolve a musica -> Musica
    catalogada fica com confianca alta e status resolvida -> MusicaHistorico registra o play.
    Nada aqui bate em rede de verdade (Spotify e YouTube mockados na borda)."""
    radio_config, programa = radialista_e_programa
    programa.musicas_permitidas = []
    programa.generos_musicais = ["Sertanejo"]
    db_session.commit()

    monkeypatch.setattr(
        "app.live.router.buscar_faixas_por_categoria",
        lambda genero, excluir_titulos=None: [("Jorge & Mateus", "Propaganda")],
    )
    monkeypatch.setattr("app.live.song_service.obter_fim_seguro", lambda video_id, duracao: None)
    monkeypatch.setattr(
        "app.live.song_service.buscar_musica",
        lambda query, **kwargs: MusicaEncontrada(
            video_id="sp1", titulo="Propaganda", canal="Jorge e Mateus Oficial", duracao_segundos=180
        ),
    )
    monkeypatch.setattr("app.live.router.gerar_resposta", lambda system, msg: "Vamos ouvir essa aqui!")

    resposta = client.post(
        _url_proxima(radio_config.id, programa.id),
        json={"historico": ["abertura: oi"], "total_falas": 1},
        headers=auth_headers(account.id),
    )

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["tipo"] == "musica"
    assert corpo["video_id"] == "sp1"
    assert corpo["titulo_musica"] == "Propaganda"
    assert corpo["duracao_segundos"] == 180

    musica_db = db_session.query(Musica).filter_by(youtube_video_id="sp1").one()
    assert musica_db.titulo_normalizado == "propaganda"
    assert musica_db.artista_normalizado == "jorge e mateus"
    assert musica_db.confianca == "alta"
    assert musica_db.status == "resolvida"

    historico = db_session.query(MusicaHistorico).filter_by(programa_id=programa.id).one()
    assert historico.video_id == "sp1"
    assert historico.song_id == musica_db.id
    assert historico.origem == "auto"


def _pedido_fila(radio_config_id, tipo="musica", telefone="5511999999999", **kwargs):
    return FilaAoVivo(
        radio_config_id=radio_config_id,
        telefone=telefone,
        nome=kwargs.pop("nome", ""),
        tipo=tipo,
        mensagem_usuario=kwargs.pop("mensagem_usuario", "toca uma musica"),
        musica_query=kwargs.pop("musica_query", None),
        **kwargs,
    )


@freeze_time(AGORA_UTC)
def test_no_ar_com_programa_na_escala_agora(client, account, auth_headers, radialista_e_programa):
    radio_config, programa = radialista_e_programa

    resposta = client.get("/live/no-ar", headers=auth_headers(account.id))
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["no_ar"] is True
    assert corpo["radialista_id"] == radio_config.id
    assert corpo["programa_id"] == programa.id
    assert corpo["programa_nome"] == "Programa Principal"


@freeze_time("2026-08-10 23:00:00")  # 20:00 local, fora do 10:00-14:00
def test_no_ar_fora_do_horario_devolve_false(client, account, auth_headers, radialista_e_programa):
    resposta = client.get("/live/no-ar", headers=auth_headers(account.id))
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["no_ar"] is False
    assert corpo["radialista_id"] is None


@freeze_time(AGORA_UTC)
def test_no_ar_ignora_radialista_inativo(client, account, auth_headers, db_session, radialista_e_programa):
    radio_config, _ = radialista_e_programa
    radio_config.ativo = False
    db_session.commit()

    resposta = client.get("/live/no-ar", headers=auth_headers(account.id))
    assert resposta.json()["no_ar"] is False


def test_historico_fila_mais_recente_primeiro(client, account, auth_headers, db_session, radialista_e_programa):
    radio_config, _ = radialista_e_programa
    agora = datetime.datetime.now(datetime.timezone.utc)
    db_session.add_all(
        [
            _pedido_fila(radio_config.id, criado_em=agora - datetime.timedelta(minutes=10)),
            _pedido_fila(radio_config.id, criado_em=agora),
        ]
    )
    db_session.commit()

    resposta = client.get(f"/live/{radio_config.id}/fila/historico", headers=auth_headers(account.id))
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["total"] == 2
    assert corpo["pedidos"][0]["criado_em"] > corpo["pedidos"][1]["criado_em"]


def test_historico_fila_filtra_por_atendido(client, account, auth_headers, db_session, radialista_e_programa):
    radio_config, _ = radialista_e_programa
    db_session.add_all(
        [
            _pedido_fila(radio_config.id, atendido=True, atendido_em=datetime.datetime.now(datetime.timezone.utc)),
            _pedido_fila(radio_config.id, atendido=False),
        ]
    )
    db_session.commit()

    atendidos = client.get(
        f"/live/{radio_config.id}/fila/historico?atendido=true", headers=auth_headers(account.id)
    )
    assert atendidos.json()["total"] == 1
    assert atendidos.json()["pedidos"][0]["atendido"] is True

    pendentes = client.get(
        f"/live/{radio_config.id}/fila/historico?atendido=false", headers=auth_headers(account.id)
    )
    assert pendentes.json()["total"] == 1
    assert pendentes.json()["pedidos"][0]["atendido"] is False


def test_historico_fila_respeita_janela_de_dias(client, account, auth_headers, db_session, radialista_e_programa):
    radio_config, _ = radialista_e_programa
    agora = datetime.datetime.now(datetime.timezone.utc)
    db_session.add_all(
        [
            _pedido_fila(radio_config.id, criado_em=agora - datetime.timedelta(days=45)),
            _pedido_fila(radio_config.id, criado_em=agora),
        ]
    )
    db_session.commit()

    resposta = client.get(f"/live/{radio_config.id}/fila/historico?dias=30", headers=auth_headers(account.id))
    assert resposta.json()["total"] == 1


def test_historico_fila_pagina(client, account, auth_headers, db_session, radialista_e_programa):
    radio_config, _ = radialista_e_programa
    db_session.add_all([_pedido_fila(radio_config.id) for _ in range(5)])
    db_session.commit()

    resposta = client.get(
        f"/live/{radio_config.id}/fila/historico?pagina=1&tamanho_pagina=2", headers=auth_headers(account.id)
    )
    corpo = resposta.json()
    assert len(corpo["pedidos"]) == 2
    assert corpo["total"] == 5
    assert corpo["total_paginas"] == 3


def test_historico_fila_radialista_inexistente_404(client, account, auth_headers):
    resposta = client.get("/live/999999/fila/historico", headers=auth_headers(account.id))
    assert resposta.status_code == 404


def _outro_programa_mesma_radio(db_session, radio_config):
    outro = Programa(
        radio_config_id=radio_config.id,
        nome="Programa Da Tarde",
        horario_inicio=datetime.time(14, 0),
        horario_fim=datetime.time(18, 0),
        estrutura_blocos=[],
    )
    db_session.add(outro)
    db_session.commit()
    db_session.refresh(outro)
    return outro


@freeze_time(AGORA_UTC)
def test_musica_de_outro_programa_da_mesma_radio_e_evitada(
    client, account, auth_headers, radialista_e_programa, db_session, monkeypatch
):
    """Anti-repeticao cross-programa: musica tocada ha' pouco em OUTRO programa da mesma radio
    (mesmo video_id ou so' titulo em versao diferente) precisa entrar no evitar_video_ids/
    titulos_tocados passado pra buscar_musica no bloco automatico -- ver
    _musicas_recentes_da_radio em app.live.router."""
    radio_config, programa = radialista_e_programa
    outro_programa = _outro_programa_mesma_radio(db_session, radio_config)
    agora = datetime.datetime.now(datetime.timezone.utc)
    db_session.add(
        MusicaHistorico(
            programa_id=outro_programa.id,
            video_id="tocou-na-tarde",
            titulo="Artista X - Cancao Boa (Ao Vivo)",
            canal="Canal Y",
            query="cancao boa",
            query_normalizada="cancao boa",
            origem="auto",
            criado_em=agora - datetime.timedelta(hours=1),
        )
    )
    db_session.commit()

    monkeypatch.setattr("app.live.router.gerar_resposta", lambda system, msg: "Vamos ouvir essa!")
    chamadas_busca = []

    def _fake_buscar_musica(query, **kwargs):
        chamadas_busca.append(kwargs)
        return MusicaEncontrada(video_id="nova-musica", titulo="Outra Faixa", canal="Canal Z")

    monkeypatch.setattr("app.live.router.buscar_musica", _fake_buscar_musica)

    resposta = client.post(
        _url_proxima(radio_config.id, programa.id),
        json={"historico": ["abertura: oi"], "total_falas": 1},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 200
    assert resposta.json()["tipo"] == "musica"

    assert "tocou-na-tarde" in chamadas_busca[0]["evitar_video_ids"]
    assert "artista x cancao boa" in chamadas_busca[0]["titulos_tocados"]


@freeze_time(AGORA_UTC)
def test_musica_antiga_de_outro_programa_fora_da_janela_nao_e_evitada(
    client, account, auth_headers, radialista_e_programa, db_session, monkeypatch
):
    """Janela de 48h (_HORAS_JANELA_MUSICAS_RADIO): musica tocada em outro programa ha' mais
    tempo que isso nao deve mais travar a busca -- senao um catalogo pequeno de genero de nicho
    ficaria sem musica nenhuma pra tocar depois de alguns dias de transmissao."""
    radio_config, programa = radialista_e_programa
    outro_programa = _outro_programa_mesma_radio(db_session, radio_config)
    agora = datetime.datetime.now(datetime.timezone.utc)
    db_session.add(
        MusicaHistorico(
            programa_id=outro_programa.id,
            video_id="tocou-faz-tempo",
            titulo="Artista Antigo - Cancao Velha",
            canal="Canal Y",
            query="cancao velha",
            query_normalizada="cancao velha",
            origem="auto",
            criado_em=agora - datetime.timedelta(hours=49),
        )
    )
    db_session.commit()

    monkeypatch.setattr("app.live.router.gerar_resposta", lambda system, msg: "Vamos ouvir essa!")
    chamadas_busca = []

    def _fake_buscar_musica(query, **kwargs):
        chamadas_busca.append(kwargs)
        return MusicaEncontrada(video_id="nova-musica", titulo="Outra Faixa", canal="Canal Z")

    monkeypatch.setattr("app.live.router.buscar_musica", _fake_buscar_musica)

    resposta = client.post(
        _url_proxima(radio_config.id, programa.id),
        json={"historico": ["abertura: oi"], "total_falas": 1},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 200

    assert "tocou-faz-tempo" not in chamadas_busca[0]["evitar_video_ids"]
    assert "artista antigo cancao velha" not in chamadas_busca[0]["titulos_tocados"]


@freeze_time(AGORA_UTC)
def test_tema_de_outro_programa_e_injetado_no_prompt(
    client, account, auth_headers, radialista_e_programa, db_session, monkeypatch
):
    """Anti-repeticao cross-programa pro lado de assunto: tema comentado recentemente em OUTRO
    programa da mesma radio entra na instrucao 'nao repita assunto' do prompt, mesmo o
    historico de sessao (Redis) do programa atual estando vazio -- ver
    _temas_recentes_da_radio em app.live.router."""
    radio_config, programa = radialista_e_programa
    outro_programa = _outro_programa_mesma_radio(db_session, radio_config)
    agora = datetime.datetime.now(datetime.timezone.utc)
    db_session.add(
        TemaHistorico(programa_id=outro_programa.id, tema="eleicoes municipais", criado_em=agora - datetime.timedelta(hours=2))
    )
    db_session.commit()

    monkeypatch.setattr("app.live.router.classificar_tema_fala", lambda texto: "")
    prompts = []

    def _fake_gerar_resposta(system, msg):
        prompts.append(system)
        return "comentario qualquer"

    monkeypatch.setattr("app.live.router.gerar_resposta", _fake_gerar_resposta)

    # total_falas=3 cai no bloco "comentario" do roteiro padrao.
    resposta = client.post(
        _url_proxima(radio_config.id, programa.id),
        json={"historico": [], "total_falas": 3},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 200
    assert resposta.json()["tipo"] == "comentario"
    assert "eleicoes municipais" in prompts[0]


@freeze_time(AGORA_UTC)
def test_tema_antigo_de_outro_programa_fora_da_janela_nao_e_injetado(
    client, account, auth_headers, radialista_e_programa, db_session, monkeypatch
):
    """Janela de 7 dias (_DIAS_JANELA_TEMAS_RADIO): tema comentado ha' mais tempo que isso em
    outro programa nao deve mais aparecer na instrucao 'nao repita assunto'."""
    radio_config, programa = radialista_e_programa
    outro_programa = _outro_programa_mesma_radio(db_session, radio_config)
    agora = datetime.datetime.now(datetime.timezone.utc)
    db_session.add(
        TemaHistorico(programa_id=outro_programa.id, tema="assunto de semana passada", criado_em=agora - datetime.timedelta(days=8))
    )
    db_session.commit()

    monkeypatch.setattr("app.live.router.classificar_tema_fala", lambda texto: "")
    prompts = []

    def _fake_gerar_resposta(system, msg):
        prompts.append(system)
        return "comentario qualquer"

    monkeypatch.setattr("app.live.router.gerar_resposta", _fake_gerar_resposta)

    resposta = client.post(
        _url_proxima(radio_config.id, programa.id),
        json={"historico": [], "total_falas": 3},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 200
    assert "assunto de semana passada" not in prompts[0]


# ---------------------------------------------------------------------------
# Camada editorial: diversidade de assunto, timing e "programa legal de acompanhar"
# ---------------------------------------------------------------------------


@freeze_time(AGORA_UTC)
def test_pool_de_assuntos_roda_em_ordem_antes_de_repetir(
    client, account, auth_headers, radialista_e_programa, db_session, monkeypatch
):
    """A.3: assuntos_ao_vivo configurados viram fila rotativa persistida (mesmo primitivo
    round-robin de _proxima_variacao) -- cada bloco de comentario/noticia/chamada_ouvinte
    consome o proximo item da lista, ciclo completo antes de repetir."""
    radio_config, programa = radialista_e_programa
    programa.assuntos_ao_vivo = ["futebol de sabado", "aniversario da cidade", "trafego de pipoca"]
    db_session.commit()

    prompts = []
    monkeypatch.setattr(
        "app.live.router.gerar_resposta", lambda system, msg: prompts.append(system) or "comentario generico"
    )

    # total_falas 3, 8, 13 caem todos no bloco "comentario" do roteiro padrao.
    for total_falas in (3, 8, 13):
        resposta = client.post(
            _url_proxima(radio_config.id, programa.id),
            json={"historico": [], "total_falas": total_falas},
            headers=auth_headers(account.id),
        )
        assert resposta.status_code == 200
        assert resposta.json()["tipo"] == "comentario"

    assert "Assunto sugerido pra este bloco: futebol de sabado" in prompts[0]
    assert "Assunto sugerido pra este bloco: aniversario da cidade" in prompts[1]
    assert "Assunto sugerido pra este bloco: trafego de pipoca" in prompts[2]


@freeze_time(AGORA_UTC)
def test_formato_de_comentario_varia_entre_falas(
    client, account, auth_headers, radialista_e_programa, monkeypatch
):
    """D.1: formato da fala de comentario roda em rotacao (pergunta retorica, mini-lista,
    opiniao, convite a responder, monologo padrao), nao so o assunto."""
    radio_config, programa = radialista_e_programa
    prompts = []
    monkeypatch.setattr(
        "app.live.router.gerar_resposta", lambda system, msg: prompts.append(system) or "comentario generico"
    )

    # total_falas 3, 8, 13, 18, 23 caem todos no bloco "comentario" do roteiro padrao.
    for total_falas in (3, 8, 13, 18, 23):
        resposta = client.post(
            _url_proxima(radio_config.id, programa.id),
            json={"historico": [], "total_falas": total_falas},
            headers=auth_headers(account.id),
        )
        assert resposta.status_code == 200
        assert resposta.json()["tipo"] == "comentario"

    formatos = [
        next(linha for linha in prompt.split("\n") if linha.startswith("Para este comentário"))
        for prompt in prompts
    ]
    assert len(set(formatos)) == 5


@freeze_time(AGORA_UTC)
def test_pesquisa_sem_resultados_nao_autoriza_efemeride_inventada(
    client, account, auth_headers, radialista_e_programa, db_session, monkeypatch
):
    """Autorização para pesquisar não substitui uma fonte retornada pela busca."""
    radio_config, programa = radialista_e_programa
    programa.pode_pesquisar = True
    db_session.commit()

    prompts = []
    monkeypatch.setattr(
        "app.live.router.gerar_resposta", lambda system, msg: prompts.append(system) or "comentario generico"
    )

    resposta = client.post(
        _url_proxima(radio_config.id, programa.id),
        json={"historico": [], "total_falas": 3},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 200
    assert "data histórica marcante" not in prompts[0]
    assert "Não há notícias verificadas" in prompts[0]
    assert resposta.json()["pesquisa_noticias"]["status"] == "sem_resultados"


@freeze_time(AGORA_UTC)
def test_efemeride_instrucao_ausente_sem_pesquisa(
    client, account, auth_headers, radialista_e_programa, monkeypatch
):
    radio_config, programa = radialista_e_programa
    prompts = []
    monkeypatch.setattr(
        "app.live.router.gerar_resposta", lambda system, msg: prompts.append(system) or "comentario generico"
    )

    resposta = client.post(
        _url_proxima(radio_config.id, programa.id),
        json={"historico": [], "total_falas": 3},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 200
    assert "data histórica marcante" not in prompts[0]


@freeze_time(AGORA_UTC)
def test_nudge_noticia_leve_em_horario_leve(
    client, account, auth_headers, radialista_e_programa, db_session, monkeypatch
):
    """B.3: no horario de almoco (perfil 'leve', ver _perfil_editorial), bloco de noticia
    recebe um nudge pra preferir conteudo leve em vez de forcar noticia pesada."""
    radio_config, programa = radialista_e_programa
    programa.pode_pesquisar = True
    db_session.commit()

    prompts = []
    monkeypatch.setattr(
        "app.live.router.gerar_resposta", lambda system, msg: prompts.append(system) or "O tempo segue firme."
    )

    # total_falas=4 -> roteiro padrao cai em "noticia" (indice 3); AGORA_UTC = 12:00 local,
    # dentro do bucket "entretenimento leve" de _perfil_editorial.
    resposta = client.post(
        _url_proxima(radio_config.id, programa.id),
        json={"historico": [], "total_falas": 4},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 200
    assert resposta.json()["tipo"] == "noticia"
    assert "prefira notícia leve" in prompts[0]


@freeze_time(AGORA_UTC)
def test_quadro_fixo_consome_proprio_pool_em_rotacao(
    client, account, auth_headers, radialista_e_programa, db_session, monkeypatch
):
    """C.1: quadro fixo (label customizado dentro de estrutura_blocos, ex. "Curiosidade das
    10") tem seu proprio pool de conteudo (programa.quadros_fixos), consumido em rotacao a
    cada vez que o bloco sai no roteiro."""
    radio_config, programa = radialista_e_programa
    programa.estrutura_blocos = ["Curiosidade das 10"]
    programa.quadros_fixos = {"Curiosidade das 10": ["curiosidade um", "curiosidade dois"]}
    # desliga a insercao aleatoria de comentario extra fora da estrutura (ver _tipo_proximo_bloco)
    # pra o teste nao flakar: com ela ligada, ha' 15% de chance do 2o bloco (total_falas=1) cair
    # em "comentario" avulso em vez do quadro fixo customizado.
    programa.ia_pode_adicionar_blocos = False
    db_session.commit()

    monkeypatch.setattr("app.live.router.classificar_categoria_bloco", lambda nome: "comentario")
    monkeypatch.setattr("app.live.router.classificar_tema_fala", lambda texto: "")

    prompts = []
    monkeypatch.setattr(
        "app.live.router.gerar_resposta", lambda system, msg: prompts.append(system) or "curiosidade generica"
    )

    for total_falas in (0, 1):
        resposta = client.post(
            _url_proxima(radio_config.id, programa.id),
            json={"historico": [], "total_falas": total_falas},
            headers=auth_headers(account.id),
        )
        assert resposta.status_code == 200

    assert "quadro fixo 'Curiosidade das 10'" in prompts[0]
    assert "curiosidade um" in prompts[0]
    assert "curiosidade dois" in prompts[1]
    # quadro fixo ja da o conteudo especifico -- nao soma com o pool generico de assuntos.
    assert "Assunto sugerido pra este bloco" not in prompts[0]


def test_fio_condutor_da_abertura_e_retomado_no_encerramento(
    client, account, auth_headers, radialista_e_programa, monkeypatch
):
    """C.2: pergunta/expectativa lancada na abertura (ver classificar_fio_condutor) fica
    guardada na sessao e e' referenciada de volta no bloco de encerramento -- um arco que
    atravessa o programa inteiro, nao so' conexao bloco-a-bloco."""
    radio_config, programa = radialista_e_programa
    monkeypatch.setattr(
        "app.live.router.classificar_fio_condutor",
        lambda texto: "será que hoje bate recorde de calor",
    )

    with freeze_time(AGORA_UTC):
        monkeypatch.setattr(
            "app.live.router.gerar_resposta",
            lambda system, msg: "Bom dia! Será que hoje bate recorde de calor?",
        )
        r1 = client.post(
            _url_proxima(radio_config.id, programa.id),
            json={"historico": [], "total_falas": 0},
            headers=auth_headers(account.id),
        )
        assert r1.status_code == 200
        assert r1.json()["tipo"] == "abertura"

    prompts = []
    with freeze_time("2026-08-10 16:58:00"):  # 13:58 local -- 2 min antes do fim (14:00)
        monkeypatch.setattr(
            "app.live.router.gerar_resposta",
            lambda system, msg: prompts.append(system) or "Foi um prazer, até mais!",
        )
        r2 = client.post(
            _url_proxima(radio_config.id, programa.id),
            json={"historico": ["abertura: oi"], "total_falas": 3},
            headers=auth_headers(account.id),
        )
        assert r2.status_code == 200
        assert r2.json()["tipo"] == "encerramento"

    assert "será que hoje bate recorde de calor" in prompts[0]


@freeze_time(AGORA_UTC)
def test_ouvinte_recorrente_e_citado_quando_reaparece(
    client, account, auth_headers, radialista_e_programa, db_session, monkeypatch
):
    """C.3: ouvinte que ja mandou mensagem antes na mesma transmissao (mesmo nome, pedido ja
    atendido dentro da janela de sessao) e' citado como recorrente quando manda outra
    mensagem -- sensacao de programa vivo com gente de verdade interagindo."""
    radio_config, programa = radialista_e_programa
    agora = datetime.datetime.now(datetime.timezone.utc)
    pedido_antigo = FilaAoVivo(
        radio_config_id=radio_config.id,
        telefone="5511999999999",
        nome="Ze",
        tipo="musica",
        mensagem_usuario="toca uma sofrencia",
        atendido=True,
        atendido_em=agora - datetime.timedelta(minutes=30),
        criado_em=agora - datetime.timedelta(minutes=30),
    )
    pedido_novo = FilaAoVivo(
        radio_config_id=radio_config.id,
        telefone="5511999999999",
        nome="Ze",
        tipo="abraco",
        mensagem_usuario="mais um oi",
        criado_em=agora,
    )
    db_session.add_all([pedido_antigo, pedido_novo])
    db_session.commit()

    prompts = []
    monkeypatch.setattr(
        "app.live.router.gerar_resposta", lambda system, msg: prompts.append(system) or "Fala Ze!"
    )

    # total_falas=5 -> roteiro padrao cai em "chamada_ouvinte" (indice 4).
    resposta = client.post(
        _url_proxima(radio_config.id, programa.id),
        json={"historico": [], "total_falas": 5},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 200
    assert resposta.json()["tipo"] == "chamada_ouvinte"
    assert "Ze já apareceu antes nesta transmissão pedindo uma música" in prompts[0]


@freeze_time(AGORA_UTC)
def test_ouvinte_sem_pedido_anterior_nao_e_citado_como_recorrente(
    client, account, auth_headers, radialista_e_programa, db_session, monkeypatch
):
    radio_config, programa = radialista_e_programa
    pedido = FilaAoVivo(
        radio_config_id=radio_config.id,
        telefone="5511999999999",
        nome="Maria",
        tipo="abraco",
        mensagem_usuario="oi pela primeira vez",
    )
    db_session.add(pedido)
    db_session.commit()

    prompts = []
    monkeypatch.setattr(
        "app.live.router.gerar_resposta", lambda system, msg: prompts.append(system) or "Fala Maria!"
    )

    resposta = client.post(
        _url_proxima(radio_config.id, programa.id),
        json={"historico": [], "total_falas": 5},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 200
    assert "já apareceu antes nesta transmissão" not in prompts[0]


@freeze_time(AGORA_UTC)
def test_pedido_de_sorteio_nao_confirma_inscricao_sem_registro(
    client, account, auth_headers, radialista_e_programa, db_session, monkeypatch
):
    """A fila de pedidos não é um cadastro verificado de inscrições."""
    radio_config, programa = radialista_e_programa
    pedido = FilaAoVivo(
        radio_config_id=radio_config.id,
        telefone="5511999999999",
        nome="Joana",
        tipo="sorteio",
        mensagem_usuario="quero participar do sorteio",
    )
    db_session.add(pedido)
    db_session.commit()

    prompts = []
    monkeypatch.setattr(
        "app.live.router.gerar_resposta", lambda system, msg: prompts.append(system) or "Joana, recebemos seu contato sobre o sorteio."
    )

    resposta = client.post(
        _url_proxima(radio_config.id, programa.id),
        json={"historico": [], "total_falas": 5},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 200
    assert "Joana enviou uma solicitação sobre o sorteio" in prompts[0]
    assert "Não confirme inscrição" in prompts[0]

    pedido_atualizado = db_session.query(FilaAoVivo).filter_by(id=pedido.id).first()
    assert pedido_atualizado.atendido is True


@freeze_time(AGORA_UTC)
def test_pedido_de_abraco_reacao_calibrada_pelo_tom(
    client, account, auth_headers, radialista_e_programa, db_session, monkeypatch
):
    """Frente S: a instrucao de reacao ao pedido de abraco referencia explicitamente o tom do
    programa, em vez de so' pedir um comentario generico."""
    radio_config, programa = radialista_e_programa
    pedido = FilaAoVivo(
        radio_config_id=radio_config.id,
        telefone="5511999999999",
        nome="Pedro",
        tipo="abraco",
        mensagem_usuario="mandando um alo daqui",
    )
    db_session.add(pedido)
    db_session.commit()

    prompts = []
    monkeypatch.setattr(
        "app.live.router.gerar_resposta", lambda system, msg: prompts.append(system) or "E aí, Pedro!"
    )

    resposta = client.post(
        _url_proxima(radio_config.id, programa.id),
        json={"historico": [], "total_falas": 5},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 200
    assert "calibre a reação pelo tom do programa" in prompts[0]


@freeze_time(AGORA_UTC)
def test_pedido_com_natureza_reacao_engracada_gera_instrucao_de_brincar_junto(
    client, account, auth_headers, radialista_e_programa, db_session, monkeypatch
):
    """Frente T: natureza reacao_engracada troca o catch-all generico por instrucao especifica
    de brincar junto com o ouvinte."""
    radio_config, programa = radialista_e_programa
    pedido = FilaAoVivo(
        radio_config_id=radio_config.id,
        telefone="5511999999999",
        nome="Bia",
        tipo="abraco",
        natureza="reacao_engracada",
        mensagem_usuario="kkkkk vim so mandar uma piada ruim",
    )
    db_session.add(pedido)
    db_session.commit()

    prompts = []
    monkeypatch.setattr(
        "app.live.router.gerar_resposta", lambda system, msg: prompts.append(system) or "Kkk, boa Bia!"
    )

    resposta = client.post(
        _url_proxima(radio_config.id, programa.id),
        json={"historico": [], "total_falas": 5},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 200
    assert "é uma mensagem bem-humorada" in prompts[0]


@freeze_time(AGORA_UTC)
def test_pedido_com_natureza_reclamacao_gera_instrucao_de_reconhecer_com_respeito(
    client, account, auth_headers, radialista_e_programa, db_session, monkeypatch
):
    """Frente T: natureza reclamacao pede reconhecimento respeitoso, nao reacao bem-humorada."""
    radio_config, programa = radialista_e_programa
    pedido = FilaAoVivo(
        radio_config_id=radio_config.id,
        telefone="5511999999999",
        nome="Carlos",
        tipo="abraco",
        natureza="reclamacao",
        mensagem_usuario="o sinal da radio ta chiando muito hoje",
    )
    db_session.add(pedido)
    db_session.commit()

    prompts = []
    monkeypatch.setattr(
        "app.live.router.gerar_resposta", lambda system, msg: prompts.append(system) or "Valeu pelo aviso, Carlos!"
    )

    resposta = client.post(
        _url_proxima(radio_config.id, programa.id),
        json={"historico": [], "total_falas": 5},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 200
    assert "é uma reclamação ou crítica" in prompts[0]


@freeze_time(AGORA_UTC)
def test_pedido_com_natureza_pergunta_gera_instrucao_de_responder(
    client, account, auth_headers, radialista_e_programa, db_session, monkeypatch
):
    """Frente T: natureza pergunta pede resposta de verdade em vez de so' reagir ao clima."""
    radio_config, programa = radialista_e_programa
    pedido = FilaAoVivo(
        radio_config_id=radio_config.id,
        telefone="5511999999999",
        nome="Ana",
        tipo="abraco",
        natureza="pergunta",
        mensagem_usuario="que horas termina o programa hoje?",
    )
    db_session.add(pedido)
    db_session.commit()

    prompts = []
    monkeypatch.setattr(
        "app.live.router.gerar_resposta", lambda system, msg: prompts.append(system) or "Boa pergunta, Ana!"
    )

    resposta = client.post(
        _url_proxima(radio_config.id, programa.id),
        json={"historico": [], "total_falas": 5},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 200
    assert "responda de verdade a pergunta" in prompts[0]


@freeze_time(AGORA_UTC)  # 12:00 local, exatamente na metade de um programa 10:00-14:00
def test_marco_tempo_metade_do_programa_mencionado(
    client, account, auth_headers, radialista_e_programa, monkeypatch
):
    """B.4: aritmetica pura sobre horario_inicio/horario_fim -- marco de tempo so aparece com
    o gate probabilistico (aqui forcado a sempre disparar)."""
    radio_config, programa = radialista_e_programa
    monkeypatch.setattr("app.live.router.random.random", lambda: 0.0)

    prompts = []
    monkeypatch.setattr(
        "app.live.router.gerar_resposta", lambda system, msg: prompts.append(system) or "Seguimos no ar."
    )

    resposta = client.post(
        _url_proxima(radio_config.id, programa.id),
        json={"historico": [], "total_falas": 3},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 200
    assert "na metade do programa de hoje" in prompts[0]


@freeze_time("2026-08-10 13:05:00")  # 10:05 local -- 5 min apos o inicio (10:00) do programa
def test_marco_tempo_inicio_do_programa_mencionado(
    client, account, auth_headers, radialista_e_programa, monkeypatch
):
    radio_config, programa = radialista_e_programa
    monkeypatch.setattr("app.live.router.random.random", lambda: 0.0)

    prompts = []
    monkeypatch.setattr(
        "app.live.router.gerar_resposta", lambda system, msg: prompts.append(system) or "Bom dia!"
    )

    resposta = client.post(
        _url_proxima(radio_config.id, programa.id),
        json={"historico": [], "total_falas": 3},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 200
    assert "acabou de começar agora" in prompts[0]


@freeze_time(AGORA_UTC)
def test_ajuste_energia_no_miolo_do_programa(client, account, auth_headers, radialista_e_programa, monkeypatch):
    """I.3: no meio do programa (12:00 de um programa 10:00-14:00, ver AGORA_UTC), a instrucao de
    energia mais contida aparece mesmo sem gate probabilistico -- e' aritmetica de tempo, nao sorteio."""
    radio_config, programa = radialista_e_programa

    prompts = []
    monkeypatch.setattr(
        "app.live.router.gerar_resposta", lambda system, msg: prompts.append(system) or "Seguimos no ar."
    )

    resposta = client.post(
        _url_proxima(radio_config.id, programa.id),
        json={"historico": [], "total_falas": 3},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 200
    assert "energia um pouco mais contida" in prompts[0]


@freeze_time("2026-08-10 13:05:00")  # 10:05 local -- so 5min decorridos, fora do miolo (30%-70%)
def test_sem_ajuste_de_energia_no_inicio_do_programa(
    client, account, auth_headers, radialista_e_programa, monkeypatch
):
    radio_config, programa = radialista_e_programa

    prompts = []
    monkeypatch.setattr(
        "app.live.router.gerar_resposta", lambda system, msg: prompts.append(system) or "Bom dia!"
    )

    resposta = client.post(
        _url_proxima(radio_config.id, programa.id),
        json={"historico": [], "total_falas": 3},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 200
    assert "energia um pouco mais contida" not in prompts[0]


@freeze_time(AGORA_UTC)
def test_mudanca_de_ideia_com_gate_forcado(client, account, auth_headers, radialista_e_programa, monkeypatch):
    """I.1: gate probabilistico forcado (random=0.0) pra instrucao de mudanca genuina de ideia
    no meio da fala -- categoria comentario (total_falas=3), nunca em noticia."""
    radio_config, programa = radialista_e_programa
    monkeypatch.setattr("app.live.router.random.random", lambda: 0.0)

    prompts = []
    monkeypatch.setattr(
        "app.live.router.gerar_resposta", lambda system, msg: prompts.append(system) or "Seguimos no ar."
    )

    resposta = client.post(
        _url_proxima(radio_config.id, programa.id),
        json={"historico": [], "total_falas": 3},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 200
    assert "genuinamente mudar de ideia" in prompts[0]


@freeze_time(AGORA_UTC)
def test_imperfeicao_gramatical_com_gate_forcado(client, account, auth_headers, radialista_e_programa, monkeypatch):
    """I.4: mesmo gate forcado, agora pra concordancia coloquial calibrada."""
    radio_config, programa = radialista_e_programa
    monkeypatch.setattr("app.live.router.random.random", lambda: 0.0)

    prompts = []
    monkeypatch.setattr(
        "app.live.router.gerar_resposta", lambda system, msg: prompts.append(system) or "Seguimos no ar."
    )

    resposta = client.post(
        _url_proxima(radio_config.id, programa.id),
        json={"historico": [], "total_falas": 3},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 200
    assert "concordância um pouco mais coloquial" in prompts[0]


@freeze_time(AGORA_UTC)
def test_noticia_nunca_recebe_mudanca_de_ideia_nem_imperfeicao(
    client, account, auth_headers, radialista_e_programa, db_session, monkeypatch
):
    radio_config, programa = radialista_e_programa
    # Sem isso, categoria "noticia" cai automaticamente pra "musica" (sem fonte configurada --
    # ver gerar_proxima_fala) e o bloco resolvido nunca seria noticia de verdade.
    programa.tipos_noticias = ["geral"]
    db_session.commit()
    monkeypatch.setattr("app.live.router.random.random", lambda: 0.0)

    prompts = []
    monkeypatch.setattr(
        "app.live.router.gerar_resposta", lambda system, msg: prompts.append(system) or "E foi isso."
    )

    # total_falas=4 -> roteiro padrao cai em "noticia" (indice 3).
    resposta = client.post(
        _url_proxima(radio_config.id, programa.id),
        json={"historico": [], "total_falas": 4},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 200
    assert resposta.json()["tipo"] == "noticia"
    assert "genuinamente mudar de ideia" not in prompts[0]
    assert "concordância um pouco mais coloquial" not in prompts[0]


@freeze_time(AGORA_UTC)
def test_pedido_recente_gera_instrucao_de_interrupcao(
    client, account, auth_headers, radialista_e_programa, db_session, monkeypatch
):
    """I.2: pedido que chegou ha pouco (dentro da janela) enquanto o bloco atual e' outro tipo
    (comentario) -- pode gerar interrupcao natural, sem consumir o pedido de verdade."""
    radio_config, programa = radialista_e_programa
    pedido = FilaAoVivo(
        radio_config_id=radio_config.id,
        telefone="5511988887777",
        nome="Carla",
        tipo="abraco",
        mensagem_usuario="acabei de chegar",
        atendido=False,
        criado_em=datetime.datetime.now(datetime.timezone.utc),
    )
    db_session.add(pedido)
    db_session.commit()

    prompts = []
    monkeypatch.setattr(
        "app.live.router.gerar_resposta", lambda system, msg: prompts.append(system) or "Seguimos no ar."
    )

    resposta = client.post(
        _url_proxima(radio_config.id, programa.id),
        json={"historico": [], "total_falas": 3},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 200
    assert "Acabou de chegar uma mensagem nova" in prompts[0]
    # so' espiou -- pedido continua nao atendido pro bloco chamada_ouvinte de verdade consumir depois.
    db_session.refresh(pedido)
    assert pedido.atendido is False


@freeze_time(AGORA_UTC)
def test_pedido_antigo_nao_gera_instrucao_de_interrupcao(
    client, account, auth_headers, radialista_e_programa, db_session, monkeypatch
):
    radio_config, programa = radialista_e_programa
    pedido = FilaAoVivo(
        radio_config_id=radio_config.id,
        telefone="5511988887777",
        nome="Carla",
        tipo="abraco",
        mensagem_usuario="mensagem de ha muito tempo",
        atendido=False,
        criado_em=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=10),
    )
    db_session.add(pedido)
    db_session.commit()

    prompts = []
    monkeypatch.setattr(
        "app.live.router.gerar_resposta", lambda system, msg: prompts.append(system) or "Seguimos no ar."
    )

    resposta = client.post(
        _url_proxima(radio_config.id, programa.id),
        json={"historico": [], "total_falas": 3},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 200
    assert "Acabou de chegar uma mensagem nova" not in prompts[0]


@freeze_time(AGORA_UTC)
def test_callback_tema_de_transmissao_anterior(
    client, account, auth_headers, radialista_e_programa, db_session, monkeypatch
):
    """J.1: reaproveita TemaHistorico ja persistente (outras transmissoes da mesma radio) pra
    sugerir callback explicito -- gate forcado, tema vem de uma transmissao anterior (sessao
    Redis atual esta vazia/fresca no teste)."""
    radio_config, programa = radialista_e_programa
    db_session.add(TemaHistorico(programa_id=programa.id, tema="Trânsito parado na BR-101"))
    db_session.commit()

    monkeypatch.setattr("app.live.router.random.random", lambda: 0.0)
    prompts = []
    monkeypatch.setattr(
        "app.live.router.gerar_resposta", lambda system, msg: prompts.append(system) or "Seguimos no ar."
    )

    resposta = client.post(
        _url_proxima(radio_config.id, programa.id),
        json={"historico": [], "total_falas": 3},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 200
    assert "callback explícito" in prompts[0]
    assert "Trânsito parado na BR-101" in prompts[0]


@freeze_time(AGORA_UTC)
def test_ouvinte_recorrente_de_dias_anteriores_e_citado(
    client, account, auth_headers, radialista_e_programa, db_session, monkeypatch
):
    """J.2: mesmo telefone, pedido atendido ha 5 dias (fora da janela de sessao de 6h, dentro da
    janela de 30 dias) -- reconhecido como "ja apareceu em dias diferentes", nao "nesta transmissao"."""
    radio_config, programa = radialista_e_programa
    agora = datetime.datetime.now(datetime.timezone.utc)
    pedido_de_dias_atras = FilaAoVivo(
        radio_config_id=radio_config.id,
        telefone="5511977776666",
        nome="Roberto",
        tipo="musica",
        mensagem_usuario="toca uma antiga",
        atendido=True,
        atendido_em=agora - datetime.timedelta(days=5),
        criado_em=agora - datetime.timedelta(days=5),
    )
    pedido_novo = FilaAoVivo(
        radio_config_id=radio_config.id,
        telefone="5511977776666",
        nome="Roberto",
        tipo="abraco",
        mensagem_usuario="voltei",
        criado_em=agora,
    )
    db_session.add_all([pedido_de_dias_atras, pedido_novo])
    db_session.commit()

    prompts = []
    monkeypatch.setattr(
        "app.live.router.gerar_resposta", lambda system, msg: prompts.append(system) or "Fala Roberto!"
    )

    # total_falas=5 -> roteiro padrao cai em "chamada_ouvinte" (indice 4).
    resposta = client.post(
        _url_proxima(radio_config.id, programa.id),
        json={"historico": [], "total_falas": 5},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 200
    assert "já apareceu em uma transmissão de outro dia" in prompts[0]
    assert "já apareceu antes nesta transmissão" not in prompts[0]


@freeze_time(AGORA_UTC)
def test_radio_fm_processa_audio_embutido_e_endpoint_tts(
    client, account, auth_headers, radialista_e_programa, monkeypatch
):
    import base64
    import io
    from pydub import AudioSegment
    from pydub.generators import Sine

    radio_config, programa = radialista_e_programa
    buffer = io.BytesIO()
    Sine(220).to_audio_segment(duration=1000).apply_gain(-12).export(buffer, format="mp3")
    original = buffer.getvalue()
    monkeypatch.setattr("app.live.router.gerar_resposta", lambda *a, **kw: "Bom dia, ouvintes.")
    monkeypatch.setattr("app.live.router.tts_habilitado", lambda *a: True)
    monkeypatch.setattr("app.live.router.classificar_tom_fala", lambda *a: "neutro")
    monkeypatch.setattr("app.live.router.sintetizar_audio", lambda *a, **kw: original)
    headers = auth_headers(account.id)
    proxima = client.post(_url_proxima(radio_config.id, programa.id),
                          json={"total_falas": 0, "perfil_pos_producao": "radio_fm"}, headers=headers)
    assert proxima.status_code == 200
    assert proxima.json()["audio_status"] == "pronto"
    embutido = base64.b64decode(proxima.json()["audio_base64"])
    avulso = client.post(f"/live/{radio_config.id}/tts",
                         json={"texto": "Bom dia, ouvintes.", "perfil_pos_producao": "radio_fm"}, headers=headers)
    assert avulso.status_code == 200
    assert embutido == avulso.content
    assert embutido != original
    assert abs(len(AudioSegment.from_file(io.BytesIO(embutido), format="mp3")) - 1000) < 50


@pytest.fixture()
def programa_musical(radialista_e_programa, db_session, monkeypatch):
    radialista, programa = radialista_e_programa
    programa.perfil_programacao = "musical_companhia"
    db_session.commit()
    monkeypatch.setattr("app.live.router.classificar_fio_condutor", lambda _: "")
    monkeypatch.setattr("app.live.router.resumir_contexto_musica", lambda *_: "")
    monkeypatch.setattr("app.live.router.random.random", lambda: 1.0)
    return radialista, programa


@freeze_time(AGORA_UTC)
def test_musical_toca_sequencia_sem_llm_de_locucao_ou_tts(
    client, account, auth_headers, programa_musical, monkeypatch
):
    from unittest.mock import Mock
    radialista, programa = programa_musical
    gerar = Mock(side_effect=AssertionError("não gerar fala para música sem pedido"))
    tts = Mock(side_effect=AssertionError("não sintetizar texto vazio"))
    monkeypatch.setattr("app.live.router.gerar_resposta", gerar)
    monkeypatch.setattr("app.live.router.sintetizar_audio", tts)
    monkeypatch.setattr("app.live.router._buscar_musica_para_bloco", lambda *_: MusicaEncontrada(
        video_id="faixa123", titulo="Clássico", canal="Artista", duracao_segundos=240,
    ))
    r = client.post(_url_proxima(radialista.id, programa.id), headers=auth_headers(account.id),
                    json={"total_falas": 2, "historico": ["musica: faixa anterior"]})
    assert r.status_code == 200
    d = r.json()
    assert d["video_id"] == "faixa123"
    assert d["musicas"][0]["canal"] == "Artista"
    assert d["fala"] == ""
    assert d["audio_status"] == "nao_aplicavel"
    assert d["pausa_antes_ms"] == 0
    gerar.assert_not_called()
    tts.assert_not_called()


def test_musical_repete_sequencia_sem_reabrir_ou_inserir_comentarios(programa_musical, monkeypatch):
    from app.live.router import _tipo_proximo_bloco
    _, programa = programa_musical
    monkeypatch.setattr("app.live.router.random.random", lambda: 0.0)
    tipos = [_tipo_proximo_bloco(programa, n, "musica") for n in range(13)]
    assert tipos == ["abertura"] + ["musica", "musica", "identificacao", "musica", "musica", "retomada"] * 2
    programa.estrutura_blocos = ["abertura", "musica", "vinheta:9", "retomada", "encerramento"]
    tipos = [_tipo_proximo_bloco(programa, n, "musica") for n in range(7)]
    assert tipos == ["abertura", "musica", "vinheta:9", "retomada", "musica", "vinheta:9", "retomada"]


@freeze_time(AGORA_UTC)
def test_musical_revisa_retomada_longa_uma_vez(
    client, account, auth_headers, programa_musical, monkeypatch
):
    radialista, programa = programa_musical
    prompts = []
    curta = "Bom ter sua companhia! A seleção de clássicos continua por aqui."
    def gerar(system, msg):
        prompts.append(system)
        return "Esta seleção acompanha seu dia com música. " * 12 if len(prompts) == 1 else curta
    monkeypatch.setattr("app.live.router.gerar_resposta", gerar)
    r = client.post(_url_proxima(radialista.id, programa.id), headers=auth_headers(account.id),
                    json={"total_falas": 6, "historico": ["musica: faixa anterior"]})
    assert r.status_code == 200
    assert r.json()["tipo"] == "retomada"
    assert r.json()["fala"] == curta
    assert r.json()["duracao_alvo_segundos"] == [6, 12]
    assert len(prompts) == 2
    assert "no máximo 25 palavras" in prompts[1]
    assert "A fala deve durar o equivalente a umas 4 a 6 frases" not in prompts[0]
    assert "hesitação pontual" not in prompts[0]


@freeze_time(AGORA_UTC)
def test_musical_pedido_real_continua_anunciado(
    client, account, auth_headers, programa_musical, db_session, monkeypatch
):
    radialista, programa = programa_musical
    account.atendimento_ouvinte_ativo = False
    db_session.add(FilaAoVivo(radio_config_id=radialista.id, telefone="5500000000000", nome="Ana",
                             tipo="musica", mensagem_usuario="Quero ouvir Clássico", musica_query="Clássico"))
    db_session.commit()
    monkeypatch.setattr("app.live.router.buscar_musica", lambda *_, **kw: MusicaEncontrada(
        video_id="pedido123", titulo="Clássico", canal="Artista"))
    monkeypatch.setattr("app.live.router.gerar_resposta", lambda *_: "A Ana pediu e vem aí: Clássico!")
    r = client.post(_url_proxima(radialista.id, programa.id), headers=auth_headers(account.id),
                    json={"total_falas": 1, "historico": ["abertura: Bom dia"]})
    assert r.status_code == 200
    assert r.json()["fala"] == "A Ana pediu e vem aí: Clássico!"
    assert r.json()["video_id"] == "pedido123"
    assert r.json()["duracao_alvo_segundos"] == [4, 8]


@freeze_time("2026-08-10 16:59:30")
def test_musical_encerra_perto_do_fim_em_vez_de_iniciar_outra_musica(
    client, account, auth_headers, programa_musical, monkeypatch
):
    radialista, programa = programa_musical
    monkeypatch.setattr("app.live.router.gerar_resposta", lambda *_: "Obrigado pela companhia, até a próxima!")
    r = client.post(_url_proxima(radialista.id, programa.id), headers=auth_headers(account.id),
                    json={"total_falas": 7, "historico": ["retomada: Seguimos juntos"]})
    assert r.status_code == 200
    assert r.json()["tipo"] == "encerramento"
    assert r.json()["duracao_alvo_segundos"] == [10, 18]
    assert r.json()["video_id"] is None


@freeze_time(AGORA_UTC)
def test_preferencias_da_voz_chegam_aos_tres_caminhos_de_audio(
    client, account, auth_headers, radialista_e_programa, db_session, monkeypatch
):
    from app.models.perfil_voz import ConfiguracaoVoz, MetadadosVoz
    radialista, programa = radialista_e_programa
    monkeypatch.setattr('app.tts.profiles.settings.elevenlabs_voice_id', 'padrao-pvc')
    db_session.add_all([
        MetadadosVoz(voz_id='padrao-pvc', categoria='professional'),
        ConfiguracaoVoz(account_id=account.id, voz_id='padrao-pvc', modelo='eleven_multilingual_v2',
                        perfil='natural', formato='mp3_44100_192', pronuncias={'Locufy': 'Locufai'}),
    ])
    db_session.commit()
    chamadas = []
    def sintetizar(*args, **kwargs):
        chamadas.append(kwargs)
        return b'audio'
    monkeypatch.setattr('app.live.router.tts_habilitado', lambda *a: True)
    monkeypatch.setattr('app.live.router.gerar_resposta', lambda *a, **kw: 'Boa tarde, ouvintes.')
    monkeypatch.setattr('app.live.router.sintetizar_audio', sintetizar)
    monkeypatch.setattr('app.live.router.sintetizar_audio_stream', lambda *a, **kw: iter([sintetizar(*a, **kw)]))
    monkeypatch.setattr('app.live.router.processar_audio', lambda audio, perfil: audio)
    monkeypatch.setattr('app.live.router.classificar_tom_fala', lambda *a: 'neutro')
    headers = auth_headers(account.id)
    resposta = client.post(_url_proxima(radialista.id, programa.id), json={'total_falas': 0}, headers=headers)
    assert resposta.status_code == 200
    assert resposta.json()['audio_status'] == 'pronto'
    for extra in ({}, {'perfil_pos_producao': 'radio_fm'}):
        resposta = client.post(f'/live/{radialista.id}/tts', json={'texto': 'Olá', **extra}, headers=headers)
        assert resposta.status_code == 200
        assert resposta.content == b'audio'
    assert len(chamadas) == 3
    for chamada in chamadas:
        assert {k: chamada[k] for k in ('eh_clonada', 'modelo', 'perfil', 'formato', 'pronuncias')} == {
            'eh_clonada': False, 'modelo': 'eleven_multilingual_v2', 'perfil': 'natural',
            'formato': 'mp3_44100_192', 'pronuncias': {'Locufy': 'Locufai'},
        }


def test_voz_padrao_pendente_bloqueia_sintese(client, account, auth_headers, radialista_e_programa, db_session, monkeypatch):
    from app.models.perfil_voz import MetadadosVoz
    from unittest.mock import Mock
    radialista, _ = radialista_e_programa
    monkeypatch.setattr('app.tts.profiles.settings.elevenlabs_voice_id', 'padrao-pendente')
    db_session.add(MetadadosVoz(voz_id='padrao-pendente', categoria='cloned', requer_verificacao=True))
    db_session.commit()
    monkeypatch.setattr('app.live.router.tts_habilitado', lambda *a: True)
    sintetizar = Mock(side_effect=AssertionError('Não pode sintetizar voz pendente'))
    monkeypatch.setattr('app.live.router.sintetizar_audio_stream', sintetizar)
    resposta = client.post(f'/live/{radialista.id}/tts', json={'texto': 'Olá'}, headers=auth_headers(account.id))
    assert resposta.status_code == 409
    sintetizar.assert_not_called()
