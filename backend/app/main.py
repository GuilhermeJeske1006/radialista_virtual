import logging
import logging.handlers
import pathlib

import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sentry_sdk.integrations.logging import LoggingIntegration
from sqlalchemy import inspect, text

from app.admin_sistema.auth_router import router as admin_sistema_auth_router
from app.admin_sistema.router import router as admin_sistema_router
from app.auth.router import router as auth_router
from app.biblioteca_audio.router import router as biblioteca_audio_router
from app.billing.router import router as billing_router
from app.categorias_vinheta.defaults import CATEGORIAS_PADRAO
from app.categorias_vinheta.router import router as categorias_vinheta_router
from app.config.router import router as config_router
from app.config.settings import settings
from app.db.database import Base, engine
from app.equipe.router import router as equipe_router
from app.live.router import router as live_router
from app.metrics.router import router as metrics_router
from app.models import (  # noqa: F401 -- garante que as tabelas sejam registradas no metadata
    Account,
    BibliotecaAudioItem,
    CategoriaVinheta,
    ConviteUsuario,
    FilaAoVivo,
    InteractionLog,
    Musica,
    MusicaHistorico,
    Notificacao,
    PasswordResetToken,
    Patrocinador,
    Programa,
    ProgramaRadialista,
    RadioConfig,
    SuperAdmin,
    TemaHistorico,
    Usuario,
    VozClonada,
)
from app.notificacoes.router import router as notificacoes_router
from app.onboarding.router import router as onboarding_router
from app.patrocinadores.router import router as patrocinadores_router
from app.suporte.router import router as suporte_router
from app.tts.router import router as tts_router
from app.whatsapp.webhook import router as whatsapp_router

_LOG_DIR = pathlib.Path("logs")
_LOG_DIR.mkdir(parents=True, exist_ok=True)

# Sem isso, log so' vive no stdout do container -- some se ele reiniciar (restart:
# unless-stopped, reload do uvicorn em dev) antes de alguem olhar. Arquivo rotativo
# (10MB x 5) sobrevive o restart e da' pra investigar erro depois do fato.
_arquivo_handler = logging.handlers.RotatingFileHandler(
    _LOG_DIR / "app.log", maxBytes=10 * 1024 * 1024, backupCount=5
)
_arquivo_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))

logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler(), _arquivo_handler])

# DSN vazio (dev local sem Sentry configurado) desativa o SDK inteiro -- init() com
# dsn=None e' um no-op documentado, sem custo nem chamada de rede.
sentry_sdk.init(
    dsn=settings.sentry_dsn or None,
    environment=settings.sentry_environment,
    traces_sample_rate=settings.sentry_traces_sample_rate,
    enable_logs=settings.sentry_enable_logs,
    integrations=[
        # warning+ vira log buscavel no Sentry; error+ continua virando evento (default).
        LoggingIntegration(sentry_logs_level=logging.WARNING),
    ],
)

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


@app.middleware("http")
async def _security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    return response


app.include_router(whatsapp_router)
app.include_router(auth_router)
app.include_router(equipe_router)
app.include_router(config_router)
app.include_router(onboarding_router)
app.include_router(metrics_router)
app.include_router(billing_router)
app.include_router(live_router)
app.include_router(tts_router)
app.include_router(patrocinadores_router)
app.include_router(biblioteca_audio_router)
app.include_router(categorias_vinheta_router)
app.include_router(suporte_router)
app.include_router(notificacoes_router)
app.include_router(admin_sistema_router)
app.include_router(admin_sistema_auth_router)


@app.on_event("startup")
async def criar_tabelas():
    Base.metadata.create_all(bind=engine)
    garantir_colunas_radio_config()
    garantir_colunas_account()
    garantir_colunas_programa()
    garantir_colunas_interaction_log()
    garantir_colunas_musica_historico()
    garantir_colunas_patrocinador()
    garantir_colunas_categoria_vinheta()
    corrigir_tipo_categoria_vinheta_legado()
    migrar_categoria_biblioteca_audio()
    semear_categorias_padrao_em_contas_existentes()
    migrar_conteudo_para_programas()
    migrar_whatsapp_para_account()
    migrar_usuarios_de_account()
    garantir_colunas_password_reset_token()
    limpar_coluna_is_staff_legado()


