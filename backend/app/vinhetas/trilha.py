"""Trilha instrumental por baixo da voz das vinhetas -- uma por programa, compartilhada pelas 3.

Ordem de prioridade (ver obter_trilha_programa):
1. trilha enviada pelo usuario pro programa (origem="upload");
2. trilha que o programa ja tem (nao paga a Music API de novo a cada regeracao);
3. trilha nova gerada por IA (ElevenLabs Music API), se VINHETA_TRILHA_IA_HABILITADA;
4. banco local de trilhas livres de direitos (app/vinhetas/assets/trilhas/<estilo>/*.mp3);
5. sem trilha -- a vinheta sai so' com a voz processada. Trilha nunca quebra a geracao.

NUNCA usar as musicas do YouTube do ao vivo (buscar_musica/buscar_musica_fundo) aqui: nao temos
direito de uso delas fora do player embutido.
"""
import logging
import random
import time
import uuid
from pathlib import Path

import httpx
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.models.programa import Programa
from app.models.trilha_vinheta import TrilhaVinheta
from app.storage import get_storage
from app.util.texto import sem_acento
from app.vinhetas.audio import ErroAudio, preparar_trilha

logger = logging.getLogger("radialista.vinhetas.trilha")

_MUSIC_URL = "https://api.elevenlabs.io/v1/music"
_MUSIC_TIMEOUT_SEGUNDOS = 120.0

# 20 s de groove continuo cobre com folga a vinheta mais longa (encerramento: 1 s + ate' ~9 s de
# voz + 3 s de cauda); cada vinheta recorta o seu pedaco (ver PresetMix.recorte em audio.py).
DURACAO_TRILHA_IA_MS = 20_000

BANCO_DIR = Path(__file__).parent / "assets" / "trilhas"

ESTILOS = ("sertanejo", "gospel", "pop_jovem", "jornalismo", "romantico", "eletronico", "generico")

# Genero musical (normalizado, sem acento) -> estilo do banco. Casamento por substring, na ordem.
_GENERO_PARA_ESTILO: tuple[tuple[str, str], ...] = (
    ("sertanej", "sertanejo"), ("modao", "sertanejo"), ("moda de viola", "sertanejo"),
    ("vaneira", "sertanejo"), ("forro", "sertanejo"), ("piseiro", "sertanejo"), ("arrocha", "sertanejo"),
    ("gospel", "gospel"), ("louvor", "gospel"), ("adoracao", "gospel"), ("catolic", "gospel"),
    ("evangel", "gospel"), ("crist", "gospel"),
    ("eletr", "eletronico"), ("house", "eletronico"), ("techno", "eletronico"), ("edm", "eletronico"),
    ("dance", "eletronico"),
    ("romant", "romantico"), ("flashback", "romantico"), ("mpb", "romantico"), ("bossa", "romantico"),
    ("love", "romantico"),
    ("pop", "pop_jovem"), ("rock", "pop_jovem"), ("funk", "pop_jovem"), ("rap", "pop_jovem"),
    ("hip hop", "pop_jovem"), ("pagode", "pop_jovem"), ("samba", "pop_jovem"), ("axe", "pop_jovem"),
    ("reggae", "pop_jovem"),
)

# Descricao de cada estilo pra Music API, em ingles (a API entende melhor) e SO' com vocabulario
# controlado: nada de texto livre do programa (generos, tom, descricao) no prompt. Texto livre ja
# derrubou a geracao -- "hits do momento" e o nome do locutor no tom fizeram a API recusar com
# "copyrighted_material_detected", e a vinheta saia sem trilha.
_ESTILO_PROMPT = {
    "sertanejo": "Brazilian sertanejo style, acoustic guitar and viola, light percussion",
    "gospel": "uplifting contemporary worship style, piano and warm pads",
    "pop_jovem": "modern upbeat pop, punchy drums, bright synths",
    "jornalismo": "news broadcast theme, urgent pulse, strings and timpani",
    "romantico": "romantic ballad feel, soft piano and strings",
    "eletronico": "electronic dance style, four-on-the-floor beat, synth lead",
    "generico": "versatile upbeat pop, clean electric guitar, bass and drums",
}

# Ultimo recurso quando a API recusa o prompt do estilo e a sugestao dela.
# Pedir "final marcado" fazia o modelo compor uma musica curta que ACABA no meio da duracao pedida
# (15 s pedidos = ~9 s de musica + decaimento + silencio) -- a cauda das vinhetas saia muda. A trilha
# e' uma cama: groove continuo ate' o ultimo segundo; o final da vinheta sai dos fades do mix.
_ESTRUTURA_CAMA = (
    "Starts immediately with a strong hit, then one continuous steady groove at full energy for the "
    "entire length, no breakdown, no fade out, no ending, seamless loop."
)

