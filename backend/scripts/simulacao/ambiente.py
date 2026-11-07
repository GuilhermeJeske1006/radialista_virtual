"""Preparação do ambiente da simulação: variáveis, fakeredis, SQLite em memória e cenário no banco.

`preparar_processo` roda no CLI antes de qualquer import de app.* (nos testes, quem faz isso é o
conftest). As variáveis de ambiente se sobrepõem ao .env (app/config/settings.py).
"""

import contextlib
import dataclasses
import os
from typing import Iterator

# Valores que valem em todos os modos. Chaves de serviços que a simulação nunca usa recebem valores
# falsos sempre, para nenhuma credencial real entrar no processo.
VARIAVEIS_FIXAS = {
    "SENTRY_DSN": "",
    "SENTRY_ENVIRONMENT": "simulacao",
    "IA_MEDICAO_HABILITADA": "false",
    "IA_ORCAMENTO_BLOQUEAR": "false",
    "STORAGE_BACKEND": "local",
    "YOUTUBE_API_KEY": "",
    "SPOTIFY_CLIENT_ID": "",
    "SPOTIFY_CLIENT_SECRET": "",
    "WUZAPI_USER_TOKEN": "simulacao-wuzapi-falso",
    "WUZAPI_ADMIN_TOKEN": "simulacao-wuzapi-admin-falso",
    "JWT_SECRET": "simulacao-jwt-falso-nao-usar-em-producao",
    "STRIPE_SECRET_KEY": "sk_test_simulacao_falso",
    "STRIPE_WEBHOOK_SECRET": "whsec_simulacao_falso",
    "FRONTEND_URL": "http://localhost:3000",
    # Nenhum Postgres: qualquer sessão que escape da simulação cai num SQLite vazio, não num banco real.
    "DATABASE_URL": "sqlite://",
    "REDIS_URL": "redis://simulacao-fakeredis:6379/0",
}

# fake: nenhuma chave paga. llm: mantém a chave da Anthropic do .env. completo: mantém as duas.
VARIAVEIS_POR_MODO = {
    "fake": {"ANTHROPIC_API_KEY": "simulacao-chave-falsa", "ELEVENLABS_API_KEY": ""},
    "llm": {"ELEVENLABS_API_KEY": ""},
    "completo": {},
}


def preparar_processo(modo: str) -> None:
    os.environ.update(VARIAVEIS_FIXAS)
    os.environ.update(VARIAVEIS_POR_MODO[modo])
    import fakeredis
    import redis

    redis.from_url = lambda *args, **kwargs: fakeredis.FakeStrictRedis(decode_responses=True)


def criar_banco():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    import app.models  # noqa: F401 -- registra todas as tabelas no Base.metadata
    from app.db.database import Base

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    sessao = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    return engine, sessao


@contextlib.contextmanager
def cliente_http(sessao) -> Iterator:
    """TestClient sem `with` (não dispara o startup de app.main), como em tests/conftest.py."""
    from fastapi.testclient import TestClient

    from app.db.database import get_db
    from app.main import app

    anteriores = dict(app.dependency_overrides)

    def _get_db():
        yield sessao

    app.dependency_overrides[get_db] = _get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(anteriores)


@dataclasses.dataclass
class Cenario:
    account_id: int
    usuario_id: int
    radialista_id: int
    programa_id: int
    timezone: str
    vinhetas: dict[int, object]
    patrocinadores: dict[int, object]
    estrutura_blocos: list[str]


def semear(sessao, fixture) -> Cenario:
    """Conta, usuário admin, locutor, programa, vinhetas e patrocinadores da fixture."""
    from app.models.account import Account
    from app.models.biblioteca_audio import BibliotecaAudioItem
    from app.models.patrocinador import Patrocinador
    from app.models.programa import Programa
    from app.models.radio_config import RadioConfig
    from app.models.usuario import Usuario

    conta = Account(**fixture.conta.model_dump())
    sessao.add(conta)
    sessao.flush()
    usuario = Usuario(email=f"simulacao+{fixture.id}@locufy.invalid", senha_hash="sem-login-na-simulacao",
                      nome="Simulação", account_id=conta.id, role="admin")
    radialista = RadioConfig(account_id=conta.id, **fixture.radialista.model_dump())
    sessao.add_all([usuario, radialista])
    sessao.flush()

    campos = dict(fixture.programa)
    campos["horario_inicio"] = fixture.horario("horario_inicio")
    campos["horario_fim"] = fixture.horario("horario_fim")
    estrutura_bruta = list(campos.pop("estrutura_blocos", []))
    programa = Programa(radio_config_id=radialista.id, estrutura_blocos=[], **campos)
    sessao.add(programa)
    sessao.flush()

    vinhetas_por_papel, vinhetas = {}, {}
    for vinheta in fixture.vinhetas:
        item = BibliotecaAudioItem(
            account_id=conta.id, nome=f"Vinheta {vinheta.papel}", programa_id=programa.id, papel=vinheta.papel,
            texto=vinheta.texto, audio_path=f"sim/{vinheta.papel}.mp3" if vinheta.com_audio else None,
            duracao_segundos=round(vinheta.duracao_s) if vinheta.duracao_s else None, ativo=True,
            status="pronta", origem="simulacao",
        )
        sessao.add(item)
        sessao.flush()
        vinhetas_por_papel[vinheta.papel] = item.id
        vinhetas[item.id] = vinheta

    patrocinadores_por_chave, patrocinadores = {}, {}
    for patrocinador in fixture.patrocinadores:
        item = Patrocinador(
            account_id=conta.id, nome=patrocinador.nome, tipo_conteudo=patrocinador.tipo_conteudo,
            texto=patrocinador.texto,
            audio_path=f"sim/{patrocinador.chave}.mp3" if patrocinador.tipo_conteudo == "audio" else None,
            duracao_segundos=round(patrocinador.duracao_s) if patrocinador.duracao_s else None, ativo=True,
        )
        sessao.add(item)
        sessao.flush()
        patrocinadores_por_chave[patrocinador.chave] = item.id
        patrocinadores[item.id] = patrocinador

    def _resolver(bloco: str) -> str:
        if bloco.startswith("vinheta:@"):
            return f"vinheta:{vinhetas_por_papel[bloco.removeprefix('vinheta:@')]}"
        if bloco.startswith("patrocinador:@"):
            return f"patrocinador:{patrocinadores_por_chave[bloco.removeprefix('patrocinador:@')]}"
        return bloco

    programa.estrutura_blocos = [_resolver(b) for b in estrutura_bruta]
    sessao.commit()
    return Cenario(
        account_id=conta.id, usuario_id=usuario.id, radialista_id=radialista.id, programa_id=programa.id,
        timezone=fixture.radialista.timezone, vinhetas=vinhetas, patrocinadores=patrocinadores,
        estrutura_blocos=list(programa.estrutura_blocos),
    )
