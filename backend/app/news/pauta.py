"""Seleciona a próxima notícia real (ver app.models.noticia, alimentada por app.news.worker)
pra virar pauta de um bloco de notícia do ao vivo, e monta o texto de "lauda" injetado no
prompt (ver Fase 2 do plano de jornalismo) -- o espelho de fato apurado que faltava pro
locutor, no lugar da regra sem matéria-prima que existia antes.

Também cobre a seleção pros blocos derivados (Fase 4: escalada, plantão) e o protocolo de
correção no ar (Fase 7): tudo parte do mesmo pool de candidatos (ver `_candidatos`), só variando
o filtro/recorte de cada chamador. Cada notícia é contada uma única vez (nunca volta a ser pauta
depois de ir ao ar) -- sem bloco GIRO nem rotação de ângulo (fato/impacto/serviço/reação/
contexto), que existiam antes pra trazer a mesma notícia de volta em blocos diferentes.

Também não cita o nome do veículo/portal de onde a notícia veio (ver montar_lauda/
montar_escalada): isso é só apuração interna da redação (`Noticia.fonte_nome`), nunca vira
"segundo o G1" no ar.
"""

import dataclasses
import datetime
import itertools
import unicodedata

from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.noticia import Noticia
from app.models.noticia_historico import NoticiaHistorico
from app.models.programa import Programa

# Ângulo padrão de toda notícia comum (única aparição, ver docstring do módulo).
_ANGULO_PADRAO = "fato"

# Ângulo especial: usado só quando a fonte retifica uma pauta já ao ar (ver Fase 7 do plano de
# jornalismo, `correcao_pendente`) -- a única forma de uma notícia voltar a ser pauta.
ANGULO_CORRECAO = "correcao"

# Score mínimo (0-100, ver app.news.curadoria) pra uma notícia concorrer a PLANTÃO -- sem isso
# qualquer pauta mediana viraria plantão e a categoria perderia o sentido de urgência/impacto.
LIMIAR_SCORE_PLANTAO = 85.0

# Dose "pitada" (ver Fase 5 do plano de jornalismo) prioriza categorias leves em vez de excluir
# hard news por completo -- viés de ordenação (soft), não filtro duro: um programa que já tem
# tipos_noticias configurado pra hard news continua enxergando essas notícias, só não como
# primeira opção quando houver alternativa leve com score parecido.
_CATEGORIAS_LEVES = {"servico_publico", "agenda_cultura", "clima_defesa_civil"}
_BONUS_DOSE_PITADA = 20.0

# Janela de validade por categoria (ver app.news.curadoria.CATEGORIAS_NOTICIA) -- hard news
# envelhece rápido, serviço aguenta um pouco mais, agenda/cultura dura a semana.
_JANELA_VALIDADE_HORAS = {
    "seguranca": 24,
    "transito": 24,
    "clima_defesa_civil": 24,
    "saude": 24,
    "economia": 48,
    "servico_publico": 48,
    "geral": 48,
    "agenda_cultura": 24 * 7,
}

_MAX_CANDIDATOS = 200


def _sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


def _categoria_permitida(categoria: str, tipos_noticias: list[str]) -> bool:
    """Programa sem tipos_noticias configurado aceita qualquer categoria (comportamento atual,
    sem essa lista o bloco já não distinguia tipo de notícia). Com a lista configurada, casa por
    substring normalizada (ex.: 'trânsito e clima' cobre as categorias 'transito' e
    'clima_defesa_civil') -- 'geral' sempre passa, pra não travar a pauta por falta de categoria
    específica configurada."""
    if not tipos_noticias:
        return True
    if categoria == "geral":
        return True
    termos = _sem_acento(" ".join(tipos_noticias).lower())
    pedacos = categoria.replace("_", " ").split()
    return any(_sem_acento(pedaco) in termos for pedaco in pedacos)


def _bate_topico_proibido(noticia: Noticia, topicos_proibidos: list[str]) -> bool:
    if not topicos_proibidos:
        return False
    texto = f"{noticia.titulo} {noticia.resumo}".lower()
    return any(topico.lower() in texto for topico in topicos_proibidos)


def _primeira_frase(fala: str) -> str:
    for separador in (".", "!", "?"):
        indice = fala.find(separador)
        if indice != -1:
            return fala[: indice + 1].strip()
    return fala.strip()[:80]


def _score_efetivo(noticia: Noticia, dose: str) -> float:
    if dose == "pitada" and noticia.categoria in _CATEGORIAS_LEVES:
        return noticia.score + _BONUS_DOSE_PITADA
    return noticia.score


@dataclasses.dataclass
class NoticiaPauta:
    noticia_id: int
    titulo: str
    resumo: str
    fonte_nome: str
    fonte_tipo: str
    url: str
    categoria: str
    publicado_em: datetime.datetime
    angulo: str
    aberturas_usadas: list[str]
    detalhes: dict = dataclasses.field(default_factory=dict)


