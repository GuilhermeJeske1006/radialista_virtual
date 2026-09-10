import logging
import random
import re
import time
import unicodedata
from collections.abc import Iterator

import httpx

from app.config.settings import settings
from app.numeros import normalizar_texto_fala

logger = logging.getLogger("radialista.tts")

# ElevenLabs 429 (rate limit de conta, comum com varios blocos gerando TTS em
# sequencia rapida no ao vivo) e' quase sempre transitorio -- vale tentar de novo
# antes de desistir e o front cair pra voz generica do navegador.
_TTS_MAX_TENTATIVAS = 3
_TTS_BACKOFF_BASE_SEGUNDOS = 1.5
_TTS_TIMEOUT_SEGUNDOS = 25.0
_TTS_MAX_ESPERA_RETRY_SEGUNDOS = 3.0

_ELEVENLABS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
_ELEVENLABS_STREAM_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"
_ELEVENLABS_VOICES_URL = "https://api.elevenlabs.io/v1/voices/add"
_ELEVENLABS_VOICE_URL = "https://api.elevenlabs.io/v1/voices/{voice_id}"
_ELEVENLABS_SHARED_VOICES_URL = "https://api.elevenlabs.io/v1/shared-voices"

# radio e sempre em portugues -- fixa o idioma pro modelo nao tentar detectar sozinho por
# trecho (numero solto e onde a deteccao mais erra, cai pra leitura estilo ingles).
_LANGUAGE_CODE = "pt"

_VOICE_SETTINGS_PADRAO = {
    "stability": 0.35,
    "similarity_boost": 0.8,
    "style": 0.4,
    "use_speaker_boost": True,
    "speed": 0.97,
}

# Perfil inicial do Flash para comparacao por escuta. Os presets abaixo foram
# calibrados para a locucao anterior: empilhar estilo, tom e desaceleracao do clone
# no Flash mudou a entrega vocal. Mantemos este perfil independente desses deltas.
_VOICE_SETTINGS_FLASH = {
    "stability": 0.5,
    "similarity_boost": 0.75,
    "style": 0.0,
    "use_speaker_boost": True,
    "speed": 1.0,
}

# ajustes de prosodia por tipo de bloco do programa ao vivo (ver _PROSODIA_BLOCO em app.live.router):
# blocos de abertura/musica/chamada pedem mais energia e ritmo mais rapido (menos estabilidade, mais estilo);
# comentario/noticia pedem ritmo mais calmo e estavel.
#
# stability abaixo de ~0.3 deixa o v3 instavel demais e sai artefato nas terminacoes de frase/palavra
# (a propria ElevenLabs recomenda nao descer disso) -- piso levantado pra 0.34/0.37 depois de reclamacao
# de locucao "com cara de IA" nas terminacoes, mais evidente nos blocos energicos que usavam 0.28/0.32.
#
# speed reduzido ~0.03 em todos os tipos (reclamacao recorrente de locucao rapida demais mesmo depois
# dos ajustes anteriores) -- mantem a diferenca relativa entre bloco energico/calmo, so' desloca o
# piso geral pra baixo.
_VOICE_SETTINGS_POR_TIPO = {
    "abertura": {"stability": 0.34, "style": 0.55, "speed": 1.02},
    "musica": {"stability": 0.34, "style": 0.55, "speed": 1.02},
    "chamada_ouvinte": {"stability": 0.37, "style": 0.5, "speed": 1.0},
    "comentario": {"stability": 0.45, "style": 0.3, "speed": 0.92},
    "noticia": {"stability": 0.5, "style": 0.25, "speed": 0.9},
    "patrocinador": {"stability": 0.4, "style": 0.35, "speed": 0.97},
}

# ajuste fino por cima do tipo de bloco, a partir do tom real da fala gerada (ver
# app.llm.client.classificar_tom_fala) -- o mesmo tipo de bloco pode sair mais ou menos
# intenso dependendo do que o locutor realmente falou naquela vez.
#
# delta de stability do tom "energico" reduzido (-0.07 -> -0.04): empilhado com o piso ja baixo
# dos blocos energicos, derrubava a stability efetiva perto de 0.3 de novo.
_AJUSTE_TOM = {
    "energico": {"stability": -0.04, "style": 0.1, "speed": 0.04},
    "calmo": {"stability": 0.07, "style": -0.1, "speed": -0.04},
    "neutro": {},
}