_PROMPT_GENERICO = (
    f"Original instrumental radio jingle bed, no vocals. Upbeat pop, guitar, bass and drums. {_ESTRUTURA_CAMA}"
)


def estilo_do_programa(programa: Programa) -> str:
    if getattr(programa, "perfil", "") == "jornalismo":
        return "jornalismo"
    if getattr(programa, "perfil", "") == "religioso":
        return "gospel"
    for genero in programa.generos_musicais or []:
        normalizado = sem_acento(str(genero).lower())
        for trecho, estilo in _GENERO_PARA_ESTILO:
            if trecho in normalizado:
                return estilo
    return "generico"


def _energia_por_horario(programa: Programa) -> str:
    hora = programa.horario_inicio.hour if programa.horario_inicio else 12
    if 5 <= hora < 12:
        return "high energy, bright morning mood"
    if 12 <= hora < 18:
        return "medium-high energy"
    if 18 <= hora < 22:
        return "medium energy, warm evening mood"
    return "calm, relaxed late-night mood"


def prompt_trilha_ia(programa: Programa) -> str:
    """Prompt da Music API a partir do estilo mapeado e do horario do programa -- nunca com texto
    livre dele (ver _ESTILO_PROMPT). force_instrumental vai no corpo da chamada (parametro oficial
    da API); o "no vocals" aqui e' reforco, nao a garantia."""
    return (
        f"Original instrumental radio jingle bed, no vocals. {_ESTILO_PROMPT[estilo_do_programa(programa)]}. "
        f"{_energia_por_horario(programa)}. {_ESTRUTURA_CAMA}"
    )


class PromptRecusado(RuntimeError):
    """Music API recusou o prompt (status bad_prompt). `sugestao` e' o prompt alternativo que ela
    devolve em data.prompt_suggestion, quando devolve."""

    def __init__(self, motivo: str, sugestao: str | None):
        super().__init__(f"prompt recusado pela Music API: {motivo}")
        self.sugestao = sugestao


def trilha_ia_disponivel() -> bool:
    return bool(settings.vinheta_trilha_ia_habilitada and settings.elevenlabs_api_key)


def compor_trilha_ia(prompt: str, duracao_ms: int = DURACAO_TRILHA_IA_MS) -> bytes:
    """POST /v1/music (ElevenLabs Music API): devolve o MP3 da trilha. Levanta em falha."""
    with httpx.Client(timeout=_MUSIC_TIMEOUT_SEGUNDOS) as client:
        resposta = client.post(
            _MUSIC_URL,
            params={"output_format": "mp3_44100_192"},
            headers={"xi-api-key": settings.elevenlabs_api_key, "Content-Type": "application/json"},
            json={
                "prompt": prompt,
                "music_length_ms": duracao_ms,
                "model_id": settings.elevenlabs_music_model,
                "force_instrumental": True,
            },
        )
        if resposta.status_code >= 400:
            logger.warning("Falha na ElevenLabs Music API (%s): %s", resposta.status_code, resposta.text[:1000])
            detalhe = _detalhe_erro(resposta)
            if detalhe.get("status") == "bad_prompt":
                dados = detalhe.get("data") or {}
                raise PromptRecusado(str(dados.get("reason") or "bad_prompt"), dados.get("prompt_suggestion") or None)
        resposta.raise_for_status()
        return resposta.content


def _detalhe_erro(resposta: httpx.Response) -> dict:
    try:
        detalhe = resposta.json().get("detail")
    except (ValueError, AttributeError):
        return {}
    return detalhe if isinstance(detalhe, dict) else {}


def compor_com_retentativa(prompt: str) -> tuple[bytes, str]:
    """Prompt recusado: tenta a sugestao da propria API e, por ultimo, um prompt generico fixo
    (no maximo 3 chamadas). Devolve (mp3, prompt que funcionou). Outras falhas (rede, 5xx,
    saldo) sobem direto."""
    fila, usados = [prompt], set()
    while fila and len(usados) < 3:
        atual = fila.pop(0)
        if atual in usados:
            continue
        usados.add(atual)
        try:
            return compor_trilha_ia(atual), atual
        except PromptRecusado as exc:
            logger.warning("Music API recusou o prompt (%s): %r", exc, atual)
            fila = [p for p in (exc.sugestao, *fila, _PROMPT_GENERICO) if p]
    raise RuntimeError("Music API recusou todos os prompts")


