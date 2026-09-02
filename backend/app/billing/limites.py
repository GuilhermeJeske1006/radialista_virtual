import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.compra_excedente import CompraExcedente
from app.models.interaction_log import InteractionLog
from app.models.radio_config import RadioConfig
from app.planos import limites_do_plano

# Mensagem do ouvinte so consome cota do plano quando de fato vira resposta (entra na
# fila do ao vivo pra virar abraco/pedido de musica, ou recebe resposta automatica no
# proprio WhatsApp). Mensagem bloqueada (horario, rate limit, conteudo, plano) ou so
# registrada sem resposta ("guardado") nao conta.
_STATUS_RESPONDIDA = ("fila_musica", "fila_abraco", "respondido_whatsapp")


def mes_referencia_atual() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m")


def mensagens_respondidas_no_mes(db: Session, account_id: int) -> int:
    inicio_mes = datetime.datetime.now(datetime.timezone.utc).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )
    return (
        db.query(InteractionLog)
        .join(RadioConfig, InteractionLog.radio_config_id == RadioConfig.id)
        .filter(
            RadioConfig.account_id == account_id,
            InteractionLog.origem == "ouvinte",
            InteractionLog.status.in_(_STATUS_RESPONDIDA),
            InteractionLog.criado_em >= inicio_mes,
        )
        .count()
    )


def limite_agentes_efetivo(account: Account) -> int:
    return limites_do_plano(account.plano).agentes + account.agentes_extras


def limite_radialistas_por_programa(account: Account) -> int:
    return limites_do_plano(account.plano).radialistas_por_programa


def mensagens_extras_do_mes(db: Session, account_id: int) -> int:
    total = (
        db.query(func.coalesce(func.sum(CompraExcedente.quantidade), 0))
        .filter(
            CompraExcedente.account_id == account_id,
            CompraExcedente.mes_referencia == mes_referencia_atual(),
        )
        .scalar()
    )
    return int(total or 0)


def limite_mensagens_efetivo(db: Session, account: Account) -> int:
    return limites_do_plano(account.plano).mensagens_mes + mensagens_extras_do_mes(db, account.id)
