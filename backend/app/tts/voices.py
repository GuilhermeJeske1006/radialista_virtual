"""Catalogo de vozes em portugues brasileiro da ElevenLabs."""

from concurrent.futures import ThreadPoolExecutor

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.account import Account
from app.tts.client import obter_preview_url

# Estilo de programa em que a voz soa bem, e os tipos de rádio (app.llm.tipos_radio) em que ela é
# indicada. "regional" marca sotaque de uma região: serve a qualquer tipo, por escolha da rádio.
PERFIS_VOZ = {
    "comunicador": {"rotulo": "Comunicador popular", "tipos_radio": ("popular_mix", "sertaneja", "mpb_variedades")},
    "jovem": {"rotulo": "Jovem e hits", "tipos_radio": ("jovem_pop", "eletronica_dance")},
    "jornalismo": {"rotulo": "Jornalismo", "tipos_radio": ("jornalismo_noticia",)},
    "noite": {"rotulo": "Noite e romântico", "tipos_radio": ("regional_flashback", "mpb_variedades")},
    "gospel": {"rotulo": "Gospel e reflexão", "tipos_radio": ("gospel",)},
    "interior": {"rotulo": "Sertanejo e interior", "tipos_radio": ("sertaneja", "regional_flashback")},
    "regional": {"rotulo": "Sotaque regional", "tipos_radio": ()},
    "esporte": {"rotulo": "Esporte", "tipos_radio": ("jornalismo_noticia", "popular_mix")},
    "maduro": {"rotulo": "Voz madura", "tipos_radio": ("regional_flashback", "gospel")},
}

