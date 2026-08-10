import json


def extrair_json(texto: str) -> dict:
    """Faz parse de uma resposta de LLM que deveria ser JSON puro, mas as vezes vem
    envolvida em fences de markdown (```json ... ```) apesar do prompt pedir JSON cru.
    """
    texto = texto.strip()
    if texto.startswith("```"):
        texto = texto.strip("`")
        if texto[:4].lower() == "json":
            texto = texto[4:]
    return json.loads(texto)
