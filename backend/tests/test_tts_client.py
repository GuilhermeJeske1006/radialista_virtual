import httpx
import pytest

from app.tts import client as tts_client


class _FakeResponse:
    def __init__(self, status_code=200, content=b"audio-bytes", json_data=None, headers=None):
        self.status_code = status_code
        self.content = content
        self._json_data = json_data or {}
        self.headers = headers or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("erro", request=None, response=self)

    def json(self):
        return self._json_data


class _FakeClient:
    def __init__(self, respostas):
        self._respostas = list(respostas)
        self.chamadas = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def post(self, url, **kwargs):
        self.chamadas.append(("post", url, kwargs))
        return self._respostas.pop(0)

    def delete(self, url, **kwargs):
        self.chamadas.append(("delete", url, kwargs))
        return self._respostas.pop(0)

    def get(self, url, **kwargs):
        self.chamadas.append(("get", url, kwargs))
        return self._respostas.pop(0)


class _FakeStreamResponse:
    def __init__(self, status_code=200, chunks=(b"mp3-data",), headers=None):
        self.status_code = status_code
        self._chunks = list(chunks)
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def iter_bytes(self):
        yield from self._chunks

    def read(self):
        return b"".join(self._chunks)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("erro", request=None, response=self)


class _FakeStreamClient:
    def __init__(self, respostas):
        self._respostas = list(respostas)
        self.chamadas = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def stream(self, method, url, **kwargs):
        self.chamadas.append((method, url, kwargs))
        return self._respostas.pop(0)


def _habilitar_elevenlabs(monkeypatch):
    monkeypatch.setattr(tts_client.settings, "elevenlabs_api_key", "fake-key")
    monkeypatch.setattr(tts_client.settings, "elevenlabs_voice_id", "voz-padrao")


def test_tts_habilitado_falso_sem_api_key(monkeypatch):
    monkeypatch.setattr(tts_client.settings, "elevenlabs_api_key", "")
    assert tts_client.tts_habilitado() is False


def test_tts_habilitado_com_voice_id_explicito(monkeypatch):
    monkeypatch.setattr(tts_client.settings, "elevenlabs_api_key", "fake-key")
    monkeypatch.setattr(tts_client.settings, "elevenlabs_voice_id", "")
    assert tts_client.tts_habilitado("voz-especifica") is True


def test_construir_voice_settings_aplica_preset_do_tipo_bloco():
    settings_musica = tts_client._construir_voice_settings("musica", None, "eleven_multilingual_v2", False)
    settings_comentario = tts_client._construir_voice_settings("comentario", None, "eleven_multilingual_v2", False)
    assert settings_musica["speed"] > settings_comentario["speed"]


def test_construir_voice_settings_bloco_customizado_reconhece_prefixo(monkeypatch):
    monkeypatch.setattr(tts_client.random, "uniform", lambda a, b: 0.0)
    a = tts_client._construir_voice_settings("Musica Vaneira", None, "eleven_multilingual_v2", False)
    b = tts_client._construir_voice_settings("musica", None, "eleven_multilingual_v2", False)
    assert a == b


def test_construir_voice_settings_clampa_valores(monkeypatch):
    resultado = tts_client._construir_voice_settings("noticia", "calmo", "eleven_multilingual_v2", False)
    assert 0.0 <= resultado["stability"] <= 1.0
    assert 0.0 <= resultado["style"] <= 1.0
    assert 0.7 <= resultado["speed"] <= 1.2


def test_construir_voice_settings_clonada_forca_similarity_alto():
    resultado = tts_client._construir_voice_settings("comentario", None, "eleven_multilingual_v2", True)
    assert resultado["similarity_boost"] == tts_client._SIMILARITY_BOOST_CLONE
    assert resultado["use_speaker_boost"] is True


def test_construir_voice_settings_v3_remove_similarity_mesmo_clonada():
    resultado = tts_client._construir_voice_settings("comentario", None, "eleven_v3", True)
    assert "similarity_boost" not in resultado
    assert "use_speaker_boost" not in resultado


def test_sintetizar_audio_clonada_usa_mesmo_modelo_do_catalogo(monkeypatch):
    _habilitar_elevenlabs(monkeypatch)
    monkeypatch.setattr(tts_client.settings, "elevenlabs_model", "eleven_v3")
    fake = _FakeClient([_FakeResponse(status_code=200, content=b"mp3-data")])
    monkeypatch.setattr(tts_client.httpx, "Client", lambda **kwargs: fake)

    tts_client.sintetizar_audio("ola", eh_clonada=True)
    payload = fake.chamadas[0][2]["json"]
    assert payload["model_id"] == "eleven_v3"
    assert "similarity_boost" not in payload["voice_settings"]