# IDs e perfis conferidos em https://elevenlabs.io/text-to-speech/portuguese
# em 2026-09-08. Will e' o perfil brasileiro, nao a voz homonima em ingles.
VOZES_DISPONIVEIS = [
    {"voz_id": "Qrdut83w0Cr152Yb4Xn3", "nome": "Paulo", "genero": "masculina", "descricao": "Português brasileiro · Expressiva e confiante",
     "perfis": ["jornalismo", "comunicador"]},
    {"voz_id": "CstacWqMhJQlnfLPxRG4", "nome": "Will", "genero": "masculina", "descricao": "Português brasileiro · Grave, suave e afetuosa",
     "perfis": ["noite", "gospel"]},
    {"voz_id": "lWq4KDY8znfkV0DrK8Vb", "nome": "Yasmin Alves", "genero": "feminina", "descricao": "Português brasileiro · Leve, clara e musical",
     "perfis": ["noite", "gospel"]},
    {"voz_id": "cyD08lEy76q03ER1jZ7y", "nome": "Scheila", "genero": "feminina", "descricao": "Português brasileiro · Séria e direta",
     "perfis": ["jornalismo"]},
    # Biblioteca pt-BR (shared-voices, accent=brazilian), entre as mais usadas em 2026; nota 4,00 na
    # escuta às cegas de docs/benchmarks/2026-11-23-entrega-voz, contra 2,17 de Paulo/Yasmin no v3.
    {"voz_id": "rpNe0HOx7heUulPiOEaG", "nome": "Diego", "genero": "masculina", "descricao": "Português brasileiro · Locutor confiante",
     "perfis": ["comunicador"]},
    {"voz_id": "GDzHdQOi6jjf8zaXhCYD", "nome": "Raquel", "genero": "feminina", "descricao": "Português brasileiro · Expressiva e enérgica",
     "perfis": ["jovem", "comunicador"]},
    # Biblioteca pt-BR verificada no eleven_v4, sem preço extra, aviso de remoção de 730 dias e sem
    # moderação ao vivo; triagem e escuta em docs/benchmarks/2026-11-25-vozes-v4. Adicionar à conta da
    # ElevenLabs com scripts/adicionar_vozes_biblioteca.py (o aviso de remoção só vale para voz adicionada).
    # Comunicador popular
    {"voz_id": "HR2TRGmi4QbMsO5omv7l", "nome": "Rômulo", "genero": "masculina", "descricao": "Português brasileiro · Radialista experiente e caloroso",
     "perfis": ["comunicador"]},
    {"voz_id": "YU8EsJtXFMyKMxYtheDk", "nome": "Mário", "genero": "masculina", "descricao": "Português brasileiro · Animado e alto-astral",
     "perfis": ["comunicador", "jovem"]},
    {"voz_id": "4za2kOXGgUd57HRSQ1fn", "nome": "Lendário", "genero": "masculina", "descricao": "Português brasileiro · Vibrante e empolgado",
     "perfis": ["comunicador", "esporte"]},
    {"voz_id": "YklVF5l1Q8os8glyd5SM", "nome": "Camilla", "genero": "feminina", "descricao": "Português brasileiro · Locutora suave e acolhedora",
     "perfis": ["comunicador", "noite"]},
    {"voz_id": "TOXnXBKJSHqTwwqoWW0D", "nome": "Christine", "genero": "feminina", "descricao": "Português brasileiro · Dinâmica, de conversa",
     "perfis": ["comunicador", "jornalismo"]},
    # Jovem e hits
    {"voz_id": "TJ1zld0fSLwyF02SLwgy", "nome": "Eddy", "genero": "masculina", "descricao": "Português brasileiro · Locutor de FM carismático",
     "perfis": ["jovem", "comunicador"]},
    {"voz_id": "LuQ9eaWO9yCQrR73VQFa", "nome": "Victor Pinho", "genero": "masculina", "descricao": "Português brasileiro · Jovem e cheio de energia",
     "perfis": ["jovem"]},
    {"voz_id": "33B4UnXyTNbgLmdEDh5P", "nome": "Keren", "genero": "feminina", "descricao": "Português brasileiro · Jovem, doce e vibrante",
     "perfis": ["jovem"]},
    {"voz_id": "r2fkFV8WAqXq2AqBpgJT", "nome": "Amanda", "genero": "feminina", "descricao": "Português brasileiro · Divertida e comunicativa",
     "perfis": ["jovem", "comunicador"]},
    # Jornalismo
    {"voz_id": "9pDzHy2OpOgeXM8SeL0t", "nome": "Borges", "genero": "masculina", "descricao": "Português brasileiro · Claro e seguro, de jornal",
     "perfis": ["jornalismo"]},
    {"voz_id": "TY3h8ANhQUsJaa0Bga5F", "nome": "Cássio", "genero": "masculina", "descricao": "Português brasileiro · Grave, firme e direto",
     "perfis": ["jornalismo"]},
    {"voz_id": "MZxV5lN3cv7hi1376O0m", "nome": "Ana Dias", "genero": "feminina", "descricao": "Português brasileiro · Firme e envolvente",
     "perfis": ["jornalismo"]},
    # Noite e romântico
    {"voz_id": "ZqE9vIHPcrC35dZv0Svu", "nome": "Adam", "genero": "masculina", "descricao": "Português brasileiro · Grave, quente e romântico",
     "perfis": ["noite"]},
    {"voz_id": "EbiSUflQjzm4g7S895SC", "nome": "Léo Antônio", "genero": "masculina", "descricao": "Português brasileiro · Sereno e acolhedor",
     "perfis": ["noite", "gospel"]},
    {"voz_id": "GM2UA3fbsIaLHcswCDX9", "nome": "Nina", "genero": "feminina", "descricao": "Português brasileiro · Doce, refinada e segura",
     "perfis": ["noite"]},
    {"voz_id": "UZ8QqWVrz7tMdxiglcLh", "nome": "Lívia", "genero": "feminina", "descricao": "Português brasileiro · Calorosa e calma",
     "perfis": ["noite", "gospel"]},
    # Gospel e reflexão
    {"voz_id": "YNOujSUmHtgN6anjqXPf", "nome": "Victor Power", "genero": "masculina", "descricao": "Português brasileiro · Grave, sábio e marcante",
     "perfis": ["gospel"]},
    {"voz_id": "hgTbkcw2ddnzYh66cwCI", "nome": "Aninha", "genero": "feminina", "descricao": "Português brasileiro · Calma e reconfortante",
     "perfis": ["gospel"]},
    # Sertanejo e interior
    {"voz_id": "mP51FBaz7jxNEIeFJwxX", "nome": "Silas", "genero": "masculina", "descricao": "Português brasileiro · Homem do interior, sotaque caipira",
     "perfis": ["interior"]},
    {"voz_id": "lUaTJLTsNnLQQ5G5LJen", "nome": "Tomaz", "genero": "masculina", "descricao": "Português brasileiro · Tranquilo, sotaque do interior mineiro",
     "perfis": ["interior", "regional"]},
    {"voz_id": "GOkMqfyKMLVUcYfO2WbB", "nome": "Jenifer", "genero": "feminina", "descricao": "Português brasileiro · Natural, sotaque do interior paulista",
     "perfis": ["interior"]},
    # Sotaque regional
    {"voz_id": "4J31DrhygVjvFsoj7BsM", "nome": "Eduardo", "genero": "masculina", "descricao": "Português brasileiro · Claro, sotaque do Sul",
     "perfis": ["regional", "comunicador"]},
    {"voz_id": "EsbcEfYoTFrRNrRCVEHp", "nome": "Gaúcha", "genero": "feminina", "descricao": "Português brasileiro · Envolvente, sotaque gaúcho",
     "perfis": ["regional"]},
    {"voz_id": "bOfmGBubwU6YlrKXeRkh", "nome": "Cícero", "genero": "masculina", "descricao": "Português brasileiro · Amigável, sotaque nordestino",
     "perfis": ["regional"]},
    {"voz_id": "Fy0y2P2qP6NrsDcvbxmJ", "nome": "Thayane", "genero": "feminina", "descricao": "Português brasileiro · Segura, sotaque do Norte",
     "perfis": ["regional"]},
    {"voz_id": "PznTnBc8X6pvixs9UkQm", "nome": "Dani", "genero": "feminina", "descricao": "Português brasileiro · Calorosa, sotaque carioca",
     "perfis": ["regional"]},
    # Esporte
    {"voz_id": "Fjiik8aKXNDjmxd1Q2jF", "nome": "Nassif", "genero": "masculina", "descricao": "Português brasileiro · Narrador esportivo explosivo",
     "perfis": ["esporte"]},
    # Voz madura
    {"voz_id": "rnJZLKxtlBZt77uIED10", "nome": "Sérgio", "genero": "masculina", "descricao": "Português brasileiro · Sênior, grave e decidido",
     "perfis": ["maduro", "jornalismo"]},
    {"voz_id": "zoe2cQFqDDW4DteHDEWI", "nome": "Manoel", "genero": "masculina", "descricao": "Português brasileiro · Senhor de voz calorosa",
     "perfis": ["maduro"]},
    {"voz_id": "tafm7ExcoJRarAhYvRDv", "nome": "Ester", "genero": "feminina", "descricao": "Português brasileiro · Madura, serena e natural",
     "perfis": ["maduro"]},
]

