"""Simula as mensagens de ouvinte de um Reel no webhook real do WhatsApp, sem enviar nada.

Execute em backend: PYTHONPATH=. .venv/bin/python scripts/conversa_teste.py V5
Le marketing/reels/<id>/roteiro.json (campo mensagens_ouvinte das cenas) e grava
marketing/reels/<id>/conversa.json. O webhook roda dentro deste processo (TestClient), com a
assinatura HMAC da conta de demonstracao; o envio pelo WuzAPI e' trocado por uma funcao que so'
guarda o texto, entao nenhuma mensagem sai para numero real. Pedidos de musica e abraco entram
na fila do ao vivo de verdade. Precisa do Postgres e do Redis locais (./start-dev.sh) e de
rodar scripts/seed_demo.py antes.
"""

import datetime
import hashlib
import hmac
import json
import os
import sys
import uuid
from pathlib import Path
from unittest import mock

RAIZ = Path(__file__).resolve().parents[2]
# A conta de demonstracao e' isenta de cobranca; desligar a medicao aqui evita que o consumo de
# IA desta simulacao entre no extrato ou seja barrado pelo orcamento configurado no .env.
os.environ["IA_MEDICAO_HABILITADA"] = "false"
os.environ["IA_ORCAMENTO_BLOQUEAR"] = "false"
TELEFONE_TESTE = "5500000000000"
NOME_OUVINTE = "Ana"
ROTULOS_STATUS = {
    "bloqueado_conteudo": "Bloqueada — conteúdo não permitido",
    "bloqueado_horario": "Bloqueada — fora do horário do programa",
    "bloqueado_rate_limit": "Bloqueada — limite de mensagens por hora",
}


def _carregar(video: str) -> tuple[dict, list[str]]:
    demo_path = RAIZ / "marketing" / "reels" / ".demo.json"
    if not demo_path.exists():
        sys.exit("Rode scripts/seed_demo.py antes (marketing/reels/.demo.json nao existe).")
    roteiro_path = RAIZ / "marketing" / "reels" / video / "roteiro.json"
    roteiro = json.loads(roteiro_path.read_text())
    mensagens = [m for cena in roteiro["cenas"] for m in (cena.get("mensagens_ouvinte") or [])]
    if not mensagens:
        sys.exit(f"{video} nao tem mensagens_ouvinte no roteiro.json.")
    return json.loads(demo_path.read_text()), mensagens


def main(video: str) -> None:
    demo, mensagens = _carregar(video)

    from fastapi.testclient import TestClient

    from app.db.database import SessionLocal
    from app.main import app
    from app.models.account import Account
    from app.models.interaction_log import InteractionLog
    from app.models.radio_config import RadioConfig

    db = SessionLocal()
    account = db.get(Account, demo["account_id"])
    chave = account.wuzapi_hmac_key
    configs = [c.id for c in db.query(RadioConfig).filter_by(account_id=account.id).all()]
    db.close()

    enviadas: list[str] = []
    hora = datetime.datetime.now().replace(hour=14, minute=2, second=0)
    conversa: list[dict] = []

    # Sem "with": o lifespan (agendadores do app) nao sobe neste processo.
    client = TestClient(app)
    with mock.patch("app.whatsapp.webhook.enviar_mensagem", side_effect=lambda tel, texto, token: enviadas.append(texto)):
        for texto in mensagens:
            corpo = {
                "type": "Message",
                "userID": demo["wuzapi_user_id"],
                "event": {
                    "Info": {
                        "ID": f"REELS{uuid.uuid4().hex[:16].upper()}",
                        "Chat": f"{TELEFONE_TESTE}@s.whatsapp.net",
                        "Sender": f"{TELEFONE_TESTE}@s.whatsapp.net",
                        "PushName": NOME_OUVINTE,
                        "FromMe": False,
                    },
                    "Message": {"conversation": texto},
                },
            }
            raw = json.dumps(corpo, ensure_ascii=False).encode()
            assinatura = hmac.new(chave.encode(), raw, hashlib.sha256).hexdigest()
            antes = len(enviadas)
            resposta = client.post(
                "/webhook/whatsapp", content=raw,
                headers={"content-type": "application/json", "x-hmac-signature": assinatura},
            )
            resultado = resposta.json()
            conversa.append({"de": "ouvinte", "texto": texto, "hora": hora.strftime("%H:%M")})
            hora += datetime.timedelta(minutes=1)
            if len(enviadas) > antes:
                conversa.append({"de": "locutor", "texto": enviadas[-1], "hora": hora.strftime("%H:%M")})
            else:
                db = SessionLocal()
                log = (
                    db.query(InteractionLog)
                    .filter(InteractionLog.radio_config_id.in_(configs), InteractionLog.telefone == TELEFONE_TESTE)
                    .order_by(InteractionLog.id.desc())
                    .first()
                )
                db.close()
                status = log.status if log else resultado.get("motivo", "sem_resposta")
                conversa.append({"de": "sistema", "texto": ROTULOS_STATUS.get(status, status), "status": status})
            print(f"> {texto}\n  {conversa[-1]['texto']}  [{resultado}]")

    destino = RAIZ / "marketing" / "reels" / video / "conversa.json"
    destino.write_text(json.dumps(conversa, ensure_ascii=False, indent=2))
    print(f"Conversa salva em {destino.relative_to(RAIZ)}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Uso: scripts/conversa_teste.py <id-do-video>")
    main(sys.argv[1])
