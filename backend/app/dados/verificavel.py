"""Tipo comum de dado verificável e a regra única de validade (F5, docs/melhoria-radio/f5/auditoria.md §6.3).

Regra 5 da skill referencia-radio: dado de cidade, clima, trânsito, placar só com fonte, horário e validade; vencido,
omitir ou dizer o horário da última atualização. A mesma regra vale para a pauta RSS (`janela_noticia`), para o
bloco de dados do prompt (`estado`) e para o validador da fala (`idade_maxima`).

Os números ficam em `CONFIG_DADOS`: são hipóteses de projeto (auditoria §11, "Números"), nunca constantes soltas.
Puro: sem banco, sem Redis, sem rede; não importa o router nem app.live.contexto.
"""

import dataclasses
import datetime
from typing import Literal, Mapping
from zoneinfo import ZoneInfo

from app.numeros import cardinal_feminino, numero_por_extenso

TipoDado = Literal["noticia", "servico", "transito", "clima", "previsao", "agenda", "esporte", "correcao",
                   "assunto", "aviso", "comercial"]
EstadoDado = Literal["valido", "vencido", "sem_fonte", "nao_aprovado", "futuro"]
ESTADOS: tuple[str, ...] = ("valido", "vencido", "sem_fonte", "nao_aprovado", "futuro")


# ---------------------------------------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------------------------------------

@dataclasses.dataclass(frozen=True)
class ConfigDados:
    # Janela de validade da notícia RSS por categoria, contada da publicação (os valores de app.news.pauta antes da
    # F5): hard news envelhece rápido, serviço aguenta um pouco mais, agenda/cultura dura a semana.
    janela_noticia_h: Mapping[str, int] = dataclasses.field(default_factory=lambda: {
        "seguranca": 24, "transito": 24, "clima_defesa_civil": 24, "saude": 24, "economia": 48,
        "servico_publico": 48, "geral": 48, "agenda_cultura": 24 * 7,
    })
    janela_noticia_padrao_h: int = 48
    # Validade por tipo quando o dado não traz `valido_ate`, contada de `atualizado_em`: o clima da observação, a
    # apuração web da consulta.
    validade_s: Mapping[str, int] = dataclasses.field(default_factory=lambda: {
        "clima": 3600, "pesquisa": 7200, "noticia_pesquisa": 7200, "esporte": 7200,
    })
    # Idade máxima do dado para a fala afirmar como atual, por categoria de afirmação (app.dados.checagem): acima
    # disso, só com o horário. Categoria fora daqui não tem limite próprio além da validade.
    idade_max_afirmacao_s: Mapping[str, int] = dataclasses.field(default_factory=lambda: {
        "temperatura": 3600, "condicao_tempo": 3600, "transito": 1800, "placar": 900,
    })
    # Dado vencido no bloco de dados do prompt (D4): "com_horario" vai com a hora da última atualização; o resto é
    # omitido.
    vencido_no_prompt: Mapping[str, str] = dataclasses.field(default_factory=lambda: {"clima": "com_horario"})
    idade_max_vencido_s: int = 10800           # vencido mais velho que isso some do prompt, mesmo com horário
    clima_cache_ttl_s: int = 1800              # cache da consulta ao Open-Meteo (igual ao de antes da F5)
    clima_ultima_leitura_ttl_s: int = 10800    # última leitura guardada para quando a API cair (D5)
    tolerancia_futuro_s: int = 300             # relógio da fonte adiantado até isso ainda é "agora"
    limite_texto: int = 600                    # caracteres de texto externo por campo no bloco
    limite_nome: int = 40                      # caracteres do nome do ouvinte (D15)
    nome_substituto: str = "um ouvinte"        # nome com ordem embutida
    # Quem pode ser citado no ar como fonte do dado, por tipo (D8: o prompt pede, o validador não exige).
    fonte_no_ar: Mapping[str, str] = dataclasses.field(default_factory=lambda: {
        "clima": "o serviço de meteorologia",
    })
    # Agenda com data do evento (D12): fim do evento quando só há hora de início.
    duracao_evento_padrao_s: int = 4 * 3600


CONFIG_DADOS = ConfigDados()


# ---------------------------------------------------------------------------------------------------------
# Estrutura
# ---------------------------------------------------------------------------------------------------------

@dataclasses.dataclass(frozen=True)
class DadoVerificavel:
    """Um dado que pode ir ao ar. Montado em memória a partir de colunas que já existem (D13, sem migração)."""

    id: str                                  # "noticia:12" | "pesquisa:3" | "clima:<cidade>" | "assunto:7"
    tipo: TipoDado
    valor: str                               # texto já limpo (sem ordem embutida), números como vieram
    fonte: str                               # quem publicou ou mediu (registro); "" = sem fonte, nunca vai ao prompt
    atualizado_em: datetime.datetime | None  # publicação, observação ou consulta
    valido_ate: datetime.datetime | None     # None = pela regra do tipo, ou atemporal (assunto de reserva)
    local: str = ""
    aprovado: bool = True                    # False: curadoria bloqueou, ou nada sobrou depois da limpeza
    atribuicao: str = ""                     # quem pode ser citado no ar; vazio = não citar fonte
    origem: str = ""                         # "rss" | "pesquisa_web" | "pesquisa_publica" | "integracao_clima" | ...
    detalhes: Mapping[str, str] = dataclasses.field(default_factory=dict, hash=False)
    alertas: tuple[str, ...] = ()            # "instrucao_removida", "resumo_cru", "ultima_leitura"