# audio tag [excited] do eleven_v3 (so mandado no tom "energico") direciona uma entrega ofegante --
# muita respiracao audivel entre as frases, mais que o [calm] do tom oposto. Tirado ate ter como
# validar por audicao um tag mais neutro; energia do bloco continua vindo so de stability/style/speed.
#
# So aplicado quando a fala nao ja vem com uma tag inline propria (ver _TAGS_V3_PERMITIDAS abaixo) --
# o prompt em app.live.router agora deixa o proprio LLM inserir tag no ponto exato da fala que faz
# sentido; prefixar [calm] por cima disso empilharia duas instrucoes de emocao conflitantes.
_TAG_POR_TOM = {
    "calmo": "[calm]",
}

# Tags de direcao vocal/emocao do eleven_v3 que o prompt (ver app.live.router) instrui o LLM a
# inserir inline, no ponto exato da fala -- lista fechada de proposito: o LLM "alucina" tag fora
# dela com alguma frequencia (testado por audicao), e tag desconhecida pro modelo e' lida como
# texto literal em vez de virar direcao vocal (ex.: "[surpreso] Nao acredito" sai com a palavra
# "surpreso" falada).
_TAGS_V3_EMOCAO = {"excited", "calm", "laughs", "sighs", "whispers", "sarcastic"}

# Whitelist completa aceita no texto antes de mandar pro eleven_v3 -- emocao (acima) mais [pause],
# que nao e' emocao (nao deve suprimir o _TAG_POR_TOM abaixo) mas e' inserido por este mesmo
# modulo a partir de "......" (ver _PAUSA_TROCA_ASSUNTO).
_TAGS_V3_PERMITIDAS = _TAGS_V3_EMOCAO | {"pause"}

_TAG_INLINE_RE = re.compile(r"\[([^\[\]]*)\]")


def _sanitizar_tags_v3(texto: str) -> str:
    """Remove qualquer tag [algo] que nao esteja na whitelist (ver _TAGS_V3_PERMITIDAS) antes de
    mandar pro eleven_v3 -- rede de seguranca contra o LLM inventar tag fora da lista permitida
    pelo prompt, ou deixar passar quando o texto nem chega a rodar nesse modelo.
    """
    # Processa também colchetes aninhados. Não deixa instruções fora da lista
    # serem pronunciadas; texto entre colchetes é reservado a direção vocal.
    while True:
        novo = _TAG_INLINE_RE.sub(lambda m: f"[{m.group(1).strip().lower()}]" if m.group(1).strip().lower() in _TAGS_V3_PERMITIDAS else "", texto)
        if novo == texto:
            return novo
        texto = novo


def _tem_tag_emocao_v3(texto: str) -> bool:
    return any(m.group(1).lower() in _TAGS_V3_EMOCAO for m in _TAG_INLINE_RE.finditer(texto))

# reticencias duplas ("......") sao a instrucao do prompt (ver app.live.router) pro locutor marcar uma
# pausa forte e real -- na troca de assunto/bloco, ou no meio da fala antes de um ponto de peso (noticia
# forte, nome do sorteado, climax de piada). Medido direto na API (par de chamadas identicas, uma so
# com "..." em vez de tag) que o eleven_v3 trata "..." exatamente como "." -- zero pausa extra, saida
# em bytes identica. A tag de audio [pause] e' o que realmente funciona (~1.5s medido, reproduzivel),
# entao a reticencia dupla e' convertida pra ela antes de mandar pro v3; reticencia simples (pausa de
# respiracao dentro da frase) fica como esta -- vira "." de qualquer forma, e trocar toda ocorrencia
# por [pause] (~1.5s cada) encheria a fala de silencio, pior que o problema original. O prompt pede uso
# raro (no maximo 1x por fala) -- em todo ponto final tambem destruiria o efeito.
_PAUSA_TROCA_ASSUNTO = re.compile(r"\.{4,}")