@pytest.mark.parametrize("eh_clonada", [False, True])
@pytest.mark.parametrize("tipo_bloco,tom", [("musica", "energico"), ("noticia", "calmo")])
@pytest.mark.parametrize("streaming", [False, True])
def test_flash_envia_perfil_proprio_sem_deltas_do_v3(monkeypatch, eh_clonada, tipo_bloco, tom, streaming):
    _habilitar_elevenlabs(monkeypatch)
    monkeypatch.setattr(tts_client.settings, "elevenlabs_model", "eleven_flash_v2_5")
    monkeypatch.setattr(tts_client.random, "uniform", lambda a, b: 0.0)
    fake = _FakeStreamClient([_FakeStreamResponse()]) if streaming else _FakeClient([_FakeResponse()])
    monkeypatch.setattr(tts_client.httpx, "Client", lambda **kwargs: fake)
    parametros = dict(tipo_bloco=tipo_bloco, tom=tom, eh_clonada=eh_clonada, texto_anterior="Fala anterior.")
    if streaming:
        list(tts_client.sintetizar_audio_stream("Ola ouvintes!", **parametros))
    else:
        tts_client.sintetizar_audio("Ola ouvintes!", **parametros)
    payload = fake.chamadas[0][2]["json"]
    assert payload["model_id"] == "eleven_flash_v2_5"
    assert payload["voice_settings"] == {
        "stability": 0.5, "similarity_boost": 0.75, "style": 0.0,
        "use_speaker_boost": True, "speed": 1.0,
    }
    assert payload["previous_text"] == "Fala anterior."
    assert payload["language_code"] == "pt"


def test_sintetizar_audio_v3_nao_manda_previous_text(monkeypatch):
    """eleven_v3 devolve 400 (unsupported_model) se previous_text for mandado -- ver
    comentario em sintetizar_audio. texto_anterior deve ser descartado nesse modelo."""
    _habilitar_elevenlabs(monkeypatch)
    monkeypatch.setattr(tts_client.settings, "elevenlabs_model", "eleven_v3")
    fake = _FakeClient([_FakeResponse(status_code=200, content=b"mp3-data")])
    monkeypatch.setattr(tts_client.httpx, "Client", lambda **kwargs: fake)

    tts_client.sintetizar_audio("ola", texto_anterior="fala anterior")
    payload = fake.chamadas[0][2]["json"]
    assert "previous_text" not in payload


def test_sintetizar_audio_v2_manda_previous_text(monkeypatch):
    _habilitar_elevenlabs(monkeypatch)
    monkeypatch.setattr(tts_client.settings, "elevenlabs_model", "eleven_multilingual_v2")
    fake = _FakeClient([_FakeResponse(status_code=200, content=b"mp3-data")])
    monkeypatch.setattr(tts_client.httpx, "Client", lambda **kwargs: fake)

    tts_client.sintetizar_audio("ola", texto_anterior="fala anterior")
    payload = fake.chamadas[0][2]["json"]
    assert payload["previous_text"] == "fala anterior"


def test_sintetizar_audio_v3_converte_reticencias_duplas_em_pause(monkeypatch):
    """"......" (troca de assunto, ver prompt em app.live.router) nao gera pausa nenhuma no
    eleven_v3 -- medido na API real, mesma duracao que um ".". A tag [pause] e' o que
    realmente funciona, entao a reticencia dupla e' convertida antes de mandar pro v3."""
    _habilitar_elevenlabs(monkeypatch)
    monkeypatch.setattr(tts_client.settings, "elevenlabs_model", "eleven_v3")
    fake = _FakeClient([_FakeResponse(status_code=200, content=b"mp3-data")])
    monkeypatch.setattr(tts_client.httpx, "Client", lambda **kwargs: fake)

    tts_client.sintetizar_audio("Bom dia ouvintes...... Vamos falar de futebol.")
    payload = fake.chamadas[0][2]["json"]
    assert "[pause]" in payload["text"]
    assert "......" not in payload["text"]


