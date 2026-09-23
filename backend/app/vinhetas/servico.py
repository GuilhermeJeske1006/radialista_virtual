"""Vinhetas automaticas de programa: criacao, job de audio, remix e limpeza.

As vinhetas sao BibliotecaAudioItem com origem="auto" (ver app/models/biblioteca_audio.py) --
o mesmo "vinheta:<id>" que o ao vivo, o cartwall e a tela /vinhetagem ja entendem.

Fluxo na criacao do programa (criar_vinhetas_programa + agendar_processamento):
texto via LLM -> 3 itens "pendente" -> estrutura_blocos -> commit -> job em segundo plano:
trilha -> TTS -> voz processada -> mix por papel -> master -> "pronta".
"""
import logging
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

from fastapi import BackgroundTasks
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.database import SessionLocal, engine
from app.models.account import Account
from app.models.biblioteca_audio import BibliotecaAudioItem
from app.models.categoria_vinheta import CategoriaVinheta
from app.models.programa import Programa
from app.models.radio_config import RadioConfig
from app.models.trilha_vinheta import TrilhaVinheta
from app.storage import get_storage
from app.tts.client import sintetizar_audio, tts_habilitado
from app.tts.profiles import parametros_sintese
from app.vinhetas import audio
from app.vinhetas.estrutura import inserir_vinhetas_na_estrutura, remover_vinhetas_das_estruturas
from app.vinhetas.gerador import NOMES_PAPEL, PAPEIS, gerar_textos_vinhetas
from app.vinhetas.trilha import excluir_trilha, obter_trilha_programa

logger = logging.getLogger("radialista.vinhetas")

# Papel da vinheta -> nome da categoria padrao de vinhetagem (app/categorias_vinheta/defaults.py)
# em que ela aparece na tela /vinhetagem. Categoria renomeada/excluida = "Sem categoria".
_CATEGORIA_POR_PAPEL = {"abertura": "Abertura", "passagem": "Vinhetas", "encerramento": "Encerramento"}

# tipo_bloco repassado ao TTS (ajusta prosodia, ver _construir_voice_settings em app.tts.client).
_TIPO_BLOCO_TTS = {"abertura": "abertura", "encerramento": "encerramento", "passagem": None}

_MSG_TTS_INDISPONIVEL = "Voz IA indisponível -- o ao vivo fala o texto na hora, sem trilha."


def _abrir_sessao() -> Session:
    return SessionLocal()


def vinhetas_auto_do_programa(db: Session, account_id: int, programa_id: int) -> list[BibliotecaAudioItem]:
    return (
        db.query(BibliotecaAudioItem)
        .filter_by(account_id=account_id, programa_id=programa_id, origem="auto")
        .order_by(BibliotecaAudioItem.id)
        .all()
    )


def vinheta_encerramento(db: Session, account_id: int, programa_id: int) -> BibliotecaAudioItem | None:
    return (
        db.query(BibliotecaAudioItem)
        .filter_by(account_id=account_id, programa_id=programa_id, papel="encerramento", ativo=True)
        .order_by(BibliotecaAudioItem.id.desc())
        .first()
    )


def _categorias_por_papel(db: Session, account_id: int) -> dict[str, int]:
    categorias = db.query(CategoriaVinheta).filter_by(account_id=account_id, tipo="biblioteca").all()
    por_nome = {c.nome: c.id for c in categorias}
    return {papel: por_nome[nome] for papel, nome in _CATEGORIA_POR_PAPEL.items() if nome in por_nome}


def _remover_arquivos(item: BibliotecaAudioItem) -> None:
    storage = get_storage()
    for caminho in (item.audio_path, item.voz_path):
        if caminho:
            storage.delete(caminho)


def excluir_vinhetas(db: Session, account_id: int, itens: list[BibliotecaAudioItem]) -> None:
    """Remove arquivos, tira da estrutura_blocos de toda a conta e apaga as linhas (sem commit)."""
    remover_vinhetas_das_estruturas(db, account_id, [item.id for item in itens])
    for item in itens:
        _remover_arquivos(item)
        db.delete(item)
    db.flush()


