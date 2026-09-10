"""Diagnóstico offline da validação de clonagem, sem gravar no banco ou chamar APIs.

Em backend: PYTHONPATH=. .venv/bin/python scripts/auditar_entrada_clone.py
O resultado descreve o comportamento atual, não aprova a qualidade das amostras.
"""

import asyncio
import io
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi import HTTPException, UploadFile
from pydub import AudioSegment
from pydub.generators import Sine

from app.tts import client as tts
from app.tts import router


async def auditar():
    resultados = []
    for nome, audio in (
        ("silencio_21s", AudioSegment.silent(duration=21000)),
        ("tom_senoidal_21s_sem_fala", Sine(440).to_audio_segment(duration=21000).apply_gain(-18)),
        ("silencio_5s_controle", AudioSegment.silent(duration=5000)),
    ):
        buffer = io.BytesIO()
        audio.export(buffer, format="wav")
        buffer.seek(0)
        db = MagicMock()
        db.refresh.side_effect = lambda voz: setattr(voz, "id", 1)
        with (
            patch.object(router.settings, "elevenlabs_api_key", "fake-key"),
            patch.object(router, "limite_excedido", return_value=False),
            patch.object(router, "clonar_voz", return_value={"voice_id": "voz-fake", "requires_verification": False}) as clonar,
            patch.object(router, "obter_preview_url", return_value=None),
        ):
            try:
                await router.criar_voz_clonada(
                    nome="Diagnóstico", arquivo=UploadFile(filename="teste.wav", file=buffer),
                    arquivos=None,
                    account=SimpleNamespace(id=1, plano="growth"), db=db,
                )
                resultado = "aceito_pela_validacao_local"
            except HTTPException as exc:
                resultado = f"rejeitado_{exc.status_code}"
            resultados.append({"caso": nome, "resultado": resultado, "chamaria_provedor": clonar.called})

    texto = "[muito feliz] Boa tarde! [surpreso] Olá! [áudio] Teste."
    return {
        "modo": "offline; banco e provedor simulados; decodificação WAV real",
        "entradas": resultados,
        "sanitizacao": {"entrada": texto, "saida": tts._sanitizar_tags_v3(texto)},
        "perfil_sem_jitter": perfil_sem_jitter(),
    }


def perfil_sem_jitter():
    with patch.object(tts.random, "uniform", return_value=0):
        return {tipo: tts._construir_voice_settings(tipo, tom, "eleven_v3", True)
                for tipo, tom in (("musica", "energico"), ("comentario", "calmo"), ("noticia", "calmo"))}


if __name__ == "__main__":
    print(json.dumps(asyncio.run(auditar()), ensure_ascii=False, indent=2))
