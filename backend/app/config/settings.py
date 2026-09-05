from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    anthropic_api_key: str
    wuzapi_base_url: str = "http://localhost:8080"
    wuzapi_user_token: str
    wuzapi_admin_token: str = ""
    wuzapi_webhook_url: str = "http://host.docker.internal:8000/webhook/whatsapp"
    locutor_nome: str = "Ze do Radio"

    database_url: str = "postgresql://radialista:radialista@localhost:5433/radialista"
    redis_url: str = "redis://localhost:6379/0"

    # Sem default de proposito: segredo fraco/publico no repo permitiria forjar
    # token de qualquer conta. Gere com: openssl rand -hex 32
    jwt_secret: str
    jwt_expire_minutes: int = 60 * 24 * 7

    frontend_url: str = "http://localhost:3000"
    # Origens extras liberadas no CORS alem de frontend_url (ex.: tunel ngrok em dev),
    # separadas por virgula. Vazio = so' frontend_url (e variante localhost/127.0.0.1).
    cors_extra_origins: str = ""

    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_id_starter: str = ""
    stripe_price_id_growth: str = ""
    stripe_price_id_professional: str = ""

    youtube_api_key: str = ""

    # Client Credentials Flow (developer.spotify.com/dashboard) -- usado so' pra descobrir
    # faixas oficiais por genero (app/live/spotify.py), nunca pra tocar audio. Vazio desativa
    # a integracao e o fluxo cai pro comportamento anterior (sugestao via LLM).
    spotify_client_id: str = ""
    spotify_client_secret: str = ""

    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = ""
    # eleven_v3 suporta audio tags ([excited], [calm], etc) pra emocao mais humana; eleven_multilingual_v2
    # fica como fallback facil via env var se v3 (ainda em alpha na ElevenLabs) apresentar instabilidade.
    elevenlabs_model: str = "eleven_v3"

    # Diretorio (local, relativo ou absoluto) onde ficam os arquivos enviados pelo usuario
    # (ex.: audio de patrocinadores -- app/patrocinadores/router.py) quando storage_backend=local.
    upload_dir: str = "uploads"

    # Backend de armazenamento dos arquivos enviados: "local" (disco, dev) ou "s3" (AWS, producao).
    storage_backend: str = "local"
    # Bucket S3 (obrigatorio se storage_backend=s3). Credenciais nao ficam aqui: o boto3 resolve
    # sozinho via AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY, ~/.aws/credentials ou IAM role.
    aws_s3_bucket: str = ""
    aws_region: str = "us-east-1"
    # Endpoint alternativo (ex.: LocalStack/MinIO pra testar S3 localmente). Vazio = AWS de verdade.
    aws_s3_endpoint_url: str = ""

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "Radialista Virtual <no-reply@radialista.app>"

    # Monitoramento de erros (sentry.io) -- deixe vazio pra desativar (dev local).
    sentry_dsn: str = ""
    sentry_environment: str = "development"
    # Fracao de requests com tracing de performance (0.0 a 1.0) -- 0 manda so' erros,
    # sem overhead de tracing. Sentry cobra por evento de trace, entao comeca conservador.
    sentry_traces_sample_rate: float = 0.0
    # Manda logging.warning/error/etc pro Sentry Logs (busca/alerta por log, nao so' por excecao).
    sentry_enable_logs: bool = True

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
