"""Memória editorial baseada exclusivamente em blocos confirmados pelo player."""

import datetime

from sqlalchemy.orm import Session

from app.models.canal_whatsapp import BlocoReproduzido, ContribuicaoOuvinte
from app.models.programa import Programa
from app.models.radio_config import RadioConfig


def ocorrencia_atual(db: Session, programa: Programa) -> str:
    from app.whatsapp.atendimento import ocorrencia

    radio = db.get(RadioConfig, programa.radio_config_id)
    return ocorrencia(programa, radio.timezone)


def historico_confirmado(db: Session, programa: Programa) -> list[BlocoReproduzido]:
    """Não confunde preparo com conteúdo ouvido, nem carrega outra ocorrência do programa."""
    radio = db.get(RadioConfig, programa.radio_config_id)
    limite = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=2)
    return db.query(BlocoReproduzido).filter_by(
        account_id=radio.account_id, programa_id=programa.id,
        ocorrencia=ocorrencia_atual(db, programa), estado="concluido",
    ).filter(BlocoReproduzido.atualizado_em >= limite).order_by(
        BlocoReproduzido.atualizado_em.desc(), BlocoReproduzido.id.desc(),
    ).limit(12).all()


def contribuicoes_validas(db: Session, programa: Programa) -> set[int]:
    radio = db.get(RadioConfig, programa.radio_config_id)
    return {a for (a,) in db.query(ContribuicaoOuvinte.assunto_id).filter(
        ContribuicaoOuvinte.account_id == radio.account_id,
        ContribuicaoOuvinte.programa_id == programa.id,
        ContribuicaoOuvinte.ocorrencia == ocorrencia_atual(db, programa),
        ContribuicaoOuvinte.estado.in_(("aprovada", "utilizada")),
    ).all()}


def notas_do_assunto(assunto_id: int, historico: list[BlocoReproduzido]) -> list[dict]:
    return [{"fala": b.fala[:1800], "pergunta": (b.assunto or {}).get("pergunta", ""),
             "confirmado_em": b.atualizado_em.isoformat()}
            for b in reversed([b for b in historico if b.assunto_id == assunto_id][:2])]
