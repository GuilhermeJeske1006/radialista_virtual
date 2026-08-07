import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from app.auth.router import router as auth_router
from app.billing.router import router as billing_router
from app.config.router import router as config_router
from app.config.settings import settings
from app.db.database import Base, engine
from app.live.router import router as live_router
from app.metrics.router import router as metrics_router
from app.models import Account, FilaAoVivo, Programa, RadioConfig  # noqa: F401 -- garante que as tabelas sejam registradas no metadata
from app.onboarding.router import router as onboarding_router
from app.tts.router import router as tts_router
from app.whatsapp.webhook import router as whatsapp_router

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Radialista Virtual")

_frontend_origins = {settings.frontend_url}
if "localhost" in settings.frontend_url:
    _frontend_origins.add(settings.frontend_url.replace("localhost", "127.0.0.1"))
elif "127.0.0.1" in settings.frontend_url:
    _frontend_origins.add(settings.frontend_url.replace("127.0.0.1", "localhost"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(_frontend_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(whatsapp_router)
app.include_router(auth_router)
app.include_router(config_router)
app.include_router(onboarding_router)
app.include_router(metrics_router)
app.include_router(billing_router)
app.include_router(live_router)
app.include_router(tts_router)


@app.on_event("startup")
async def criar_tabelas():
    Base.metadata.create_all(bind=engine)
    garantir_colunas_radio_config()
    garantir_colunas_account()
    garantir_colunas_programa()
    migrar_conteudo_para_programas()
    migrar_whatsapp_para_account()


def garantir_colunas_radio_config():
    inspector = inspect(engine)
    if "radio_configs" not in inspector.get_table_names():
        return

    colunas = {coluna["name"] for coluna in inspector.get_columns("radio_configs")}
    novas_colunas = {
        "voz_id": "VARCHAR NULL",
    }

    # account_id era unique (1 radialista por conta); agora uma conta pode ter varios radialistas.
    indice_account_id_unico = any(
        indice["name"] == "ix_radio_configs_account_id" and indice["unique"]
        for indice in inspector.get_indexes("radio_configs")
    )

    with engine.begin() as conn:
        for nome, definicao in novas_colunas.items():
            if nome not in colunas:
                conn.execute(text(f"ALTER TABLE radio_configs ADD COLUMN {nome} {definicao}"))

        if indice_account_id_unico:
            conn.execute(text("DROP INDEX IF EXISTS ix_radio_configs_account_id"))
            conn.execute(text("CREATE INDEX ix_radio_configs_account_id ON radio_configs (account_id)"))


def garantir_colunas_account():
    inspector = inspect(engine)
    if "accounts" not in inspector.get_table_names():
        return

    colunas = {coluna["name"] for coluna in inspector.get_columns("accounts")}
    novas_colunas = {
        "plano": "VARCHAR DEFAULT 'starter' NOT NULL",
        "nome": "VARCHAR DEFAULT '' NOT NULL",
        "wuzapi_token": "VARCHAR NULL",
        "wuzapi_user_id": "VARCHAR NULL",
    }

    with engine.begin() as conn:
        for nome, definicao in novas_colunas.items():
            if nome not in colunas:
                conn.execute(text(f"ALTER TABLE accounts ADD COLUMN {nome} {definicao}"))
        if "wuzapi_token" not in colunas:
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_accounts_wuzapi_token ON accounts (wuzapi_token)"))
        if "wuzapi_user_id" not in colunas:
            conn.execute(
                text("CREATE UNIQUE INDEX IF NOT EXISTS ix_accounts_wuzapi_user_id ON accounts (wuzapi_user_id)")
            )


def garantir_colunas_programa():
    inspector = inspect(engine)
    if "programas" not in inspector.get_table_names():
        return

    colunas = {coluna["name"] for coluna in inspector.get_columns("programas")}
    novas_colunas = {
        "data_especifica": "DATE NULL",
        "estrutura_blocos": "JSON DEFAULT '[]' NOT NULL",
        "ia_pode_adicionar_blocos": "BOOLEAN DEFAULT TRUE NOT NULL",
    }

    with engine.begin() as conn:
        for nome, definicao in novas_colunas.items():
            if nome not in colunas:
                conn.execute(text(f"ALTER TABLE programas ADD COLUMN {nome} {definicao}"))


# Colunas de conteudo (tom, topicos, mensagens, musicas, noticias, pesquisa) que
# migraram de RadioConfig (locutor) para Programa -- um mesmo locutor pode
# apresentar programas com conteudo diferente em horarios diferentes.
_COLUNAS_CONTEUDO_PROGRAMA = {
    "tom": "VARCHAR DEFAULT '' NOT NULL",
    "topicos_permitidos": "JSON DEFAULT '[]' NOT NULL",
    "topicos_proibidos": "JSON DEFAULT '[]' NOT NULL",
    "mensagem_saudacao": "VARCHAR DEFAULT '' NOT NULL",
    "mensagem_recusa": "VARCHAR DEFAULT '' NOT NULL",
    "limite_mensagens_hora": "INTEGER DEFAULT 10 NOT NULL",
    "generos_musicais": "JSON DEFAULT '[]' NOT NULL",
    "musicas_permitidas": "JSON DEFAULT '[]' NOT NULL",
    "musicas_bloqueadas": "JSON DEFAULT '[]' NOT NULL",
    "criterios_busca_musicas": "VARCHAR DEFAULT '' NOT NULL",
    "assuntos_ao_vivo": "JSON DEFAULT '[]' NOT NULL",
    "tipos_noticias": "JSON DEFAULT '[]' NOT NULL",
    "fontes_noticias": "JSON DEFAULT '[]' NOT NULL",
    "pode_pesquisar": "BOOLEAN DEFAULT FALSE NOT NULL",
    "fontes_pesquisa": "JSON DEFAULT '[]' NOT NULL",
    "instrucoes_pesquisa": "VARCHAR DEFAULT '' NOT NULL",
}


def migrar_conteudo_para_programas():
    inspector = inspect(engine)
    if "programas" not in inspector.get_table_names() or "radio_configs" not in inspector.get_table_names():
        return

    colunas_programas = {coluna["name"] for coluna in inspector.get_columns("programas")}
    colunas_radio_configs = {coluna["name"] for coluna in inspector.get_columns("radio_configs")}

    # "tom" so existe em radio_configs enquanto essa migracao (uma unica vez) nao rodou.
    precisa_migrar_dados = "tom" in colunas_radio_configs

    with engine.begin() as conn:
        for nome, definicao in _COLUNAS_CONTEUDO_PROGRAMA.items():
            if nome not in colunas_programas:
                conn.execute(text(f"ALTER TABLE programas ADD COLUMN {nome} {definicao}"))

        if not precisa_migrar_dados:
            return

        colunas_copiar = ", ".join(_COLUNAS_CONTEUDO_PROGRAMA.keys())
        atribuicoes = ", ".join(f"{c} = rc.{c}" for c in _COLUNAS_CONTEUDO_PROGRAMA.keys())

        # Todo programa existente herda o conteudo do locutor que o hospeda hoje.
        conn.execute(
            text(f"UPDATE programas p SET {atribuicoes} FROM radio_configs rc WHERE p.radio_config_id = rc.id")
        )

        # Locutor sem nenhum programa cadastrado ganha um "Programa Principal" 24h
        # pra nao perder a configuracao que ele ja tinha.
        conn.execute(
            text(
                f"""
                INSERT INTO programas (
                    radio_config_id, nome, dias_semana, horario_inicio, horario_fim, ativo, criado_em, {colunas_copiar}
                )
                SELECT
                    rc.id, 'Programa Principal', '[]'::json, '00:00:00', '23:59:59', true, now(),
                    {", ".join(f"rc.{c}" for c in _COLUNAS_CONTEUDO_PROGRAMA.keys())}
                FROM radio_configs rc
                WHERE NOT EXISTS (SELECT 1 FROM programas p WHERE p.radio_config_id = rc.id)
                """
            )
        )

        for coluna in [*_COLUNAS_CONTEUDO_PROGRAMA.keys(), "horario_inicio", "horario_fim"]:
            conn.execute(text(f"ALTER TABLE radio_configs DROP COLUMN IF EXISTS {coluna}"))


def migrar_whatsapp_para_account():
    """Move wuzapi_token/wuzapi_user_id de radio_configs (1 por agente) pra accounts
    (1 por conta -- ver Account.wuzapi_token). So existe enquanto radio_configs ainda
    tiver essas colunas (migracao roda uma unica vez).
    """
    inspector = inspect(engine)
    if "radio_configs" not in inspector.get_table_names() or "accounts" not in inspector.get_table_names():
        return

    colunas_radio_configs = {coluna["name"] for coluna in inspector.get_columns("radio_configs")}
    if "wuzapi_token" not in colunas_radio_configs:
        return

    with engine.begin() as conn:
        indice_token_unico = any(
            indice["name"] == "ix_radio_configs_wuzapi_token" for indice in inspector.get_indexes("radio_configs")
        )
        indice_user_id_unico = any(
            indice["name"] == "ix_radio_configs_wuzapi_user_id" for indice in inspector.get_indexes("radio_configs")
        )
        if indice_token_unico:
            conn.execute(text("DROP INDEX IF EXISTS ix_radio_configs_wuzapi_token"))
        if indice_user_id_unico:
            conn.execute(text("DROP INDEX IF EXISTS ix_radio_configs_wuzapi_user_id"))

        # Um radialista (o mais antigo com token) empresta seu numero pra conta inteira.
        conn.execute(
            text(
                """
                UPDATE accounts a SET
                    wuzapi_token = rc.wuzapi_token,
                    wuzapi_user_id = rc.wuzapi_user_id
                FROM (
                    SELECT DISTINCT ON (account_id) account_id, wuzapi_token, wuzapi_user_id
                    FROM radio_configs
                    WHERE wuzapi_token IS NOT NULL
                    ORDER BY account_id, id ASC
                ) rc
                WHERE a.id = rc.account_id AND a.wuzapi_token IS NULL
                """
            )
        )

        conn.execute(text("ALTER TABLE radio_configs DROP COLUMN IF EXISTS wuzapi_token"))
        conn.execute(text("ALTER TABLE radio_configs DROP COLUMN IF EXISTS wuzapi_user_id"))


@app.get("/health")
async def health():
    return {"status": "ok"}
