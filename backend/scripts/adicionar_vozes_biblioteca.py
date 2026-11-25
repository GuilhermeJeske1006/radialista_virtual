"""Adiciona à conta da ElevenLabs as vozes da biblioteca que estão no catálogo (app/tts/voices.py).

O aviso de remoção (notice_period, 730 dias nas vozes novas do catálogo) só vale para quem tem a voz na
conta: sem isso, se o dono tirar a voz da biblioteca, o locutor que usa essa voz para de falar na hora.
A primeira síntese com o id de uma voz da biblioteca já a adiciona à conta (medido em 25/11/2026: voz
nunca usada dá 400 (voice_not_found) em GET /v1/voices/{id}, a mesma voz depois de uma síntese aparece com
sharing.status "copied"). Este script adiciona antes do primeiro uso e avisa se alguma voz do catálogo
saiu da biblioteca. Voz da biblioteca na conta não ocupa slot de voz própria (85 vozes na conta,
voice_slots_used = 2, só os clones).

Rodar uma vez por conta da ElevenLabs (dev e produção usam chaves diferentes), a partir de backend:
  PYTHONPATH=. .venv-test/bin/python scripts/adicionar_vozes_biblioteca.py            # só lista
  PYTHONPATH=. .venv-test/bin/python scripts/adicionar_vozes_biblioteca.py --aplicar  # adiciona
Idempotente: voz já na conta é pulada. O id da voz não muda ao adicionar.
"""

import argparse

import httpx

from app.config.settings import settings
from app.tts.voices import VOZES_DISPONIVEIS

API = "https://api.elevenlabs.io/v1"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--aplicar", action="store_true", help="adiciona de fato (sem isso, só lista)")
    args = parser.parse_args()
    headers = {"xi-api-key": settings.elevenlabs_api_key}
    faltando = 0
    with httpx.Client(timeout=30) as client:
        for voz in VOZES_DISPONIVEIS:
            voz_id, nome = voz["voz_id"], voz["nome"]
            if client.get(f"{API}/voices/{voz_id}", headers=headers).status_code == 200:
                print(f"na conta     {nome} ({voz_id})")
                continue
            r = client.get(f"{API}/shared-voices", headers=headers, params={"search": voz_id, "page_size": 5})
            r.raise_for_status()
            publica = next((v for v in r.json().get("voices", []) if v["voice_id"] == voz_id), None)
            if publica is None:
                print(f"FORA DA BIBLIOTECA {nome} ({voz_id}): conferir se a voz foi removida")
                continue
            faltando += 1
            if not args.aplicar:
                print(f"falta        {nome} ({voz_id}), aviso de {publica.get('notice_period')} dias")
                continue
            r = client.post(f"{API}/voices/add/{publica['public_owner_id']}/{voz_id}", headers=headers,
                            json={"new_name": f"Locufy - {nome}"})
            print(f"adicionada   {nome} ({voz_id})" if r.status_code == 200
                  else f"ERRO {r.status_code} {nome} ({voz_id}): {r.text[:200]}")
    if faltando and not args.aplicar:
        print(f"\n{faltando} voz(es) fora da conta. Rode com --aplicar para adicionar.")


if __name__ == "__main__":
    main()