_VOZES_POR_ID = {voz["voz_id"]: voz for voz in VOZES_DISPONIVEIS}


def listar_vozes() -> list[dict]:
    return VOZES_DISPONIVEIS


def rotulos_perfis(voz: dict) -> list[str]:
    return [PERFIS_VOZ[p]["rotulo"] for p in voz.get("perfis", ())]


def indicada_para_tipo_radio(voz: dict, tipo_radio: str | None) -> bool:
    return bool(tipo_radio) and any(tipo_radio in PERFIS_VOZ[p]["tipos_radio"] for p in voz.get("perfis", ()))


# so guarda preview_url resolvida com sucesso -- falha (sem api key, erro de rede) fica de
# fora do cache pra tentar de novo na proxima chamada, em vez de travar em None pra sempre.
_preview_cache: dict[str, str] = {}


def listar_vozes_com_preview() -> list[dict]:
    """Catalogo enriquecido com preview_url (amostra curta) de cada voz, pra o usuario
    ouvir antes de escolher. Voz sem preview disponivel (falha ou API nao configurada)
    entra com preview_url None -- o front so nao mostra o player pra ela.

    As previews faltantes sao buscadas em paralelo: com o catalogo maior, a busca em serie
    (ate 2 chamadas por voz) deixava a primeira listagem lenta.
    """
    faltando = [voz["voz_id"] for voz in VOZES_DISPONIVEIS if voz["voz_id"] not in _preview_cache]
    if faltando:
        with ThreadPoolExecutor(max_workers=min(8, len(faltando))) as executor:
            for voz_id, preview_url in zip(faltando, executor.map(obter_preview_url, faltando)):
                if preview_url:
                    _preview_cache[voz_id] = preview_url
    return [
        {**voz, "perfis_rotulos": rotulos_perfis(voz), "preview_url": _preview_cache.get(voz["voz_id"])}
        for voz in VOZES_DISPONIVEIS
    ]


def voz_valida(voz_id: str) -> bool:
    return voz_id in _VOZES_POR_ID


def descricao_voz(voz_id: str | None) -> str | None:
    """Descricao curta (genero + timbre) da voz do catalogo fixo, pra dar contexto ao LLM na
    hora de gerar personalidade/programa coerente com a voz ja escolhida. Voz clonada (fora do
    catalogo fixo) nao tem descricao aqui -- retorna None.
    """
    voz = _VOZES_POR_ID.get(voz_id or "")
    if not voz:
        return None
    estilos = ", ".join(rotulos_perfis(voz))
    return f"{voz['nome']}, voz {voz['genero']}, {voz['descricao']}" + (f" (indicada para: {estilos})" if estilos else "")


def voz_valida_para_conta(db: Session, account_id: int, voz_id: str, incluir_pendente: bool = False) -> bool:
    """Valida um voz_id do catalogo fixo, uma voz clonada (app/models/voz_clonada.py)
    pertencente a essa conta, ou uma voz clonada marcada como compartilhada (disponivel
    pra qualquer conta escolher, embora so a conta que criou possa renomear/excluir).
    """
    from app.models.perfil_voz import MetadadosVoz
    meta = db.get(MetadadosVoz, voz_id)
    if not incluir_pendente and meta and meta.requer_verificacao:
        return False
    if voz_valida(voz_id):
        return True

    from sqlalchemy import or_

    from app.models.voz_clonada import VozClonada

    return (
        db.query(VozClonada)
        .filter(VozClonada.voz_id == voz_id)
        .filter(or_(VozClonada.account_id == account_id, VozClonada.compartilhada.is_(True)))
        .first()
        is not None
    )


def validar_voz_ou_400(db: Session, account: Account, voz_id: str | None) -> str | None:
    voz_id = (voz_id or "").strip() or None
    if voz_id is not None and not voz_valida_para_conta(db, account.id, voz_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Voz invalida")
    return voz_id
