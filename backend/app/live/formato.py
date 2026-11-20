"""Constantes do formato musical e compatibilidade com o catálogo de formatos (F6).

Continua dono dos números e roteiros de antes da F6 (`ROTEIRO_PADRAO`, `ROTEIRO_MUSICAL`, `ORCAMENTOS`) e dos
utilitários de texto; o catálogo (`app.live.formatos`) os lê daqui sem copiar. `musical_companhia` e
`direcao_musical` delegam ao catálogo com importação tardia (o catálogo importa este módulo).
"""
import re
import unicodedata

# Roteiro que o ao vivo segue quando o programa nao tem estrutura_blocos propria (ver
# _tipo_proximo_bloco em app.live.router). Compartilhado com app.vinhetas.estrutura, que
# materializa ele antes de inserir as vinhetas numa estrutura vazia.
ROTEIRO_PADRAO = ("musica", "abertura", "comentario", "noticia", "chamada_ouvinte")

ROTEIRO_MUSICAL = ("musica", "musica", "identificacao", "musica", "musica", "retomada")

# Tempos são metas editoriais; a velocidade da voz determina a duração final.
ORCAMENTOS = {
    "abertura": (20, 30, 65),
    "retomada": (6, 12, 25),
    "identificacao": (3, 7, 14),
    "musica": (4, 8, 18),
    "encerramento": (10, 18, 38),
}


def musical_companhia(programa) -> bool:
    """O programa segue o ciclo musical (`musical_adulto` ou o alias `musical_companhia`)."""
    from app.live.formatos import formato_do_programa

    return formato_do_programa(programa).comportamento.ciclo == "musical"


def orcamento_fala(tipo: str, primeira: bool = False) -> tuple[int, int, int]:
    tipo = _tipo_fala(tipo)
    if tipo == "abertura" and not primeira:
        tipo = "retomada"
    return ORCAMENTOS.get(tipo, (10, 20, 45))


def contar_palavras(texto: str) -> int:
    return len(re.findall(r"\S+", re.sub(r"\[[^\]]*\]", "", texto)))


def _tipo_fala(tipo: str) -> str:
    normalizado = "".join(c for c in unicodedata.normalize("NFD", tipo.strip().lower())
                          if unicodedata.category(c) != "Mn")
    return normalizado.split(" ", 1)[0]


def direcao_musical(tipo: str, primeira: bool = False, orcamento: tuple[int, int, int] | None = None) -> str:
    """Direção do formato musical (texto inalterado desde a F2). `orcamento` (mínimo s, máximo s, palavras) substitui
    o de ORCAMENTOS quando o relógio da hora (app.live.relogio) calculou o espaço deste bloco."""
    from app.live.formatos import ID_MUSICAL, direcao_formato

    return direcao_formato(ID_MUSICAL, tipo, primeira, orcamento)
