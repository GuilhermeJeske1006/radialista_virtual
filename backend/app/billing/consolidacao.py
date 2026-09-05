from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.programa import Programa
from app.models.radio_config import RadioConfig


def marca_consolidada(db: Session, account: Account) -> bool:
    """Espelha frontend-painel/lib/useConfiguracaoInicial.ts (radialistaPronto + programaAtivo +
    whatsappConectado): so' faz sentido empurrar upgrade/compra numa conta que ja terminou a
    configuracao inicial -- senao o problema dela e' onboarding, nao plano pequeno."""
    if not account.wuzapi_token:
        return False

    radialista_pronto = (
        db.query(RadioConfig)
        .filter(
            RadioConfig.account_id == account.id,
            RadioConfig.ativo.is_(True),
            RadioConfig.voz_id.isnot(None),
            RadioConfig.voz_id != "",
        )
        .first()
        is not None
    )
    if not radialista_pronto:
        return False

    programa_ativo = (
        db.query(Programa)
        .join(RadioConfig, Programa.radio_config_id == RadioConfig.id)
        .filter(RadioConfig.account_id == account.id, Programa.ativo.is_(True))
        .first()
        is not None
    )
    return programa_ativo
