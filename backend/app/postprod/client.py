import json
import logging
from pathlib import Path

from app.postprod.audio_io import mp3_bytes_para_array
from app.postprod.mastering import finalizar_audio
from app.postprod.effects import montar_pipeline
from app.postprod.naturalness import aplicar_jitter_de_pitch, aplicar_ruido_de_sala

logger = logging.getLogger("radialista.postprod")

_PERFIS_DIR = Path(__file__).parent / "perfis"


def carregar_perfil(nome: str) -> dict:
    caminho = _PERFIS_DIR / f"{nome}.json"
    if Path(nome).name != nome or not caminho.exists():
        raise ValueError(f"Perfil de pos-producao desconhecido: {nome}")
    return json.loads(caminho.read_text(encoding="utf-8"))


def processar_audio(mp3_bytes: bytes, perfil_nome: str) -> bytes:
    """Aplica o pipeline de pos-producao (EQ, compressao, saturacao, reverb,
    naturalidade opcional e masterizacao final) de um perfil de estilo sobre um audio mp3 gerado por TTS.

    Recebe e devolve mp3 em memoria -- ver app/tts/client.py:sintetizar_audio, que nunca
    toca disco (docs/plano-pos-producao-voz.md secao 1)."""
    perfil = carregar_perfil(perfil_nome)

    audio, sample_rate, _ = mp3_bytes_para_array(mp3_bytes)

    pipeline = montar_pipeline(perfil)
    audio = pipeline(audio, sample_rate)

    nat = perfil["naturalness"]
    audio = aplicar_jitter_de_pitch(audio, sample_rate, nat["pitch_jitter_cents"])
    if nat["room_noise_db"] is not None:
        audio = aplicar_ruido_de_sala(audio, nat["room_noise_db"])

    return finalizar_audio(audio, sample_rate, perfil)
