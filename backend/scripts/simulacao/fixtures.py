"""Modelos Pydantic das fixtures da simulação: relógio, programa, catálogo, pedidos e injeções.

Não importa app.*: o CLI carrega a fixture antes de preparar o ambiente do backend.
Todos os valores numéricos (orçamentos, durações, relógios) são hipóteses de projeto da pesquisa
(docs/pesquisa-radio-locufy.md §9 e skill referencia-radio), guardados aqui como configuração.
"""

import datetime
import json
import pathlib
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

DIR_FIXTURES = pathlib.Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "programas"
DIR_RELOGIOS = DIR_FIXTURES / "relogios"
DIR_CATALOGOS = DIR_FIXTURES / "catalogos"

_HORARIO_RE = re.compile(r"^\d{2}:\d{2}$")


class _Estrito(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EventoRelogio(_Estrito):
    inicio_s: int = Field(ge=0)
    duracao_s: int = Field(gt=0)
    tipo: str
    grupo: Literal["musica", "fala", "intervalo"]
    rotulo: str
    natureza: Literal["obrigatorio", "ajustavel"]
    hard_time: bool = False
    # Categorias de bloco do backend (ou tipos de evento do as_run) que cumprem este evento.
    corresponde_a: list[str] = Field(default_factory=list)


class Relogio(_Estrito):
    id: str
    nome: str
    fonte: str
    hipotese: bool
    nota: str = ""
    eventos: list[EventoRelogio] = Field(min_length=1)

    def duracao_por_grupo(self) -> dict[str, int]:
        soma = {"musica": 0, "fala": 0, "intervalo": 0}
        for evento in self.eventos:
            soma[evento.grupo] += evento.duracao_s
        return soma


class Faixa(_Estrito):
    video_id: str
    titulo: str
    artista: str
    generos: list[str] = Field(min_length=1)
    duracao_s: int = Field(gt=0)
    fim_s: int | None = None
    contexto: str = ""
    indisponivel: bool = False

    @property
    def duracao_tocada_s(self) -> int:
        """Mesma conta do player: (fim_segundos ou duracao_segundos) - inicio_segundos."""
        return self.fim_s or self.duracao_s

    @property
    def rotulo(self) -> str:
        """Formato do as_run e do histórico do painel: 'Título - Artista'."""
        return f"{self.titulo} - {self.artista}"


class Catalogo(_Estrito):
    id: str
    descricao: str
    faixas: list[Faixa] = Field(min_length=1)


class Orcamento(_Estrito):
    min: float = Field(ge=0)
    max: float = Field(gt=0)
    # Meta usada pelo dublê do LLM. Vazio = ponto médio entre min e max.
    alvo: float | None = None
    fonte: str = ""

    def alvo_s(self) -> float:
        return self.alvo if self.alvo is not None else (self.min + self.max) / 2


class Conta(_Estrito):
    nome_radio: str
    slogan: str = ""
    frequencia: str = ""
    cidade: str = ""
    atendimento_ouvinte_ativo: bool = False


class Radialista(_Estrito):
    nome_locutor: str
    personalidade: str = ""
    timezone: str = "America/Sao_Paulo"


class Vinheta(_Estrito):
    papel: str
    texto: str
    duracao_s: float | None = None
    com_audio: bool = False


class PatrocinadorFixture(_Estrito):
    chave: str
    nome: str
    tipo_conteudo: Literal["texto", "audio"] = "texto"
    texto: str
    duracao_s: float | None = None


class Pedido(_Estrito):
    chega_em_s: float = Field(ge=0)
    tipo: Literal["musica", "abraco", "sorteio"]
    nome: str
    telefone: str
    natureza: str = "recado_comum"
    musica_query: str | None = None
    mensagem: str
    texto_autorizado: str


class Injecao(_Estrito):
    """Distorção aplicada pelo dublê na n-ésima fala gerada (contando a partir de 1, sem as revisões)."""

    fala: int = Field(ge=1)
    tipo: Literal["promessa", "excesso", "cita_musica", "cita_ouvinte"]
    frase: str = ""
    fator: float = 1.6
    titulo: str = ""
    artista: str = ""
    nome: str = ""


class FixturePrograma(_Estrito):
    id: str
    formato: str
    descricao: str
    relogio: str
    timezone: str
    inicio: datetime.datetime
    unidade_fala: Orcamento
    orcamento_ref_s: dict[str, Orcamento]
    conta: Conta
    radialista: Radialista
    # Replica as colunas de app.models.programa.Programa (o teste confere os nomes).
    programa: dict[str, Any]
    # Nome legível de quadros fixos (rótulo do bloco -> nome falado), usado só pelo dublê.
    rotulos_quadros: dict[str, str] = Field(default_factory=dict)
    catalogo: str
    vinhetas: list[Vinheta] = Field(default_factory=list)
    patrocinadores: list[PatrocinadorFixture] = Field(default_factory=list)
    pedidos: list[Pedido] = Field(default_factory=list)
    injecoes: list[Injecao] = Field(default_factory=list)

    @field_validator("inicio")
    @classmethod
    def _inicio_com_fuso(cls, valor: datetime.datetime) -> datetime.datetime:
        if valor.tzinfo is None:
            raise ValueError("inicio precisa de fuso horário (ex.: 2026-11-10T14:00:00-03:00)")
        return valor

    @model_validator(mode="after")
    def _programa_coerente(self) -> "FixturePrograma":
        for campo in ("nome", "horario_inicio", "horario_fim"):
            if campo not in self.programa:
                raise ValueError(f"programa.{campo} é obrigatório")
        for campo in ("horario_inicio", "horario_fim"):
            if not _HORARIO_RE.match(str(self.programa[campo])):
                raise ValueError(f"programa.{campo} deve ser HH:MM")
        if "padrao" not in self.orcamento_ref_s:
            raise ValueError("orcamento_ref_s precisa da chave 'padrao'")
        return self

    @property
    def formato_musical(self) -> bool:
        return self.programa.get("perfil_programacao") == "musical_companhia"

    def horario(self, campo: str) -> datetime.time:
        hora, minuto = str(self.programa[campo]).split(":")
        return datetime.time(int(hora), int(minuto))

    def duracao_programa_s(self) -> int:
        inicio, fim = self.horario("horario_inicio"), self.horario("horario_fim")
        segundos = (fim.hour * 60 + fim.minute - inicio.hour * 60 - inicio.minute) * 60
        return segundos if segundos > 0 else segundos + 24 * 3600

    def orcamento_para(self, tipo: str, categoria: str | None = None) -> Orcamento:
        """Orçamento de referência do formato: rótulo do bloco, depois categoria, depois 'padrao'."""
        for chave in (tipo, categoria):
            if chave and chave in self.orcamento_ref_s:
                return self.orcamento_ref_s[chave]
        return self.orcamento_ref_s["padrao"]


def _ler_json(caminho: pathlib.Path) -> dict:
    return json.loads(caminho.read_text(encoding="utf-8"))


def _caminho(id_ou_caminho: str | pathlib.Path, pasta: pathlib.Path) -> pathlib.Path:
    caminho = pathlib.Path(id_ou_caminho)
    if caminho.suffix == ".json" and caminho.exists():
        return caminho
    candidato = pasta / f"{id_ou_caminho}.json"
    if candidato.exists():
        return candidato
    raise FileNotFoundError(f"Fixture não encontrada: {id_ou_caminho} (procurado em {pasta})")


def carregar_fixture(id_ou_caminho: str | pathlib.Path) -> FixturePrograma:
    return FixturePrograma.model_validate(_ler_json(_caminho(id_ou_caminho, DIR_FIXTURES)))


def carregar_catalogo(id_ou_caminho: str | pathlib.Path) -> Catalogo:
    return Catalogo.model_validate(_ler_json(_caminho(id_ou_caminho, DIR_CATALOGOS)))


def carregar_relogio(id_ou_caminho: str | pathlib.Path) -> Relogio:
    """Aceita o id curto ('A', 'B', 'C') ou o caminho de um arquivo de relógio."""
    caminho = pathlib.Path(str(id_ou_caminho))
    if caminho.suffix == ".json" and caminho.exists():
        return Relogio.model_validate(_ler_json(caminho))
    for arquivo in sorted(DIR_RELOGIOS.glob("*.json")):
        dados = _ler_json(arquivo)
        if dados.get("id") == str(id_ou_caminho) or arquivo.stem == str(id_ou_caminho):
            return Relogio.model_validate(dados)
    raise FileNotFoundError(f"Relógio não encontrado: {id_ou_caminho} (procurado em {DIR_RELOGIOS})")
