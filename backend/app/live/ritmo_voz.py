"""Calibração do ritmo da fala por voz (F2): amostras medidas no áudio final e cadeia do wpm.

Único módulo da calibração que acessa banco e Redis. O banco (tabela ritmos_voz) guarda só agregados
numéricos e é a fonte da calibração, porque o Redis de produção descarta chaves por LRU e não tem
volume. O Redis serve para deduplicar amostras (o cache de TTS devolve os mesmos bytes para o mesmo
texto e voz) e para o orçamento que o /proxima deixa para o /tts ler. Tudo falha aberto: sem banco ou
sem Redis o áudio sai do mesmo jeito, perde-se só a amostra ou o log. Desenho em
docs/melhoria-radio/f2/auditoria.md (§4.4).

Cadeia de `wpm_para`: categoria da voz com amostras suficientes → agregado da voz (mesmo modelo e
perfil) → padrão do modelo → padrão geral (app.live.orcamento.wpm_padrao).
"""
import datetime
import hashlib
import json
import logging
from dataclasses import dataclass, field

from redis.exceptions import RedisError
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.config.redis_client import redis_client
from app.config.settings import settings
from app.live.orcamento import wpm_observado, wpm_padrao
from app.models.perfil_voz import RitmoVoz
from app.tts.client import CATEGORIAS_PROSODIA, categoria_tipo_bloco
from app.tts.profiles import modelo_e_perfil

logger = logging.getLogger("radialista.live.ritmo_voz")

_TTL_DEDUPE_S = 24 * 60 * 60          # igual ao cache de TTS (settings.ia_cache_ttl_segundos)
_TTL_ORCAMENTO_PENDENTE_S = 15 * 60   # do /proxima até o painel chamar /tts
CATEGORIA_GERAL = "padrao"


@dataclass(frozen=True)
class VozEfetiva:
    voz_id: str
    modelo: str
    perfil: str


def voz_efetiva(db: Session, account_id: int, voz_id: str | None) -> VozEfetiva:
    voz, modelo, perfil = modelo_e_perfil(db, account_id, voz_id)
    return VozEfetiva(voz_id=voz or CATEGORIA_GERAL, modelo=modelo, perfil=perfil)


def categoria_ritmo(tipo_bloco: str | None) -> str:
    """Categoria de prosodia do bloco (a mesma que escolhe o speed no TTS); sem preset, a geral."""
    categoria = categoria_tipo_bloco(tipo_bloco or "")
    return categoria if categoria in CATEGORIAS_PROSODIA else CATEGORIA_GERAL


@dataclass
class Ritmos:
    """Agregados de uma voz (mesmo modelo e perfil), lidos numa consulta só."""

    modelo: str
    por_categoria: dict[str, tuple[int, float, float]] = field(default_factory=dict)

    def _calibrado(self, categoria: str | None) -> tuple[float, str] | None:
        minimo = settings.fala_calibracao_min_amostras
        if categoria is not None:
            amostras, palavras, segundos = self.por_categoria.get(categoria, (0, 0.0, 0.0))
            if amostras >= minimo and segundos > 0:
                return palavras / segundos * 60, "categoria"
        amostras = sum(v[0] for v in self.por_categoria.values())
        segundos = sum(v[2] for v in self.por_categoria.values())
        if amostras >= minimo and segundos > 0:
            return sum(v[1] for v in self.por_categoria.values()) / segundos * 60, "voz"
        return None

    def wpm(self, categoria: str | None = None) -> float:
        calibrado = self._calibrado(categoria)
        return calibrado[0] if calibrado else wpm_padrao(self.modelo)

    def fonte(self, categoria: str | None = None) -> str:
        calibrado = self._calibrado(categoria)
        if calibrado:
            return calibrado[1]
        return "modelo" if self.modelo in settings.fala_wpm_padrao_por_modelo else "geral"


