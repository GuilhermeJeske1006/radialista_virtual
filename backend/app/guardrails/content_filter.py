from app.models.programa import Programa

# Filtro de seguranca sempre ativo, independente da configuracao da radio.
TERMOS_SEMPRE_BLOQUEADOS = ["arma", "bomba", "suicidio", "droga ilicita"]


def contem_topico_proibido(texto: str, programa: Programa) -> bool:
    texto_lower = texto.lower()
    termos = list(programa.topicos_proibidos) + TERMOS_SEMPRE_BLOQUEADOS
    return any(termo.lower() in texto_lower for termo in termos)
