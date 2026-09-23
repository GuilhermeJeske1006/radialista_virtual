import datetime
import io
import json
import subprocess
from pathlib import Path

import pytest
from freezegun import freeze_time

from app.config.redis_client import redis_client
from app.config.settings import settings
from app.live.formato import ROTEIRO_PADRAO
from app.models.biblioteca_audio import BibliotecaAudioItem
from app.models.programa import Programa
from app.models.radio_config import RadioConfig
from app.models.trilha_vinheta import TrilhaVinheta
from app.tts.voices import VOZES_DISPONIVEIS
from app.vinhetas import audio, gerador, servico, trilha as trilha_mod
from app.vinhetas.estrutura import inserir_vinhetas_na_estrutura

AGORA_UTC = "2026-08-10 15:00:00"  # 12:00 local, dentro de um programa 10:00-14:00


# ---------------------------------------------------------------- audio sintetico (lavfi)


def _lavfi_mp3(fonte: str, *filtros: str) -> bytes:
    args = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", fonte]
    if filtros:
        args += ["-af", ",".join(filtros)]
    args += ["-c:a", "libmp3lame", "-f", "mp3", "pipe:1"]
    return subprocess.run(args, capture_output=True, check=True).stdout


def _voz_sintetica(duracao: float = 3.0) -> bytes:
    """Tom senoidal com silencio antes/depois (o processamento tem que cortar)."""
    return _lavfi_mp3(f"sine=frequency=220:duration={duracao}", "adelay=400:all=1", "apad=pad_dur=0.4")


def _trilha_sintetica(duracao: float = 15.0) -> bytes:
    return _lavfi_mp3(f"anoisesrc=color=pink:duration={duracao}:amplitude=0.3")


@pytest.fixture(scope="module")
def voz_mp3() -> bytes:
    return _voz_sintetica()


@pytest.fixture(scope="module")
def trilha_mp3() -> bytes:
    return _trilha_sintetica()


@pytest.fixture(autouse=True)
def _upload_dir_temporario(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))


@pytest.fixture()
def banco_vazio(tmp_path, monkeypatch):
    pasta = tmp_path / "banco"
    pasta.mkdir()
    monkeypatch.setattr(trilha_mod, "BANCO_DIR", pasta)
    return pasta


@pytest.fixture()
def banco_com_trilha(banco_vazio, trilha_mp3):
    (banco_vazio / "generico").mkdir()
    (banco_vazio / "generico" / "placeholder.mp3").write_bytes(trilha_mp3)
    return banco_vazio


@pytest.fixture()
def tts_fake(monkeypatch, voz_mp3):
    chamadas = []

    def _sintetizar(texto, voz, **kwargs):
        chamadas.append((texto, voz, kwargs.get("tipo_bloco")))
        return voz_mp3

    monkeypatch.setattr(servico, "tts_habilitado", lambda voz=None: True)
    monkeypatch.setattr(servico, "sintetizar_audio", _sintetizar)
    monkeypatch.setattr(servico, "parametros_sintese", lambda db, account_id, voz: {})
    return chamadas


@pytest.fixture()
def music_fake(monkeypatch, trilha_mp3):
    chamadas = []

    def _compor(prompt, duracao_ms=trilha_mod.DURACAO_TRILHA_IA_MS):
        chamadas.append(prompt)
        return trilha_mp3

    monkeypatch.setattr(trilha_mod, "trilha_ia_disponivel", lambda: True)
    monkeypatch.setattr(trilha_mod, "compor_trilha_ia", _compor)
    return chamadas


@pytest.fixture()
def radialista_e_programa(db_session, account):
    account.nome_radio = "Rádio Cidade"
    account.frequencia = "98.5 FM"
    radio_config = RadioConfig(
        account_id=account.id, nome_locutor="Zé", timezone="America/Sao_Paulo", voz_id="voz-do-ze"
    )
    db_session.add(radio_config)
    db_session.commit()
    programa = Programa(
        radio_config_id=radio_config.id,
        nome="Manhã em Sintonia",
        horario_inicio=datetime.time(10, 0),
        horario_fim=datetime.time(14, 0),
        estrutura_blocos=[],
        generos_musicais=["sertanejo"],
    )
    db_session.add(programa)
    db_session.commit()
    return radio_config, programa


