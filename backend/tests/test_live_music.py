from app.live.music import MusicaEncontrada, buscar_musica, buscar_musica_fundo
from app.config.settings import settings


def _item(video_id, titulo, canal):
    return {
        "id": {"videoId": video_id},
        "snippet": {"title": titulo, "channelTitle": canal},
    }


def test_buscar_musica_sem_api_key_devolve_none(monkeypatch):
    monkeypatch.setattr(settings, "youtube_api_key", "")
    assert buscar_musica("qualquer coisa") is None


def test_buscar_musica_prioriza_canal_oficial_topic(monkeypatch):
    monkeypatch.setattr(settings, "youtube_api_key", "fake-key")
    itens = [
        _item("id1", "Musica Generica", "Canal Qualquer"),
        _item("id2", "Musica Oficial", "Artista - Topic"),
    ]
    monkeypatch.setattr("app.live.music._buscar_itens", lambda query: itens)
    monkeypatch.setattr("app.live.music._buscar_duracoes", lambda ids: {})

    resultado = buscar_musica("minha musica")
    assert resultado.video_id == "id2"
    assert resultado.canal == "Artista - Topic"


def test_buscar_musica_ignora_bloqueados(monkeypatch):
    monkeypatch.setattr(settings, "youtube_api_key", "fake-key")
    itens = [
        _item("id1", "Musica Proibida", "Canal Ruim"),
        _item("id2", "Musica Permitida", "Canal Bom"),
    ]
    monkeypatch.setattr("app.live.music._buscar_itens", lambda query: itens)
    monkeypatch.setattr("app.live.music._buscar_duracoes", lambda ids: {})

    resultado = buscar_musica("minha musica", bloqueados=["proibida"])
    assert resultado.video_id == "id2"


def test_buscar_musica_evita_video_ids_ja_tocados(monkeypatch):
    monkeypatch.setattr(settings, "youtube_api_key", "fake-key")
    itens = [_item("id1", "Musica A", "Canal A"), _item("id2", "Musica B", "Canal B")]
    monkeypatch.setattr("app.live.music._buscar_itens", lambda query: itens)
    monkeypatch.setattr("app.live.music._buscar_duracoes", lambda ids: {})

    resultado = buscar_musica("minha musica", evitar_video_ids={"id1"})
    assert resultado.video_id == "id2"


def test_buscar_musica_respeita_limite_por_canal(monkeypatch):
    monkeypatch.setattr(settings, "youtube_api_key", "fake-key")
    itens = [_item("id1", "Musica A", "Canal Saturado"), _item("id2", "Musica B", "Canal Livre")]
    monkeypatch.setattr("app.live.music._buscar_itens", lambda query: itens)
    monkeypatch.setattr("app.live.music._buscar_duracoes", lambda ids: {})

    resultado = buscar_musica(
        "minha musica", canais_recentes={"canal saturado": 2}, limite_por_canal=2
    )
    assert resultado.video_id == "id2"


def test_buscar_musica_pula_conteudo_sobre_a_musica(monkeypatch):
    monkeypatch.setattr(settings, "youtube_api_key", "fake-key")
    itens = [
        _item("id1", "A historia de uma musica famosa", "Canal Documentario"),
        _item("id2", "Musica de verdade", "Canal Normal"),
    ]
    monkeypatch.setattr("app.live.music._buscar_itens", lambda query: itens)
    monkeypatch.setattr("app.live.music._buscar_duracoes", lambda ids: {})

    resultado = buscar_musica("minha musica")
    assert resultado.video_id == "id2"


def test_buscar_musica_sem_resultado_nenhum_devolve_none(monkeypatch):
    monkeypatch.setattr(settings, "youtube_api_key", "fake-key")
    monkeypatch.setattr("app.live.music._buscar_itens", lambda query: [])
    monkeypatch.setattr("app.live.music._buscar_duracoes", lambda ids: {})

    assert buscar_musica("nada encontrado") is None


def test_buscar_musica_fundo_usa_genero_aleatorio(monkeypatch):
    monkeypatch.setattr(settings, "youtube_api_key", "fake-key")
    capturado = {}

    def _fake_buscar_musica(query, bloqueados=None, **kwargs):
        capturado["query"] = query
        return MusicaEncontrada(video_id="id1", titulo="Instrumental", canal="Canal X")

    monkeypatch.setattr("app.live.music.buscar_musica", _fake_buscar_musica)
    resultado = buscar_musica_fundo(["sertanejo"])
    assert "sertanejo" in capturado["query"]
    assert resultado.video_id == "id1"


def test_buscar_musica_fundo_sem_generos_usa_query_generica(monkeypatch):
    capturado = {}

    def _fake_buscar_musica(query, bloqueados=None, **kwargs):
        capturado["query"] = query
        return None

    monkeypatch.setattr("app.live.music.buscar_musica", _fake_buscar_musica)
    buscar_musica_fundo([])
    assert capturado["query"] == "musica instrumental radio fundo"
