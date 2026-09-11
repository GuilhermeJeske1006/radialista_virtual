"""Deriva um gancho de conversa a partir de uma musica ja tocada (ver MusicaHistorico) --
reaproveita o mesmo contexto real (resumir_contexto_musica) que ja' e' usado pra anunciar a
faixa (ver app.live.router._contexto_musica), so' que persistido como Assunto em vez de morrer
no anuncio -- ver Fase B/G do plano-assuntos.md ("historia por tras da musica").

So' um gancho por musica (nao passa pelo derivador em lote de app.topics.derivador: o contexto
ja vem enxuto de resumir_contexto_musica, explodir em varios ganchos seria forcar conteudo que
nao existe). Nunca inventa: quando resumir_contexto_musica devolve vazio (metadado insuficiente),
nao gera Assunto nenhum.
"""

import logging

from sqlalchemy.orm import Session

from app.llm.client import resumir_contexto_musica
from app.models.assunto import Assunto
from app.models.musica import Musica
from app.models.musica_historico import MusicaHistorico
from app.models.programa import Programa

logger = logging.getLogger("radialista.topics.fontes.de_musica")

_TAGS_MUSICA = ["musica", "memoria", "afeto"]


def _ja_derivada(db: Session, musica_historico_id: int) -> bool:
    return (
        db.query(Assunto.id).filter_by(origem="musica", origem_ref_id=musica_historico_id).first() is not None
    )


def derivar_de_musica(db: Session, historico: MusicaHistorico, account_id: int) -> Assunto | None:
    if historico.song_id is None or _ja_derivada(db, historico.id):
        return None

    musica = db.get(Musica, historico.song_id)
    if musica is None or not musica.youtube_metadados:
        return None

    metadados = musica.youtube_metadados
    contexto = resumir_contexto_musica(
        titulo=musica.titulo,
        canal=musica.artista,
        descricao=metadados.get("descricao") or "",
        tags=metadados.get("tags") or [],
        ano=metadados.get("ano"),
    )
    if not contexto:
        return None

    # Genero do programa onde a musica tocou (ver Programa.generos_musicais) -- sem isso o
    # gancho so' carrega tag generica ("musica", "memoria", "afeto") e nunca casa com o filtro
    # por genero de nenhum programa (bug real, achado testando o fluxo ao vivo: uma faixa
    # sertaneja tocada num programa sertanejo nunca concorria a virar assunto DO PROPRIO
    # programa por falta dessa tag). O genero do YouTube (tags brutas do video) e' ruido demais
    # pra usar aqui (costuma ser nome de artista/album, nao genero musical).
    programa = db.get(Programa, historico.programa_id)
    tags = list(_TAGS_MUSICA) + [g.lower() for g in (programa.generos_musicais if programa else [])]

    assunto = Assunto(
        account_id=account_id,
        origem="musica",
        origem_ref_id=historico.id,
        titulo=f"{musica.artista} - {musica.titulo}",
        gancho=contexto,
        fatos=[contexto],
        tags=tags,
        validade_ate=None,
        peso_base=4.0,
    )
    db.add(assunto)
    db.commit()
    return assunto
