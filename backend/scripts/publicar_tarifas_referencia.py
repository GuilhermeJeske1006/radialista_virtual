"""Publica as tarifas de REFERÊNCIA (settings.ia_tarifas_*) para desenvolvimento e homologação.

  PYTHONPATH=. .venv-test/bin/python scripts/publicar_tarifas_referencia.py --ambiente-de-teste

Não use em produção: a tabela comercial deve ter as tarifas contratadas, publicadas em
POST /billing/admin/tarifas. Recusa rodar com chave Stripe live. Idempotente por versão.
"""
import argparse
import sys
from uuid import uuid4

VERSAO = "referencia-2026-09"


def tarifas(settings):
    def llm(entrada, saida):
        milhao = {"divisor": "1000000"}
        return {"entrada": {"preco": str(entrada), **milhao}, "saida": {"preco": str(saida), **milhao},
                "cache_write": {"preco": str(entrada * 1.25), **milhao}, "cache_read": {"preco": str(entrada * 0.1), **milhao},
                "buscas": {"preco": "0.01", "divisor": "1"}}
    itens = [("llm", "anthropic", modelo, llm(*precos)) for modelo, precos in settings.ia_tarifas_llm.items()]
    itens += [("tts", "elevenlabs", modelo, {"caracteres": {"preco": str(preco), "divisor": "1000"}})
              for modelo, preco in settings.ia_tarifas_tts.items()]
    itens.append(("stt", "elevenlabs", "scribe_v1", {"segundos": {"preco": str(settings.ia_stt_usd_hora), "divisor": "3600"}}))
    itens.append(("music", "elevenlabs", settings.elevenlabs_music_model,
                  {"milissegundos": {"preco": str(settings.ia_music_usd_minuto), "divisor": "60000"}}))
    return itens


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ambiente-de-teste", action="store_true", required=True,
                        help="confirma que o banco é de desenvolvimento/homologação")
    parser.parse_args()

    from sqlalchemy import select
    from app.config.settings import settings
    from app.db.database import SessionLocal, engine
    from app.db.migrations.consumo_20260925 import aplicar
    from app.models.consumo_flex import TarifaIA

    if settings.stripe_secret_key.startswith(("sk_live", "rk_live")):
        sys.exit("Recusado: chave Stripe live configurada. Publique as tarifas contratadas pelo endpoint administrativo.")
    aplicar(engine)
    with SessionLocal() as db, db.begin():
        for tipo, provedor, modelo, unidades in tarifas(settings):
            if db.scalar(select(TarifaIA.id).where(TarifaIA.tipo == tipo, TarifaIA.modelo == modelo, TarifaIA.versao == VERSAO)):
                print(f"já publicada: {tipo} {modelo}")
                continue
            db.add(TarifaIA(id=str(uuid4()), tipo=tipo, provedor=provedor, modelo=modelo, versao=VERSAO, unidades=unidades,
                            moeda="USD", cambio=str(settings.ia_cambio_brl_usd), acrescimo="100",
                            descricao="Tarifa de referência para testes", limitacoes="Não é tarifa contratada.", exemplos=[]))
            print(f"publicada: {tipo} {modelo}")


if __name__ == "__main__":
    main()
