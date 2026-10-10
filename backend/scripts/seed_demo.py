"""Cria (ou atualiza) a radio de demonstracao usada nos Reels da Locufy.

Execute em backend: PYTHONPATH=. .venv/bin/python scripts/seed_demo.py
Idempotente: rodar de novo so' confere e completa o que faltar. Recusa banco que nao seja local.
Imprime o login de demonstracao e grava marketing/reels/.demo.json (fora do git) com
login, senha e ids, lido pelos scripts de gravacao e de conversa.
"""

import datetime
import json
import secrets
import sys
from pathlib import Path
from urllib.parse import urlparse

from app.auth.security import hash_senha
from app.categorias_vinheta.defaults import criar_categorias_padrao
from app.config.settings import settings
from app.db.database import Base, SessionLocal, engine
from app.models.account import Account
from app.models.patrocinador import Patrocinador
from app.models.programa import Programa
from app.models.programa_radialista import ProgramaRadialista
from app.models.radio_config import RadioConfig
from app.models.usuario import Usuario

EMAIL_DEMO = "demo@locufy.local"
WUZAPI_TOKEN_DEMO = "demo-reels-locufy"
WUZAPI_USER_ID_DEMO = "demo-reels-locufy"
NOME_PROGRAMA = "Tarde da Cidade"
NOME_PATROCINADOR = "Mercado Bom Preço"
ARQUIVO_DEMO = Path(__file__).resolve().parents[2] / "marketing" / "reels" / ".demo.json"

RADIALISTAS = [
    {
        "nome_locutor": "Zé do Rádio",
        "voz_id": "Qrdut83w0Cr152Yb4Xn3",  # Paulo
        "personalidade": "Animado, bem-humorado e próximo do ouvinte; fala como vizinho que conhece todo mundo da cidade.",
        "papel": "Apresentador principal",
        "comportamento": "Conduz o programa, chama os blocos e manda os abraços dos ouvintes.",
    },
    {
        "nome_locutor": "Lia",
        "voz_id": "lWq4KDY8znfkV0DrK8Vb",  # Yasmin Alves
        "personalidade": "Leve, curiosa e rápida nas respostas; adora música e histórias dos ouvintes.",
        "papel": "Co-apresentadora",
        "comportamento": "Comenta as músicas e puxa conversa com o Zé.",
    },
    {
        "nome_locutor": "Beto",
        "voz_id": "CstacWqMhJQlnfLPxRG4",  # Will
        "personalidade": "Calmo e informado; traz o contexto das notícias sem pesar o clima.",
        "papel": "Comentarista",
        "comportamento": "Entra nas notícias e nos comentários com uma opinião curta e equilibrada.",
    },
]


def _garantir_banco_local() -> None:
    url = urlparse(settings.database_url)
    host = url.hostname or ""
    if url.scheme.startswith("sqlite"):
        return
    if host not in ("localhost", "127.0.0.1", "db", "postgres", "host.docker.internal"):
        sys.exit(f"Banco nao parece local ({host}). Abortando para nao tocar producao.")