def garantir_colunas_radio_config():
    inspector = inspect(engine)
    if "radio_configs" not in inspector.get_table_names():
        return

    colunas = {coluna["name"] for coluna in inspector.get_columns("radio_configs")}
    novas_colunas = {
        "voz_id": "VARCHAR NULL",
        "resposta_automatica_whatsapp": "BOOLEAN NOT NULL DEFAULT false",
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
        "wuzapi_token": "VARCHAR NULL",
        "wuzapi_user_id": "VARCHAR NULL",
        "wuzapi_hmac_key": "VARCHAR NULL",
        "agentes_extras": "INTEGER DEFAULT 0 NOT NULL",
        "cidade": "VARCHAR DEFAULT '' NOT NULL",
        "onboarding_email_enviado": "BOOLEAN DEFAULT FALSE NOT NULL",
        "wuzapi_desconectado_alerta_enviado": "BOOLEAN DEFAULT FALSE NOT NULL",
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
        "descricao": "VARCHAR DEFAULT '' NOT NULL",
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
    "limite_mensagens_hora": "INTEGER DEFAULT 1000 NOT NULL",
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


def garantir_colunas_interaction_log():
    inspector = inspect(engine)
    if "interaction_logs" not in inspector.get_table_names():
        return

    colunas = {coluna["name"] for coluna in inspector.get_columns("interaction_logs")}
    novas_colunas = {
        "nome": "VARCHAR NULL",
        "origem": "VARCHAR DEFAULT 'ouvinte' NOT NULL",
    }
    with engine.begin() as conn:
        for nome, definicao in novas_colunas.items():
            if nome not in colunas:
                conn.execute(text(f"ALTER TABLE interaction_logs ADD COLUMN {nome} {definicao}"))


def garantir_colunas_musica_historico():
    inspector = inspect(engine)
    if "musica_historico" not in inspector.get_table_names():
        return

    colunas = {coluna["name"] for coluna in inspector.get_columns("musica_historico")}
    with engine.begin() as conn:
        if "song_id" not in colunas:
            conn.execute(text("ALTER TABLE musica_historico ADD COLUMN song_id INTEGER NULL"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_musica_historico_song_id ON musica_historico (song_id)"))


def garantir_colunas_patrocinador():
    inspector = inspect(engine)
    if "patrocinadores" not in inspector.get_table_names():
        return

    colunas = {coluna["name"] for coluna in inspector.get_columns("patrocinadores")}
    novas_colunas = {
        "voz_id": "VARCHAR NULL",
        "duracao_segundos": "INTEGER NULL",
        "categoria_id": "INTEGER NULL",
    }

    with engine.begin() as conn:
        for nome, definicao in novas_colunas.items():
            if nome not in colunas:
                conn.execute(text(f"ALTER TABLE patrocinadores ADD COLUMN {nome} {definicao}"))


def garantir_colunas_categoria_vinheta():
    inspector = inspect(engine)
    if "categorias_vinheta" not in inspector.get_table_names():
        return

    colunas = {coluna["name"] for coluna in inspector.get_columns("categorias_vinheta")}
    if "tipo" not in colunas:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE categorias_vinheta ADD COLUMN tipo VARCHAR DEFAULT 'biblioteca' NOT NULL"))


def corrigir_tipo_categoria_vinheta_legado():
    """tipo da categoria de vinhetagem se chamava "vinheta" e foi renomeado pra "biblioteca"
    (bate com o nome real do model/rota -- BibliotecaAudioItem / /biblioteca-audio). Corrige
    categoria criada com o nome antigo. Vira no-op depois que roda a primeira vez.
    """
    inspector = inspect(engine)
    if "categorias_vinheta" not in inspector.get_table_names():
        return
    with engine.begin() as conn:
        conn.execute(text("UPDATE categorias_vinheta SET tipo = 'biblioteca' WHERE tipo = 'vinheta'"))


def migrar_categoria_biblioteca_audio():
    """biblioteca_audio_itens.categoria (string livre) virou categoria_id (FK pra
    CategoriaVinheta), compartilhada com Patrocinador.categoria_id -- ver
    app/categorias_vinheta/router.py. Cada valor de string distinto vira uma categoria
    de verdade. So roda enquanto a coluna antiga ainda existir.
    """
    inspector = inspect(engine)
    if "biblioteca_audio_itens" not in inspector.get_table_names():
        return

    colunas = {coluna["name"] for coluna in inspector.get_columns("biblioteca_audio_itens")}

    with engine.begin() as conn:
        if "categoria_id" not in colunas:
            conn.execute(text("ALTER TABLE biblioteca_audio_itens ADD COLUMN categoria_id INTEGER NULL"))

        if "categoria" not in colunas:
            return

        linhas = conn.execute(
            text(
                "SELECT DISTINCT account_id, categoria FROM biblioteca_audio_itens "
                "WHERE categoria IS NOT NULL AND categoria <> ''"
            )
        ).fetchall()

        for account_id, categoria in linhas:
            categoria_id = conn.execute(
                text("SELECT id FROM categorias_vinheta WHERE account_id = :account_id AND nome = :nome"),
                {"account_id": account_id, "nome": categoria},
            ).scalar()
            if categoria_id is None:
                categoria_id = conn.execute(
                    text(
                        "INSERT INTO categorias_vinheta (account_id, nome, tipo, criado_em) "
                        "VALUES (:account_id, :nome, 'biblioteca', now()) RETURNING id"
                    ),
                    {"account_id": account_id, "nome": categoria},
                ).scalar()
            conn.execute(
                text(
                    "UPDATE biblioteca_audio_itens SET categoria_id = :categoria_id "
                    "WHERE account_id = :account_id AND categoria = :nome"
                ),
                {"categoria_id": categoria_id, "account_id": account_id, "nome": categoria},
            )

        conn.execute(text("ALTER TABLE biblioteca_audio_itens DROP COLUMN categoria"))


def semear_categorias_padrao_em_contas_existentes():
    """Conta nova ja ganha as categorias padrao em app/auth/router.py (registrar). Essa funcao
    cobre quem se cadastrou antes dessa tela existir (ou teve as categorias zeradas por
    engano) -- so preenche conta que hoje esta com zero categorias, pra nao duplicar quem
    ja organizou as proprias.
    """
    inspector = inspect(engine)
    if "categorias_vinheta" not in inspector.get_table_names() or "accounts" not in inspector.get_table_names():
        return

    with engine.begin() as conn:
        contas_sem_categoria = conn.execute(
            text(
                "SELECT a.id FROM accounts a "
                "WHERE NOT EXISTS (SELECT 1 FROM categorias_vinheta c WHERE c.account_id = a.id)"
            )
        ).fetchall()

        for (account_id,) in contas_sem_categoria:
            for nome, tipo in CATEGORIAS_PADRAO:
                conn.execute(
                    text(
                        "INSERT INTO categorias_vinheta (account_id, nome, tipo, criado_em) "
                        "VALUES (:account_id, :nome, :tipo, now())"
                    ),
                    {"account_id": account_id, "nome": nome, "tipo": tipo},
                )


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


def migrar_usuarios_de_account():
    """Move email/senha_hash/nome de accounts (1 login = 1 conta) pra usuarios
    (varias pessoas por conta, ver Usuario) -- cada conta existente ganha um
    usuario admin com os dados que estavam nela. So roda enquanto accounts
    ainda tiver essas colunas (migracao uma unica vez).
    """
    inspector = inspect(engine)
    if "accounts" not in inspector.get_table_names() or "usuarios" not in inspector.get_table_names():
        return

    colunas_accounts = {coluna["name"] for coluna in inspector.get_columns("accounts")}
    if "senha_hash" not in colunas_accounts:
        return

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO usuarios (email, senha_hash, nome, account_id, role, ativo, criado_em)
                SELECT a.email, a.senha_hash, COALESCE(a.nome, ''), a.id, 'admin', true, a.criado_em
                FROM accounts a
                WHERE NOT EXISTS (SELECT 1 FROM usuarios u WHERE u.account_id = a.id)
                """
            )
        )

        conn.execute(text("DROP INDEX IF EXISTS ix_accounts_email"))
        conn.execute(text("ALTER TABLE accounts DROP COLUMN IF EXISTS email"))
        conn.execute(text("ALTER TABLE accounts DROP COLUMN IF EXISTS senha_hash"))
        conn.execute(text("ALTER TABLE accounts DROP COLUMN IF EXISTS nome"))


def garantir_colunas_password_reset_token():
    """password_reset_tokens.account_id vira usuario_id -- tokens em voo (validos
    por so 30min) sao descartados no cutover, quem estava no meio do fluxo pede
    de novo. So roda enquanto a coluna antiga ainda existir.
    """
    inspector = inspect(engine)
    if "password_reset_tokens" not in inspector.get_table_names():
        return

    colunas = {coluna["name"] for coluna in inspector.get_columns("password_reset_tokens")}
    if "account_id" not in colunas:
        return

    with engine.begin() as conn:
        conn.execute(text("DROP INDEX IF EXISTS ix_password_reset_tokens_account_id"))
        conn.execute(text("ALTER TABLE password_reset_tokens DROP COLUMN account_id"))
        conn.execute(text("ALTER TABLE password_reset_tokens ADD COLUMN usuario_id INTEGER"))
        conn.execute(
            text("CREATE INDEX IF NOT EXISTS ix_password_reset_tokens_usuario_id ON password_reset_tokens (usuario_id)")
        )


def limpar_coluna_is_staff_legado():
    """is_staff em usuarios foi substituido por um super-admin isolado (tabela super_admins,
    sem relacao com Usuario/Account -- ver app/admin_sistema/). So roda enquanto a coluna
    antiga ainda existir.
    """
    inspector = inspect(engine)
    if "usuarios" not in inspector.get_table_names():
        return

    colunas = {coluna["name"] for coluna in inspector.get_columns("usuarios")}
    if "is_staff" in colunas:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE usuarios DROP COLUMN is_staff"))


@app.get("/health")
async def health():
    return {"status": "ok"}