def criar_vinhetas_programa(
    db: Session, account: Account, radialista: RadioConfig, programa: Programa, substituir: bool = False
) -> list[BibliotecaAudioItem]:
    """Cria as 3 vinhetas (status="pendente") e coloca na estrutura do programa. Nao commita --
    quem chama commita e depois agenda o audio (agendar_processamento).

    Idempotente: se o programa ja tem vinhetas automaticas, devolve elas (garantindo a estrutura)
    em vez de duplicar -- a nao ser com substituir=True (regerar), que apaga e cria de novo."""
    existentes = vinhetas_auto_do_programa(db, account.id, programa.id)
    if existentes and not substituir:
        inserir_vinhetas_na_estrutura(programa, existentes)
        return existentes
    if existentes:
        excluir_vinhetas(db, account.id, existentes)

    textos = gerar_textos_vinhetas(account, radialista, programa)
    categorias = _categorias_por_papel(db, account.id)
    itens = []
    for papel in PAPEIS:
        item = BibliotecaAudioItem(
            account_id=account.id,
            programa_id=programa.id,
            nome=f"{NOMES_PAPEL[papel]} – {programa.nome}",
            categoria_id=categorias.get(papel),
            papel=papel,
            texto=textos[papel],
            status="pendente",
            origem="auto",
            ativo=True,
        )
        db.add(item)
        itens.append(item)
    db.flush()
    inserir_vinhetas_na_estrutura(programa, itens)
    return itens


def agendar_processamento(background_tasks: BackgroundTasks | None, vinheta_ids: list[int], **opcoes) -> None:
    """Job de audio fora do request: a Music API pode levar dezenas de segundos. Sem worker de
    fila no projeto, usa BackgroundTasks (roda no mesmo processo depois da resposta). Reinicio no
    meio do job deixa a vinheta presa -- recuperar_vinhetas_travadas limpa isso no boot."""
    if not vinheta_ids:
        return
    if background_tasks is None:
        _processar_em_background(vinheta_ids, **opcoes)
    else:
        background_tasks.add_task(_processar_em_background, vinheta_ids, **opcoes)


def criar_vinhetas_com_seguranca(
    db: Session,
    account: Account,
    radialista: RadioConfig,
    programa: Programa,
    background_tasks: BackgroundTasks | None,
    substituir: bool = False,
) -> list[BibliotecaAudioItem]:
    """Chamado pelas rotas de criacao de programa DEPOIS do commit do programa: nada aqui pode
    derrubar a criacao dele. Falha vira rollback so' das vinhetas + warning."""
    try:
        itens = criar_vinhetas_programa(db, account, radialista, programa, substituir=substituir)
        db.commit()
    except Exception:
        db.rollback()
        logger.warning("Falha ao criar vinhetas do programa: programa_id=%s", programa.id, exc_info=True)
        return []
    db.refresh(programa)
    agendar_processamento(background_tasks, [item.id for item in itens])
    logger.info("Vinhetas criadas: programa_id=%s ids=%s", programa.id, [item.id for item in itens])
    return itens


def _processar_em_background(vinheta_ids: list[int], **opcoes) -> None:
    db = _abrir_sessao()
    try:
        processar_vinhetas(db, vinheta_ids, **opcoes)
    except Exception:
        logger.warning("Job de audio das vinhetas falhou: ids=%s", vinheta_ids, exc_info=True)
    finally:
        db.close()


def _voz_efetiva(db: Session, item: BibliotecaAudioItem) -> str | None:
    if item.voz_id:
        return item.voz_id
    if item.programa_id is None:
        return None
    programa = db.get(Programa, item.programa_id)
    radialista = db.get(RadioConfig, programa.radio_config_id) if programa else None
    return radialista.voz_id if radialista else None


def _pedido_voz(db: Session, item: BibliotecaAudioItem) -> dict | None:
    """Tudo que o TTS precisa, lido do banco na thread principal (a Session nao e' thread-safe).
    None quando o TTS nao esta disponivel pra essa voz."""
    voz = _voz_efetiva(db, item)
    if not item.texto or not tts_habilitado(voz):
        return None
    return {
        "texto": item.texto,
        "voz": voz,
        "tipo_bloco": _TIPO_BLOCO_TTS.get(item.papel),
        "parametros": parametros_sintese(db, item.account_id, voz),
    }