def _candidatos(
    db: Session,
    programa: Programa,
    account: Account,
    *,
    score_minimo: float = 0.0,
):
    """Gera, em ordem de relevância, toda notícia ativa da conta que ainda cabe como pauta pra
    este programa -- dentro da janela de validade da categoria, dentro dos tipos/tópicos
    configurados, e que ainda não foi ao ar neste programa (cada notícia conta uma única vez,
    ver docstring do módulo). Base comum de `proxima_noticia` (notícia comum), `proximas_noticias`
    (escalada) e `proxima_para_plantao` (score mínimo)."""
    agora = datetime.datetime.now(datetime.timezone.utc)
    tipos_noticias = programa.tipos_noticias or []
    topicos_proibidos = programa.topicos_proibidos or []
    dose = getattr(programa, "dose_noticia", "jornalistica") or "jornalistica"

    query = db.query(Noticia).filter(Noticia.account_id == account.id, Noticia.ativa.is_(True))
    if score_minimo:
        query = query.filter(Noticia.score >= score_minimo)
    candidatos = query.order_by(Noticia.score.desc(), Noticia.publicado_em.desc()).limit(_MAX_CANDIDATOS).all()
    if dose == "pitada":
        candidatos = sorted(candidatos, key=lambda n: _score_efetivo(n, dose), reverse=True)

    for noticia in candidatos:
        publicado_em = noticia.publicado_em
        if publicado_em.tzinfo is None:
            publicado_em = publicado_em.replace(tzinfo=datetime.timezone.utc)
        janela_horas = _JANELA_VALIDADE_HORAS.get(noticia.categoria, 48)
        if publicado_em < agora - datetime.timedelta(hours=janela_horas):
            continue
        if not _categoria_permitida(noticia.categoria, tipos_noticias):
            continue
        if _bate_topico_proibido(noticia, topicos_proibidos):
            continue

        historico = (
            db.query(NoticiaHistorico)
            .filter(NoticiaHistorico.noticia_id == noticia.id, NoticiaHistorico.programa_id == programa.id)
            .order_by(NoticiaHistorico.criado_em.desc())
            .all()
        )
        # Já foi ao ar neste programa (correção não conta, ver ANGULO_CORRECAO) -- cada notícia
        # é contada uma única vez, nunca mais volta a ser pauta (ver docstring do módulo).
        if any(h.angulo != ANGULO_CORRECAO for h in historico):
            continue

        yield NoticiaPauta(
            noticia_id=noticia.id,
            titulo=noticia.titulo,
            resumo=noticia.resumo,
            fonte_nome=noticia.fonte_nome,
            fonte_tipo=noticia.fonte_tipo,
            url=noticia.url,
            categoria=noticia.categoria,
            publicado_em=publicado_em,
            angulo=_ANGULO_PADRAO,
            aberturas_usadas=[],
            detalhes=noticia.detalhes or {},
        )


def proxima_noticia(db: Session, programa: Programa, account: Account) -> NoticiaPauta | None:
    """Uma única pauta pro bloco de notícia comum (ou serviço/reporter, que usam o mesmo
    recorte). None quando não há nenhuma pauta real disponível -- o chamador (ver
    app.live.router) não deve inventar notícia nesse caso, só cair pro fallback existente."""
    return next(_candidatos(db, programa, account), None)


def proximas_noticias(db: Session, programa: Programa, account: Account, limite: int = 3) -> list[NoticiaPauta]:
    """Várias pautas de uma vez, pro bloco ESCALADA (ver Fase 4 do plano de jornalismo) --
    manchetes de uma frase cada, sem repetir notícia entre si."""
    return list(itertools.islice(_candidatos(db, programa, account), limite))


def proxima_para_plantao(db: Session, programa: Programa, account: Account) -> NoticiaPauta | None:
    """Só devolve pauta quando o score de noticiabilidade (ver app.news.curadoria) está acima de
    LIMIAR_SCORE_PLANTAO -- sem isso qualquer notícia mediana viraria plantão."""
    return next(_candidatos(db, programa, account, score_minimo=LIMIAR_SCORE_PLANTAO), None)