def test_sintetizar_audio_v3_preserva_reticencia_simples(monkeypatch):
    _habilitar_elevenlabs(monkeypatch)
    monkeypatch.setattr(tts_client.settings, "elevenlabs_model", "eleven_v3")
    fake = _FakeClient([_FakeResponse(status_code=200, content=b"mp3-data")])
    monkeypatch.setattr(tts_client.httpx, "Client", lambda **kwargs: fake)

    tts_client.sintetizar_audio("Bom dia ouvintes... vamos comecar.")
    payload = fake.chamadas[0][2]["json"]
    assert "[pause]" not in payload["text"]
    assert "..." in payload["text"]


def test_sintetizar_audio_v2_nao_converte_reticencias(monkeypatch):
    _habilitar_elevenlabs(monkeypatch)
    monkeypatch.setattr(tts_client.settings, "elevenlabs_model", "eleven_multilingual_v2")
    fake = _FakeClient([_FakeResponse(status_code=200, content=b"mp3-data")])
    monkeypatch.setattr(tts_client.httpx, "Client", lambda **kwargs: fake)

    tts_client.sintetizar_audio("Bom dia ouvintes...... Vamos falar de futebol.")
    payload = fake.chamadas[0][2]["json"]
    assert "[pause]" not in payload["text"]
    assert "......" in payload["text"]


def test_sintetizar_audio_v3_preserva_tag_permitida(monkeypatch):
    _habilitar_elevenlabs(monkeypatch)
    monkeypatch.setattr(tts_client.settings, "elevenlabs_model", "eleven_v3")
    fake = _FakeClient([_FakeResponse(status_code=200, content=b"mp3-data")])
    monkeypatch.setattr(tts_client.httpx, "Client", lambda **kwargs: fake)

    tts_client.sintetizar_audio("[excited] Vamos comecar o programa!")
    payload = fake.chamadas[0][2]["json"]
    assert "[excited]" in payload["text"]


def test_sintetizar_audio_v3_remove_tag_fora_da_whitelist(monkeypatch):
    _habilitar_elevenlabs(monkeypatch)
    monkeypatch.setattr(tts_client.settings, "elevenlabs_model", "eleven_v3")
    fake = _FakeClient([_FakeResponse(status_code=200, content=b"mp3-data")])
    monkeypatch.setattr(tts_client.httpx, "Client", lambda **kwargs: fake)

    tts_client.sintetizar_audio("[surpreso] Nao acredito nessa noticia.")
    payload = fake.chamadas[0][2]["json"]
    assert "[surpreso]" not in payload["text"]
    assert "Nao acredito nessa noticia." in payload["text"]


def test_sintetizar_audio_v3_tag_inline_suprime_tag_por_tom(monkeypatch):
    """Fala que ja vem com tag de emocao do LLM nao deve levar tambem o prefixo estatico
    [calm] do tom classificado -- evita empilhar duas instrucoes de emocao conflitantes."""
    _habilitar_elevenlabs(monkeypatch)
    monkeypatch.setattr(tts_client.settings, "elevenlabs_model", "eleven_v3")
    fake = _FakeClient([_FakeResponse(status_code=200, content=b"mp3-data")])
    monkeypatch.setattr(tts_client.httpx, "Client", lambda **kwargs: fake)

    tts_client.sintetizar_audio("[excited] Que noticia otima.", tom="calmo")
    payload = fake.chamadas[0][2]["json"]
    assert payload["text"].count("[") == 1


def test_sintetizar_audio_v3_sem_tag_inline_mantem_tag_por_tom(monkeypatch):
    _habilitar_elevenlabs(monkeypatch)
    monkeypatch.setattr(tts_client.settings, "elevenlabs_model", "eleven_v3")
    fake = _FakeClient([_FakeResponse(status_code=200, content=b"mp3-data")])
    monkeypatch.setattr(tts_client.httpx, "Client", lambda **kwargs: fake)

    tts_client.sintetizar_audio("Vamos com calma agora.", tom="calmo")
    payload = fake.chamadas[0][2]["json"]
    assert payload["text"].startswith("[calm]")


def test_sintetizar_audio_v2_nao_sanitiza_tags(monkeypatch):
    """Sanitizacao de tag e' regra especifica do eleven_v3 (ver prompt condicional em
    app.live.router) -- fora dele, o texto nem deveria trazer tag, mas nao ha' motivo pra
    tocar no texto de um modelo que nunca recebeu essa instrucao."""
    _habilitar_elevenlabs(monkeypatch)
    monkeypatch.setattr(tts_client.settings, "elevenlabs_model", "eleven_multilingual_v2")
    fake = _FakeClient([_FakeResponse(status_code=200, content=b"mp3-data")])
    monkeypatch.setattr(tts_client.httpx, "Client", lambda **kwargs: fake)

    tts_client.sintetizar_audio("[surpreso] Ola ouvintes.")
    payload = fake.chamadas[0][2]["json"]
    assert "[surpreso]" in payload["text"]


