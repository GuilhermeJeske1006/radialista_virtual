import unicodedata


def sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


def lista_ou(lista: list[str] | None, padrao: str) -> str:
    return ", ".join(lista) if lista else padrao