def _sintetizar_voz_seca(pedido: dict) -> bytes:
    """TTS + processamento da voz seca -- so' rede e ffmpeg, sem banco (roda em thread)."""
    tts = sintetizar_audio(pedido["texto"], pedido["voz"], tipo_bloco=pedido["tipo_bloco"], **pedido["parametros"])
    return audio.processar_voz(tts)


def _guardar_voz(item: BibliotecaAudioItem, voz_wav: bytes) -> None:
    caminho = f"vinhetas/{item.account_id}/voz-{uuid.uuid4().hex}.wav"
    get_storage().save(caminho, voz_wav)
    if item.voz_path:
        get_storage().delete(item.voz_path)
    item.voz_path = caminho


def _salvar_final(item: BibliotecaAudioItem, conteudo: bytes) -> None:
    caminho = f"vinhetas/{item.account_id}/{uuid.uuid4().hex}.mp3"
    get_storage().save(caminho, conteudo)
    if item.audio_path:
        get_storage().delete(item.audio_path)
    item.audio_path = caminho
    item.audio_nome_original = f"{item.nome}.mp3"
    try:
        item.duracao_segundos = round(audio.duracao_bytes(conteudo))
    except audio.ErroAudio:
        item.duracao_segundos = None


def _ler_trilha(db: Session, item: BibliotecaAudioItem) -> bytes | None:
    if not item.usar_trilha or item.trilha_id is None:
        return None
    trilha = db.get(TrilhaVinheta, item.trilha_id)
    if trilha is None or trilha.account_id != item.account_id:
        return None
    return get_storage().read(trilha.audio_path)


def mixar_item(db: Session, item: BibliotecaAudioItem, voz_wav: bytes | None = None) -> None:
    """Remixa a partir da voz seca guardada -- sem TTS nem Music API. Mix com trilha falhando,
    guarda a melhor versao possivel (so' voz processada) e marca erro."""
    if voz_wav is None:
        voz_wav = get_storage().read(item.voz_path) if item.voz_path else None
    if voz_wav is None:
        raise audio.ErroAudio("vinheta ainda nao tem voz gerada")

    trilha = _ler_trilha(db, item)
    try:
        final = audio.mixar(voz_wav, trilha, item.papel or "passagem", item.volume_trilha_db)
        item.status, item.erro_msg = "pronta", None
    except audio.ErroAudio as exc:
        if trilha is None:
            raise
        logger.warning("Mix com trilha falhou, salvando so' a voz: vinheta_id=%s", item.id, exc_info=True)
        final = audio.mixar(voz_wav, None, item.papel or "passagem")
        item.status, item.erro_msg = "erro", f"Mix com trilha falhou ({exc}); vinheta ficou só com a voz."
    _salvar_final(item, final)


def _resolver_trilhas(db: Session, itens: list[BibliotecaAudioItem], forcar_nova_trilha: bool) -> None:
    """Uma trilha pro programa inteiro (uma chamada a Music API), resolvida uma vez so'."""
    trilhas_por_programa: dict[int, int | None] = {}
    for item in itens:
        if item.programa_id is None or not item.usar_trilha:
            continue
        if item.programa_id not in trilhas_por_programa:
            programa = db.get(Programa, item.programa_id)
            reutilizavel = None if forcar_nova_trilha else item.trilha_id
            if programa is None:
                trilhas_por_programa[item.programa_id] = None
            elif reutilizavel is not None and db.get(TrilhaVinheta, reutilizavel) is not None:
                trilhas_por_programa[item.programa_id] = reutilizavel
            else:
                trilha = obter_trilha_programa(db, item.account_id, programa, forcar_nova_ia=forcar_nova_trilha)
                trilhas_por_programa[item.programa_id] = trilha.id if trilha else None
                db.commit()
        item.trilha_id = trilhas_por_programa[item.programa_id]


