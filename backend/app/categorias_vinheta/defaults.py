from sqlalchemy.orm import Session

from app.models.categoria_vinheta import CategoriaVinheta

# Categorias padrao que toda conta nova ja recebe pronta, pra o operador nao comecar do zero
# na tela de vinhetagem. Cada uma ja nasce com o tipo certo (biblioteca = audio pro cartwall,
# BibliotecaAudioItem; propaganda = Patrocinador) -- e' o tipo da categoria que decide o que
# pode entrar nela. Ver app/auth/router.py (registrar) e app/db/seed.py.
CATEGORIAS_PADRAO: list[tuple[str, str]] = [
    ("Abertura", "biblioteca"),
    ("Vinhetas", "biblioteca"),
    ("Efeitos Sonoros", "biblioteca"),
    ("Comerciais", "propaganda"),
    ("Encerramento", "biblioteca"),
]


def criar_categorias_padrao(db: Session, account_id: int) -> None:
    for nome, tipo in CATEGORIAS_PADRAO:
        db.add(CategoriaVinheta(account_id=account_id, nome=nome, tipo=tipo))
