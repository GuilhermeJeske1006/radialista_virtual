"""Combinações prontas de texto + voz para gerar e operar um locutor.

Uma combinação só é oferecida quando os modelos dela têm tarifa vigente publicada. O
preço por hora usa as premissas de docs/simulacao-plano-consumo.md sobre essas
tarifas: é referência para a escolha, não valor faturado (a fatura usa o medido).
"""
import json
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import func, select

from app.billing.flex import MICRO, calcular, conta_consumo, tarifa_atual
from app.config.settings import settings
from app.models.consumo_flex import UsoIA


@dataclass(frozen=True)
class Combinacao:
    id: str
    nome: str
    texto: str
    voz: str
    descricao: str
    limitacoes: str
    recomendada: bool = False


# Todas as combinações dos 3 modelos de texto com as 2 vozes, do maior ao menor custo.
# Limitações vêm das avaliações em docs/benchmarks (2026-09-24-economia e
# 2026-09-25-combinacoes): sem prometer equivalência entre opções que executam a mesma tarefa.
COMBINACOES = (
    Combinacao(
        "premium", "Premium", "claude-opus-5", "eleven_v3",
        "Texto mais elaborado e voz mais expressiva, com direção vocal (risada, suspiro, empolgação). "
        "É a configuração padrão do Locufy.",
        "Maior custo. Falas muito longas demoram mais para ficar prontas.",
        recomendada=True,
    ),
    Combinacao(
        "equilibrada", "Equilibrada", "claude-sonnet-5", "eleven_v3",
        "A mesma voz expressiva do Premium, com geração de texto mais barata.",
        "Texto menos elaborado que o Premium em pautas com muitos detalhes.",
    ),
    Combinacao(
        "voz_premium", "Voz Premium", "claude-haiku-4-5", "eleven_v3",
        "Voz expressiva com o texto de menor custo.",
        "O texto chegou a acrescentar fato não informado nas avaliações. Revise falas sobre datas e eventos.",
    ),
    Combinacao(
        "texto_premium", "Texto Premium", "claude-opus-5", "eleven_flash_v2_5",
        "O texto mais elaborado com a voz mais rápida e barata.",
        "Voz sem direção vocal e menos expressiva; pode trocar palavras por formas coloquiais (\"para\" → \"pra\").",
    ),
    Combinacao(
        "agil", "Ágil", "claude-sonnet-5", "eleven_flash_v2_5",
        "Voz mais rápida e mais barata de gerar.",
        "Voz sem direção vocal e menos expressiva; pode trocar palavras por formas coloquiais (\"para\" → \"pra\").",
    ),
    Combinacao(
        "essencial", "Essencial", "claude-haiku-4-5", "eleven_flash_v2_5",
        "Menor custo por hora de programa.",
        "Nas avaliações, o texto acrescentou fato não informado e passou do tamanho pedido. Revise falas "
        "sobre datas e eventos. Voz sem direção vocal.",
    ),
)

# O que cada modelo faz dentro do locutor, para o cliente entender a combinação. Mesmas
# fontes das limitações acima: nada além do que as avaliações mostraram.
MODELOS = {
    "claude-opus-5": {
        "funcao": "texto",
        "descricao": "O mais elaborado: aproveita melhor pautas com muitos detalhes e varia mais o jeito de falar.",
    },
    "claude-sonnet-5": {
        "funcao": "texto",
        "descricao": "Texto natural com custo menor. Em pautas com muitos detalhes, fica menos elaborado que o Opus.",
    },
    "claude-haiku-4-5": {
        "funcao": "texto",
        "descricao": "O de menor custo. Nas avaliações, chegou a acrescentar fato não informado e a passar do "
                     "tamanho pedido.",
    },
    "eleven_v3": {
        "funcao": "voz",
        "descricao": "A mais expressiva, com direção vocal (risada, suspiro, empolgação). Falas muito longas "
                     "demoram mais para ficar prontas.",
    },
    "eleven_flash_v2_5": {
        "funcao": "voz",
        "descricao": "A mais rápida e barata de gerar. Sem direção vocal, menos expressiva; pode trocar palavras "
                     "por formas coloquiais (\"para\" → \"pra\").",
    },
}