def _criar_vinhetas(db_session, account, radialista, programa):
    itens = servico.criar_vinhetas_programa(db_session, account, radialista, programa)
    db_session.commit()
    return {item.papel: item for item in itens}


def _criar_radialista(client, auth_headers, account_id):
    return client.post(
        "/config/radialistas",
        json={"nome_locutor": "Zé", "personalidade": "", "timezone": "America/Sao_Paulo"},
        headers=auth_headers(account_id),
    ).json()


def _programa_payload(**kwargs):
    padrao = dict(nome="Manhã em Sintonia", horario_inicio="10:00:00", horario_fim="12:00:00", tom="animado")
    padrao.update(kwargs)
    return padrao


def _consumo_quota_ia() -> int:
    return sum(int(redis_client.get(k) or 0) for k in redis_client.keys("*gerar_config_ia*"))


# ---------------------------------------------------------------- criacao + estrutura


def test_criar_programa_manual_cria_3_vinhetas_e_insere_na_estrutura(client, account, auth_headers, db_session):
    radialista = _criar_radialista(client, auth_headers, account.id)
    estrutura = ["musica", "comentario", "musica", "noticia", "musica"]
    resposta = client.post(
        f"/config/radialistas/{radialista['id']}/programas",
        json=_programa_payload(estrutura_blocos=estrutura),
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 201
    programa = resposta.json()

    vinhetas = client.get(f"/vinhetas?programa_id={programa['id']}", headers=auth_headers(account.id)).json()
    por_papel = {v["papel"]: v for v in vinhetas}
    assert set(por_papel) == {"abertura", "passagem", "encerramento"}
    assert all(v["origem"] == "auto" for v in vinhetas)

    abertura, passagem = f"vinheta:{por_papel['abertura']['id']}", f"vinheta:{por_papel['passagem']['id']}"
    assert programa["estrutura_blocos"] == [
        abertura, "musica", "comentario", passagem, "musica", "noticia", "musica",
    ]
    assert f"vinheta:{por_papel['encerramento']['id']}" not in programa["estrutura_blocos"]


def test_estrutura_vazia_vira_roteiro_padrao_mais_vinhetas(db_session, account, radialista_e_programa):
    radialista, programa = radialista_e_programa
    vinhetas = _criar_vinhetas(db_session, account, radialista, programa)

    estrutura = programa.estrutura_blocos
    sem_vinhetas = [b for b in estrutura if not b.startswith("vinheta:")]
    assert sem_vinhetas == list(ROTEIRO_PADRAO)
    assert estrutura[0] == f"vinheta:{vinhetas['abertura'].id}"
    assert f"vinheta:{vinhetas['passagem'].id}" in estrutura


def test_insercao_nao_cola_vinheta_em_patrocinador_nem_duplica(db_session, account, radialista_e_programa):
    radialista, programa = radialista_e_programa
    programa.estrutura_blocos = ["musica", "comentario", "patrocinador:7"]
    vinhetas = _criar_vinhetas(db_session, account, radialista, programa)

    estrutura = programa.estrutura_blocos
    for i, bloco in enumerate(estrutura):
        vizinho = estrutura[(i + 1) % len(estrutura)]
        insercoes = (bloco.startswith(("vinheta:", "patrocinador:")), vizinho.startswith(("vinheta:", "patrocinador:")))
        assert insercoes != (True, True), estrutura

    antes = list(estrutura)
    inserir_vinhetas_na_estrutura(programa, list(vinhetas.values()))
    assert programa.estrutura_blocos == antes


def test_gerar_ia_radialista_mais_programa_cria_vinhetas(client, account, auth_headers, monkeypatch):
    monkeypatch.setattr(
        "app.config.router.gerar_configuracao_ia",
        lambda descricao, tipo_radio=None, account=None, roster_existente=None: (
            {"nome_locutor": "IA", "personalidade": "animado", "voz_id": VOZES_DISPONIVEIS[0]["voz_id"],
             "timezone": "America/Sao_Paulo"},
            {"nome": "Programa IA", "tom": "animado", "horario_inicio": "08:00:00", "horario_fim": "10:00:00"},
        ),
    )
    resposta = client.post(
        "/config/radialistas/gerar-ia", json={"descricao": "radio animada"}, headers=auth_headers(account.id)
    )
    assert resposta.status_code == 201
    programa = resposta.json()["programa"]
    vinhetas = client.get(f"/vinhetas?programa_id={programa['id']}", headers=auth_headers(account.id)).json()
    assert len(vinhetas) == 3
    assert any(b.startswith("vinheta:") for b in programa["estrutura_blocos"])
    # O programa consome 1 geracao; as vinhetas nao consomem nenhuma a mais.
    assert _consumo_quota_ia() == 1


def test_criar_vinhetas_nao_consome_quota_de_ia(client, account, auth_headers):
    radialista = _criar_radialista(client, auth_headers, account.id)
    client.post(
        f"/config/radialistas/{radialista['id']}/programas",
        json=_programa_payload(), headers=auth_headers(account.id),
    )
    assert _consumo_quota_ia() == 0


def test_llm_com_json_invalido_duas_vezes_cai_no_template(
    client, account, auth_headers, monkeypatch, db_session
):
    chamadas = []
    monkeypatch.setattr(gerador, "gerar_configuracao", lambda system, msg: chamadas.append(1) or "isso nao e json")
    radialista = _criar_radialista(client, auth_headers, account.id)
    resposta = client.post(
        f"/config/radialistas/{radialista['id']}/programas",
        json=_programa_payload(), headers=auth_headers(account.id),
    )
    assert resposta.status_code == 201
    assert len(chamadas) == 2
    vinhetas = client.get(f"/vinhetas?programa_id={resposta.json()['id']}", headers=auth_headers(account.id)).json()
    abertura = next(v for v in vinhetas if v["papel"] == "abertura")
    assert abertura["texto"].startswith("Tá começando o Manhã em Sintonia, com Zé")


def test_llm_valido_usa_textos_e_escreve_frequencia_com_separador(db_session, account, radialista_e_programa, monkeypatch):
    radialista, programa = radialista_e_programa
    mensagens = []

    def _llm(system, msg):
        mensagens.append(msg)
        return json.dumps({
            "abertura": "Começa agora o **Manhã em Sintonia** 🎉",
            "passagem": "Manhã em Sintonia, na Rádio Cidade.",
            "encerramento": "Fim do Manhã em Sintonia. Rádio Cidade, noventa e oito ponto cinco FM.",
        })

    monkeypatch.setattr(gerador, "gerar_configuracao", _llm)
    vinhetas = _criar_vinhetas(db_session, account, radialista, programa)
    assert vinhetas["abertura"].texto == "Começa agora o Manhã em Sintonia"
    assert "diga 'ponto'" in mensagens[0]


def test_template_escreve_frequencia_por_extenso(account, radialista_e_programa):
    radialista, programa = radialista_e_programa
    textos = gerador.textos_template(account, radialista, programa)
    assert "noventa e oito ponto cinco FM" in textos["abertura"]


def test_falha_ao_criar_vinhetas_nao_derruba_criacao_do_programa(client, account, auth_headers, monkeypatch):
    def _explode(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(servico, "gerar_textos_vinhetas", _explode)
    radialista = _criar_radialista(client, auth_headers, account.id)
    resposta = client.post(
        f"/config/radialistas/{radialista['id']}/programas",
        json=_programa_payload(), headers=auth_headers(account.id),
    )
    assert resposta.status_code == 201
    assert resposta.json()["nome"] == "Manhã em Sintonia"


# ---------------------------------------------------------------- audio


@pytest.mark.parametrize("papel", ["abertura", "passagem", "encerramento"])
def test_mixer_duracao_bate_com_preset(papel, voz_mp3, trilha_mp3, tmp_path):
    voz = audio.processar_voz(voz_mp3)
    duracao_voz = audio.duracao_bytes(voz, ".wav")
    assert duracao_voz == pytest.approx(3.0, abs=0.15)  # silencio de antes/depois foi cortado

    final = audio.mixar(voz, trilha_mp3, papel)
    caminho = tmp_path / f"{papel}.mp3"
    caminho.write_bytes(final)

    preset = audio.PRESETS[papel]
    assert audio.duracao_segundos(caminho) == pytest.approx(preset.intro_s + duracao_voz + preset.cauda_s, abs=0.1)
    assert float(audio.medir_loudness(caminho)["input_i"]) == pytest.approx(-16, abs=1)


def test_mixer_sem_trilha_masteriza_no_alvo(voz_mp3, tmp_path):
    final = audio.mixar(audio.processar_voz(voz_mp3), None, "passagem")
    caminho = tmp_path / "sem_trilha.mp3"
    caminho.write_bytes(final)
    assert float(audio.medir_loudness(caminho)["input_i"]) == pytest.approx(-16, abs=1)


def test_mesma_trilha_nas_3_vinhetas_com_uma_chamada_a_music_api(
    db_session, account, radialista_e_programa, tts_fake, music_fake, banco_vazio
):
    radialista, programa = radialista_e_programa
    vinhetas = _criar_vinhetas(db_session, account, radialista, programa)

    servico.processar_vinhetas(db_session, [v.id for v in vinhetas.values()])

    assert len(music_fake) == 1
    assert "instrumental" in music_fake[0] and "sertanejo" in music_fake[0]
    trilhas = {v.trilha_id for v in vinhetas.values()}
    assert len(trilhas) == 1 and None not in trilhas
    assert all(v.status == "pronta" and v.audio_path and v.voz_path for v in vinhetas.values())
    assert [c[1] for c in tts_fake] == ["voz-do-ze"] * 3
    assert {c[2] for c in tts_fake} == {"abertura", "encerramento", None}


def test_music_api_falha_cai_no_banco_local(
    db_session, account, radialista_e_programa, tts_fake, banco_com_trilha, monkeypatch
):
    monkeypatch.setattr(trilha_mod, "trilha_ia_disponivel", lambda: True)
    monkeypatch.setattr(trilha_mod, "compor_trilha_ia", lambda prompt, duracao_ms=0: (_ for _ in ()).throw(
        RuntimeError("music fora do ar")))
    radialista, programa = radialista_e_programa
    vinhetas = _criar_vinhetas(db_session, account, radialista, programa)

    servico.processar_vinhetas(db_session, [v.id for v in vinhetas.values()])

    trilha = db_session.get(TrilhaVinheta, vinhetas["abertura"].trilha_id)
    assert trilha.origem == "banco"
    assert all(v.status == "pronta" for v in vinhetas.values())


def test_banco_vazio_cai_em_sem_trilha_e_vinheta_fica_pronta(
    db_session, account, radialista_e_programa, tts_fake, banco_vazio, monkeypatch
):
    monkeypatch.setattr(trilha_mod, "trilha_ia_disponivel", lambda: False)
    radialista, programa = radialista_e_programa
    vinhetas = _criar_vinhetas(db_session, account, radialista, programa)

    servico.processar_vinhetas(db_session, [v.id for v in vinhetas.values()])

    assert all(v.trilha_id is None for v in vinhetas.values())
    assert all(v.status == "pronta" and v.audio_path for v in vinhetas.values())


def test_tts_desligado_cria_vinheta_sem_audio_com_fallback_de_texto(
    db_session, account, radialista_e_programa, banco_vazio
):
    radialista, programa = radialista_e_programa
    vinhetas = _criar_vinhetas(db_session, account, radialista, programa)

    servico.processar_vinhetas(db_session, [v.id for v in vinhetas.values()])

    for vinheta in vinhetas.values():
        assert vinheta.audio_path is None
        assert vinheta.status == "erro"
        assert vinheta.texto


def test_remixar_nao_chama_tts_nem_music_api(
    client, db_session, account, auth_headers, radialista_e_programa, tts_fake, music_fake, banco_vazio
):
    radialista, programa = radialista_e_programa
    vinhetas = _criar_vinhetas(db_session, account, radialista, programa)
    servico.processar_vinhetas(db_session, [v.id for v in vinhetas.values()])
    tts_antes, music_antes = len(tts_fake), len(music_fake)
    audio_antes = vinhetas["abertura"].audio_path

    resposta = client.post(
        f"/vinhetas/{vinhetas['abertura'].id}/remixar",
        json={"volume_trilha_db": -20, "usar_trilha": True},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 200
    assert resposta.json()["volume_trilha_db"] == -20
    assert resposta.json()["status"] == "pronta"
    assert (len(tts_fake), len(music_fake)) == (tts_antes, music_antes)
    db_session.refresh(vinhetas["abertura"])
    assert vinhetas["abertura"].audio_path != audio_antes


def test_remixar_volume_fora_da_faixa_falha(client, db_session, account, auth_headers, radialista_e_programa):
    radialista, programa = radialista_e_programa
    vinhetas = _criar_vinhetas(db_session, account, radialista, programa)
    resposta = client.post(
        f"/vinhetas/{vinhetas['abertura'].id}/remixar", json={"volume_trilha_db": 0},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 422


def test_editar_texto_regera_so_a_voz(
    client, db_session, account, auth_headers, radialista_e_programa, tts_fake, music_fake, banco_vazio
):
    radialista, programa = radialista_e_programa
    vinhetas = _criar_vinhetas(db_session, account, radialista, programa)
    servico.processar_vinhetas(db_session, [v.id for v in vinhetas.values()])
    tts_antes = len(tts_fake)

    resposta = client.put(
        f"/vinhetas/{vinhetas['passagem'].id}", json={"texto": "Texto novo da passagem."},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 200
    db_session.refresh(vinhetas["passagem"])
    assert vinhetas["passagem"].texto == "Texto novo da passagem."
    assert vinhetas["passagem"].status == "pronta"
    assert len(tts_fake) == tts_antes + 1
    assert len(music_fake) == 1  # trilha reaproveitada


def test_upload_de_trilha_com_formato_invalido_falha(client, account, auth_headers, radialista_e_programa):
    _, programa = radialista_e_programa
    resposta = client.post(
        f"/programas/{programa.id}/trilha/upload",
        files={"arquivo": ("trilha.ogg", io.BytesIO(b"x"), "audio/ogg")},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 400


def test_upload_de_trilha_corrompida_falha(client, account, auth_headers, radialista_e_programa):
    _, programa = radialista_e_programa
    resposta = client.post(
        f"/programas/{programa.id}/trilha/upload",
        files={"arquivo": ("trilha.mp3", io.BytesIO(b"nao e audio"), "audio/mpeg")},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 400


def test_upload_de_trilha_valida_remixa_as_vinhetas(
    client, db_session, account, auth_headers, radialista_e_programa, tts_fake, banco_vazio, trilha_mp3
):
    radialista, programa = radialista_e_programa
    vinhetas = _criar_vinhetas(db_session, account, radialista, programa)
    servico.processar_vinhetas(db_session, [v.id for v in vinhetas.values()])

    resposta = client.post(
        f"/programas/{programa.id}/trilha/upload",
        files={"arquivo": ("minha.mp3", io.BytesIO(trilha_mp3), "audio/mpeg")},
        headers=auth_headers(account.id),
    )
    assert resposta.status_code == 200
    assert {v["trilha_origem"] for v in resposta.json()} == {"upload"}


# ---------------------------------------------------------------- ao vivo + rotas


def _url_proxima(radialista_id, programa_id):
    return f"/live/{radialista_id}/programas/{programa_id}/proxima"


@freeze_time(AGORA_UTC)
def test_bloco_vinheta_devolve_tipo_vinheta_sem_llm(
    client, db_session, account, auth_headers, radialista_e_programa, monkeypatch
):
    radialista, programa = radialista_e_programa
    vinhetas = _criar_vinhetas(db_session, account, radialista, programa)
    monkeypatch.setattr("app.live.router.gerar_resposta", lambda *a: pytest.fail("vinheta nao passa pelo LLM"))
    monkeypatch.setattr(
        "app.live.router.classificar_categoria_bloco", lambda *a: pytest.fail("vinheta nao e' classificada")
    )

    corpo = client.post(
        _url_proxima(radialista.id, programa.id), json={"historico": [], "total_falas": 0},
        headers=auth_headers(account.id),
    ).json()

    assert corpo["tipo"] == "vinheta"
    assert corpo["vinheta_id"] == vinhetas["abertura"].id
    assert corpo["fala"] == vinhetas["abertura"].texto
    # pendente: ainda sem audio mixado -> painel fala o texto via TTS na hora
    assert corpo["vinheta_audio"] is False


@freeze_time(AGORA_UTC)
def test_vinheta_pronta_devolve_vinheta_audio(client, db_session, account, auth_headers, radialista_e_programa):
    radialista, programa = radialista_e_programa
    vinhetas = _criar_vinhetas(db_session, account, radialista, programa)
    vinhetas["abertura"].audio_path, vinhetas["abertura"].status = "vinhetas/1/x.mp3", "pronta"
    db_session.commit()

    corpo = client.post(
        _url_proxima(radialista.id, programa.id), json={"historico": [], "total_falas": 0},
        headers=auth_headers(account.id),
    ).json()
    assert corpo["vinheta_audio"] is True


@freeze_time(AGORA_UTC)
def test_vinheta_desativada_pula_pro_proximo_bloco(
    client, db_session, account, auth_headers, radialista_e_programa, monkeypatch
):
    radialista, programa = radialista_e_programa
    vinhetas = _criar_vinhetas(db_session, account, radialista, programa)
    programa.estrutura_blocos = [f"vinheta:{vinhetas['abertura'].id}", "comentario", "noticia"]
    vinhetas["abertura"].ativo = False
    db_session.commit()
    monkeypatch.setattr("app.live.router.gerar_resposta", lambda *a: "Seguimos juntos por aqui.")

    corpo = client.post(
        _url_proxima(radialista.id, programa.id), json={"historico": [], "total_falas": 0},
        headers=auth_headers(account.id),
    ).json()
    assert corpo["tipo"] == "comentario"
    assert corpo["passos_roteiro"] == 2


@freeze_time("2026-08-10 16:58:00")  # 13:58 local -- 2 min antes do fim (14:00)
def test_encerramento_informa_vinheta_de_encerramento(
    client, db_session, account, auth_headers, radialista_e_programa, monkeypatch
):
    radialista, programa = radialista_e_programa
    vinhetas = _criar_vinhetas(db_session, account, radialista, programa)
    monkeypatch.setattr("app.live.router.gerar_resposta", lambda *a: "Foi um prazer, até amanhã!")

    corpo = client.post(
        _url_proxima(radialista.id, programa.id), json={"historico": [], "total_falas": 3},
        headers=auth_headers(account.id),
    ).json()
    assert corpo["tipo"] == "encerramento"
    assert corpo["vinheta_encerramento_id"] == vinhetas["encerramento"].id
    assert corpo["vinheta_encerramento_texto"] == vinhetas["encerramento"].texto


def test_prompt_mostra_vinheta_sem_id(account, radialista_e_programa):
    from app.llm.prompt_builder import rotulo_bloco_prompt

    assert rotulo_bloco_prompt("vinheta:12") == "vinheta"
    assert rotulo_bloco_prompt("patrocinador:3") == "patrocinador"
    assert rotulo_bloco_prompt("musica") == "musica"


def test_delete_da_vinheta_remove_da_estrutura(client, db_session, account, auth_headers, radialista_e_programa):
    radialista, programa = radialista_e_programa
    vinhetas = _criar_vinhetas(db_session, account, radialista, programa)
    bloco = f"vinheta:{vinhetas['passagem'].id}"
    assert bloco in programa.estrutura_blocos

    resposta = client.delete(f"/vinhetas/{vinhetas['passagem'].id}", headers=auth_headers(account.id))
    assert resposta.status_code == 204
    db_session.expire_all()
    assert bloco not in db_session.get(Programa, programa.id).estrutura_blocos


def test_excluir_programa_apaga_vinhetas_auto_e_trilha(
    client, db_session, account, auth_headers, radialista_e_programa, tts_fake, music_fake, banco_vazio
):
    radialista, programa = radialista_e_programa
    vinhetas = _criar_vinhetas(db_session, account, radialista, programa)
    servico.processar_vinhetas(db_session, [v.id for v in vinhetas.values()])
    caminhos = [Path(settings.upload_dir) / v.audio_path for v in vinhetas.values()]
    assert all(c.exists() for c in caminhos)

    resposta = client.delete(f"/config/programas/{programa.id}", headers=auth_headers(account.id))
    assert resposta.status_code == 204
    assert db_session.query(BibliotecaAudioItem).filter_by(origem="auto").count() == 0
    assert db_session.query(TrilhaVinheta).count() == 0
    assert not any(c.exists() for c in caminhos)


def test_regerar_vinhetas_troca_por_novas(client, db_session, account, auth_headers, radialista_e_programa):
    radialista, programa = radialista_e_programa
    _criar_vinhetas(db_session, account, radialista, programa)

    resposta = client.post(f"/programas/{programa.id}/vinhetas/regerar", headers=auth_headers(account.id))
    assert resposta.status_code == 200
    novas = resposta.json()
    assert len(novas) == 3
    assert db_session.query(BibliotecaAudioItem).filter_by(programa_id=programa.id).count() == 3
    db_session.expire_all()
    estrutura = db_session.get(Programa, programa.id).estrutura_blocos
    # sem duplicar: so' abertura + passagem na estrutura, uma vez cada
    assert sorted(b for b in estrutura if b.startswith("vinheta:")) == sorted(
        f"vinheta:{v['id']}" for v in novas if v["papel"] in ("abertura", "passagem")
    )


def test_conta_a_nao_acessa_vinheta_nem_trilha_da_conta_b(
    client, db_session, account_factory, auth_headers
):
    dono = account_factory(email="dono-vinheta@a.com")
    outro = account_factory(email="outro-vinheta@a.com")
    radialista = RadioConfig(account_id=dono.id, nome_locutor="Zé")
    db_session.add(radialista)
    db_session.commit()
    programa = Programa(
        radio_config_id=radialista.id, nome="P", horario_inicio=datetime.time(10), horario_fim=datetime.time(11),
    )
    db_session.add(programa)
    db_session.commit()
    vinhetas = _criar_vinhetas(db_session, dono, radialista, programa)
    trilha = TrilhaVinheta(account_id=dono.id, programa_id=programa.id, origem="banco", audio_path="trilhas/1/x.mp3")
    db_session.add(trilha)
    db_session.commit()

    cabecalho = auth_headers(outro.id)
    vinheta_id = vinhetas["abertura"].id
    assert client.get(f"/vinhetas/{vinheta_id}", headers=cabecalho).status_code == 404
    assert client.get(f"/vinhetas/{vinheta_id}/audio", headers=cabecalho).status_code == 404
    assert client.put(f"/vinhetas/{vinheta_id}", json={"nome": "x"}, headers=cabecalho).status_code == 404
    assert client.delete(f"/vinhetas/{vinheta_id}", headers=cabecalho).status_code == 404
    assert client.get(f"/trilhas/{trilha.id}/audio", headers=cabecalho).status_code == 404
    assert client.post(f"/programas/{programa.id}/vinhetas/regerar", headers=cabecalho).status_code == 404
    assert client.get("/vinhetas", headers=cabecalho).json() == []


def test_recuperar_vinhetas_travadas_marca_erro(monkeypatch, db_session, account, radialista_e_programa):
    radialista, programa = radialista_e_programa
    vinhetas = _criar_vinhetas(db_session, account, radialista, programa)
    monkeypatch.setattr(servico, "engine", db_session.get_bind())

    servico.recuperar_vinhetas_travadas()

    db_session.expire_all()
    assert all(db_session.get(BibliotecaAudioItem, v.id).status == "erro" for v in vinhetas.values())


# ---------------------------------------------------------------- regressoes: trilha lenta / sem musica


def test_mixer_abertura_sem_trilha_com_eco_termina(voz_mp3, tmp_path):
    """"apad,atrim" no ramo de eco nao terminava no ffmpeg 7.1 (container de producao): travava
    ate' o timeout de 60 s escrevendo GBs de silencio."""
    voz = audio.processar_voz(voz_mp3)
    final = audio.mixar(voz, None, "abertura")
    caminho = tmp_path / "abertura_sem_trilha.mp3"
    caminho.write_bytes(final)
    assert audio.duracao_segundos(caminho) == pytest.approx(0.1 + audio.duracao_bytes(voz, ".wav") + 0.4, abs=0.1)


def test_prompt_da_trilha_nao_usa_texto_livre_do_programa(radialista_e_programa):
    _, programa = radialista_e_programa
    programa.generos_musicais = ["pop nacional", "hits do momento"]
    programa.tom = "animado, com o jeito do Carlos puxando conversa"
    prompt = trilha_mod.prompt_trilha_ia(programa)
    assert "hits" not in prompt.lower() and "Carlos" not in prompt
    assert "instrumental" in prompt and "pop" in prompt


def test_prompt_recusado_tenta_sugestao_da_api(monkeypatch, trilha_mp3):
    tentativas = []

    def _compor(prompt, duracao_ms=0):
        tentativas.append(prompt)
        if len(tentativas) == 1:
            raise trilha_mod.PromptRecusado("copyrighted_material_detected", "sugestao segura")
        return trilha_mp3

    monkeypatch.setattr(trilha_mod, "compor_trilha_ia", _compor)
    conteudo, prompt = trilha_mod.compor_com_retentativa("prompt original")
    assert conteudo == trilha_mp3
    assert tentativas == ["prompt original", "sugestao segura"]
    assert prompt == "sugestao segura"


def test_prompt_recusado_sempre_desiste_em_3_chamadas(monkeypatch):
    tentativas = []

    def _compor(prompt, duracao_ms=0):
        tentativas.append(prompt)
        raise trilha_mod.PromptRecusado("bad_prompt", f"sugestao {len(tentativas)}")

    monkeypatch.setattr(trilha_mod, "compor_trilha_ia", _compor)
    with pytest.raises(RuntimeError):
        trilha_mod.compor_com_retentativa("prompt original")
    assert len(tentativas) == 3


def test_compor_trilha_ia_identifica_prompt_recusado(monkeypatch):
    import httpx

    corpo = {"detail": {"status": "bad_prompt", "data": {"reason": "copyrighted_material_detected",
                                                          "prompt_suggestion": "outro prompt"}}}

    def _post(self, url, **kwargs):
        return httpx.Response(400, json=corpo, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.Client, "post", _post)
    with pytest.raises(trilha_mod.PromptRecusado) as exc:
        trilha_mod.compor_trilha_ia("x")
    assert exc.value.sugestao == "outro prompt"


def test_preparar_trilha_corta_silencio_do_fim(trilha_mp3):
    com_rabo_mudo = _lavfi_mp3("anoisesrc=color=pink:duration=6:amplitude=0.3", "apad=pad_dur=4")
    assert audio.duracao_bytes(com_rabo_mudo) == pytest.approx(10, abs=0.2)
    preparado, duracao_ms = audio.preparar_trilha(com_rabo_mudo)
    assert duracao_ms == pytest.approx(6000, abs=250)


def test_trilha_e_vozes_saem_juntas(db_session, account, radialista_e_programa, tts_fake, banco_vazio, monkeypatch,
                                    trilha_mp3):
    """TTS roda em paralelo com a Music API: a trilha lenta nao pode serializar as 3 vozes."""
    import threading
    import time as time_mod

    comecou_tts = threading.Event()

    def _compor(prompt, duracao_ms=0):
        assert comecou_tts.wait(5), "TTS so' comecou depois da trilha"
        time_mod.sleep(0.2)
        return trilha_mp3

    sintetizar_original = servico.sintetizar_audio

    def _sintetizar(*args, **kwargs):
        comecou_tts.set()
        return sintetizar_original(*args, **kwargs)

    monkeypatch.setattr(trilha_mod, "trilha_ia_disponivel", lambda: True)
    monkeypatch.setattr(trilha_mod, "compor_trilha_ia", _compor)
    monkeypatch.setattr(servico, "sintetizar_audio", _sintetizar)
    radialista, programa = radialista_e_programa
    vinhetas = _criar_vinhetas(db_session, account, radialista, programa)

    servico.processar_vinhetas(db_session, [v.id for v in vinhetas.values()])
    assert all(v.status == "pronta" and v.trilha_id for v in vinhetas.values())
