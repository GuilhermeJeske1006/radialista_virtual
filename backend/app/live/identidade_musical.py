"""Correspondência de obra e artista, independente da posição na busca do YouTube."""
import html
import re

from app.util.texto import sem_acento


def normalizar(texto: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", sem_acento(html.unescape(texto).lower()).replace("&", " e ")).strip()


def _compacto(texto: str) -> str:
    return normalizar(texto).replace(" ", "")


_VERSAO_ALTERNATIVA = re.compile(
    r"\b(demo|medley|cover|karaoke|instrumental|slowed|sped up|speed up|ao vivo|live|"
    r"acoustic|acustic[oa]|unplugged|extended|remix|wogan|top of the pops|hit man|performance)\b"
)
_METADADO = re.compile(
    r"\b(official|oficial|music video|video|audio|lyrics?|lyric video|visualizer|hd|hq|4k|"
    r"remaster(?:ed|izado|izada)?|digital master|radio edit|video edit|album version|single version|"
    r"stereo|mono|version|versao)\b"
)


def versao_de_estudio(titulo: str, titulo_obra: str | None = None) -> bool:
    texto = normalizar(titulo)
    if titulo_obra:
        texto = texto.replace(normalizar(titulo_obra), "", 1)
    return not _VERSAO_ALTERNATIVA.search(texto) and " / " not in html.unescape(titulo)


def corresponde(artista: str, titulo: str, encontrado: str, canal: str) -> bool:
    """Exige ambos. Metadados de upload/remaster não mudam a obra; medleys não são uma faixa."""
    esperado = _compacto(artista)
    canal_limpo = re.sub(r"(?:vevo|topic|official|oficial)$", "", _compacto(canal))
    texto = normalizar(encontrado)
    nome = normalizar(artista)
    artista_no_titulo = bool(re.search(rf"(?<!\w){re.escape(nome)}(?!\w)", texto))
    if esperado != canal_limpo and not artista_no_titulo:
        return False
    # Remove o artista somente como prefixo/sufixo separado: não apaga palavras do título.
    original = html.unescape(encontrado)
    partes = re.split(r"\s+[-–—|]\s+", original)
    if len(partes) > 1 and _compacto(partes[0]) == esperado:
        original = " - ".join(partes[1:])
    elif len(partes) > 1 and _compacto(partes[-1]) == esperado:
        original = " - ".join(partes[:-1])
    if " / " in original or re.search(r"\bmedley\b", normalizar(original)):
        return False
    if normalizar(original) == normalizar(titulo):
        return True
    def obra(valor):
        valor = re.sub(r"[\[(]([^\])]+)[\])]", lambda m: "" if (
            _VERSAO_ALTERNATIVA.search(normalizar(m.group(1))) or _METADADO.search(normalizar(m.group(1)))
            or re.fullmatch(r"\d{4}", m.group(1).strip())
        ) else m.group(0), valor)
        valor = normalizar(valor)
        return " ".join(_METADADO.sub(" ", valor).split())
    esperado_titulo = obra(titulo)
    return bool(esperado_titulo) and obra(original) == esperado_titulo
