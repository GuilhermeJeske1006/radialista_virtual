import datetime
import json

import pytest
from freezegun import freeze_time

from app.live.music import MusicaEncontrada
from app.live.router import _escolher_query_musica, _registrar_historico_persistente
from app.models.biblioteca_audio import BibliotecaAudioItem
from app.models.fila_ao_vivo import FilaAoVivo
from app.models.musica_historico import MusicaHistorico
from app.models.patrocinador import Patrocinador
from app.models.programa import Programa
from app.models.programa_radialista import ProgramaRadialista
from app.models.radio_config import RadioConfig

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
        lambda generos, bloqueados=None: MusicaEncontrada(video_id="bg1", titulo="Fundo", canal="Canal"),
    )
    resposta = client.get(
        f"/live/{radio_config.id}/programas/{programa.id}/musica-fundo", headers=auth_headers(account.id)
    )
    assert resposta.status_code == 200
    assert resposta.json()["video_id"] == "bg1"


@freeze_time(AGORA_UTC)
def test_musica_de_fundo_sem_resultado_404(client, account, auth_headers, radialista_e_programa, monkeypatch):
    radio_config, programa = radialista_e_programa
    monkeypatch.setattr("app.live.router.buscar_musica_fundo", lambda generos, bloqueados=None: None)
    resposta = client.get(
        f"/live/{radio_config.id}/programas/{programa.id}/musica-fundo", headers=auth_headers(account.id)
    )
    assert resposta.status_code == 404


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
        "app.live.router.sintetizar_audio", lambda texto, voz_id, tipo_bloco=None, tom=None: b"audio-bytes"
    )

    resposta = client.post(
        f"/live/{radio_config.id}/tts", json={"texto": "ola ouvintes"}, headers=auth_headers(account.id)
    )
    assert resposta.status_code == 200
    assert resposta.content == b"audio-bytes"


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
        "app.live.router.sintetizar_audio", lambda texto, voz_id, tipo_bloco=None, tom=None: b"audio-cru"
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


def test_tts_endpoint_com_perfil_pos_producao_invalido_400(
    client, account, auth_headers, radialista_e_programa, monkeypatch
):
    radio_config, _ = radialista_e_programa
    monkeypatch.setattr("app.live.router.tts_habilitado", lambda voz_id=None: True)
    monkeypatch.setattr("app.live.router.classificar_tom_fala", lambda texto, tipo: "neutro")
    monkeypatch.setattr(
        "app.live.router.sintetizar_audio", lambda texto, voz_id, tipo_bloco=None, tom=None: b"audio-cru"
    )

    resposta = client.post(
        f"/live/{radio_config.id}/tts",
        json={"texto": "ola", "perfil_pos_producao": "perfil-que-nao-existe"},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 400


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

    query, genero = _escolher_query_musica(db_session, programa)

    assert genero is None
    assert "Musica A" in capturado["population"]
    assert "Musica B" in capturado["population"]
    assert "sofrencia pedida" in capturado["population"]
    indice_sofrencia = capturado["population"].index("sofrencia pedida")
    indice_musica_c = capturado["population"].index("musica c")
    assert capturado["weights"][indice_sofrencia] > capturado["weights"][indice_musica_c]
    assert query == capturado["population"][0]


def test_escolher_query_musica_sem_curadoria_cai_pro_genero_da_radio(db_session, radialista_e_programa):
    _, programa = radialista_e_programa
    programa.musicas_permitidas = []
    programa.generos_musicais = ["Sertanejo"]
    db_session.commit()

    query, genero = _escolher_query_musica(db_session, programa)
    assert genero == "Sertanejo"
    assert query == "Sertanejo musica"


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
