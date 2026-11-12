"""Desvincula um programa excluído sem apagar as evidências do atendimento."""
from app.models.canal_whatsapp import (EntradaWhatsapp, BlocoReproduzido, DiscussaoPrograma,
    ContribuicaoOuvinte, EstadoTransmissao, DecisaoPauta)


def arquivar_programa(db, programa_id):
    db.query(EntradaWhatsapp).filter_by(programa_id=programa_id, estado="pendente").update({"estado": "expirada"})
    db.query(EntradaWhatsapp).filter_by(programa_id=programa_id).update({"programa_id": None})
    db.query(BlocoReproduzido).filter(BlocoReproduzido.programa_id == programa_id,
        BlocoReproduzido.estado.in_(("preparado", "reproduzindo"))).update({"estado": "interrompido"})
    db.query(BlocoReproduzido).filter_by(programa_id=programa_id).update({"programa_id": None})
    db.query(DiscussaoPrograma).filter_by(programa_id=programa_id).update({"estado": "encerrada", "programa_id": None})
    db.query(ContribuicaoOuvinte).filter_by(programa_id=programa_id, estado="aguardando_revisao").update({"estado": "expirada"})
    db.query(ContribuicaoOuvinte).filter_by(programa_id=programa_id).update({"programa_id": None})
    db.query(EstadoTransmissao).filter_by(programa_id=programa_id).delete()
    db.query(DecisaoPauta).filter_by(programa_id=programa_id).delete()