# Premissas da simulação: 10% de fala nova (6 min por hora de programa; o resto é música
# e áudio pronto), 2 gerações por minuto de fala com 1.500/150 tokens, 3 classificações
# auxiliares de 500/32 tokens por geração e 1.000 caracteres de locução por minuto.
MINUTOS_FALA_POR_HORA = 6
GERACOES_POR_MINUTO = 2
TOKENS_ENTRADA_GERACAO, TOKENS_SAIDA_GERACAO = 1500, 150
CLASSIFICACOES_POR_GERACAO = 3
TOKENS_ENTRADA_CLASSIFICACAO, TOKENS_SAIDA_CLASSIFICACAO = 500, 32
CARACTERES_POR_MINUTO = 1000
# Cenário mostrado quando ainda não há programa: 1 hora por dia, 30 dias.
HORAS_MES_REFERENCIA = 30

PREMISSAS = (
    f"Estimativa com {MINUTOS_FALA_POR_HORA} minutos de fala nova por hora de programa; música e áudios "
    "já prontos não geram nova cobrança. O valor faturado segue as unidades realmente medidas."
)

# Exemplos gerados por scripts/validar_combinacoes.py --exportar-exemplos: texto e áudio
# reais de cada combinação (mesmo pedido, mesma voz) e as unidades medidas na geração.
ARQUIVO_EXEMPLOS = Path(__file__).with_name("exemplos_combinacoes.json")


@lru_cache(maxsize=1)
def exemplos():
    try:
        return json.loads(ARQUIVO_EXEMPLOS.read_text())
    except (OSError, ValueError):
        return {}


def habilitadas():
    por_id = {c.id: c for c in COMBINACOES}
    return [por_id[i] for i in settings.ia_combinacoes if i in por_id]


def _brl(micro):
    return float((Decimal(micro) / MICRO).quantize(Decimal("0.0001")))


def _componentes_hora(tarifas):
    geracoes = MINUTOS_FALA_POR_HORA * GERACOES_POR_MINUTO
    classificacoes = geracoes * CLASSIFICACOES_POR_GERACAO
    return {
        "texto": calcular(tarifas["texto"], {"entrada": TOKENS_ENTRADA_GERACAO * geracoes,
                                             "saida": TOKENS_SAIDA_GERACAO * geracoes})[1],
        "classificacao": calcular(tarifas["classificacao"], {"entrada": TOKENS_ENTRADA_CLASSIFICACAO * classificacoes,
                                                             "saida": TOKENS_SAIDA_CLASSIFICACAO * classificacoes})[1],
        "voz": calcular(tarifas["voz"], {"caracteres": CARACTERES_POR_MINUTO * MINUTOS_FALA_POR_HORA})[1],
    }


def _preco_hora(tarifa_texto, tarifa_classificacao, tarifa_voz):
    return sum(_componentes_hora({"texto": tarifa_texto, "classificacao": tarifa_classificacao, "voz": tarifa_voz}).values())


def _exemplo(c, tarifas):
    dados = exemplos().get(c.id)
    if not dados:
        return None
    # Preço do exemplo com a tarifa vigente: o mesmo cálculo que a fatura faria para essas unidades.
    preco = (calcular(tarifas["texto"], dados["unidades_texto"])[1]
             + calcular(tarifas["voz"], {"caracteres": dados["caracteres_voz"]})[1])
    return {"pedido": dados["pedido"], "texto": dados["texto"], "audio_url": dados["audio_url"],
            "duracao_segundos": dados["duracao_segundos"], "caracteres_voz": dados["caracteres_voz"],
            "voz_padrao": True, "preco_brl": _brl(preco)}


