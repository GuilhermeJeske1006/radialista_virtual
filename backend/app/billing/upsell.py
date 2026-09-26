import dataclasses

from sqlalchemy.orm import Session

from app.models.account import Account

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
    from app.models.consumo_flex import ContaConsumo
    conta = db.get(ContaConsumo, account.id)
    if conta and conta.limite and conta.exposicao >= conta.limite * 0.9:
        return SinalUpsell(tipo="limite_financeiro", titulo="Consumo próximo do limite financeiro",
            mensagem="Confira o extrato e ajuste seu limite financeiro em /billing se desejar continuar gerando.",
            enviar_email=False)
    return None
