"""Configuracao global de testes.

Precisa rodar ANTES de qualquer import de app.* porque:
- app.config.settings.Settings() exige ANTHROPIC_API_KEY/WUZAPI_USER_TOKEN/JWT_SECRET
  (sem default de proposito, ver app/config/settings.py) -- setamos valores fake.
- app.config.redis_client cria o client Redis real no import (`redis.from_url(...)`) --
  trocamos por fakeredis pra nao depender de um Redis rodando durante os testes.
"""

import os

os.environ["ANTHROPIC_API_KEY"] = "test-anthropic-key"
os.environ["WUZAPI_USER_TOKEN"] = "test-wuzapi-user-token"
os.environ["WUZAPI_ADMIN_TOKEN"] = "test-wuzapi-admin-token"
os.environ["JWT_SECRET"] = "test-jwt-secret-not-for-prod"
os.environ["FRONTEND_URL"] = "http://localhost:3000"
os.environ["STRIPE_SECRET_KEY"] = "sk_test_fake"
os.environ["STRIPE_WEBHOOK_SECRET"] = "whsec_test_fake"
os.environ["ELEVENLABS_API_KEY"] = ""
os.environ["YOUTUBE_API_KEY"] = ""
os.environ["SPOTIFY_CLIENT_ID"] = ""
os.environ["SPOTIFY_CLIENT_SECRET"] = ""

import fakeredis
import redis as redis_module

redis_module.from_url = lambda *args, **kwargs: fakeredis.FakeStrictRedis(decode_responses=True)

import pytest  # noqa: E402 -- precisa vir depois do os.environ/fakeredis acima
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

import app.models  # noqa: F401, E402 -- registra todas as tabelas no Base.metadata
from app.auth.security import criar_token, hash_senha  # noqa: E402
from app.db.database import Base, get_db  # noqa: E402
from app.models.account import Account  # noqa: E402
from app.models.usuario import Usuario  # noqa: E402


@pytest.fixture(autouse=True)
def _redis_limpo():
    """Fakeredis e' um singleton de processo (criado uma vez no import de
    app.config.redis_client) -- sem isso, rate limit/cache de um teste vazaria pro proximo."""
    from app.config.redis_client import redis_client

    redis_client.flushall()
    yield
    redis_client.flushall()


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    testing_session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = testing_session_local()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def client(db_session):
    """TestClient sem `with` de proposito -- nao dispara o startup event de app.main
    (que faria Base.metadata.create_all contra o Postgres real de settings.database_url).
    As rotas so' usam o banco via Depends(get_db), que sobrescrevemos abaixo."""
    from app.main import app

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture()
def account_factory(db_session):
    def _criar(email: str = "user@example.com", senha: str = "senha12345", **kwargs) -> Account:
        account = Account(**kwargs)
        db_session.add(account)
        db_session.flush()

        usuario = Usuario(email=email, senha_hash=hash_senha(senha), account_id=account.id, role="admin")
        db_session.add(usuario)
        db_session.commit()
        db_session.refresh(account)
        return account

    return _criar


@pytest.fixture()
def account(account_factory) -> Account:
    return account_factory()


@pytest.fixture()
def usuario_factory(db_session):
    def _criar(account_id: int, email: str, senha: str = "senha12345", role: str = "membro", **kwargs) -> Usuario:
        usuario = Usuario(email=email, senha_hash=hash_senha(senha), account_id=account_id, role=role, **kwargs)
        db_session.add(usuario)
        db_session.commit()
        db_session.refresh(usuario)
        return usuario

    return _criar


@pytest.fixture()
def auth_headers(db_session):
    def _headers(account_id: int) -> dict:
        usuario = db_session.query(Usuario).filter_by(account_id=account_id, role="admin").first()
        return {"Authorization": f"Bearer {criar_token(usuario.id)}"}

    return _headers
