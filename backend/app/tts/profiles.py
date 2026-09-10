"""Resolve tipo real e preferências sem alterar o modelo global do servidor."""
import datetime

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.models.perfil_voz import ConfiguracaoVoz, MetadadosVoz
from app.tts.client import obter_metadados_voz


def consultar_metadados(db: Session, voz_id: str, atualizar: bool = False) -> MetadadosVoz:
    meta = db.get(MetadadosVoz, voz_id)
    agora = datetime.datetime.now(datetime.timezone.utc)
    if meta and not atualizar and (agora - meta.atualizado_em.replace(tzinfo=datetime.timezone.utc)).total_seconds() < 3600:
        return meta
    dados = obter_metadados_voz(voz_id)
    if meta is None:
        try:
            with db.begin_nested():
                meta = MetadadosVoz(voz_id=voz_id, categoria="desconhecida", requer_verificacao=False, atualizado_em=agora)
                db.add(meta)
                db.flush()
        except IntegrityError:
            meta = db.get(MetadadosVoz, voz_id)
    if dados:
        for chave, valor in dados.items():
            if valor is not None:
                setattr(meta, chave, valor)
    # Em falha preserva categoria e verificação anteriores. TTL também evita
    # repetir uma consulta sem sucesso a cada bloco do ao vivo.
    meta.atualizado_em = agora
    db.commit()
    return meta


def parametros_sintese(db: Session, account_id: int, voz_id: str | None) -> dict:
    efetiva = voz_id or settings.elevenlabs_voice_id
    if not efetiva:
        return {"eh_clonada": False}
    meta = consultar_metadados(db, efetiva)
    if meta.requer_verificacao:
        raise HTTPException(status_code=409, detail="Esta voz aguarda verificação na ElevenLabs. Conclua a verificação e atualize o status da voz.")
    # Categoria desconhecida nunca é presumida como IVC. PVC e biblioteca não
    # recebem os deltas específicos de amostras instantâneas.
    parametros = {"eh_clonada": meta.categoria == "cloned"}
    config = db.query(ConfiguracaoVoz).filter_by(account_id=account_id, voz_id=efetiva).first()
    if config:
        parametros.update(modelo=config.modelo, perfil=config.perfil, formato=config.formato, pronuncias=config.pronuncias)
    return parametros