def processar_vinhetas(
    db: Session,
    vinheta_ids: list[int],
    regerar_voz: bool = True,
    forcar_nova_trilha: bool = False,
) -> None:
    """Trilha e vozes em paralelo: a Music API leva dezenas de segundos e as 3 chamadas de TTS
    nao dependem dela -- em sequencia o tempo total era trilha + 3x TTS. So' o mix espera os dois."""
    itens = (
        db.query(BibliotecaAudioItem)
        .filter(BibliotecaAudioItem.id.in_(vinheta_ids))
        .order_by(BibliotecaAudioItem.id)
        .all()
    )
    if not itens:
        return
    inicio = time.monotonic()
    for item in itens:
        item.status, item.erro_msg = "gerando", None
    db.commit()

    pedidos: dict[int, dict | None] = {}
    for item in itens:
        if regerar_voz or not item.voz_path:
            try:
                pedidos[item.id] = _pedido_voz(db, item)
            except Exception:
                logger.warning("Falha ao preparar a voz da vinheta: vinheta_id=%s", item.id, exc_info=True)
                pedidos[item.id] = None

    with ThreadPoolExecutor(max_workers=len(itens)) as pool:
        vozes = {vid: pool.submit(_sintetizar_voz_seca, pedido) for vid, pedido in pedidos.items() if pedido}
        _resolver_trilhas(db, itens, forcar_nova_trilha)
        tempo_trilha_ms = int((time.monotonic() - inicio) * 1000)

        for item in itens:
            try:
                voz_wav = None
                if item.id in pedidos:
                    if pedidos[item.id] is None:
                        item.status, item.erro_msg = "erro", _MSG_TTS_INDISPONIVEL
                        db.commit()
                        continue
                    voz_wav = vozes[item.id].result()
                    _guardar_voz(item, voz_wav)
                mixar_item(db, item, voz_wav)
            except Exception as exc:
                logger.warning("Falha no audio da vinheta: vinheta_id=%s programa_id=%s", item.id, item.programa_id,
                               exc_info=True)
                item.status, item.erro_msg = "erro", f"Falha ao gerar o áudio: {str(exc)[:200]}"
            db.commit()

    logger.info(
        "vinhetas_job_concluido ids=%s tempo_trilha_ms=%s tempo_total_ms=%s status=%s",
        vinheta_ids, tempo_trilha_ms, int((time.monotonic() - inicio) * 1000), [i.status for i in itens],
    )


def excluir_dados_do_programa(db: Session, account_id: int, programa_id: int) -> None:
    """Ao excluir um programa: apaga as vinhetas automaticas e as trilhas dele (com arquivos).
    Vinheta manual ligada ao programa sobrevive como avulsa. Sem commit."""
    excluir_vinhetas(db, account_id, vinhetas_auto_do_programa(db, account_id, programa_id))
    db.query(BibliotecaAudioItem).filter_by(account_id=account_id, programa_id=programa_id).update(
        {"programa_id": None, "trilha_id": None}
    )
    trilhas = db.query(TrilhaVinheta).filter_by(account_id=account_id, programa_id=programa_id).all()
    if trilhas:
        db.query(BibliotecaAudioItem).filter(
            BibliotecaAudioItem.trilha_id.in_([t.id for t in trilhas])
        ).update({"trilha_id": None}, synchronize_session=False)
    for trilha in trilhas:
        excluir_trilha(db, trilha)
    db.flush()


def recuperar_vinhetas_travadas() -> None:
    """Boot: vinheta que ficou "pendente"/"gerando" quando o processo caiu nunca vai terminar
    (BackgroundTasks morre junto com o processo). Marca erro pra o usuario poder gerar de novo --
    o ao vivo ja cobre com TTS na hora enquanto isso."""
    try:
        with engine.begin() as conn:
            resultado = conn.execute(
                text(
                    "UPDATE biblioteca_audio_itens SET status = 'erro', erro_msg = :msg "
                    "WHERE status IN ('pendente', 'gerando')"
                ),
                {"msg": "Geração interrompida por reinício do servidor. Clique em Gerar de novo."},
            )
        if resultado.rowcount:
            logger.warning("Vinhetas travadas marcadas como erro no boot: %s", resultado.rowcount)
    except Exception:
        logger.warning("Falha ao recuperar vinhetas travadas no boot", exc_info=True)