def correcao_pendente(db: Session, programa: Programa) -> NoticiaPauta | None:
    """Notícia que já foi ao ar neste programa e que a fonte retificou depois (ver
    Noticia.retificada, marcado por app.news.worker) e que ainda não recebeu correção no ar --
    prioridade sobre qualquer outra pauta (ver Fase 7 do plano de jornalismo: corrigir
    explicitamente é prática padrão de jornalismo e barato de checar)."""
    ja_corrigidas = {
        h.noticia_id
        for h in db.query(NoticiaHistorico).filter_by(programa_id=programa.id, angulo=ANGULO_CORRECAO).all()
    }
    pendentes = (
        db.query(Noticia)
        .join(NoticiaHistorico, NoticiaHistorico.noticia_id == Noticia.id)
        .filter(NoticiaHistorico.programa_id == programa.id, Noticia.retificada.is_(True))
        .order_by(NoticiaHistorico.criado_em.desc())
        .all()
    )
    for noticia in pendentes:
        if noticia.id in ja_corrigidas:
            continue
        publicado_em = noticia.publicado_em
        if publicado_em.tzinfo is None:
            publicado_em = publicado_em.replace(tzinfo=datetime.timezone.utc)
        return NoticiaPauta(
            noticia_id=noticia.id,
            titulo=noticia.titulo,
            resumo=noticia.texto_retificacao or noticia.resumo,
            fonte_nome=noticia.fonte_nome,
            fonte_tipo=noticia.fonte_tipo,
            url=noticia.url,
            categoria=noticia.categoria,
            publicado_em=publicado_em,
            angulo=ANGULO_CORRECAO,
            aberturas_usadas=[],
            detalhes=noticia.detalhes or {},
        )
    return None


def montar_lauda(pauta: NoticiaPauta) -> str:
    """Monta o bloco 'PAUTA DESTE BLOCO' injetado no prompt (ver Fase 2 do plano) -- o espelho
    de fato apurado que substitui a regra vazia de antes. Só entram campos com conteúdo real:
    campo vazio na curadoria (ver app.news.curadoria) simplesmente não aparece, em vez de
    aparecer como 'não informado' e virar munição pro locutor comentar a própria lacuna."""
    if pauta.angulo == ANGULO_CORRECAO:
        return (
            "CORREÇÃO PENDENTE -- prioridade sobre qualquer outro assunto deste bloco: a fonte "
            f"retificou uma informação já dada no ar. Fato original: {pauta.titulo}. Correção: "
            f"{pauta.resumo}. Anuncie explicitamente que está corrigindo uma informação dada antes "
            "(ex.: 'corrigindo uma informação que a gente deu há pouco...'), sem se desculpar de "
            "forma exagerada nem esconder que houve mudança."
        )

    detalhes = pauta.detalhes or {}
    linhas = [
        "PAUTA DESTE BLOCO (fato apurado -- use só o que está aqui, não acrescente nada):",
        f"- Fato: {pauta.titulo}",
        f"- Quando: {detalhes.get('quando') or pauta.publicado_em.strftime('%d/%m/%Y %H:%M')}",
    ]
    if detalhes.get("onde"):
        linhas.append(f"- Onde: {detalhes['onde']}")
    if pauta.resumo:
        linhas.append(f"- Detalhe: {pauta.resumo}")
    if detalhes.get("numeros"):
        linhas.append(f"- Números: {detalhes['numeros']}")
    if detalhes.get("pessoas"):
        linhas.append(f"- Pessoas: {detalhes['pessoas']}")
    if detalhes.get("impacto"):
        linhas.append(f"- Impacto pro ouvinte: {detalhes['impacto']}")
    if detalhes.get("servico"):
        linhas.append(f"- Serviço: {detalhes['servico']}")
    if detalhes.get("proximo_passo"):
        linhas.append(f"- Próximo passo: {detalhes['proximo_passo']}")
    if detalhes.get("ainda_nao_divulgado"):
        linhas.append(
            f"- Ainda não divulgado: {detalhes['ainda_nao_divulgado']} -- relate isso como estado da "
            "apuração (ex.: 'a perícia ainda trabalha no local'), nunca como disclaimer sobre o que "
            "você pode ou não afirmar."
        )
    linhas.append(f"- ÂNGULO DESTE BLOCO: {pauta.angulo.upper()}")
    if pauta.aberturas_usadas:
        aberturas = "; ".join(f'"{a}"' for a in pauta.aberturas_usadas)
        linhas.append(
            f"Esta notícia já foi ao ar antes nesta transmissão, com abertura(ões): {aberturas}. "
            "Comece a fala de um jeito diferente dessas -- mesmo fato, abertura nova, sob o ângulo indicado acima."
        )
    return "\n".join(linhas)


def montar_escalada(pautas: list[NoticiaPauta]) -> str:
    """Bloco 'PAUTA DESTA ESCALADA' com várias manchetes de uma vez (ver Fase 4 do plano)."""
    linhas = ["PAUTA DESTA ESCALADA (fatos apurados -- uma manchete de uma frase pra cada, nessa ordem):"]
    for i, pauta in enumerate(pautas, start=1):
        linhas.append(f"{i}. {pauta.titulo}")
    return "\n".join(linhas)
