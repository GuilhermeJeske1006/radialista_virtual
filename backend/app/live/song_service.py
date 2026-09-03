import logging
import re

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config.redis_client import redis_client
from app.live.audio_analysis import obter_fim_seguro
from app.live.music import MusicaEncontrada, _sem_acento, _titulo_normalizado, buscar_musica
from app.models.musica import Musica

logger = logging.getLogger("radialista.song_service")

# Tempo max que um processo pode segurar o lock de resolucao (ver _tentar_lock_resolucao) --
# cobre buscar_musica (Search + Videos API, alguns segundos) com folga; se o processo cair
# sem liberar o lock, ele expira sozinho em vez de travar a musica pra sempre.
_TTL_LOCK_RESOLUCAO_SEGUNDOS = 30


def _normalizar(texto: str) -> str:
    """Chave de lookup de Musica -- mesma logica de _titulo_normalizado (app.live.music),
    mas sem descartar termos de versao (titulo/artista da LLM nao carrega "(Official Video)"
    etc), so' precisa que "Jorge & Mateus" e "jorge e mateus" caiam na mesma entrada."""
    texto = _sem_acento(texto.lower()).replace("&", " e ")
    return re.sub(r"[^a-z0-9]+", " ", texto).strip()


def dividir_artista_titulo(texto: str) -> tuple[str, str] | None:
    """Separa 'Artista - Nome da Musica' em (artista, titulo). Usado tanto pra sugestao da LLM
    (formato pedido em _SUGESTAO_MUSICA_SYSTEM_PROMPT, ver app.llm.client) quanto pra entrada de
    musicas_permitidas (texto livre digitado pelo admin no painel -- ver _escolher_query_musica
    em app.live.router) quando o admin ja escreveu nesse mesmo formato. None se o texto nao
    vier assim -- caller cai pro comportamento atual (usa o texto como query livre, sem
    catalogar)."""
    if " - " not in texto:
        return None
    artista, titulo = texto.split(" - ", 1)
    artista, titulo = artista.strip(), titulo.strip()
    if not artista or not titulo:
        return None
    return artista, titulo


def buscar_ou_criar_musica(db: Session, titulo: str, artista: str) -> Musica:
    """Encontra a Musica catalogada pra este titulo+artista, ou cria uma nova sem
    youtube_video_id (resolvido depois, ver resolver_musica_catalogada). Constraint unica em
    (titulo_normalizado, artista_normalizado) e' quem garante nao duplicar -- IntegrityError
    de uma criacao concorrente (duas falas gerando a mesma sugestao ao mesmo tempo) e' tratado
    relendo a linha que venceu a corrida, em vez de propagar o erro."""
    titulo_normalizado = _normalizar(titulo)
    artista_normalizado = _normalizar(artista)

    musica = (
        db.query(Musica)
        .filter_by(titulo_normalizado=titulo_normalizado, artista_normalizado=artista_normalizado)
        .first()
    )
    if musica is not None:
        return musica

    musica = Musica(
        titulo=titulo,
        artista=artista,
        titulo_normalizado=titulo_normalizado,
        artista_normalizado=artista_normalizado,
    )
    db.add(musica)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        musica = (
            db.query(Musica)
            .filter_by(titulo_normalizado=titulo_normalizado, artista_normalizado=artista_normalizado)
            .first()
        )
        if musica is None:
            raise
    return musica


def _musica_encontrada_do_catalogo(musica: Musica) -> MusicaEncontrada:
    metadados = musica.youtube_metadados or {}
    return MusicaEncontrada(
        video_id=musica.youtube_video_id,
        titulo=musica.youtube_titulo or musica.titulo,
        canal=musica.youtube_canal or "",
        inicio_segundos=musica.youtube_inicio_segundos,
        fim_segundos=obter_fim_seguro(musica.youtube_video_id, musica.duracao_segundos),
        descricao=metadados.get("descricao", ""),
        tags=metadados.get("tags") or [],
        ano=metadados.get("ano"),
        duracao_segundos=musica.duracao_segundos,
        musica_catalogada_id=musica.id,
    )