# similarity_boost/use_speaker_boost nao sao suportados pelo eleven_v3 -- _construir_voice_settings
# remove essas chaves do payload quando o modelo e' v3, pra voz do catalogo e pra voz clonada.
_CHAVES_INDISPONIVEIS_V3 = {"similarity_boost", "use_speaker_boost"}

# Voz clonada (Instant Voice Cloning, ver clonar_voz) usava similarity_boost alto + fallback forcado
# pro multilingual_v2 (que suporta esse parametro) pra soar mais parecida com a amostra -- mas o v2 e'
# mais literal/robotico que o v3, sobretudo na entonacao de pontuacao e terminacao de frase, o que
# virou reclamacao maior que a perda de fidelidade. Voz clonada roda no mesmo modelo configurado pro
# catalogo (ver settings.elevenlabs_model) desde entao; sem similarity_boost/use_speaker_boost quando
# esse modelo for v3 (removidos como qualquer outra voz, ver _CHAVES_INDISPONIVEIS_V3 acima).
_SIMILARITY_BOOST_CLONE = 0.8

# Empiricamente a voz clonada ainda sai um pouco mais rapida/menos estavel que uma voz de catalogo
# com os mesmos multiplicadores de tipo de bloco/tom -- ajuste fino pra compensar, aplicado antes do
# clamp em _construir_voice_settings. Reavaliar por audicao se o modelo do catalogo mudar.
#
# delta de stability subido de 0.1 pra 0.15 (reclamacao de clone "robotizado" nos blocos energicos,
# onde a stability efetiva ficava perto de 0.44) -- mantido como delta proporcional em vez de floor
# fixo pra preservar a diferenca relativa entre tipo de bloco (abertura/musica continuam mais soltos
# que noticia/comentario, so' desloca todos pra cima). Trocar pra floor fixo (max(stability, X)) e'
# o proximo passo se o delta maior nao resolver, mas achataria essa diferenca entre blocos.
_AJUSTE_SPEED_CLONADA = -0.08
_AJUSTE_CLONADA = {"stability": 0.15, "style": -0.15}

# Medido em docs/benchmarks/2026-09-10/vozes-padrao-catalogo.md: com o mesmo voice_settings,
# Paulo sai 13-21% mais rapido (palavras/minuto) que as outras 3 vozes do catalogo fixo
# (Will, Yasmin, Scheila), sobretudo em musica/comentario (ate 282 wpm, acima da faixa
# natural de radio de ~150-190 wpm). Multiplicador (nao delta fixo) pra escalar proporcionalmente
# em qualquer tipo de bloco/tom, em vez de achatar so' os blocos mais rapidos.
_AJUSTE_SPEED_MULTIPLICADOR_POR_VOZ = {"Qrdut83w0Cr152Yb4Xn3": 0.85}  # Paulo

# tipo de bloco/tom fixam sempre o mesmo voice_settings -- em bloco recorrente (ex.: varias
# "musica" numa transmissao) isso saia identico take a take, cara de robo lendo script. Medido
# na API (3 sinteses do mesmo texto/settings vs 3 com este jitter): desvio do pitch medio entre
# takes sobe de ~2Hz pra ~5Hz e da duracao de ~0.3s pra ~0.4s -- variacao proxima da que um
# locutor real tem repetindo a mesma frase. Aplicado por cima do clamp de cada bloco de ajuste
# (tipo/tom/clonada), pra nao interferir na calibracao relativa entre eles.
_JITTER_STABILITY = 0.03
_JITTER_STYLE = 0.03
_JITTER_SPEED = 0.015


def _aplicar_jitter(voice_settings: dict) -> dict:
    voice_settings["stability"] = max(
        0.0, min(1.0, voice_settings["stability"] + random.uniform(-_JITTER_STABILITY, _JITTER_STABILITY))
    )
    voice_settings["style"] = max(
        0.0, min(1.0, voice_settings["style"] + random.uniform(-_JITTER_STYLE, _JITTER_STYLE))
    )
    voice_settings["speed"] = max(
        0.7, min(1.2, voice_settings["speed"] + random.uniform(-_JITTER_SPEED, _JITTER_SPEED))
    )
    return voice_settings


