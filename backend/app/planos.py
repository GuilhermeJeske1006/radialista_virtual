from dataclasses import dataclass


@dataclass(frozen=True)
class LimitesPlano:
    # Numero de radialistas (personas de IA) que a conta pode ter. Todos atendem
    # pelo mesmo numero de WhatsApp da conta (Account.wuzapi_token) -- WhatsApp
    # nao e' limitado por plano, so existe um por conta.
    agentes: int
    mensagens_mes: int


PLANO_PADRAO = "starter"

PLANOS: dict[str, LimitesPlano] = {
    "starter": LimitesPlano(agentes=1, mensagens_mes=1000),
    "growth": LimitesPlano(agentes=3, mensagens_mes=3000),
    "professional": LimitesPlano(agentes=5, mensagens_mes=7500),
    "business": LimitesPlano(agentes=10, mensagens_mes=15000),
}


def limites_do_plano(plano: str) -> LimitesPlano:
    return PLANOS.get(plano, PLANOS[PLANO_PADRAO])
