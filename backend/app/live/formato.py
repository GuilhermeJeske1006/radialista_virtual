"""Direção editorial do formato musical, independente de fornecedores de IA."""
import re
import unicodedata

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
    return getattr(programa, "perfil_programacao", "padrao") == "musical_companhia"


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


def direcao_musical(tipo: str, primeira: bool = False) -> str:
    tipo = _tipo_fala(tipo)
    minimo, maximo, palavras = orcamento_fala(tipo, primeira)
    funcao = {
        "abertura": "Receba o ouvinte e apresente o programa uma única vez." if primeira else
        "Faça uma retomada breve; o programa já está em andamento.",
        "retomada": "Faça uma retomada breve; o programa já está em andamento.",
        "identificacao": "Diga apenas o nome da rádio ou do programa e uma assinatura curta.",
        "musica": "Anuncie brevemente a faixa confirmada e o pedido real, quando fornecido.",
        "encerramento": "Despeça-se do programa. Não prometa retorno após intervalo.",
    }.get(tipo, "Cumpra somente a função deste bloco, de forma breve.")
    return (
        "FORMATO MUSICAL DE COMPANHIA: a música ocupa o centro do programa. "
        f"{funcao} Meta de locução: {minimo} a {maximo} segundos, no máximo {palavras} palavras. "
        "Esta duração substitui a orientação genérica de quatro a seis frases. "
        "Fale com proximidade e energia moderada; use português coloquial, sem linguagem de publicidade "
        "genérica, adjetivos em série, hesitações encenadas ou risadas obrigatórias. "
        "Não acrescente assunto, hora, clima, pergunta, convite ao WhatsApp ou gancho só para preencher. "
        "Não anuncie cada música da sequência, não peça [BLOCO_MUSICAS:N] e não invente vinhetas. "
        "Não prometa intervalo, retorno ou conteúdo futuro sem programação confirmada. "
        "Mantenha as regras factuais e de atendimento dos pedidos reais."
    )