def tts_habilitado(voice_id: str | None = None) -> bool:
    return bool(settings.elevenlabs_api_key and (voice_id or settings.elevenlabs_voice_id))


def _sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


def _categoria_tipo_bloco(tipo_bloco: str) -> str:
    """Reconhece bloco customizado (ex.: 'Musica Vaneira') como variacao do tipo base 'musica'
    pra manter a prosodia certa, mesmo sem bater exatamente com o preset -- ver mesma logica em
    app.live.router._categoria_bloco.
    """
    normalizado = _sem_acento(tipo_bloco.strip().lower())
    for base in _VOICE_SETTINGS_POR_TIPO:
        if normalizado == base or normalizado.startswith(f"{base} ") or normalizado.startswith(f"{base}:"):
            return base
    return normalizado


def _construir_voice_settings(tipo_bloco: str | None, tom: str | None, modelo: str, eh_clonada: bool, voice_id: str | None = None) -> dict:
    if modelo == "eleven_flash_v2_5":
        return _aplicar_jitter(dict(_VOICE_SETTINGS_FLASH))

    categoria = _categoria_tipo_bloco(tipo_bloco) if tipo_bloco else ""
    voice_settings = {**_VOICE_SETTINGS_PADRAO, **_VOICE_SETTINGS_POR_TIPO.get(categoria, {})}
    for chave, delta in _AJUSTE_TOM.get(tom or "", {}).items():
        voice_settings[chave] = voice_settings[chave] + delta

    if eh_clonada:
        voice_settings["speed"] = voice_settings["speed"] + _AJUSTE_SPEED_CLONADA
        for chave, delta in _AJUSTE_CLONADA.items():
            voice_settings[chave] = voice_settings[chave] + delta

    voice_settings["speed"] = voice_settings["speed"] * _AJUSTE_SPEED_MULTIPLICADOR_POR_VOZ.get(voice_id or "", 1.0)

    voice_settings["stability"] = max(0.0, min(1.0, voice_settings["stability"]))
    voice_settings["style"] = max(0.0, min(1.0, voice_settings["style"]))
    voice_settings["speed"] = max(0.7, min(1.2, voice_settings["speed"]))
    _aplicar_jitter(voice_settings)

    if eh_clonada:
        voice_settings["similarity_boost"] = _SIMILARITY_BOOST_CLONE
        voice_settings["use_speaker_boost"] = True

    if modelo != "eleven_v3":
        return voice_settings
    return {k: v for k, v in voice_settings.items() if k not in _CHAVES_INDISPONIVEIS_V3}


