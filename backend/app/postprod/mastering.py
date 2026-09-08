"""De-essing e masterizacao em PCM, com uma unica codificacao MP3 no final."""
import json
import math
import subprocess

import numpy as np

from app.postprod.audio_io import array_para_mp3_bytes


def finalizar_audio(audio: np.ndarray, sample_rate: int, perfil: dict) -> bytes:
    # Duas passagens evitam variar o ganho durante a frase. -2 dBTP deixa margem
    # para os picos criados pela codificacao MP3 (o destino desejado e <= -1 dBTP).
    if not np.any(audio):
        return array_para_mp3_bytes(audio, sample_rate)
    entrada = np.ascontiguousarray(audio.T, dtype='<f4').tobytes()
    base = ["ffmpeg", "-hide_banner", "-nostdin", "-f", "f32le", "-ar", str(sample_rate),
            "-ac", str(audio.shape[0]), "-i", "pipe:0"]
    deesser = perfil.get("deesser")
    prefixo = (f"deesser=i={deesser['intensity']}:m={deesser['max']}:f={deesser['frequency']},"
               if deesser else "")
    normalizacao = f"loudnorm=I={perfil['loudness_target_lufs']}:TP={perfil.get('true_peak_db', -2)}:LRA=7"

    def executar(args):
        try:
            resultado = subprocess.run(base + args, input=entrada, capture_output=True, timeout=30, check=True)
        except (OSError, subprocess.SubprocessError) as exc:
            raise RuntimeError("Falha na masterizacao de audio") from exc
        return resultado

    analise = executar(["-af", prefixo + normalizacao + ":print_format=json", "-f", "null", "-"])
    log = analise.stderr.decode("utf-8", errors="replace")
    medidas = json.loads(log[log.rfind("{"):log.rfind("}") + 1])
    if all(math.isfinite(float(medidas[k])) for k in ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset")):
        normalizacao += (f":measured_I={medidas['input_i']}:measured_TP={medidas['input_tp']}"
                         f":measured_LRA={medidas['input_lra']}:measured_thresh={medidas['input_thresh']}"
                         f":offset={medidas['target_offset']}:linear=true")
    # Silencio e clipes muito curtos podem nao ter loudness integrado mensuravel.
    pcm = executar(["-af", prefixo + normalizacao, "-ar", str(sample_rate),
                    "-f", "f32le", "pipe:1"]).stdout
    final = np.frombuffer(pcm, dtype="<f4").reshape(-1, audio.shape[0]).T
    return array_para_mp3_bytes(final, sample_rate)
