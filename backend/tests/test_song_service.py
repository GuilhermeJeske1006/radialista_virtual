from app.config.redis_client import redis_client
from app.live.music import MusicaEncontrada
from app.live.song_service import (
    buscar_ou_criar_musica,
    dividir_artista_titulo,
    resolver_musica_catalogada,
)
from app.models.musica import Musica


def test_dividir_artista_titulo_separa_artista_e_titulo():
    assert dividir_artista_titulo("Jorge & Mateus - Propaganda") == ("Jorge & Mateus", "Propaganda")


def test_dividir_artista_titulo_sem_formato_esperado_devolve_none():
    assert dividir_artista_titulo("so um nome qualquer") is None
    assert dividir_artista_titulo(" - ") is None


def test_buscar_ou_criar_musica_deduplica_por_normalizacao(db_session):
    primeira = buscar_ou_criar_musica(db_session, "Propaganda", "Jorge & Mateus")
    segunda = buscar_ou_criar_musica(db_session, "propaganda", "jorge e mateus")

    assert primeira.id == segunda.id
    assert db_session.query(Musica).count() == 1


def test_buscar_ou_criar_musica_titulos_diferentes_nao_deduplicam(db_session):
    primeira = buscar_ou_criar_musica(db_session, "Propaganda", "Jorge & Mateus")
    segunda = buscar_ou_criar_musica(db_session, "Cheia de Manias", "Jorge & Mateus")

    assert primeira.id != segunda.id
    assert db_session.query(Musica).count() == 2


def test_resolver_musica_catalogada_busca_youtube_e_persiste(db_session, monkeypatch):
    monkeypatch.setattr("app.live.song_service.obter_fim_seguro", lambda video_id, duracao: None)

    chamadas = []

    def _fake_buscar_musica(query, **kwargs):
        chamadas.append(query)
        return MusicaEncontrada(
            video_id="abc123",
            titulo="Propaganda",
            canal="Jorge e Mateus Oficial",
            duracao_segundos=200,
            descricao="uma musica",
            tags=["sertanejo"],
            ano="2015",
        )

    monkeypatch.setattr("app.live.song_service.buscar_musica", _fake_buscar_musica)

    resultado = resolver_musica_catalogada(db_session, "Propaganda", "Jorge & Mateus")

    assert resultado is not None
    assert resultado.video_id == "abc123"
    assert chamadas == ["Jorge & Mateus - Propaganda"]

    musica = db_session.query(Musica).one()
    assert musica.youtube_video_id == "abc123"
    assert musica.youtube_metadados == {"descricao": "uma musica", "tags": ["sertanejo"], "ano": "2015"}


def test_resolver_musica_catalogada_reaproveita_sem_buscar_de_novo(db_session, monkeypatch):
    monkeypatch.setattr("app.live.song_service.obter_fim_seguro", lambda video_id, duracao: None)

    chamadas = []
    monkeypatch.setattr(
        "app.live.song_service.buscar_musica",
        lambda query, **kwargs: chamadas.append(query) or MusicaEncontrada(video_id="abc123", titulo="Propaganda", canal="Canal"),
    )

    resolver_musica_catalogada(db_session, "Propaganda", "Jorge & Mateus")
    resultado = resolver_musica_catalogada(db_session, "Propaganda", "Jorge & Mateus")

    assert resultado is not None
    assert resultado.video_id == "abc123"
    assert len(chamadas) == 1


def test_resolver_musica_catalogada_ja_tocado_devolve_none_sem_buscar(db_session, monkeypatch):
    monkeypatch.setattr("app.live.song_service.obter_fim_seguro", lambda video_id, duracao: None)
    monkeypatch.setattr(
        "app.live.song_service.buscar_musica",
        lambda query, **kwargs: MusicaEncontrada(video_id="abc123", titulo="Propaganda", canal="Canal"),
    )
    resolver_musica_catalogada(db_session, "Propaganda", "Jorge & Mateus")

    chamadas_apos_resolvida = []
    monkeypatch.setattr(
        "app.live.song_service.buscar_musica",
        lambda query, **kwargs: chamadas_apos_resolvida.append(query),
    )

    resultado = resolver_musica_catalogada(
        db_session, "Propaganda", "Jorge & Mateus", evitar_video_ids={"abc123"}
    )

    assert resultado is None
    assert chamadas_apos_resolvida == []


def test_resolver_musica_catalogada_lock_ocupado_nao_duplica_busca(db_session, monkeypatch):
    """Simula outro processo ja' resolvendo a mesma Musica: lock ocupado -- esta chamada
    desiste em vez de disparar uma 2a busca YouTube em paralelo pra' mesma faixa."""
    musica_db = buscar_ou_criar_musica(db_session, "Propaganda", "Jorge & Mateus")
    redis_client.set(f"lock:musica_youtube:{musica_db.id}", "1", nx=True, ex=30)

    chamadas = []
    monkeypatch.setattr(
        "app.live.song_service.buscar_musica",
        lambda query, **kwargs: chamadas.append(query),
    )

    resultado = resolver_musica_catalogada(db_session, "Propaganda", "Jorge & Mateus")

    assert resultado is None
    assert chamadas == []


def test_resolver_musica_catalogada_sem_resultado_youtube_nao_persiste(db_session, monkeypatch):
    monkeypatch.setattr("app.live.song_service.buscar_musica", lambda query, **kwargs: None)

    resultado = resolver_musica_catalogada(db_session, "Musica Inexistente", "Artista Desconhecido")

    assert resultado is None
    musica = db_session.query(Musica).one()
    assert musica.youtube_video_id is None
