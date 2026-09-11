"""Conjunto padrão de fontes oficiais pra rádio local, pré-preenchido a partir da cidade da
conta (ver Fase 1 do plano de jornalismo). Cria só o NOME da fonte (ex.: 'Defesa Civil de
Blumenau') -- nunca inventamos a URL do feed, que não temos como saber de antemão pra cada
cidade brasileira (mesma cautela já aplicada a feriados municipais, ver
Programa.feriados_municipais). A fonte nasce inativa e sem url_feed; o worker (ver
app.news.worker) ignora fonte sem feed até alguém completar o cadastro com a URL real.
"""

from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.fonte_noticia import FonteNoticia

# (nome-base, tipo, anexar cidade ao nome) -- so' anexa "de {cidade}" quando o nome-base e' de
# orgao proprio do municipio (faz sentido gramatical); nome ja generico/regional fica como esta.
_SEEDS_PADRAO = (
    ("Prefeitura", "oficial", True),
    ("Defesa Civil", "oficial", True),
    ("Corpo de Bombeiros", "oficial", True),
    ("Guarda Municipal", "oficial", True),
    ("SAMU / Secretaria de Saúde", "oficial", True),
    ("Concessionária de energia/água local", "oficial", False),
    ("Portal de notícias regional", "imprensa", False),
)


def nomes_seed(cidade: str) -> list[tuple[str, str]]:
    """[(nome, tipo)] a partir da cidade, sem tocar banco -- usado pelo seed de verdade
    (criar_seeds_fontes) e por teste, sem precisar de sessão de banco."""
    return [
        (f"{nome} de {cidade}" if anexar_cidade and cidade else nome, tipo)
        for nome, tipo, anexar_cidade in _SEEDS_PADRAO
    ]


def criar_seeds_fontes(db: Session, account: Account) -> list[FonteNoticia]:
    """Cria as fontes seed pra conta, uma única vez -- idempotente por nome (não duplica se já
    rodou antes pra essa conta). Cada fonte nasce com url_feed vazio e ativa=False: cabe à rádio
    completar a URL do feed real (via CRUD de fontes, ver app.config.router) antes dela entrar
    de fato na coleta do worker."""
    existentes = {nome for nome, in db.query(FonteNoticia.nome).filter_by(account_id=account.id).all()}
    novas = []
    for nome, tipo in nomes_seed(account.cidade):
        if nome in existentes:
            continue
        fonte = FonteNoticia(account_id=account.id, nome=nome, tipo=tipo, url_feed="", ativa=False)
        db.add(fonte)
        novas.append(fonte)
    if novas:
        db.commit()
        for fonte in novas:
            db.refresh(fonte)
    return novas