def _preparar_sintese(
    texto: str,
    tipo_bloco: str | None,
    tom: str | None,
    eh_clonada: bool,
    texto_anterior: str | None,
    modelo: str | None = None,
    perfil: str = "atual",
    pronuncias: dict[str, str] | None = None,
    voice_id: str | None = None,
) -> tuple[dict, dict]:
    """Headers e payload compartilhados entre sintetizar_audio (buffered) e
    sintetizar_audio_stream (streaming) -- so' o endpoint e a forma de ler a resposta mudam
    entre as duas (ver Plano B.4)."""
    headers = {
        "xi-api-key": settings.elevenlabs_api_key,
        "Content-Type": "application/json",
    }
    modelo = modelo or settings.elevenlabs_model
    voice_settings = _construir_voice_settings(tipo_bloco, tom, modelo, eh_clonada, voice_id)
    if perfil == "natural":
        voice_settings = {"stability": 0.5, "style": 0.0, "speed": 1.0}
        if modelo != "eleven_v3":
            voice_settings.update(similarity_boost=0.8 if eh_clonada else 0.75, use_speaker_boost=True)

    # "R$ 19,90" etc -- so' aparece em texto que nunca passou pelo LLM (ver Patrocinador.texto em
    # app.live.router, conteudo fixo), entao a instrucao de prompt "escreva numero por extenso"
    # nao alcanca esse caso. Roda pra qualquer modelo, nao so' v3 -- algarismo em portugues sai
    # errado em qualquer sintetizador.
    texto_tts = normalizar_texto_fala(texto, pronuncias)
    if modelo == "eleven_v3":
        texto_tts = _PAUSA_TROCA_ASSUNTO.sub(" [pause] ", texto_tts)
        texto_tts = _sanitizar_tags_v3(texto_tts)
        texto_tts = re.sub(r" {2,}", " ", texto_tts).strip()
        if perfil != "natural" and not _tem_tag_emocao_v3(texto_tts):
            tag = _TAG_POR_TOM.get(tom or "")
            if tag:
                texto_tts = f"{tag} {texto_tts}"
    else:
        # Tags vindas do roteiro v3 não podem vazar para vozes que usam v2/Flash.
        texto_tts = _TAG_INLINE_RE.sub("", _sanitizar_tags_v3(texto_tts)).strip()

    payload = {
        "text": texto_tts,
        "model_id": modelo,
        "voice_settings": voice_settings,
    }
    if modelo != "eleven_multilingual_v2":
        payload["language_code"] = _LANGUAGE_CODE
    # previous_text da 400 (unsupported_model) no eleven_v3 -- ElevenLabs ainda nao suporta esse
    # campo nesse modelo. So manda quando o modelo realmente aceita.
    if texto_anterior and modelo != "eleven_v3":
        payload["previous_text"] = texto_anterior

    return headers, payload


def sintetizar_audio(
    texto: str,
    voice_id: str | None = None,
    tipo_bloco: str | None = None,
    tom: str | None = None,
    eh_clonada: bool = False,
    texto_anterior: str | None = None,
    timeout_segundos: float = _TTS_TIMEOUT_SEGUNDOS,
    max_tentativas: int = _TTS_MAX_TENTATIVAS,
    modelo: str | None = None,
    perfil: str = "atual",
    pronuncias: dict[str, str] | None = None,
    formato: str = "mp3_44100_128",
) -> bytes:
    """Gera audio (mp3) a partir de texto via ElevenLabs. Lanca httpx.HTTPStatusError em falha.

    eh_clonada indica a categoria instantânea 'cloned' confirmada no provedor,
    resolvida em app.tts.profiles. Voz profissional não recebe esses deltas -- afeta o
    similarity_boost e os ajustes finos de prosodia usados (ver _SIMILARITY_BOOST_CLONE acima).

    texto_anterior e' o texto da fala imediatamente anterior (mesmo locutor), repassado como
    previous_text pra ElevenLabs manter a prosodia contigua entre chamadas -- cada bloco/linha do
    programa ao vivo e' uma chamada de API isolada, sem isso o modelo trata toda fala como um
    enunciado novo e solto, sem saber que continua uma conversa, o que sai como entonacao de
    inicio/fim de frase mais artificial/cortada.

    timeout_segundos/max_tentativas tem defaults generosos (pensados pro endpoint /tts avulso,
    que tem seu proprio orcamento de tempo isolado) -- a sintese embutida em /proxima (ver Plano
    B.3 em app.live.router) passa valores bem mais curtos aqui, porque ali o tempo desta chamada
    soma com o tempo de geracao da fala pelo LLM dentro do MESMO request, competindo pelo mesmo
    timeout que o frontend aplica na chamada de /proxima inteira -- sem isso, uma unica fala mais
    lenta na ElevenLabs estourava o timeout do frontend antes mesmo do backend responder com
    audio_status="falhou", perdendo a fala inteira (nao so' o audio) pro fallback local generico.
    """
    voice_id = voice_id or settings.elevenlabs_voice_id
    url = _ELEVENLABS_URL.format(voice_id=voice_id)
    headers, payload = _preparar_sintese(texto, tipo_bloco, tom, eh_clonada, texto_anterior, modelo, perfil, pronuncias, voice_id)
    if formato != "mp3_44100_128":
        url += f"?output_format={formato}"

    # O ao vivo nao pode ficar preso meio minuto numa unica fala. O frontend ja prepara o
    # proximo bloco em paralelo; se este provedor nao responder em tempo de radio, o bloco
    # seguinte assume com a cama musical ainda no ar.
    with httpx.Client(timeout=timeout_segundos) as client:
        for tentativa in range(1, max_tentativas + 1):
            response = client.post(url, headers=headers, json=payload)
            if response.status_code != 429 or tentativa == max_tentativas:
                if response.status_code >= 400:
                    logger.warning("Falha ao sintetizar audio na ElevenLabs (%s)", response.status_code)
                response.raise_for_status()
                return response.content

            logger.warning("Rate limit da ElevenLabs (429) na tentativa %s/%s", tentativa, max_tentativas)
            espera = float(response.headers.get("retry-after", 0)) or _TTS_BACKOFF_BASE_SEGUNDOS * tentativa
            espera = min(espera, _TTS_MAX_ESPERA_RETRY_SEGUNDOS)
            time.sleep(espera)


