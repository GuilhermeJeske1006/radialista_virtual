from dataclasses import dataclass


@dataclass(frozen=True)
class LimitesPlano:
    # Cada radialista (RadioConfig) e' 1 agente com seu proprio numero de WhatsApp
    # (wuzapi_token e' 1:1 com RadioConfig) -- por isso "agentes" tambem limita
    # quantos numeros de WhatsApp a conta pode conectar.
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
