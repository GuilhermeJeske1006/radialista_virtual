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
    funnel_origins: str = "https://locufybr.com,https://www.locufybr.com,http://localhost:3010,http://127.0.0.1:3010"

    stripe_secret_key: str = ""
    stripe_price_id_flex: str = ""
    # Sem default de proposito: stripe.Webhook.construct_event verifica a assinatura
    # calculando HMAC com esse valor como chave -- string vazia e' uma chave conhecida,
    # entao um segredo vazio deixa QUALQUER payload forjavel (atacante so' calcula o HMAC
    # com chave vazia). Ver app/billing/router.py::webhook_stripe.
    stripe_webhook_secret: str

    youtube_api_key: str = ""

    # Client Credentials Flow (developer.spotify.com/dashboard) -- usado so' pra descobrir
    # faixas oficiais por genero (app/live/spotify.py), nunca pra tocar audio. Vazio desativa
    # a integracao e o fluxo cai pro comportamento anterior (sugestao via LLM).
    spotify_client_id: str = ""
    spotify_client_secret: str = ""

    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = ""
    # V3 recupera a expressividade da locucao; o ao vivo ja prepara os proximos blocos.
    # Flash continua disponivel via ELEVENLABS_MODEL, com perfil proprio, para testes.
    elevenlabs_model: str = "eleven_v3"

    # Modelos econômicos podem ser avaliados sem trocar a voz de clientes existentes.
    llm_model: str = "claude-opus-5"
    llm_classification_model: str = "claude-haiku-4-5"
    # Prefixos dinâmicos sem hits custariam mais por escrita. Ativar só com
    # repetição medida; o cache de classificações estáveis independe desta opção.
    llm_prompt_cache: bool = False
    ia_cache_habilitado: bool = True
    ia_cache_ttl_segundos: int = 86400
    # Desligado por padrão: ligado, toda geração exige tarifa publicada (senão 503) e
    # plano ativo (trial recebe 402). Ligar por env só com GET
    # /billing/admin/tarifas/pendentes vazio no ambiente.
    ia_medicao_habilitada: bool = False
    # Bloqueio conservador por conta; false permite implantação em observação.
    # Os valores são tetos operacionais configuráveis, não promessa de margem.
    ia_orcamento_bloquear: bool = False
    ia_orcamentos_brl: dict[str, float] = {"starter": 79.2, "growth": 139.2, "professional": 259.2}
    ia_cambio_brl_usd: float = 5.5
    ia_reserva_fracao: float = 0.15
    # Limite financeiro inicial de cada conta; o cliente ajusta em /billing. Sem ele, a
    # conta recém-assinada receberia 402 em toda geração até configurar um valor.
    ia_limite_padrao_brl: float = 300.0
    # Operação sem conclusão após este prazo vira falha absorvida (custo interno) no
    # fechamento, em vez de manter a fatura em rascunho indefinidamente.
    ia_operacao_abandonada_minutos: int = 60
    # Combinações texto + voz oferecidas (ids em app/billing/combinacoes.py, nesta ordem).
    # As com Haiku mostram ao cliente a limitação de fidelidade medida nas avaliações
    # (docs/benchmarks/2026-09-25-combinacoes); remova daqui para deixar de oferecer.
    ia_combinacoes: list[str] = ["premium", "equilibrada", "voz_premium", "texto_premium", "agil", "essencial"]
    ia_tarifas_llm: dict[str, list[float]] = {
        "claude-opus-5": [5, 25], "claude-sonnet-5": [2, 10], "claude-haiku-4-5": [1, 5],
    }
    ia_tarifas_tts: dict[str, float] = {
        "eleven_v3": 0.10, "eleven_multilingual_v2": 0.10, "eleven_flash_v2_5": 0.05,
    }
    ia_stt_usd_hora: float = 0.40  # Hipótese scribe_v1: substituir pela tarifa contratada.
    ia_music_usd_minuto: float = 0.15

    # Trilha instrumental das vinhetas geradas por programa (ver app/vinhetas/trilha.py) via
    # ElevenLabs Music API. Desligado = pula direto pro banco local de trilhas livres.
    vinheta_trilha_ia_habilitada: bool = True
    elevenlabs_music_model: str = "music_v1"

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
    smtp_from: str = "Locufy <no-reply@locufybr.com>"

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
