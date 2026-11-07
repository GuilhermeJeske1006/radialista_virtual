"""Estimativa da duração de uma fala: fórmula única do backend e da bancada de simulação.

Usada pelo relógio (F1) e pelo simulador da F0. A F2 troca a origem do `wpm` (calibração por voz)
sem mudar a assinatura. O ritmo padrão (145 palavras/min) é hipótese de projeto da skill
referencia-radio e fica em `app.live.relogio.ConfigRelogio`.
"""
from app.live.formato import contar_palavras


def estimar_duracao_s(texto: str, wpm: float) -> float:
    """Segundos de fala de `texto` a `wpm` palavras por minuto. Tags `[...]` não contam."""
    if wpm <= 0:
        raise ValueError("wpm deve ser maior que zero")
    return contar_palavras(texto or "") / wpm * 60
