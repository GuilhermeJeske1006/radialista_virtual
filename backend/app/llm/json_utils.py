import json
import re


def extrair_json(texto: str) -> dict | list:
    """Faz parse de uma resposta de LLM que deveria ser JSON puro, mas as vezes vem
    envolvida em fences de markdown (```json ... ```) apesar do prompt pedir JSON cru.
    """
    texto = texto.strip()
    cerca = re.fullmatch(r"```(?:json)?\s*([\s\S]*?)\s*```", texto, re.IGNORECASE)
    if cerca:
        texto = cerca.group(1).strip()
    # Modelos podem explicar o JSON antes/depois. Aceita um único objeto completo;
    # nunca tenta reparar JSON truncado nem escolhe entre duas respostas conflitantes.
    # Resposta que já começa com "[" é uma lista (ex.: derivador de ganchos); fora isso, o objeto.
    inicio = 0 if texto.startswith("[") else texto.find("{")
    if inicio < 0:
        raise ValueError("Resposta sem objeto JSON")
    valor, fim = json.JSONDecoder().raw_decode(texto, inicio)
    if not isinstance(valor, (dict, list)) or re.search(r"[\{\[]", texto[fim:]):
        raise ValueError("Resposta JSON ambígua")
    return valor
