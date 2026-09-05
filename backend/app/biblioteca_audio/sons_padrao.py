import io
import logging
from pathlib import Path

from pydub import AudioSegment
from sqlalchemy.orm import Session

from app.models.biblioteca_audio import BibliotecaAudioItem
from app.models.categoria_vinheta import CategoriaVinheta
from app.storage import get_storage

logger = logging.getLogger("radialista.biblioteca_audio")

_ASSETS_DIR = Path(__file__).parent / "assets" / "sons_padrao"
# Categoria propria, separada de "Efeitos Sonoros" (onde a conta guarda os efeitos que ela
# mesma sobe) -- assim os sons do sistema nao se misturam com o que o operador cadastrou.
_CATEGORIA_NOME = "Cartwall"

# Efeitos sonoros basicos gerados por sintese (sem dependencia de banco externo de audio,
# ver app/biblioteca_audio/assets/sons_padrao/) que toda conta ja ganha pronta no cartwall.
# "nome" e' a chave de idempotencia -- rodar de novo nao duplica (ver criar_sons_padrao).
SONS_PADRAO: list[dict] = [
    {"arquivo": "ding_acerto.mp3", "nome": "Acerto (ding)", "cor": "#4CAF50"},
    {"arquivo": "buzzer_erro.mp3", "nome": "Erro (buzzer)", "cor": "#C0392B"},
    {"arquivo": "beep_notificacao.mp3", "nome": "Notificacao (beep)", "cor": "#3498DB"},
    {"arquivo": "whoosh_transicao.mp3", "nome": "Transicao (whoosh)", "cor": "#8E44AD"},
    {"arquivo": "alerta_breaking_news.mp3", "nome": "Alerta (breaking news)", "cor": "#E67E22"},
    {"arquivo": "telefone_tocando.mp3", "nome": "Telefone tocando", "cor": "#16A085"},
    {"arquivo": "boing_comedia.mp3", "nome": "Comedia (boing)", "cor": "#F1C40F"},
    {"arquivo": "riser_suspense.mp3", "nome": "Suspense (riser)", "cor": "#2C3E50"},
]


def _categoria_cartwall(db: Session, account_id: int) -> CategoriaVinheta:
    categoria = (
        db.query(CategoriaVinheta)
        .filter_by(account_id=account_id, nome=_CATEGORIA_NOME, tipo="biblioteca")
        .first()
    )
    if categoria is None:
        categoria = CategoriaVinheta(account_id=account_id, nome=_CATEGORIA_NOME, tipo="biblioteca")
        db.add(categoria)
        db.flush()
    return categoria


def criar_sons_padrao(db: Session, account_id: int) -> None:
    """Seeda os efeitos sonoros padrao do sistema (SONS_PADRAO) no cartwall dessa conta,
    dentro da categoria propria "Cartwall" (ver _CATEGORIA_NOME). Idempotente por nome --
    so' cria o que ainda nao existe, pra poder rodar de novo (conta nova em
    app/auth/router.py, ou backfill em app/main.py::semear_sons_padrao_em_contas_existentes)
    sem duplicar.

    Upload pro storage (S3/local) e' best-effort: uma falha aqui (storage fora do ar) fica
    so' logada, nunca impede o cadastro/registro da conta em si.
    """
    # sessao do app usa autoflush=False (app/db/database.py) -- sem isso, categoria padrao
    # criada nessa mesma chamada de registro (criar_categorias_padrao, ainda pendente/sem
    # commit) nao apareceria na query abaixo e criariamos uma "Cartwall" duplicada.
    db.flush()

    nomes_existentes = {
        nome
        for (nome,) in db.query(BibliotecaAudioItem.nome).filter_by(account_id=account_id).all()
    }
    faltantes = [som for som in SONS_PADRAO if som["nome"] not in nomes_existentes]
    if not faltantes:
        return

    storage = get_storage()
    categoria: CategoriaVinheta | None = None

    for ordem, som in enumerate(faltantes):
        try:
            conteudo = (_ASSETS_DIR / som["arquivo"]).read_bytes()
            audio_path = f"biblioteca_audio/{account_id}/sistema_{som['arquivo']}"
            storage.save(audio_path, conteudo)
        except Exception:
            logger.warning("Falha ao seedar som padrao %s pra account_id=%s", som["arquivo"], account_id, exc_info=True)
            continue

        try:
            duracao_segundos = round(AudioSegment.from_file(io.BytesIO(conteudo)).duration_seconds)
        except Exception:
            duracao_segundos = None

        # categoria so' nasce quando o 1o som realmente for gravado -- se o storage estiver
        # fora do ar pra todos, nao fica uma categoria "Cartwall" vazia pra tras.
        if categoria is None:
            categoria = _categoria_cartwall(db, account_id)

        db.add(
            BibliotecaAudioItem(
                account_id=account_id,
                nome=som["nome"],
                categoria_id=categoria.id,
                audio_path=audio_path,
                audio_nome_original=som["arquivo"],
                duracao_segundos=duracao_segundos,
                cor=som["cor"],
                ordem=ordem,
                ativo=True,
            )
        )
