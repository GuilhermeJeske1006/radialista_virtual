import datetime
import json

import pytest
from freezegun import freeze_time

from app.live.music import MusicaEncontrada
from app.live.router import _escolher_query_musica, _registrar_historico_persistente
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
        "app.live.router.sintetizar_audio", lambda texto, voz_id, tipo_bloco=None, tom=None, eh_clonada=False, texto_anterior=None: b"audio-bytes"
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


def test_tts_endpoint_com_perfil_pos_producao_invalido_400(
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

    query, genero, musica_catalogada = _escolher_query_musica(db_session, programa)

    assert genero is None
    assert musica_catalogada is None
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