def sintetizar_audio_stream(
    texto: str,
    voice_id: str | None = None,
    tipo_bloco: str | None = None,
    tom: str | None = None,
    eh_clonada: bool = False,
    texto_anterior: str | None = None,
    modelo: str | None = None,
    perfil: str = "atual",
    pronuncias: dict[str, str] | None = None,
    formato: str = "mp3_44100_128",
) -> Iterator[bytes]:
    """Mesma sintese de sintetizar_audio, via endpoint de streaming da ElevenLabs -- devolve os
    bytes do mp3 conforme chegam em vez de esperar o audio inteiro antes de responder, cortando a
    cauda de latencia em blocos de fala mais longos (ver Plano B.4).

    O CHAMADOR deve puxar o primeiro item (next()) fora de uma StreamingResponse ja iniciada:
    ate' o primeiro yield, qualquer erro de conexao/rate-limit/autenticacao ainda sobe como
    excecao normal (httpx.HTTPStatusError/HTTPError), dando pra virar HTTPException com status
    certo -- depois que os headers HTTP 200 ja foram enviados pro cliente nao da mais pra trocar
    o status code, entao esse e' o unico ponto em que o erro pode virar resposta de erro de verdade.
    """
    voice_id = voice_id or settings.elevenlabs_voice_id
    url = _ELEVENLABS_STREAM_URL.format(voice_id=voice_id)
    headers, payload = _preparar_sintese(texto, tipo_bloco, tom, eh_clonada, texto_anterior, modelo, perfil, pronuncias, voice_id)
    if formato != "mp3_44100_128":
        url += f"?output_format={formato}"

    with httpx.Client(timeout=_TTS_TIMEOUT_SEGUNDOS) as client:
        for tentativa in range(1, _TTS_MAX_TENTATIVAS + 1):
            with client.stream("POST", url, headers=headers, json=payload) as response:
                if response.status_code == 429 and tentativa < _TTS_MAX_TENTATIVAS:
                    response.read()  # drena o corpo pra liberar a conexao antes do backoff
                    logger.warning(
                        "Rate limit da ElevenLabs (429) na tentativa %s/%s (streaming)",
                        tentativa,
                        _TTS_MAX_TENTATIVAS,
                    )
                    espera = float(response.headers.get("retry-after", 0)) or _TTS_BACKOFF_BASE_SEGUNDOS * tentativa
                    espera = min(espera, _TTS_MAX_ESPERA_RETRY_SEGUNDOS)
                    time.sleep(espera)
                    continue
                if response.status_code >= 400:
                    response.read()
                    logger.warning("Falha ao sintetizar audio (streaming) na ElevenLabs (%s)", response.status_code)
                    response.raise_for_status()
                yield from response.iter_bytes()
                return


