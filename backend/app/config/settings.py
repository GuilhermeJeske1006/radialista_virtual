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

    jwt_secret: str = "troque-por-um-segredo-forte"
    jwt_expire_minutes: int = 60 * 24 * 7

    frontend_url: str = "http://localhost:3000"

    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_id: str = ""

    youtube_api_key: str = ""

    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = ""

    # Diretorio (local, relativo ou absoluto) onde ficam os arquivos enviados pelo usuario
    # (ex.: audio de patrocinadores -- app/patrocinadores/router.py). Em producao deve apontar
    # pra um volume persistente montado no container do backend.
    upload_dir: str = "uploads"

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "Radialista Virtual <no-reply@radialista.app>"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
