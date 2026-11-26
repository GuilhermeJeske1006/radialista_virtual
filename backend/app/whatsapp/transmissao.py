"""Contexto público só é publicado após confirmação do player autorizado."""
import datetime
import inspect
import re
import uuid
from functools import wraps
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Annotated, Literal
from app.auth.dependencies import get_current_account
from app.db.database import get_db
from app.models.programa import Programa
from app.models.radio_config import RadioConfig
from app.models.canal_whatsapp import BlocoReproduzido, EstadoTransmissao, DiscussaoPrograma, agora
from app.whatsapp.eventos import registrar

router = APIRouter(prefix="/ouvintes/transmissao", tags=["ouvintes"])


def utc(valor):
    return valor.replace(tzinfo=datetime.timezone.utc)


def acompanhar_geracao(func):
    @wraps(func)
    def executar(*args, **kwargs):
        resultado = func(*args, **kwargs)
        parametros = inspect.signature(func).bind(*args, **kwargs).arguments
        db, account = parametros.get("db"), parametros.get("account")
        if db is None or account is None:
            return resultado
        programa = db.get(Programa, parametros["programa_id"])
        radio = db.get(RadioConfig, programa.radio_config_id)
        from app.whatsapp.atendimento import ocorrencia
        fala = resultado.fala or ""
        perguntas = re.findall(r"[^.!?\n]+\?", fala)
        bloco = BlocoReproduzido(
            account_id=account.id, programa_id=programa.id, ocorrencia=ocorrencia(programa, radio.timezone),
            token=uuid.uuid4().hex, tipo=resultado.tipo, fala=fala[:16000],
            assunto_id=getattr(resultado, "assunto_id", None),
            assunto={"titulo": getattr(resultado, "assunto_titulo", None),
                     "pergunta": perguntas[-1].strip() if perguntas else ""},
            musica={"titulo": resultado.titulo_musica} if resultado.video_id else {},
        )
        db.add(bloco)
        db.flush()
        resultado.bloco_id, resultado.bloco_token = bloco.id, bloco.token
        resultado.bloco_programa_id = programa.id
        db.commit()
        return resultado
    return executar


def contexto_publico(db, account_id, programa_id):
    programa = db.get(Programa, programa_id)
    if not programa:
        return None
    radio = db.get(RadioConfig, programa.radio_config_id)
    if radio.account_id != account_id:
        return None
    from app.whatsapp.atendimento import ocorrencia
    atual = ocorrencia(programa, radio.timezone)
    bloco = db.query(BlocoReproduzido).filter_by(account_id=account_id, programa_id=programa_id,
        ocorrencia=atual, estado="concluido").order_by(BlocoReproduzido.atualizado_em.desc()).first()
    if not bloco or agora() - utc(bloco.atualizado_em) > datetime.timedelta(minutes=30):
        return None
    discussao = db.query(DiscussaoPrograma).filter_by(programa_id=programa_id, ocorrencia=atual,
        estado="aberta").order_by(DiscussaoPrograma.id.desc()).first()
    return {"bloco_id": bloco.id, "programa_id": programa_id, "ocorrencia": atual,
            "fala_confirmada": bloco.fala, "assunto": bloco.assunto.get("titulo"),
            "musica": bloco.musica, "confirmado_em": bloco.atualizado_em.isoformat(),
            "discussao_id": discussao.id if discussao and agora() - utc(discussao.criado_em) < datetime.timedelta(minutes=30) else None,
            "pergunta": discussao.pergunta if discussao and agora() - utc(discussao.criado_em) < datetime.timedelta(minutes=30) else None}


class FaixaExecutada(BaseModel):
    video_id: str = Field(min_length=1, max_length=64)
    titulo: str = Field(max_length=300)
    canal: str = Field(default="", max_length=180)
    duracao_segundos: int | None = Field(default=None, ge=0, le=86400)


class EventoPlayer(BaseModel):
    token: str
    player_id: str = Field(min_length=8, max_length=100)
    estado: Literal["reproduzindo", "concluido", "falhou", "interrompido", "heartbeat"]
    duracao_s: float | None = Field(default=None, ge=0, le=86400)
    motivo: str | None = Field(default=None, max_length=80, pattern=r"^[a-z0-9_:-]+$")
    faixas_executadas: list[FaixaExecutada] = Field(default_factory=list, max_length=3)
    falhas: list[Annotated[str, Field(max_length=80, pattern=r"^[a-z0-9_:-]+$")]] = Field(default_factory=list, max_length=8)