# ---------------------------------------------------------------------------------------------------------
# Validade
# ---------------------------------------------------------------------------------------------------------

def _utc(instante: datetime.datetime) -> datetime.datetime:
    return instante.replace(tzinfo=datetime.timezone.utc) if instante.tzinfo is None else instante


def valido_ate_efetivo(dado: DadoVerificavel, config: ConfigDados | None = None) -> datetime.datetime | None:
    """O `valido_ate` do dado; sem ele, `atualizado_em` + a validade do tipo (`validade_s`); sem regra, atemporal."""
    cfg = config or CONFIG_DADOS
    if dado.valido_ate is not None:
        return _utc(dado.valido_ate)
    segundos = cfg.validade_s.get(dado.tipo)
    if segundos is None or dado.atualizado_em is None:
        return None
    return _utc(dado.atualizado_em) + datetime.timedelta(seconds=segundos)


def estado(dado: DadoVerificavel, instante: datetime.datetime, config: ConfigDados | None = None) -> EstadoDado:
    """"sem_fonte", "nao_aprovado", "futuro" (atualizado depois de agora), "vencido" ou "valido", nessa ordem."""
    cfg = config or CONFIG_DADOS
    instante = _utc(instante)
    if not (dado.fonte or "").strip():
        return "sem_fonte"
    if not dado.aprovado:
        return "nao_aprovado"
    if dado.atualizado_em is not None and \
            _utc(dado.atualizado_em) > instante + datetime.timedelta(seconds=cfg.tolerancia_futuro_s):
        return "futuro"
    ate = valido_ate_efetivo(dado, cfg)
    if ate is not None and instante > ate:
        return "vencido"
    return "valido"


def janela_noticia(categoria: str | None, config: ConfigDados | None = None) -> datetime.timedelta:
    """Janela de validade da notícia RSS pela categoria da curadoria (a mesma da pauta e do assunto derivado)."""
    cfg = config or CONFIG_DADOS
    return datetime.timedelta(hours=cfg.janela_noticia_h.get(categoria or "", cfg.janela_noticia_padrao_h))


def idade_maxima(categoria_afirmacao: str, config: ConfigDados | None = None) -> datetime.timedelta | None:
    segundos = (config or CONFIG_DADOS).idade_max_afirmacao_s.get(categoria_afirmacao)
    return datetime.timedelta(seconds=segundos) if segundos is not None else None


def velho_para_afirmar(dado: DadoVerificavel, categoria_afirmacao: str, instante: datetime.datetime,
                       config: ConfigDados | None = None) -> bool:
    """Dado ainda válido, mas mais velho que a idade máxima da afirmação: só pode ir ao ar com o horário."""
    limite = idade_maxima(categoria_afirmacao, config)
    if limite is None or dado.atualizado_em is None:
        return False
    return _utc(instante) - _utc(dado.atualizado_em) > limite


def idade(dado: DadoVerificavel, instante: datetime.datetime) -> datetime.timedelta | None:
    return _utc(instante) - _utc(dado.atualizado_em) if dado.atualizado_em is not None else None


# ---------------------------------------------------------------------------------------------------------
# Horário falado (vai ao TTS: nunca algarismo)
# ---------------------------------------------------------------------------------------------------------

def horario_falado(instante: datetime.datetime, tz: str) -> str:
    """"às catorze e dez", "ao meio-dia", "à meia-noite e trinta", "à uma hora", no fuso da rádio."""
    local = _utc(instante).astimezone(ZoneInfo(tz))
    hora, minuto = local.hour, local.minute
    if hora == 12:
        base = "ao meio-dia"
    elif hora == 0:
        base = "à meia-noite"
    elif hora == 1:
        base = "à uma"
    else:
        base = f"às {cardinal_feminino(hora)}"
    if minuto:
        return f"{base} e {numero_por_extenso(minuto)}"
    if hora in (0, 12):
        return base
    return f"{base} hora" if hora == 1 else f"{base} horas"


def quando_falado(instante: datetime.datetime | None, agora: datetime.datetime, tz: str) -> str:
    """Horário falado com o dia relativo ao de agora, no fuso da rádio: "hoje, às nove horas", "ontem, às vinte e
    três e cinquenta", "no dia oito, às nove horas". Sem instante, vazio."""
    if instante is None:
        return ""
    fuso = ZoneInfo(tz)
    dia, hoje = _utc(instante).astimezone(fuso).date(), _utc(agora).astimezone(fuso).date()
    if dia == hoje:
        prefixo = "hoje"
    elif dia == hoje - datetime.timedelta(days=1):
        prefixo = "ontem"
    else:
        prefixo = f"no dia {numero_por_extenso(dia.day)}"
    return f"{prefixo}, {horario_falado(instante, tz)}"
