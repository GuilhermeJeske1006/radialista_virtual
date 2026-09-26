import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict, ValidationError
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.admin_sistema.dependencies import get_current_super_admin
from app.config.settings import settings
from app.db.database import get_db
from app.guardrails.http_rate_limit import limitar_por_ip
from app.funnel.service import Campaign, FunnelEvent, record_event

router = APIRouter(tags=["funil"])


class PublicEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    evento: Literal["landing_view", "register_click", "whatsapp_click", "demo_play", "video_play",
                    "register_started", "register_account_step", "register_radio_step", "plan_selected"]
    local: Literal["header", "hero", "pricing-flex", "pricing-starter", "pricing-growth", "pricing-professional", "faq", "footer",
                   "contact", "floating", "demo-abertura", "demo-recado", "demo-chamada", "video", "register", "landing"] = "register"
    plano: Literal["", "flex", "starter", "growth", "professional"] = ""
    campanha: Campaign = Campaign()


@router.post("/funnel/events", status_code=204, dependencies=[Depends(limitar_por_ip("funnel", limite=120, janela_segundos=60))])
async def collect(request: Request, db: Session = Depends(get_db)):
    # Sem cookies/autenticação; origens restritas e tamanho limitado antes de decodificar.
    allowed = {origin.strip() for origin in [settings.frontend_url, *settings.funnel_origins.split(",")] if origin.strip()}
    if "localhost" in settings.frontend_url:
        allowed.add(settings.frontend_url.replace("localhost", "127.0.0.1"))
    if request.headers.get("origin") not in allowed:
        raise HTTPException(403, "Origem não permitida")
    if request.headers.get("dnt") == "1" or request.headers.get("sec-gpc") == "1":
        return Response(status_code=204)
    raw = bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw) > 2048:
            raise HTTPException(413, "Evento muito grande")
    try:
        event = PublicEvent.model_validate_json(bytes(raw))
    except (ValidationError, ValueError):
        raise HTTPException(422, "Evento inválido")
    record_event(db, event.evento, event_id=str(event.id), local=event.local, plano=event.plano,
                 campanha=event.campanha.model_dump(exclude_defaults=True))
    db.commit()
    return Response(status_code=204)


@router.get("/admin/funnel", dependencies=[Depends(get_current_super_admin)])
def summary(dias: int = Query(30, ge=1, le=90), db: Session = Depends(get_db)):
    since = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=dias)
    rows = db.query(FunnelEvent.evento, FunnelEvent.local, FunnelEvent.plano,
                    func.count(FunnelEvent.id), func.sum(FunnelEvent.valor_centavos)).filter(
                    FunnelEvent.criado_em >= since).group_by(FunnelEvent.evento, FunnelEvent.local, FunnelEvent.plano).all()
    return {"dias": dias, "eventos": [dict(evento=e, local=l, plano=p, total=n, receita_centavos=v or 0) for e,l,p,n,v in rows],
            "nota": "Cliques e etapas são eventos, não visitantes únicos. Receita corresponde ao primeiro pagamento confirmado de assinaturas em BRL."}
