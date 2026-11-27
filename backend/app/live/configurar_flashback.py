"""Atalho legado: o formato flashback virou o musical com curadoria (app.live.configurar_musical).

python -m app.live.configurar_flashback --account-id 1 --programa-id 3 [--aplicar]
Mantém o perfil `flashback` e a reserva de clássicos 1970–1999.
"""
import argparse
import json

from app.db.database import SessionLocal
from app.live.configurar_musical import configurar as _configurar
from app.live.musical_curado import PERFIL_LEGADO_FLASHBACK


def configurar(db, account_id: int, programa_id: int, aplicar: bool = False):
    return _configurar(db, account_id, programa_id, aplicar, perfil=PERFIL_LEGADO_FLASHBACK,
                       exigir_flashback_no_nome=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--account-id", type=int, required=True)
    parser.add_argument("--programa-id", type=int, required=True)
    parser.add_argument("--aplicar", action="store_true")
    args = parser.parse_args()
    with SessionLocal() as sessao:
        print(json.dumps(configurar(sessao, args.account_id, args.programa_id, args.aplicar), ensure_ascii=False))
