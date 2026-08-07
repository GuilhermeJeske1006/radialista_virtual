"""Cria uma conta + RadioConfig de teste para desenvolvimento local.

Uso: python -m app.db.seed
"""

import datetime

from app.auth.security import hash_senha
from app.config.settings import settings
from app.db.database import Base, SessionLocal, engine
from app.models.account import Account
from app.models.programa import Programa
from app.models.radio_config import RadioConfig

EMAIL_TESTE = "teste@radialista.local"
SENHA_TESTE = "teste1234"


def seed() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        existente = db.query(Account).filter_by(email=EMAIL_TESTE).first()
        if existente:
            print("Conta de teste ja existe, nada a fazer.")
            return

        account = Account(
            email=EMAIL_TESTE,
            senha_hash=hash_senha(SENHA_TESTE),
            plano_status="ativo",
            wuzapi_token=settings.wuzapi_user_token,
        )
        db.add(account)
        db.flush()

        config = RadioConfig(
            account_id=account.id,
            nome_locutor=settings.locutor_nome,
        )
        db.add(config)
        db.flush()

        programa = Programa(
            radio_config_id=config.id,
            nome="Programa Principal",
            dias_semana=[],
            horario_inicio=datetime.time(0, 0),
            horario_fim=datetime.time(23, 59),
            topicos_permitidos=["transito", "clima", "musica", "noticias locais", "programacao da radio"],
            topicos_proibidos=["politica", "religiao"],
            limite_mensagens_hora=10,
        )
        db.add(programa)
        db.commit()
        print(f"Conta de teste criada: email={EMAIL_TESTE} senha={SENHA_TESTE}")
        print(f"RadioConfig criada: id={config.id} nome={config.nome_locutor}")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