def _tentar_lock_resolucao(musica_id: int) -> bool:
    """Lock nao-bloqueante (nunca espera) -- se ocupado, quem perdeu simplesmente desiste da
    resolucao agora (ver resolver_musica_catalogada) em vez de fazer uma 2a busca YouTube em
    paralelo pra' mesma Musica. Perder o lock custa, no pior caso, 1 busca a mais pro caller
    (que cai pro texto livre da sugestao) -- nunca trava nem duplica indefinidamente."""
    return bool(redis_client.set(f"lock:musica_youtube:{musica_id}", "1", nx=True, ex=_TTL_LOCK_RESOLUCAO_SEGUNDOS))


def _liberar_lock_resolucao(musica_id: int) -> None:
    redis_client.delete(f"lock:musica_youtube:{musica_id}")


def _persistir_resultado_youtube(db: Session, musica: Musica, resultado: MusicaEncontrada) -> None:
    musica.youtube_video_id = resultado.video_id
    musica.youtube_titulo = resultado.titulo
    musica.youtube_canal = resultado.canal
    musica.youtube_inicio_segundos = resultado.inicio_segundos
    musica.duracao_segundos = resultado.duracao_segundos
    musica.youtube_metadados = {
        "descricao": resultado.descricao,
        "tags": resultado.tags,
        "ano": resultado.ano,
    }
    db.commit()


def resolver_musica_catalogada(
    db: Session,
    titulo: str,
    artista: str,
    bloqueados: list[str] | None = None,
    evitar_video_ids: set[str] | None = None,
    titulos_tocados: set[str] | None = None,
    canais_recentes: dict[str, int] | None = None,
) -> MusicaEncontrada | None:
    """Resolve uma musica sugerida pela LLM (titulo+artista) sem repetir a busca no YouTube se
    ela ja foi catalogada antes: so' consulta a API quando a Musica ainda nao tem
    youtube_video_id salvo. Devolve None quando a musica catalogada ja tocou recentemente
    (video_id ou titulo normalizado presente no historico -- ver evitar_video_ids/
    titulos_tocados em app.live.music) ou quando a busca no YouTube nao encontra nada; nos
    dois casos o caller (ver _escolher_query_musica em app.live.router) cai pro comportamento
    atual de busca por texto livre.
    """
    musica_db = buscar_ou_criar_musica(db, titulo, artista)
    evitar_video_ids = evitar_video_ids or set()
    titulos_tocados = titulos_tocados or set()

    if not musica_db.youtube_video_id:
        if not _tentar_lock_resolucao(musica_db.id):
            # outro processo esta' resolvendo esta Musica agora -- desiste em vez de duplicar
            # a busca YouTube; caller cai pro texto livre da sugestao (ver _escolher_query_musica).
            logger.info("song_catalog resolucao_pulada_lock_ocupado musica_id=%s", musica_db.id)
            return None
        try:
            db.refresh(musica_db)  # outro processo pode ter resolvido enquanto esperavamos o lock
            if not musica_db.youtube_video_id:
                resultado = buscar_musica(
                    f"{artista} - {titulo}",
                    bloqueados=bloqueados,
                    evitar_video_ids=evitar_video_ids,
                    titulos_tocados=titulos_tocados,
                    canais_recentes=canais_recentes,
                    preferir_cantada=True,
                )
                if resultado is None:
                    logger.info("song_catalog youtube_resolution_miss musica_id=%s", musica_db.id)
                    return None
                _persistir_resultado_youtube(db, musica_db, resultado)
                resultado.musica_catalogada_id = musica_db.id
                logger.info(
                    "song_catalog youtube_resolution_performed musica_id=%s video_id=%s",
                    musica_db.id, resultado.video_id,
                )
                return resultado
        finally:
            _liberar_lock_resolucao(musica_db.id)

    # youtube_video_id ja existia (de uma chamada anterior, ou acabou de aparecer no refresh
    # acima porque outro processo resolveu enquanto este esperava o lock).
    titulo_ja_tocado = _titulo_normalizado(musica_db.youtube_titulo or musica_db.titulo) in titulos_tocados
    if musica_db.youtube_video_id in evitar_video_ids or titulo_ja_tocado:
        logger.info("song_catalog lookup_hit_mas_ja_tocada musica_id=%s", musica_db.id)
        return None
    logger.info("song_catalog lookup_hit musica_id=%s video_id=%s", musica_db.id, musica_db.youtube_video_id)
    return _musica_encontrada_do_catalogo(musica_db)