def arquivos_do_banco(estilo: str) -> list[Path]:
    pasta = BANCO_DIR / estilo
    if not pasta.is_dir():
        return []
    return sorted(p for p in pasta.iterdir() if p.suffix.lower() == ".mp3" and p.is_file())


def estilos_do_banco() -> dict[str, int]:
    return {estilo: len(arquivos_do_banco(estilo)) for estilo in ESTILOS}


def salvar_trilha(
    db: Session,
    account_id: int,
    programa_id: int | None,
    origem: str,
    conteudo: bytes,
    estilo: str | None = None,
    prompt: str | None = None,
    duracao_ms: int | None = None,
) -> TrilhaVinheta:
    """duracao_ms informado = conteudo ja passou por preparar_trilha (upload valida antes)."""
    if duracao_ms is None:
        try:
            conteudo, duracao_ms = preparar_trilha(conteudo)
        except ErroAudio:
            logger.warning("Nao deu pra preparar a trilha (corte de silencio), salvando como veio", exc_info=True)
    audio_path = f"trilhas/{account_id}/{uuid.uuid4().hex}.mp3"
    get_storage().save(audio_path, conteudo)
    trilha = TrilhaVinheta(
        account_id=account_id, programa_id=programa_id, origem=origem,
        estilo=estilo, prompt=prompt, audio_path=audio_path, duracao_ms=duracao_ms,
    )
    db.add(trilha)
    db.flush()
    return trilha


def gerar_trilha_ia(db: Session, account_id: int, programa: Programa) -> TrilhaVinheta:
    inicio = time.monotonic()
    conteudo, prompt = compor_com_retentativa(prompt_trilha_ia(programa))
    tempo_ms = int((time.monotonic() - inicio) * 1000)
    trilha = salvar_trilha(
        db, account_id, programa.id, "ia", conteudo, estilo=estilo_do_programa(programa), prompt=prompt,
    )
    # Duracao gerada por conta -- base pra limitar por plano depois (Music API cobra por tempo).
    logger.info(
        "vinheta_trilha_ia_gerada account_id=%s programa_id=%s duracao_ms=%s tempo_geracao_ms=%s",
        account_id, programa.id, trilha.duracao_ms, tempo_ms,
    )
    return trilha


def trilha_do_banco(
    db: Session, account_id: int, programa: Programa, estilo: str | None = None
) -> TrilhaVinheta | None:
    estilo = estilo if estilo in ESTILOS else estilo_do_programa(programa)
    arquivos = arquivos_do_banco(estilo) or arquivos_do_banco("generico")
    if not arquivos:
        return None
    escolhido = random.choice(arquivos)
    return salvar_trilha(db, account_id, programa.id, "banco", escolhido.read_bytes(), estilo=escolhido.parent.name)


def trilha_atual_do_programa(db: Session, account_id: int, programa_id: int) -> TrilhaVinheta | None:
    """Upload do usuario tem prioridade sobre qualquer outra; senao, a mais recente."""
    consulta = db.query(TrilhaVinheta).filter_by(account_id=account_id, programa_id=programa_id)
    upload = consulta.filter_by(origem="upload").order_by(TrilhaVinheta.id.desc()).first()
    return upload or consulta.order_by(TrilhaVinheta.id.desc()).first()


def obter_trilha_programa(
    db: Session, account_id: int, programa: Programa, forcar_nova_ia: bool = False
) -> TrilhaVinheta | None:
    """Resolve a trilha das vinhetas do programa seguindo a ordem do docstring do modulo. Nunca
    levanta: qualquer falha da IA cai pro banco, banco vazio devolve None (sem trilha)."""
    if not forcar_nova_ia:
        existente = trilha_atual_do_programa(db, account_id, programa.id)
        if existente is not None:
            return existente

    if trilha_ia_disponivel():
        try:
            return gerar_trilha_ia(db, account_id, programa)
        except Exception:
            logger.warning(
                "Trilha por IA falhou, caindo pro banco local: programa_id=%s", programa.id, exc_info=True,
            )

    try:
        return trilha_do_banco(db, account_id, programa)
    except Exception:
        logger.warning("Banco local de trilhas falhou: programa_id=%s", programa.id, exc_info=True)
        return None


def excluir_trilha(db: Session, trilha: TrilhaVinheta) -> None:
    get_storage().delete(trilha.audio_path)
    db.delete(trilha)