def test_sintetizar_audio_converte_valor_monetario_por_extenso(monkeypatch):
    """Texto de patrocinador (ver Patrocinador.texto em app.live.router) e' fixo e nunca passa
    pelo LLM -- a instrucao de prompt "escreva numero por extenso" nao alcanca esse texto, entao
    o TTS precisa converter "R$" sozinho, em qualquer modelo (nao so' v3)."""
    _habilitar_elevenlabs(monkeypatch)
    monkeypatch.setattr(tts_client.settings, "elevenlabs_model", "eleven_multilingual_v2")
    fake = _FakeClient([_FakeResponse(status_code=200, content=b"mp3-data")])
    monkeypatch.setattr(tts_client.httpx, "Client", lambda **kwargs: fake)

    tts_client.sintetizar_audio("So hoje por R$ 19,90!")
    payload = fake.chamadas[0][2]["json"]
    assert payload["text"] == "So hoje por dezenove reais e noventa centavos!"


def test_sintetizar_audio_devolve_bytes(monkeypatch):
    _habilitar_elevenlabs(monkeypatch)
    fake = _FakeClient([_FakeResponse(status_code=200, content=b"mp3-data")])
    monkeypatch.setattr(tts_client.httpx, "Client", lambda **kwargs: fake)

    audio = tts_client.sintetizar_audio("ola ouvintes", tipo_bloco="abertura", tom="energico")
    assert audio == b"mp3-data"


def test_sintetizar_audio_faz_retry_em_429(monkeypatch):
    _habilitar_elevenlabs(monkeypatch)
    monkeypatch.setattr(tts_client.time, "sleep", lambda segundos: None)
    fake = _FakeClient(
        [
            _FakeResponse(status_code=429, headers={"retry-after": "0"}),
            _FakeResponse(status_code=200, content=b"mp3-final"),
        ]
    )
    monkeypatch.setattr(tts_client.httpx, "Client", lambda **kwargs: fake)

    audio = tts_client.sintetizar_audio("ola")
    assert audio == b"mp3-final"
    assert len(fake.chamadas) == 2


def test_sintetizar_audio_levanta_erro_em_falha_definitiva(monkeypatch):
    _habilitar_elevenlabs(monkeypatch)
    fake = _FakeClient([_FakeResponse(status_code=500)])
    monkeypatch.setattr(tts_client.httpx, "Client", lambda **kwargs: fake)

    with pytest.raises(httpx.HTTPStatusError):
        tts_client.sintetizar_audio("ola")


def test_sintetizar_audio_stream_devolve_bytes(monkeypatch):
    _habilitar_elevenlabs(monkeypatch)
    fake = _FakeStreamClient([_FakeStreamResponse(status_code=200, chunks=[b"parte1", b"parte2"])])
    monkeypatch.setattr(tts_client.httpx, "Client", lambda **kwargs: fake)

    audio = b"".join(tts_client.sintetizar_audio_stream("ola ouvintes", tipo_bloco="abertura", tom="energico"))
    assert audio == b"parte1parte2"


def test_sintetizar_audio_stream_usa_endpoint_de_streaming(monkeypatch):
    _habilitar_elevenlabs(monkeypatch)
    fake = _FakeStreamClient([_FakeStreamResponse(status_code=200, chunks=[b"x"])])
    monkeypatch.setattr(tts_client.httpx, "Client", lambda **kwargs: fake)

    list(tts_client.sintetizar_audio_stream("ola", "voz-x"))
    metodo, url, _kwargs = fake.chamadas[0]
    assert metodo == "POST"
    assert url == tts_client._ELEVENLABS_STREAM_URL.format(voice_id="voz-x")


def test_sintetizar_audio_stream_faz_retry_em_429(monkeypatch):
    _habilitar_elevenlabs(monkeypatch)
    monkeypatch.setattr(tts_client.time, "sleep", lambda segundos: None)
    fake = _FakeStreamClient(
        [
            _FakeStreamResponse(status_code=429, headers={"retry-after": "0"}),
            _FakeStreamResponse(status_code=200, chunks=[b"mp3-final"]),
        ]
    )
    monkeypatch.setattr(tts_client.httpx, "Client", lambda **kwargs: fake)

    audio = b"".join(tts_client.sintetizar_audio_stream("ola"))
    assert audio == b"mp3-final"
    assert len(fake.chamadas) == 2


