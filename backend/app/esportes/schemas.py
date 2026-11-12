import datetime as dt
import ipaddress
import re
from typing import Literal
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator


class Modelo(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Perfil(Modelo):
    nome: str = Field(default="Locufy Esportes", min_length=1, max_length=120)
    regiao: str = Field(default="", max_length=200)
    clubes: list[str] = Field(default_factory=list, max_length=30)
    campeonatos: list[str] = Field(default_factory=list, max_length=30)
    modalidades: list[str] = Field(default_factory=lambda: ["Futebol"], max_length=20)
    fuso: str = "America/Sao_Paulo"
    estilo: str = Field(default="Energia moderada, frases curtas e linguagem brasileira.", max_length=1000)
    identidade_sonora: str = Field(default="Vinhetas breves; trilha baixa e sem trilha em explicações densas.", max_length=1000)
    participacao: bool = False
    distribuicao: dict[str, int] = Field(default_factory=lambda: {"regional": 40, "nacional": 35, "internacional": 15, "outras": 10})

    @field_validator("fuso")
    @classmethod
    def fuso_valido(cls, v):
        try:
            ZoneInfo(v)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("Fuso horário inválido") from None
        return v

    @field_validator("distribuicao")
    @classmethod
    def distribuicao_valida(cls, v):
        if set(v) != {"regional", "nacional", "internacional", "outras"} or any(n < 0 or n > 100 for n in v.values()) or sum(v.values()) != 100:
            raise ValueError("Os quatro espaços editoriais devem somar 100%")
        return v


def dominio_exato(v: str) -> str:
    v = v.lower().rstrip(".")
    if not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", v) or "." not in v or any(not p or p.startswith("-") or p.endswith("-") for p in v.split(".")):
        raise ValueError("Informe o domínio exato, sem protocolo nem caminho")
    if v.endswith((".localhost", ".local", ".internal")):
        raise ValueError("Informe um domínio público")
    try:
        ipaddress.ip_address(v)
    except ValueError:
        return v
    raise ValueError("Use o domínio da organização, não um endereço IP")


def url_original(v: str) -> str:
    u = urlsplit(v)
    if u.scheme != "https" or not u.hostname or u.username or u.password or u.port not in (None, 443):
        raise ValueError("Use o endereço HTTPS da página original")
    dominio_exato(u.hostname)
    return v


class Fonte(Modelo):
    dominio: str = Field(max_length=253)
    organizacao: str = Field(min_length=1, max_length=200)
    temas: str = Field(min_length=1, max_length=500)
    regiao: str = Field(default="Brasil", max_length=200)
    idioma: str = Field(default="pt-BR", max_length=30)
    acesso: Literal["manual", "api_autorizada", "feed_autorizado", "pagina_permitida"] = "manual"
    frequencia_permitida: str = Field(default="Consulta editorial manual", min_length=1, max_length=300)
    prioridade: int = Field(default=1, ge=1, le=10)
    ultima_revisao: dt.date
    ativa: bool = True
    condicoes_uso: str = Field(min_length=1, max_length=1000)

    _dominio = field_validator("dominio")(dominio_exato)

    @field_validator("ultima_revisao")
    @classmethod
    def revisao_passada(cls, v):
        if v > dt.datetime.now(dt.timezone.utc).date():
            raise ValueError("A revisão não pode estar no futuro")
        return v


class Fato(Modelo):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,60}$")
    texto: str = Field(min_length=1, max_length=2000)
    tipo: Literal["noticia", "agenda", "resultado", "escalacao", "transferencia", "analise", "atemporal"] = "noticia"
    evento: str = Field(min_length=1, max_length=200)
    ocorrido_em: AwareDatetime
    publicado_em: AwareDatetime
    coletado_em: AwareDatetime
    valido_ate: AwareDatetime
    fonte_id: int
    fonte_revisao: int = Field(ge=1)
    url: str = Field(max_length=2000)
    evidencia: str = Field(min_length=1, max_length=3000)
    origem_comum: str = Field(min_length=1, max_length=200)
    confirmacao: Literal["confirmado", "provavel", "negociacao", "encerrado", "contestado", "adiado", "cancelado"] = "provavel"
    oficial: bool = False
    revisado: bool = False
    sensivel: bool = False
    revisao_sensivel: bool = False
    participantes: list[str] = Field(default_factory=list, max_length=2)
    competicao: str = Field(default="", max_length=200)
    placar: list[int] = Field(default_factory=list, max_length=2)

    _url = field_validator("url")(url_original)

    @model_validator(mode="after")
    def cronologia(self):
        if self.valido_ate <= self.coletado_em or self.publicado_em > self.coletado_em:
            raise ValueError("Confira publicação, coleta e validade do fato")
        if self.placar and (len(self.placar) != 2 or any(n < 0 for n in self.placar)):
            raise ValueError("Informe os dois gols do placar, sem números negativos")
        if self.tipo == "resultado" and (len(self.participantes) != 2 or len(self.placar) != 2 or not self.competicao):
            raise ValueError("Resultado exige participantes, competição e placar")
        return self


class Bloco(Modelo):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,60}$")
    titulo: str = Field(min_length=1, max_length=120)
    tipo: Literal["abertura", "noticias", "agenda", "analise", "torcida", "intervalo", "encerramento"]
    duracao_s: int = Field(ge=5, le=600)
    responsavel: str = Field(default="Apresentador", min_length=1, max_length=120)
    transicao: str = Field(default="", max_length=300)
    opcional: bool = False
    reserva: str = Field(default="", max_length=2000)
    texto: str = Field(default="", max_length=8000)
    fato_ids: list[str] = Field(default_factory=list, max_length=60)


class ConteudoEdicao(Modelo):
    titulo: str = Field(min_length=1, max_length=160)
    modelo: Literal["boletim_2", "boletim_3", "programa_30"]
    exibicao_em: AwareDatetime
    perfil: Perfil
    fatos: list[Fato] = Field(default_factory=list, max_length=60)
    blocos: list[Bloco] = Field(min_length=1, max_length=30)

    @model_validator(mode="after")
    def integridade(self):
        if len({f.id for f in self.fatos}) != len(self.fatos) or len({b.id for b in self.blocos}) != len(self.blocos):
            raise ValueError("Identificadores de fatos e blocos devem ser únicos")
        ids = {f.id for f in self.fatos}
        if any(set(b.fato_ids) - ids or len(set(b.fato_ids)) != len(b.fato_ids) for b in self.blocos):
            raise ValueError("Bloco com referência de fato inexistente ou repetida")
        alvo = {"boletim_2": 120, "boletim_3": 180, "programa_30": 1800}[self.modelo]
        if sum(b.duracao_s for b in self.blocos) != alvo:
            raise ValueError(f"O espelho deve somar {alvo} segundos, incluindo intervalos")
        if self.blocos[0].tipo != "abertura" or self.blocos[-1].tipo != "encerramento" or not any(b.tipo == "agenda" for b in self.blocos):
            raise ValueError("Preserve abertura, agenda e encerramento")
        if self.modelo == "programa_30" and sum(b.duracao_s for b in self.blocos if b.tipo == "intervalo") != 120:
            raise ValueError("O programa tem 28 minutos editoriais e dois de intervalo")
        return self


class NovaEdicao(Modelo):
    modelo: Literal["boletim_2", "boletim_3", "programa_30"] = "boletim_3"
    exibicao_em: AwareDatetime


class SalvarEdicao(Modelo):
    revisao: int = Field(ge=1)
    conteudo: ConteudoEdicao


class Acao(Modelo):
    revisao: int = Field(ge=1)


class Aprovar(Acao):
    conferido: bool = False
