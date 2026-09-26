import base64
import io

import httpx

from app.config.settings import settings
from app.billing.consumo_ia import reservar, concluir, falhar
from pydub import AudioSegment

_ELEVENLABS_STT_URL = "https://api.elevenlabs.io/v1/speech-to-text"


def stt_habilitado() -> bool:
    return bool(settings.elevenlabs_api_key)


def transcrever_audio(audio_base64: str, mime_type: str = "audio/ogg") -> str:
    """Transcreve audio (base64, ja decriptado pelo WuzAPI) via ElevenLabs Speech-to-Text.

    Lanca httpx.HTTPStatusError em falha -- quem chama decide o fallback (webhook
    trata como transcricao vazia e so registra o log, sem travar o resto do fluxo).
    """
    audio_bytes = base64.b64decode(audio_base64)
    # Medir duração real, nunca confiar na extensão/tamanho comprimido do upload.
    # Sem atribuição (benchmarks), não precisa decodificar para controlar orçamento.
    custo_usd = None
    reserva = None
    from app.billing.contexto_ia import atual
    conta = atual.get()
    if settings.ia_orcamento_bloquear or (settings.ia_medicao_habilitada and conta and conta.id is not None):
        duracao = len(AudioSegment.from_file(io.BytesIO(audio_bytes))) / 1000
        custo_usd = duracao / 3600 * settings.ia_stt_usd_hora
        reserva = reservar("stt", "scribe_v1", custo_usd, unidades_max={"segundos": duracao})
    headers = {"xi-api-key": settings.elevenlabs_api_key}
    files = {"file": ("audio.ogg", audio_bytes, mime_type)}
    data = {"model_id": "scribe_v1"}

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(_ELEVENLABS_STT_URL, headers=headers, files=files, data=data)
            response.raise_for_status()
            texto = str(response.json().get("text") or "").strip()
            if custo_usd is not None:
                concluir(reserva, custo_usd, {"segundos": duracao}, entregue=None if texto else False,
                    request_id=response.headers.get('request-id'))
            return texto
    except BaseException:
        falhar(reserva)
        raise

