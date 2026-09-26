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


PLANO_PADRAO = "flex"
# Tetos técnicos de configuração, independentes de cobrança. Mensagens não têm franquia.
PLANOS = {"flex": LimitesPlano(agentes=100, mensagens_mes=0, clonagem_voz=True, radialistas_por_programa=10)}


def limites_do_plano(plano: str) -> LimitesPlano:
    return PLANOS[PLANO_PADRAO]


PRECO_POR_PLANO = {"flex": 69.90}
# Compatibilidade de relatórios históricos; não existem ofertas adicionais.
PRECO_AGENTE_ADICIONAL = 0
PRECO_EXCEDENTE_1000_MSG = 0
