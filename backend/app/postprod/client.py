import json
import logging
from pathlib import Path

from app.postprod.audio_io import array_para_mp3_bytes, mp3_bytes_para_array
from app.postprod.effects import montar_pipeline
from app.postprod.naturalness import aplicar_jitter_de_pitch, aplicar_ruido_de_sala

logger = logging.getLogger("radialista.postprod")

_PERFIS_DIR = Path(__file__).parent / "perfis"


def carregar_perfil(nome: str) -> dict:
    caminho = _PERFIS_DIR / f"{nome}.json"
    if not caminho.exists():
        raise ValueError(f"Perfil de pos-producao desconhecido: {nome}")
    return json.loads(caminho.read_text(encoding="utf-8"))


def processar_audio(mp3_bytes: bytes, perfil_nome: str) -> bytes:
    """Aplica o pipeline de pos-producao (EQ, compressao, saturacao, reverb, limitador,
    ruido de sala, jitter de pitch) de um perfil de estilo sobre um audio mp3 gerado por TTS.

    Recebe e devolve mp3 em memoria -- ver app/tts/client.py:sintetizar_audio, que nunca
    toca disco (docs/plano-pos-producao-voz.md secao 1)."""
    perfil = carregar_perfil(perfil_nome)

    audio, sample_rate, sample_width = mp3_bytes_para_array(mp3_bytes)

    pipeline = montar_pipeline(perfil)
    audio = pipeline(audio, sample_rate)

    nat = perfil["naturalness"]
    audio = aplicar_jitter_de_pitch(audio, sample_rate, nat["pitch_jitter_cents"])
    audio = aplicar_ruido_de_sala(audio, nat["room_noise_db"])

    return array_para_mp3_bytes(audio, sample_rate, sample_width)