def seed_demo() -> dict:
    _garantir_banco_local()
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        anterior = json.loads(ARQUIVO_DEMO.read_text()) if ARQUIVO_DEMO.exists() else {}
        usuario = db.query(Usuario).filter_by(email=EMAIL_DEMO).first()
        senha = anterior.get("senha") if usuario and anterior.get("senha") else secrets.token_urlsafe(12)

        if usuario is None:
            account = Account(plano_status="ativo", cobranca_isenta=True)
            db.add(account)
            db.flush()
            usuario = Usuario(email=EMAIL_DEMO, account_id=account.id, role="admin", nome="Demonstração Reels")
            db.add(usuario)
            criar_categorias_padrao(db, account.id)
        else:
            account = db.get(Account, usuario.account_id)
        usuario.senha_hash = hash_senha(senha)

        account.nome_radio = "Rádio Cidade FM"
        account.frequencia = "98.7"
        account.cidade = "São João Batista"
        account.slogan = "A rádio que conversa com você"
        account.plano_status = "ativo"
        account.cobranca_isenta = True
        account.atendimento_ouvinte_ativo = False
        account.wuzapi_token = WUZAPI_TOKEN_DEMO
        account.wuzapi_user_id = WUZAPI_USER_ID_DEMO
        account.wuzapi_hmac_key = account.wuzapi_hmac_key or secrets.token_hex(32)
        db.flush()

        configs = []
        for dados in RADIALISTAS:
            config = db.query(RadioConfig).filter_by(account_id=account.id, nome_locutor=dados["nome_locutor"]).first()
            if config is None:
                config = RadioConfig(account_id=account.id, nome_locutor=dados["nome_locutor"])
                db.add(config)
            config.voz_id = dados["voz_id"]
            config.personalidade = dados["personalidade"]
            config.ativo = True
            config.resposta_automatica_whatsapp = True
            db.flush()
            configs.append(config)

        dono = configs[0]
        programa = db.query(Programa).filter_by(radio_config_id=dono.id, nome=NOME_PROGRAMA).first()
        if programa is None:
            programa = Programa(radio_config_id=dono.id, nome=NOME_PROGRAMA)
            db.add(programa)
        programa.descricao = "Música boa, notícia da cidade e muita conversa com o ouvinte no fim de tarde."
        programa.dias_semana = []
        programa.data_especifica = None
        programa.horario_inicio = datetime.time(0, 0)
        programa.horario_fim = datetime.time(23, 59)
        programa.ativo = True
        programa.tom = "informal e descontraído, como locutores de rádio local conversando com o ouvinte"
        programa.topicos_permitidos = ["música", "trânsito", "clima", "notícias locais", "programação da rádio"]
        programa.topicos_proibidos = ["política partidária", "eleições", "religião"]
        programa.generos_musicais = ["sertanejo", "MPB", "pop nacional"]
        programa.limite_mensagens_hora = 1000
        db.flush()

        patrocinador = db.query(Patrocinador).filter_by(account_id=account.id, nome=NOME_PATROCINADOR).first()
        if patrocinador is None:
            patrocinador = Patrocinador(account_id=account.id, nome=NOME_PATROCINADOR)
            db.add(patrocinador)
        patrocinador.tipo_conteudo = "texto"
        patrocinador.texto = (
            "Mercado Bom Preço: hortifrúti fresquinho todo dia e as ofertas da semana "
            "que cabem no seu bolso. Mercado Bom Preço, pertinho de você."
        )
        patrocinador.ativo = True
        db.flush()

        # Chamada ao ouvinte e patrocinador logo no começo: os Reels V5 e V7 gravam esses
        # blocos sem esperar uma música inteira tocar antes.
        programa.estrutura_blocos = [
            "abertura", "chamada_ouvinte", f"patrocinador:{patrocinador.id}",
            "musica", "comentario", "noticia", "musica",
        ]

        for ordem, (config, dados) in enumerate(zip(configs, RADIALISTAS)):
            vinculo = db.query(ProgramaRadialista).filter_by(programa_id=programa.id, radio_config_id=config.id).first()
            if vinculo is None:
                vinculo = ProgramaRadialista(programa_id=programa.id, radio_config_id=config.id)
                db.add(vinculo)
            vinculo.papel = dados["papel"]
            vinculo.comportamento = dados["comportamento"]
            vinculo.ordem = ordem

        db.commit()

        demo = {
            "painel_url": settings.frontend_url,
            "email": EMAIL_DEMO,
            "senha": senha,
            "account_id": account.id,
            "programa": NOME_PROGRAMA,
            "programa_id": programa.id,
            "patrocinador_id": patrocinador.id,
            "radialistas": {c.nome_locutor: {"id": c.id, "voz_id": c.voz_id} for c in configs},
            "wuzapi_user_id": WUZAPI_USER_ID_DEMO,
        }
        ARQUIVO_DEMO.parent.mkdir(parents=True, exist_ok=True)
        ARQUIVO_DEMO.write_text(json.dumps(demo, ensure_ascii=False, indent=2))
        return demo
    finally:
        db.close()


if __name__ == "__main__":
    demo = seed_demo()
    print(f"Rádio de demonstração pronta: {demo['painel_url']}")
    print(f"Login: {demo['email']}  Senha: {demo['senha']}")
    print(f"Programa: {demo['programa']} (id {demo['programa_id']}) · radialistas: {', '.join(demo['radialistas'])}")