def clonar_voz(nome: str, audio_bytes: bytes = b"", content_type: str = "audio/mpeg", nome_arquivo: str = "amostra.mp3", *, amostras: list[tuple[str, bytes, str]] | None = None) -> dict:
    """Clona uma voz na ElevenLabs (Instant Voice Cloning) a partir de uma amostra de audio.

    Devolve voice_id e requires_verification. Lanca httpx.HTTPStatusError em falha (ex.: amostra curta demais,
    creditos de clonagem esgotados no plano ElevenLabs).
    """
    headers = {"xi-api-key": settings.elevenlabs_api_key}
    files = [("files", amostra) for amostra in (amostras or [(nome_arquivo, audio_bytes, content_type)])]
    data = {"name": nome}

    with httpx.Client(timeout=60.0) as client:
        response = client.post(_ELEVENLABS_VOICES_URL, headers=headers, data=data, files=files)
        response.raise_for_status()
        dados = response.json()
        return {"voice_id": dados["voice_id"], "requires_verification": bool(dados.get("requires_verification", False))}


def obter_metadados_voz(voice_id: str) -> dict | None:
    if not settings.elevenlabs_api_key:
        return None
    try:
        with httpx.Client(timeout=3.0) as client:
            response = client.get(_ELEVENLABS_VOICE_URL.format(voice_id=voice_id), headers={"xi-api-key": settings.elevenlabs_api_key})
            response.raise_for_status()
            dados = response.json()
            verificacao = dados.get("voice_verification") or {}
            pendente = verificacao.get("requires_verification")
            if verificacao.get("is_verified") is True:
                pendente = False
            return {"categoria": dados.get("category", "desconhecida"),
                    "idioma": (dados.get("labels") or {}).get("language"),
                    "sotaque": (dados.get("labels") or {}).get("accent"),
                    "requer_verificacao": dados.get("requires_verification", pendente)}
    except (httpx.HTTPError, ValueError):
        logger.warning("Não foi possível consultar metadados da voz")
        return None


def obter_preview_url(voice_id: str) -> str | None:
    """Busca a preview_url (amostra curta pronta, hospedada pela ElevenLabs) de uma voz.

    Devolve None se a API nao estiver configurada ou a chamada falhar -- o catalogo de
    vozes cai pra lista sem audio de amostra nesse caso, sem quebrar a pagina.
    """
    if not settings.elevenlabs_api_key:
        return None

    headers = {"xi-api-key": settings.elevenlabs_api_key}
    url = _ELEVENLABS_VOICE_URL.format(voice_id=voice_id)
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url, headers=headers)
            if response.status_code == 400:
                # voz da Voice Library (premade, ex.: catalogo fixo em app/tts/voices.py) nunca
                # foi adicionada a conta -- GET /v1/voices/{id} so' enxerga voz propria/clonada
                # e devolve voice_not_found aqui, mesmo a sintese (POST text-to-speech) funcionando
                # normal com o mesmo id. /v1/shared-voices busca no catalogo publico por id.
                response = client.get(
                    _ELEVENLABS_SHARED_VOICES_URL, headers=headers, params={"search": voice_id, "page_size": 1}
                )
                response.raise_for_status()
                vozes = response.json().get("voices") or []
                encontrada = next((v for v in vozes if v.get("voice_id") == voice_id), None)
                return encontrada.get("preview_url") if encontrada else None
            response.raise_for_status()
            return response.json().get("preview_url")
    except httpx.HTTPError:
        logger.warning("Falha ao buscar preview_url da voz %s", voice_id)
        return None


def renomear_voz(voice_id: str, nome: str) -> None:
    """Atualiza o nome de uma voz clonada na ElevenLabs. Lanca httpx.HTTPStatusError em falha."""
    url = f"{_ELEVENLABS_VOICE_URL.format(voice_id=voice_id)}/edit"
    headers = {"xi-api-key": settings.elevenlabs_api_key}
    data = {"name": nome}

    with httpx.Client(timeout=30.0) as client:
        response = client.post(url, headers=headers, data=data)
        response.raise_for_status()


def excluir_voz_clonada(voice_id: str) -> None:
    """Remove uma voz clonada na ElevenLabs. Lanca httpx.HTTPStatusError em falha."""
    url = _ELEVENLABS_VOICE_URL.format(voice_id=voice_id)
    headers = {"xi-api-key": settings.elevenlabs_api_key}

    with httpx.Client(timeout=30.0) as client:
        response = client.delete(url, headers=headers)
        response.raise_for_status()
