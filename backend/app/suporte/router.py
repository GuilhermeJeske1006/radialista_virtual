import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.auth.dependencies import get_current_usuario
from app.guardrails.http_rate_limit import limite_excedido
from app.llm.client import gerar_resposta_chat
from app.models.usuario import Usuario
from app.suporte.contexto import CONTEXTO_SISTEMA

logger = logging.getLogger("radialista.suporte")

router = APIRouter(prefix="/suporte", tags=["suporte"])

# Quantas mensagens do historico (usuario + bot) sao reenviadas ao LLM a cada pergunta --
# limita custo/tokens sem perder o contexto recente da conversa.
_HISTORICO_MAX_MENSAGENS = 12


class MensagemChat(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=2000)


class ChatRequest(BaseModel):
    mensagem: str = Field(min_length=1, max_length=2000)
    historico: list[MensagemChat] = Field(default_factory=list)


class ChatResponse(BaseModel):
    resposta: str


@router.post("/chat", response_model=ChatResponse)
def chat(dados: ChatRequest, usuario: Usuario = Depends(get_current_usuario)) -> ChatResponse:
    if limite_excedido(f"suporte_chat:{usuario.id}", limite=30, janela_segundos=3600):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Muitas perguntas em pouco tempo. Tenta de novo daqui a pouco.",
        )

    historico_recente = dados.historico[-_HISTORICO_MAX_MENSAGENS:]
    mensagens = [{"role": m.role, "content": m.content} for m in historico_recente]
    mensagens.append({"role": "user", "content": dados.mensagem})

    try:
        resposta = gerar_resposta_chat(CONTEXTO_SISTEMA, mensagens)
    except Exception:
        logger.warning("Falha ao gerar resposta do chat de suporte: usuario_id=%s", usuario.id, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Não consegui responder agora. Tenta de novo em instantes.",
        )

    return ChatResponse(resposta=resposta)