@router.post("/blocos/{bloco_id}/eventos")
def evento_player(bloco_id: int, dados: EventoPlayer, account=Depends(get_current_account), db=Depends(get_db)):
    # Todos os comandos de um programa têm a mesma ordem de locks.
    bloco = db.query(BlocoReproduzido).filter_by(id=bloco_id, account_id=account.id).first()
    if not bloco:
        raise HTTPException(404, "Bloco não encontrado")
    programa = db.query(Programa).filter_by(id=bloco.programa_id).with_for_update().one()
    db.refresh(bloco, with_for_update=True)
    radio = db.get(RadioConfig, programa.radio_config_id)
    from app.whatsapp.atendimento import ocorrencia
    if dados.token != bloco.token or bloco.ocorrencia != ocorrencia(programa, radio.timezone):
        raise HTTPException(409, "Token ou transmissão não corresponde ao bloco")
    if bloco.estado in ("concluido", "falhou", "interrompido"):
        if bloco.player_id != dados.player_id:
            raise HTTPException(409, "Bloco pertence a outro player")
        return {"estado": bloco.estado}
    estado = db.get(EstadoTransmissao, programa.id)
    if estado and estado.player_id != dados.player_id and agora() - utc(estado.heartbeat_em) < datetime.timedelta(seconds=60):
        raise HTTPException(409, "Outro player está transmitindo este programa")
    if dados.estado == "reproduzindo":
        if agora() - utc(bloco.criado_em) > datetime.timedelta(minutes=40):
            raise HTTPException(409, "Preparo expirado; gere um novo bloco")
        # Troca de bloco encerra o anterior abandonado; nunca marca como concluído.
        if estado and estado.bloco_id and estado.bloco_id != bloco.id:
            anterior = db.get(BlocoReproduzido, estado.bloco_id)
            if anterior and anterior.estado == "reproduzindo":
                anterior.estado = "interrompido"
                anterior.atualizado_em = agora()
                anterior.reproducao = {**(anterior.reproducao or {}),
                    "fim_em": agora().isoformat(), "motivo": "substituido_por_outro_bloco"}
        expirados = db.query(BlocoReproduzido).filter(
            BlocoReproduzido.programa_id == programa.id, BlocoReproduzido.account_id == account.id,
            BlocoReproduzido.estado == "preparado",
            BlocoReproduzido.criado_em < agora() - datetime.timedelta(minutes=40)).all()
        for expirado in expirados:
            expirado.estado = "interrompido"
            expirado.atualizado_em = agora()
            expirado.reproducao = {"fim_em": agora().isoformat(), "motivo": "preparo_expirado"}
        if estado is None:
            estado = EstadoTransmissao(programa_id=programa.id, ocorrencia=bloco.ocorrencia, player_id=dados.player_id)
            db.add(estado)
        estado.player_id, estado.bloco_id, estado.heartbeat_em = dados.player_id, bloco.id, agora()
        estado.ocorrencia = bloco.ocorrencia
        bloco.player_id, bloco.estado = dados.player_id, "reproduzindo"
        bloco.reproducao = {"inicio_em": agora().isoformat(), **(bloco.reproducao or {})}
    else:
        if not estado or estado.player_id != dados.player_id or estado.bloco_id != bloco.id or bloco.estado != "reproduzindo":
            raise HTTPException(409, "O bloco não está em reprodução neste player")
        estado.heartbeat_em = agora()
        if dados.estado != "heartbeat":
            bloco.estado = dados.estado
            bloco.reproducao = {**(bloco.reproducao or {}), "fim_em": agora().isoformat(),
                "duracao_s": dados.duracao_s, "motivo": dados.motivo,
                "falhas": [f[:80] for f in dados.falhas]}
            if dados.faixas_executadas:
                executadas = [f.model_dump() for f in dados.faixas_executadas]
                bloco.musica = {**(bloco.musica or {}), "executadas": executadas,
                                "titulo": executadas[-1]["titulo"]}
    bloco.atualizado_em = agora()
    if bloco.estado == "concluido":
        if bloco.assunto_id:
            from app.models.canal_whatsapp import ContribuicaoOuvinte
            contribuicoes = db.query(ContribuicaoOuvinte).filter_by(account_id=account.id,
                programa_id=programa.id, ocorrencia=bloco.ocorrencia, assunto_id=bloco.assunto_id,
                estado="aprovada").all()
            for contribuicao in contribuicoes:
                contribuicao.estado = "utilizada"
                registrar(db, account.id, "conversa.atualizada", conversa_id=contribuicao.conversa_id,
                          contribuicao_id=contribuicao.id, estado="utilizada")
        pergunta = bloco.assunto.get("pergunta")
        if pergunta and bloco.tipo in ("comentario", "chamada_ouvinte", "abertura"):
            db.query(DiscussaoPrograma).filter_by(programa_id=programa.id, estado="aberta").update({"estado": "encerrada"})
            db.add(DiscussaoPrograma(account_id=account.id, programa_id=programa.id, ocorrencia=bloco.ocorrencia,
                bloco_id=bloco.id, assunto_id=bloco.assunto_id, pergunta=pergunta))
    registrar(db, account.id, "bloco.atualizado", bloco_id=bloco.id, programa_id=programa.id, estado=bloco.estado)
    db.commit()
    return {"estado": bloco.estado}


@router.get("/programas/{programa_id}/contexto")
def obter_contexto(programa_id: int, account=Depends(get_current_account), db=Depends(get_db)):
    programa = db.get(Programa, programa_id)
    if not programa or db.get(RadioConfig, programa.radio_config_id).account_id != account.id:
        raise HTTPException(404, "Programa não encontrado")
    estado = db.get(EstadoTransmissao, programa_id)
    ativo = bool(estado and agora() - utc(estado.heartbeat_em) < datetime.timedelta(seconds=60))
    return {"player_ativo": ativo, "estado": "player_ativo" if ativo else "estado_desconhecido",
            "contexto": contexto_publico(db, account.id, programa_id)}