def carregar_ritmos(db: Session, voz: VozEfetiva) -> Ritmos:
    ritmos = Ritmos(modelo=voz.modelo)
    try:
        linhas = db.execute(
            select(RitmoVoz.categoria, RitmoVoz.amostras, RitmoVoz.palavras, RitmoVoz.segundos).where(
                RitmoVoz.voz_id == voz.voz_id, RitmoVoz.modelo == voz.modelo, RitmoVoz.perfil == voz.perfil)
        ).all()
    except SQLAlchemyError:
        logger.warning("ritmo_voz_falhou operacao=leitura voz_id=%s", voz.voz_id, exc_info=True)
        return ritmos
    ritmos.por_categoria = {c: (int(a or 0), float(p or 0), float(s or 0)) for c, a, p, s in linhas}
    return ritmos


def wpm_para(db: Session, voz: VozEfetiva, categoria: str | None = None) -> float:
    return carregar_ritmos(db, voz).wpm(categoria)


def _ja_visto(audio: bytes | None) -> bool:
    if not audio:
        return False
    chave = f"ritmo_voz:visto:{hashlib.sha1(audio).hexdigest()}"
    try:
        return not redis_client.set(chave, "1", nx=True, ex=_TTL_DEDUPE_S)
    except RedisError:
        return False


def registrar_amostra(db: Session, voz: VozEfetiva, categoria: str, *, palavras: int, duracao_s: float,
                      pausas: int = 0, audio: bytes | None = None) -> bool:
    """Soma uma amostra medida ao agregado da voz. False quando a amostra não serve (curta, fora da faixa,
    áudio repetido) ou o banco falhou; nunca levanta."""
    if wpm_observado(palavras, duracao_s, pausas) is None or _ja_visto(audio):
        return False
    segundos = duracao_s - pausas * settings.fala_pausa_explicita_s
    filtro = (RitmoVoz.voz_id == voz.voz_id, RitmoVoz.modelo == voz.modelo, RitmoVoz.perfil == voz.perfil,
              RitmoVoz.categoria == categoria)
    agora = datetime.datetime.now(datetime.timezone.utc)
    soma = update(RitmoVoz).where(*filtro).values(
        amostras=RitmoVoz.amostras + 1, palavras=RitmoVoz.palavras + float(palavras),
        segundos=RitmoVoz.segundos + float(segundos), atualizado_em=agora,
    ).execution_options(synchronize_session=False)
    try:
        if db.execute(soma).rowcount == 0:
            try:
                with db.begin_nested():
                    db.add(RitmoVoz(voz_id=voz.voz_id, modelo=voz.modelo, perfil=voz.perfil, categoria=categoria,
                                    amostras=1, palavras=float(palavras), segundos=float(segundos), atualizado_em=agora))
                    db.flush()
            except IntegrityError:
                db.execute(soma)  # outra requisição criou a linha entre o UPDATE e o INSERT
        # Acima do limite as somas caem pela metade: amostras antigas pesam menos (média móvel simples).
        db.execute(update(RitmoVoz).where(*filtro, RitmoVoz.amostras > settings.fala_calibracao_max_amostras).values(
            amostras=RitmoVoz.amostras // 2, palavras=RitmoVoz.palavras / 2, segundos=RitmoVoz.segundos / 2,
        ).execution_options(synchronize_session=False))
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.warning("ritmo_voz_falhou operacao=gravacao voz_id=%s categoria=%s", voz.voz_id, categoria,
                       exc_info=True)
        return False
    return True


# --- orçamento que o /proxima deixa para o /tts (só para o log de excesso) ----------------------

def _chave_orcamento(programa_id: int, texto: str) -> str:
    return f"fala_orcamento:{programa_id}:{hashlib.sha1((texto or '').strip().encode()).hexdigest()}"


def guardar_orcamento_pendente(programa_id: int, texto: str, dados: dict) -> None:
    try:
        redis_client.set(_chave_orcamento(programa_id, texto), json.dumps(dados), ex=_TTL_ORCAMENTO_PENDENTE_S)
    except RedisError:
        logger.info("fala_orcamento_pendente_sem_redis programa_id=%s", programa_id)


def ler_orcamento_pendente(programa_id: int, texto: str) -> dict | None:
    try:
        bruto = redis_client.get(_chave_orcamento(programa_id, texto))
    except RedisError:
        return None
    try:
        return json.loads(bruto) if bruto else None
    except (TypeError, ValueError):
        return None
