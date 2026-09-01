from dataclasses import dataclass


@dataclass(frozen=True)
class LimitesPlano:
    # Numero de radialistas (personas de IA) que a conta pode ter. Todos atendem
    # pelo mesmo numero de WhatsApp da conta (Account.wuzapi_token) -- WhatsApp
    # nao e' limitado por plano, so existe um por conta.
    agentes: int
    mensagens_mes: int
    # Clonagem de voz (ElevenLabs Instant Voice Cloning) via app/tts/router.py -- feature
    # paga na ElevenLabs, por isso reservada a partir do plano Growth.
    clonagem_voz: bool
    # Quantos radialistas podem participar de um mesmo programa (dono + co-apresentadores),
    # pro diálogo multi-voz do ao vivo -- ver app/models/programa_radialista.py.
    radialistas_por_programa: int


PLANO_PADRAO = "starter"

PLANOS: dict[str, LimitesPlano] = {
    "starter": LimitesPlano(agentes=1, mensagens_mes=2000, clonagem_voz=False, radialistas_por_programa=1),
    "growth": LimitesPlano(agentes=3, mensagens_mes=3000, clonagem_voz=True, radialistas_por_programa=2),
    "professional": LimitesPlano(agentes=5, mensagens_mes=7500, clonagem_voz=True, radialistas_por_programa=3),
}


def limites_do_plano(plano: str) -> LimitesPlano:
    return PLANOS.get(plano, PLANOS[PLANO_PADRAO])


# Espelham frontend-painel/lib/planos.ts -- usados pra montar o valor cobrado no Stripe
# Checkout (ver app/billing/stripe_client.py) e pra exibir o texto na pagina /billing.
PRECO_AGENTE_ADICIONAL = 100
PRECO_EXCEDENTE_1000_MSG = 50

# Espelha Plano.preco em frontend-painel/lib/planos.ts -- so usado pro calculo de MRR no
# painel admin do sistema (app/admin_sistema/router.py). O Stripe (via price id, ver
# stripe_client.py) continua sendo a fonte de verdade pro valor cobrado de verdade.
PRECO_POR_PLANO: dict[str, int] = {"starter": 399, "growth": 599, "professional": 999}
