"""Deriva gancho de efemeride (ano de lancamento da musica -- ver Musica.youtube_metadados,
metadado do YouTube ja coletado por app.live.music) -- "faz N anos que essa saiu". Puramente
programatico, sem chamada de LLM: e' so' aritmetica sobre um dado que ja existe, inventar uma
chamada haiku pra isso seria custo sem ganho (ver Fase B do plano-assuntos.md).

So' vira gancho quando N >= _MIN_ANOS_EFEMERIDE -- "faz 1 ano" nao tem peso de efemeride de
radio, "faz 10/20/30 anos" tem.
"""

import datetime

from sqlalchemy.orm import Session

from app.models.assunto import Assunto
from app.models.musica import Musica

_MIN_ANOS_EFEMERIDE = 5
_TAGS_EFEMERIDE = ["musica", "efemeride", "curiosidade"]


def _ja_derivada_este_ano(db: Session, musica_id: int, ano_atual: int) -> bool:
    inicio_ano = datetime.datetime(ano_atual, 1, 1, tzinfo=datetime.timezone.utc)
    return (
        db.query(Assunto.id)
        .filter(Assunto.origem == "efemeride", Assunto.origem_ref_id == musica_id, Assunto.criado_em >= inicio_ano)
        .first()
        is not None
    )


def derivar_de_efemeride(db: Session, musica: Musica, account_id: int, generos_extra: list[str] | None = None) -> Assunto | None:
    ano_lancamento_raw = (musica.youtube_metadados or {}).get("ano") if musica.youtube_metadados else None
    try:
        ano_lancamento = int(str(ano_lancamento_raw)[:4])
    except (TypeError, ValueError):
        return None

    ano_atual = datetime.datetime.now(datetime.timezone.utc).year
    anos = ano_atual - ano_lancamento
    if anos < _MIN_ANOS_EFEMERIDE:
        return None

    if _ja_derivada_este_ano(db, musica.id, ano_atual):
        return None

    assunto = Assunto(
        account_id=account_id,
        origem="efemeride",
        origem_ref_id=musica.id,
        titulo=f"{anos} anos de {musica.artista} - {musica.titulo}",
        gancho=f"Faz {anos} anos que \"{musica.titulo}\", de {musica.artista}, foi lancada.",
        fatos=[f"{musica.titulo} ({musica.artista}) foi lancada em {ano_lancamento}, ha {anos} anos."],
        # Genero de quem tocou a musica (ver mesma correcao em app.topics.fontes.de_musica) --
        # sem isso a efemeride tambem nunca casaria com o filtro por genero de nenhum programa.
        tags=list(_TAGS_EFEMERIDE) + [g.lower() for g in (generos_extra or [])],
        # Valido ate' o fim do ano corrente -- na virada, o numero de anos muda e um novo
        # Assunto e' derivado (ver _ja_derivada_este_ano), este aqui nao deve sobreviver com
        # contagem desatualizada.
        validade_ate=datetime.datetime(ano_atual, 12, 31, 23, 59, 59, tzinfo=datetime.timezone.utc),
        peso_base=3.0,
    )
    db.add(assunto)
    db.commit()
    return assunto
