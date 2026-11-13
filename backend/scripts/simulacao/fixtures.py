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
    """Distorção aplicada pelo dublê na n-ésima fala gerada (contando a partir de 1, sem as revisões).
    excesso: só a primeira versão passa do limite (a reescrita obedece); excesso_persistente (F2): o dublê
    ignora também o limite da reescrita, para exercitar o encurtamento por frases do backend.
    F5: dado_sem_fonte (afirmação sem dado, como temperatura ou placar), dado_vencido (a leitura antiga dita como
    atual) e obedece_injecao (a afirmação que a ordem embutida num título pedia), todas com a `frase`.
    F6 (coerência com o formato): debate_longo (uma frase corrida de `segundos`, que nem a reescrita nem o encurtamento
    por frases resolvem), convite (convite ao ouvinte, a `frase`) e tema_revisao (a `frase` com tema que o formato manda
    revisar)."""

    fala: int = Field(ge=1)
    tipo: Literal["promessa", "excesso", "excesso_persistente", "cita_musica", "cita_ouvinte", "dado_sem_fonte",
                  "dado_vencido", "obedece_injecao", "debate_longo", "convite", "tema_revisao"]
    frase: str = ""
    fator: float = 1.6
    segundos: float = 0
    titulo: str = ""
    artista: str = ""
    nome: str = ""


class LeituraClimaFixture(_Estrito):
    """F5: o que o dublê do clima (obter_leitura_clima) devolve a partir de `desde_s` (relativo ao início).
    `falha`: a API está fora e volta a última leitura boa guardada (marcada como última leitura)."""

    desde_s: float = 0
    falha: bool = False
    temperatura_c: float = 0
    descricao: str = "céu limpo"
    observado_s: float = 0     # horário da observação, relativo ao início


class NoticiaFixture(_Estrito):
    """F5: notícia semeada no banco do cenário (app.models.noticia.Noticia), como o worker gravaria."""

    titulo: str
    resumo: str = ""
    categoria: str = "geral"
    fonte_nome: str = "Prefeitura"
    publicado_s: float = -3600  # relativo ao início
    score: float = 80
    detalhes: dict[str, str] = Field(default_factory=dict)


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
    # F5 (só nos cenários dedicados; as três fixtures de linha de base não mudam, D14).
    clima: list[LeituraClimaFixture] = Field(default_factory=list)
    noticias: list[NoticiaFixture] = Field(default_factory=list)
    # O dublê do LLM usa um dado do bloco da mensagem (o LLM obediente): mede o falso positivo do validador.
    duble_usa_dados: bool = False
    # F6 (D19): ligado pelo simulador com --formato fixture|<id>. A referência de orçamento do as-run passa a vir do
    # catálogo de formatos quando o formato aplica orçamento (a da fixture fica para o padrao); com --formato programa
    # (as linhas de base) continua a de antes.
    orcamento_do_catalogo: bool = False

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
    def formato_backend(self):
        """O `Formato` que o backend resolve para o programa (alias incluído). Importação tardia: este módulo não
        importa app.* no topo."""
        from app.live.formatos import resolver_formato

        return resolver_formato(self.programa.get("perfil_programacao"))

    @property
    def formato_musical(self) -> bool:
        return self.formato_backend.comportamento.ciclo == "musical"

    def quadros(self) -> tuple[str, ...]:
        """Rótulos dos quadros fixos com conteúdo (a mesma regra do backend, app.live.formatos.eh_quadro_fixo)."""
        return tuple(rotulo for rotulo, pool in (self.programa.get("quadros_fixos") or {}).items() if pool)

    def referencia(self, tipo: str, categoria: str | None = None, primeira: bool = False) -> Orcamento:
        """Referência de orçamento do as-run: com `orcamento_do_catalogo` e formato que aplica orçamento, a unidade do
        catálogo para o papel do bloco; senão a da fixture (unidade_fala no musical, orcamento_ref_s no resto)."""
        formato = self.formato_backend
        if self.orcamento_do_catalogo and formato.aplica_orcamento:
            from app.live.formatos import unidade

            u = unidade(formato, tipo, primeira, quadro=tipo in self.quadros())
            return Orcamento(min=u.min_s, max=u.max_s, alvo=u.alvo_s, fonte=f"catalogo {formato.id}")
        return self.unidade_fala if self.formato_musical else self.orcamento_para(tipo, categoria)

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
