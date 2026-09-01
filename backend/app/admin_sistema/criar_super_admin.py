"""Cria (ou atualiza a senha de) um super-admin -- unica forma de provisionar acesso ao
painel /admin/*, ja que nao existe tela de cadastro (papel de operador, nao de produto).

Uso: python -m app.admin_sistema.criar_super_admin email@dominio.com "senha" ["Nome"]
"""

import sys

from app.auth.security import hash_senha
from app.db.database import Base, SessionLocal, engine
from app.models.super_admin import SuperAdmin


def criar_super_admin(email: str, senha: str, nome: str = "") -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        existente = db.query(SuperAdmin).filter_by(email=email).first()
        if existente:
            existente.senha_hash = hash_senha(senha)
            existente.ativo = True
            if nome:
                existente.nome = nome
            db.commit()
            print(f"Super-admin existente atualizado: email={email}")
            return

        admin = SuperAdmin(email=email, senha_hash=hash_senha(senha), nome=nome)
        db.add(admin)
        db.commit()
        print(f"Super-admin criado: email={email}")
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print('Uso: python -m app.admin_sistema.criar_super_admin email@dominio.com "senha" ["Nome"]')
        sys.exit(1)

    _email = sys.argv[1]
    _senha = sys.argv[2]
    _nome = sys.argv[3] if len(sys.argv) > 3 else ""
    criar_super_admin(_email, _senha, _nome)
