"""System prompt dividido em parte estável (cacheável) e parte variável por chamada.

O cache de prompt da Anthropic é por prefixo: qualquer byte diferente invalida o resto. O prompt do ao vivo tem
~80% de texto idêntico entre chamadas, mas a hora e outras linhas variáveis ficavam no meio, então o prefixo
comum era de ~600 caracteres. `SystemComPartes` é uma `str` (o texto original, na ordem original) que carrega as
duas partes: quem não conhece a divisão continua vendo uma string comum, e `criar_mensagem` só a usa com
`LLM_PROMPT_CACHE` ligado, enviando dois blocos de system (estático com `cache_control`, dinâmico sem).
"""


class SystemComPartes(str):
    estatico: str
    dinamico: str

    def __new__(cls, completo: str, estatico: str, dinamico: str):
        obj = super().__new__(cls, completo)
        obj.estatico = estatico
        obj.dinamico = dinamico
        return obj


def blocos_para_cache(system) -> list[dict] | None:
    """Dois blocos de system (estático com cache_control, dinâmico sem), ou None se não há divisão utilizável."""
    estatico = getattr(system, "estatico", None)
    if not estatico:
        return None
    blocos = [{"type": "text", "text": estatico, "cache_control": {"type": "ephemeral"}}]
    dinamico = getattr(system, "dinamico", "")
    if dinamico:
        blocos.append({"type": "text", "text": dinamico})
    return blocos