def _publica(c, tarifas):
    componentes = _componentes_hora(tarifas)
    preco_hora = sum(componentes.values())
    return {
        "id": c.id, "nome": c.nome, "descricao": c.descricao, "limitacoes": c.limitacoes,
        "recomendada": c.recomendada, "modelo_texto": c.texto, "modelo_voz": c.voz,
        "preco_hora_brl": _brl(preco_hora),
        "custo_hora_brl": {k: _brl(v) for k, v in componentes.items()},
        "preco_mes_referencia_brl": _brl(preco_hora * HORAS_MES_REFERENCIA),
        # Preço de 1.000 caracteres de locução (≈ 1 minuto de fala), com câmbio e acréscimo.
        "preco_mil_caracteres_brl": _brl(calcular(tarifas["voz"], {"caracteres": 1000})[1]),
        "exemplo": _exemplo(c, tarifas),
        "tarifas": tarifas,
    }


def catalogo(db):
    """Combinações habilitadas cujos modelos (e o classificador auxiliar) têm tarifa vigente."""
    itens = []
    for c in habilitadas():
        try:
            tarifas = {"texto": tarifa_atual(db, "llm", c.texto), "voz": tarifa_atual(db, "tts", c.voz),
                       "classificacao": tarifa_atual(db, "llm", settings.llm_classification_model)}
        except HTTPException:
            continue
        itens.append(_publica(c, tarifas))
    # Só os modelos das combinações oferecidas, na ordem em que aparecem.
    usados = dict.fromkeys(m for item in itens for m in (item["modelo_texto"], item["modelo_voz"]))
    return {"combinacoes": itens, "modelos": {m: MODELOS[m] for m in usados if m in MODELOS},
            # Modelos usados quando o programa (ou o WhatsApp) não tem escolha gravada.
            "padrao": {"texto": settings.llm_model, "voz": settings.elevenlabs_model},
            "mensalidade_brl": 69.90, "minutos_fala_por_hora": MINUTOS_FALA_POR_HORA,
            "horas_mes_referencia": HORAS_MES_REFERENCIA, "premissas": PREMISSAS}


def obter(db, combinacao_id):
    for item in catalogo(db)["combinacoes"]:
        if item["id"] == combinacao_id:
            return item
    raise HTTPException(422, "Combinação de modelos indisponível. Escolha outra opção.")


def aplicar_no_contexto(combinacao):
    """Gerações seguintes desta request (persona, programa, vinhetas) usam a combinação."""
    from app.billing.contexto_ia import atual
    conta = atual.get()
    if conta is not None and combinacao:
        conta.modelo_texto, conta.modelo_voz = combinacao["modelo_texto"], combinacao["modelo_voz"]


def salvar_escolha(db, account_id, combinacao, *, programa_id, radialista_id=None):
    """Grava a escolha do programa e, com radialista, o padrão para os próximos programas dele.
    Commita em seguida: manter o lock da conta abriria impasse com a medição da mesma request."""
    conta = conta_consumo(db, account_id)
    escolha = {"texto": combinacao["modelo_texto"], "voz": combinacao["modelo_voz"], "combinacao": combinacao["id"]}
    modelos = {**(conta.modelos or {}), str(programa_id): {**escolha, "programa_id": programa_id}}
    if radialista_id is not None:
        modelos[f"radialista:{radialista_id}"] = escolha
    conta.modelos = modelos
    db.commit()


def preco_operacao_brl(db, account_id, operacao):
    """Preço já medido desta operação (a geração que o cliente acabou de pedir)."""
    if not settings.ia_medicao_habilitada:
        return None
    total = db.scalar(select(func.coalesce(func.sum(UsoIA.preco), 0)).where(
        UsoIA.account_id == account_id, UsoIA.operacao == operacao, UsoIA.estado.in_(["medido", "concluido"])))
    return _brl(total or 0)