def test_sintetizar_audio_stream_levanta_erro_em_falha_definitiva(monkeypatch):
    """Erro precisa subir ANTES do primeiro yield -- e' o que deixa o endpoint /tts ainda
    converter pra HTTPException normal em vez de truncar uma StreamingResponse ja iniciada
    (ver docstring de sintetizar_audio_stream e uso em app.live.router.gerar_audio_fala)."""
    _habilitar_elevenlabs(monkeypatch)
    fake = _FakeStreamClient([_FakeStreamResponse(status_code=500)])
    monkeypatch.setattr(tts_client.httpx, "Client", lambda **kwargs: fake)

    with pytest.raises(httpx.HTTPStatusError):
        next(tts_client.sintetizar_audio_stream("ola"))


def test_clonar_voz_devolve_voice_id(monkeypatch):
    _habilitar_elevenlabs(monkeypatch)
    fake = _FakeClient([_FakeResponse(status_code=200, json_data={"voice_id": "novo-id"})])
    monkeypatch.setattr(tts_client.httpx, "Client", lambda **kwargs: fake)

    voice_id = tts_client.clonar_voz("Minha voz", b"audio", "audio/mpeg", "amostra.mp3")
    assert voice_id == "novo-id"


def test_obter_preview_url_sem_api_key(monkeypatch):
    monkeypatch.setattr(tts_client.settings, "elevenlabs_api_key", "")
    assert tts_client.obter_preview_url("voz-1") is None


def test_obter_preview_url_devolve_url(monkeypatch):
    _habilitar_elevenlabs(monkeypatch)
    fake = _FakeClient([_FakeResponse(status_code=200, json_data={"preview_url": "https://example.com/preview.mp3"})])
    monkeypatch.setattr(tts_client.httpx, "Client", lambda **kwargs: fake)

    assert tts_client.obter_preview_url("voz-1") == "https://example.com/preview.mp3"


def test_obter_preview_url_devolve_none_em_falha(monkeypatch):
    _habilitar_elevenlabs(monkeypatch)
    fake = _FakeClient([_FakeResponse(status_code=500)])
    monkeypatch.setattr(tts_client.httpx, "Client", lambda **kwargs: fake)

    assert tts_client.obter_preview_url("voz-1") is None


def test_obter_preview_url_cai_pra_shared_voices_quando_voz_da_library(monkeypatch):
    # voz premade (catalogo fixo em app/tts/voices.py) nao esta na conta -- GET /v1/voices/{id}
    # devolve voice_not_found (400); shared-voices e' onde a voz publica de fato existe.
    _habilitar_elevenlabs(monkeypatch)
    fake = _FakeClient(
        [
            _FakeResponse(status_code=400),
            _FakeResponse(
                status_code=200,
                json_data={"voices": [{"voice_id": "voz-1", "preview_url": "https://example.com/shared.mp3"}]},
            ),
        ]
    )
    monkeypatch.setattr(tts_client.httpx, "Client", lambda **kwargs: fake)

    assert tts_client.obter_preview_url("voz-1") == "https://example.com/shared.mp3"
    assert fake.chamadas[1][1] == tts_client._ELEVENLABS_SHARED_VOICES_URL
    assert fake.chamadas[1][2]["params"] == {"search": "voz-1", "page_size": 1}


def test_obter_preview_url_shared_voices_sem_match_devolve_none(monkeypatch):
    _habilitar_elevenlabs(monkeypatch)
    fake = _FakeClient(
        [
            _FakeResponse(status_code=400),
            _FakeResponse(status_code=200, json_data={"voices": []}),
        ]
    )
    monkeypatch.setattr(tts_client.httpx, "Client", lambda **kwargs: fake)

    assert tts_client.obter_preview_url("voz-1") is None


def test_excluir_voz_clonada_chama_delete(monkeypatch):
    _habilitar_elevenlabs(monkeypatch)
    fake = _FakeClient([_FakeResponse(status_code=200)])
    monkeypatch.setattr(tts_client.httpx, "Client", lambda **kwargs: fake)

    tts_client.excluir_voz_clonada("voz-1")
    assert fake.chamadas[0][0] == "delete"
