import datetime

from jose import jwt

from app.auth.security import ALGORITHM, criar_token, decodificar_token, hash_senha, verificar_senha
from app.config.settings import settings


def test_hash_senha_gera_hash_diferente_da_senha():
    hash_ = hash_senha("minhasenha123")
    assert hash_ != "minhasenha123"


def test_verificar_senha_aceita_senha_correta():
    hash_ = hash_senha("minhasenha123")
    assert verificar_senha("minhasenha123", hash_) is True


def test_verificar_senha_rejeita_senha_errada():
    hash_ = hash_senha("minhasenha123")
    assert verificar_senha("outrasenha", hash_) is False


def test_criar_token_decodifica_para_o_mesmo_usuario_id():
    token = criar_token(42)
    assert decodificar_token(token) == 42


def test_decodificar_token_invalido_devolve_none():
    assert decodificar_token("token-invalido") is None


def test_decodificar_token_expirado_devolve_none():
    payload = {
        "sub": "1",
        "exp": datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=1),
    }
    token_expirado = jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)
    assert decodificar_token(token_expirado) is None


def test_decodificar_token_assinado_com_outro_segredo_devolve_none():
    payload = {
        "sub": "1",
        "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=5),
    }
    token_forjado = jwt.encode(payload, "outro-segredo", algorithm=ALGORITHM)
    assert decodificar_token(token_forjado) is None
