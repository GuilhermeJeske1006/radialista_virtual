import dataclasses

from sqlalchemy.orm import Session

from app.billing.consolidacao import marca_consolidada
from app.billing.limites import (
    limite_agentes_efetivo,
    limite_mensagens_efetivo,
    mensagens_respondidas_no_mes,
)
from app.models.account import Account
from app.models.radio_config import RadioConfig

# A partir de quanto do limite mensal de mensagens ja avisa (antes de estourar de vez).
_LIMIAR_ALERTA_MENSAGENS = 0.8


@dataclasses.dataclass(frozen=True)
class SinalUpsell:
    tipo: str
    titulo: str
    mensagem: str
    # Estouro de verdade (bloqueia atendimento/cadastro) manda e-mail alem da notificacao in-app
    # -- aviso leve ("quase estourando") fica so' na central de notificacoes, nao lota a caixa
    # de entrada do admin por uma folga que ele ainda tem tempo de resolver.
    enviar_email: bool


def calcular_sinal_upsell(db: Session, account: Account) -> SinalUpsell | None:
    """Decide qual (se algum) gatilho de upsell mostrar pra conta, na ordem: agentes cheios >
    mensagens estouradas > mensagens quase estourando. Nao avalia conta que ainda nao terminou
    a configuracao inicial (ver marca_consolidada) -- upsell nela e' ruido, nao oferta util."""
    if not marca_consolidada(db, account):
        return None

    agentes_usados = db.query(RadioConfig).filter_by(account_id=account.id).count()
    agentes_limite = limite_agentes_efetivo(account)
    if agentes_usados >= agentes_limite:
        return SinalUpsell(
            tipo="agentes_cheio",
            titulo="Seus radialistas bateram o limite do plano",
            mensagem=(
                f"Sua conta ja usa {agentes_usados} de {agentes_limite} agente(s) permitidos pelo plano "
                f"{account.plano}. Adicione um agente extra ou faca upgrade em /billing pra continuar crescendo."
            ),
            enviar_email=True,
        )

    mensagens_usadas = mensagens_respondidas_no_mes(db, account.id)
    mensagens_limite = limite_mensagens_efetivo(db, account)
    if mensagens_usadas >= mensagens_limite:
        return SinalUpsell(
            tipo="mensagens_estourou",
            titulo="Seu plano estourou o limite de mensagens do mes",
            mensagem=(
                f"Sua radio ja respondeu {mensagens_usadas} mensagens este mes, acima do limite de "
                f"{mensagens_limite} do plano {account.plano}. Compre um excedente ou faca upgrade em "
                "/billing pra nao deixar ouvinte sem resposta."
            ),
            enviar_email=True,
        )

    if mensagens_usadas >= mensagens_limite * _LIMIAR_ALERTA_MENSAGENS:
        return SinalUpsell(
            tipo="mensagens_quase_estourando",
            titulo="Seu plano esta perto do limite de mensagens",
            mensagem=(
                f"Sua radio ja usou {mensagens_usadas} de {mensagens_limite} mensagens do mes no plano "
                f"{account.plano}. Considere um upgrade em /billing antes de estourar."
            ),
            enviar_email=False,
        )

    return None
