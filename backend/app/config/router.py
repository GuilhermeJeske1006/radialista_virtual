import datetime
import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_account
from app.db.database import get_db
from app.guardrails.http_rate_limit import limite_atingido, registrar_consumo
from app.llm.config_generator import (
    ajustar_configuracao_ia,
    ajustar_programa_ia,
    gerar_configuracao_ia,
    gerar_persona_ia,
    gerar_programa_ia,
    programas_existentes_do_roster,
    reparar_configuracao_ia,
    reparar_programa_ia,
)
from app.llm.tipos_radio import TIPOS_RADIO, tipo_radio_valido
from app.models.account import Account
from app.models.assunto_programa import AssuntoPrograma
from app.models.fila_ao_vivo import FilaAoVivo
from app.models.fonte_noticia import FonteNoticia
from app.models.geracao_ia import GeracaoIA
from app.models.interaction_log import InteractionLog
from app.models.musica_historico import MusicaHistorico
from app.models.noticia_historico import NoticiaHistorico
from app.models.programa import Programa
from app.models.programa_radialista import ProgramaRadialista
from app.models.radio_config import RadioConfig
from app.models.tema_historico import TemaHistorico
from app.news.seeds_fontes import criar_seeds_fontes
from app.billing.limites import limite_agentes_efetivo, limite_radialistas_por_programa
from app.tts.voices import voz_valida_para_conta

logger = logging.getLogger("radialista.config")

router = APIRouter(prefix="/config", tags=["config"])


class RadialistaRequest(BaseModel):
    nome_locutor: str
    personalidade: str = ""
    biografia: str = ""
    tracos_marcantes: list[str] = Field(default_factory=list)
    fatos_do_dia: list[str] = Field(default_factory=list)
    voz_id: str | None = None
    timezone: str = "America/Sao_Paulo"
    resposta_automatica_whatsapp: bool = False


class RadialistaResponse(RadialistaRequest):
    id: int
    ativo: bool

    model_config = {"from_attributes": True}


class ConhecimentoLocal(BaseModel):
    """Conhecimento local estruturado do lugar onde a rádio fica -- dado de configuração
    preenchido manualmente pelo dono da rádio, nunca gerado por IA/pesquisa (ver
    Account.conhecimento_local)."""

    bairros: list[str] = Field(default_factory=list)
    pontos_referencia: list[str] = Field(default_factory=list)
    eventos_recorrentes: list[str] = Field(default_factory=list)
    expressoes_regionais: list[str] = Field(default_factory=list)
    gentilico: str = ""


class BibliaRadio(BaseModel):
    """História, rotina real e grade da rádio -- dado de configuração preenchido manualmente
    pelo dono da rádio, nunca gerado por IA/pesquisa (ver Account.biblia_radio)."""

    historia: str = ""
    rotina: list[str] = Field(default_factory=list)
    programas_grade: list[str] = Field(default_factory=list)
    # Colegas que existem na rádio mas não estão ao vivo (técnico de som, comercial, outro
    # locutor da grade) -- diferente do roster (ParticipantePrograma), que é só quem apresenta.
    equipe: list[str] = Field(default_factory=list)
    # Pequenos hábitos operacionais reais ("confere trânsito antes de entrar no ar").
    habitos_trabalho: list[str] = Field(default_factory=list)


class RadioContaRequest(BaseModel):
    nome_radio: str = ""
    slogan: str = ""
    frequencia: str = ""
    telefone: str = ""
    endereco: str = ""
    cidade: str = ""
    tipo_radio: str = ""
    conhecimento_local: ConhecimentoLocal = Field(default_factory=ConhecimentoLocal)
    biblia_radio: BibliaRadio = Field(default_factory=BibliaRadio)


class RadioContaResponse(RadioContaRequest):
    wuzapi_token: str | None

    model_config = {"from_attributes": True}


class TipoRadioResponse(BaseModel):
    value: str
    label: str


class FeriadoMunicipal(BaseModel):
    data: str  # "MM-DD"
    nome: str


class ProgramaRequest(BaseModel):
    nome: str
    descricao: str = ""
    dias_semana: list[int] = Field(default_factory=list)
    data_especifica: datetime.date | None = None
    horario_inicio: datetime.time
    horario_fim: datetime.time
    ativo: bool = True

    tom: str
    topicos_permitidos: list[str] = Field(default_factory=list)
    topicos_proibidos: list[str] = Field(default_factory=list)
    mensagem_saudacao: str = ""
    mensagem_recusa: str = ""
    limite_mensagens_hora: int = 1000

    estrutura_blocos: list[str] = Field(default_factory=list)
    perfil_programacao: Literal["padrao", "musical_companhia"] = "padrao"
    ia_pode_adicionar_blocos: bool = True

    generos_musicais: list[str] = Field(default_factory=list)
    musicas_permitidas: list[str] = Field(default_factory=list)
    musicas_bloqueadas: list[str] = Field(default_factory=list)
    criterios_busca_musicas: str = ""
    musica_fundo_escolhida: str = ""

    assuntos_ao_vivo: list[str] = Field(default_factory=list)
    quadros_fixos: dict[str, list[str]] = Field(default_factory=dict)
    feriados_municipais: list[FeriadoMunicipal] = Field(default_factory=list)
    tipos_noticias: list[str] = Field(default_factory=list)
    fontes_noticias: list[str] = Field(default_factory=list)

    pode_pesquisar: bool = False
    fontes_pesquisa: list[str] = Field(default_factory=list)
    instrucoes_pesquisa: str = ""

    # Ver Fase 4/5 do plano de jornalismo (app.models.programa.Programa) -- preset de criacao e
    # dosagem de noticia, respectivamente. So preenchem campos/comportamento, o usuario continua
    # livre pra editar o resto do programa manualmente depois.
    perfil: Literal["musical", "jornalismo", "esportivo", "variedades", "religioso", "comunitario"] = "musical"
    dose_noticia: Literal["nenhuma", "pitada", "equilibrada", "jornalistica"] = "jornalistica"

    # Ver Fase A/H do plano-assuntos.md (app.models.programa.Programa) -- publico_alvo opcional
    # alimenta o matcher/reserva do banco de assuntos (deriva um briefing observado quando vazio,
    # ver app.topics.reserva); densidade_assunto regula quao informado o comentario livre deve
    # ser, mesmo espirito de dose_noticia.
    publico_alvo: str = ""
    densidade_assunto: Literal["leve", "equilibrada", "informado"] = "leve"


class ProgramaResponse(ProgramaRequest):
    id: int
    radio_config_id: int

    model_config = {"from_attributes": True}


class RadialistaProgramaRequest(BaseModel):
    papel: str = "Apresentador principal"
    comportamento: str = ""


class RadialistaProgramaResponse(BaseModel):
    radio_config_id: int
    nome_locutor: str
    voz_id: str | None
    papel: str
    comportamento: str
    e_dono: bool


class GerarConfiguracaoIARequest(BaseModel):
    descricao: str = ""


class ConfiguracaoIAResponse(BaseModel):
    radialista: RadialistaResponse
    programa: ProgramaResponse


class ConfiguracaoIAPreviewResponse(BaseModel):
    """Proposta de radialista+programa gerada via IA, ainda NAO gravada (ver Fase 2 do plano de
    melhoria) -- pra criar de verdade, revise/ajuste e poste em /config/radialistas e depois
    /config/radialistas/{id}/programas com o payload final."""

    radialista: RadialistaRequest
    programa: ProgramaRequest
    campos_corrigidos: list[str] = Field(default_factory=list)
    avisos: list[str] = Field(default_factory=list)
    # Id do registro em GeracaoIA (ver Fase 10 do plano de melhoria) -- devolva no
    # POST /gerar-ia/commit (campo geracao_id) pra fechar o loop de aprendizado.
    geracao_id: int | None = None


class ProgramaIAPreviewResponse(BaseModel):
    programa: ProgramaRequest
    campos_corrigidos: list[str] = Field(default_factory=list)
    avisos: list[str] = Field(default_factory=list)
    geracao_id: int | None = None


_DEFAULTS_CAMPOS_OBRIGATORIOS = {
    "nome": "Programa sem nome",
    "tom": "neutro",
    "horario_inicio": "08:00:00",
    "horario_fim": "09:00:00",
    "nome_locutor": "Locutor sem nome",
}


def _construir_com_defaults(modelo_cls: type[BaseModel], dados: dict) -> tuple[BaseModel, list[str]]:
    """Tenta validar `dados` contra `modelo_cls`; pra cada campo que falhar, aplica um default
    seguro (campo obrigatorio) ou remove a chave (campo opcional, cai no default do proprio
    schema) e tenta de novo -- em vez de derrubar a proposta inteira por causa de UM campo
    quebrado (ver Fase 6 do plano: proposta parcial em vez de 502-em-qualquer-coisa). Devolve o
    modelo ja valido + a lista dos campos que precisaram de correcao, pra marcar na revisao."""
    dados = dict(dados)
    corrigidos: list[str] = []
    while True:
        try:
            return modelo_cls(**dados), corrigidos
        except ValidationError as exc:
            algum_novo = False
            for erro in exc.errors():
                campo = str(erro["loc"][0]) if erro["loc"] else None
                if not campo or campo in corrigidos:
                    continue
                if campo in _DEFAULTS_CAMPOS_OBRIGATORIOS:
                    dados[campo] = _DEFAULTS_CAMPOS_OBRIGATORIOS[campo]
                else:
                    dados.pop(campo, None)
                corrigidos.append(campo)
                algum_novo = True
            if not algum_novo:
                raise


def _resumo_horario(programa: Programa) -> dict:
    """Horario + dias de um programa, resumidos pro contexto de geracao via IA -- sem isso a
    IA nao tem como propor um horario que nao colida com o que ja existe (ver
    _validar_conflito_horario), e a geracao acaba caindo em 409 na primeira tentativa quando o
    horario "obvio" pro pedido do usuario ja esta ocupado."""
    return {
        "horario_inicio": programa.horario_inicio.strftime("%H:%M"),
        "horario_fim": programa.horario_fim.strftime("%H:%M"),
        "dias_semana": programa.dias_semana or [],
    }


def _montar_roster_existente(db: Session, account: Account) -> list[dict]:
    """Radialistas + programas ja cadastrados na conta, resumidos pra dar contexto ao gerador
    de IA e evitar que ele crie algo quase identico ao que ja existe (ver app.llm.config_generator)."""
    linhas = (
        db.query(RadioConfig, Programa)
        .outerjoin(Programa, Programa.radio_config_id == RadioConfig.id)
        .filter(RadioConfig.account_id == account.id)
        .all()
    )
    roster: dict[int, dict] = {}
    for radialista, programa in linhas:
        entrada = roster.setdefault(
            radialista.id,
            {
                "nome_locutor": radialista.nome_locutor,
                "personalidade": radialista.personalidade,
                "voz_id": radialista.voz_id,
                "programas": [],
            },
        )
        if programa is not None:
            entrada["programas"].append({"nome": programa.nome, "tom": programa.tom, **_resumo_horario(programa)})
    return list(roster.values())


def _montar_programas_existentes(db: Session, account: Account, radialista: RadioConfig) -> list[dict]:
    """Todos os programas da CONTA (desse radialista e dos outros), resumidos pra dar contexto
    ao gerador de programa avulso via IA. Nome/genero repetido so importa pros programas do
    MESMO radialista, mas conflito de horario vale pra conta inteira -- so um programa toca por
    vez na frequencia, entao _validar_conflito_horario rejeita sobreposicao mesmo entre
    radialistas diferentes (ver app.llm.config_generator)."""
    linhas = (
        db.query(Programa, RadioConfig)
        .join(RadioConfig, Programa.radio_config_id == RadioConfig.id)
        .filter(RadioConfig.account_id == account.id)
        .all()
    )
    return [
        {
            "nome": p.nome,
            "tom": p.tom,
            "generos_musicais": p.generos_musicais,
            "mesmo_radialista": rc.id == radialista.id,
            **_resumo_horario(p),
        }
        for p, rc in linhas
    ]


def _buscar_radialista(db: Session, account: Account, radialista_id: int) -> RadioConfig:
    radialista = db.query(RadioConfig).filter_by(id=radialista_id, account_id=account.id).first()
    if radialista is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Radialista nao encontrado")
    return radialista


def _buscar_programa(db: Session, account: Account, programa_id: int) -> Programa:
    programa = (
        db.query(Programa)
        .join(RadioConfig, Programa.radio_config_id == RadioConfig.id)
        .filter(Programa.id == programa_id, RadioConfig.account_id == account.id)
        .first()
    )
    if programa is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Programa nao encontrado")
    return programa


def _validar_voz(db: Session, account: Account, voz_id: str | None) -> None:
    if voz_id is not None and not voz_valida_para_conta(db, account.id, voz_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Voz invalida")


def _ocorrencias_conflitam(a, b) -> bool:
    # a e b tem .dias_semana e .data_especifica (ProgramaRequest ou Programa).
    data_a = a.data_especifica
    data_b = b.data_especifica

    if data_a is not None and data_b is not None:
        return data_a == data_b
    if data_a is not None:
        return not b.dias_semana or data_a.weekday() in b.dias_semana
    if data_b is not None:
        return not a.dias_semana or data_b.weekday() in a.dias_semana

    # Ambos recorrentes. Lista vazia = todos os dias, entao sempre conflita com qualquer outra lista.
    if not a.dias_semana or not b.dias_semana:
        return True
    return bool(set(a.dias_semana) & set(b.dias_semana))


def _horarios_conflitam(inicio_a, fim_a, inicio_b, fim_b) -> bool:
    return inicio_a < fim_b and inicio_b < fim_a


def _conflitos_horario(
    db: Session,
    account_id: int,
    dados: "ProgramaRequest",
    programa_id: int | None = None,
) -> list[tuple[Programa, RadioConfig]]:
    """Lista (sem levantar excecao) os programas da conta que colidem em horario com `dados` --
    usado tanto por _validar_conflito_horario (que levanta 409 no primeiro) quanto pelos avisos
    de coerencia da tela de preview (ver Fase 5 do plano de melhoria), onde conflito e' reportado
    pro usuario decidir, nao motivo pra falhar a geracao inteira."""
    query = (
        db.query(Programa, RadioConfig)
        .join(RadioConfig, Programa.radio_config_id == RadioConfig.id)
        .filter(RadioConfig.account_id == account_id)
    )
    if programa_id is not None:
        query = query.filter(Programa.id != programa_id)
    return [
        (outro, radialista_outro)
        for outro, radialista_outro in query.all()
        if _ocorrencias_conflitam(dados, outro)
        and _horarios_conflitam(dados.horario_inicio, dados.horario_fim, outro.horario_inicio, outro.horario_fim)
    ]


def _validar_conflito_horario(
    db: Session,
    account_id: int,
    dados: "ProgramaRequest",
    programa_id: int | None = None,
) -> None:
    """So um radialista fica no ar por vez no WhatsApp da conta (app/whatsapp/webhook.py::
    _radialista_no_ar escolhe so um, mesmo se varios radialistas tiverem programa ativo no
    mesmo horario). Por isso o conflito e checado contra TODOS os programas da conta,
    nao so os do mesmo radialista.
    """
    conflitos = _conflitos_horario(db, account_id, dados, programa_id)
    if conflitos:
        outro, radialista_outro = conflitos[0]
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Horario conflita com o programa '{outro.nome}' de {radialista_outro.nome_locutor} "
                f"({outro.horario_inicio}-{outro.horario_fim})"
            ),
        )


_BLOCOS_MUSICA = {"musica"}
_BLOCOS_NOTICIA = {"noticia", "escalada", "giro", "servico", "plantao", "reporter"}


def _registrar_geracao(
    db: Session, account: Account, tipo: str, descricao: str, contexto_usado: dict, proposta: dict
) -> int:
    """Loop de aprendizado (ver Fase 10 do plano de melhoria): registra toda geracao/refinamento
    via IA -- o que foi proposto (e' comparado depois, se o cliente commitar, com o que ele de
    fato editou/aceitou em _marcar_geracao_aceita) pra apontar que campos a IA erra
    sistematicamente, e alimentar os exemplos de prompt (ver app.llm.exemplos_config) com
    configuracoes reais em vez de exemplos escritos a mao."""
    registro = GeracaoIA(
        account_id=account.id,
        tipo=tipo,
        descricao=descricao,
        contexto_usado=contexto_usado,
        proposta=proposta,
    )
    db.add(registro)
    db.commit()
    db.refresh(registro)
    return registro.id


def _marcar_geracao_aceita(db: Session, account: Account, geracao_id: int | None, proposta_final: dict) -> None:
    """Marca uma geracao (ver _registrar_geracao) como aceita/commitada, com o payload final que
    o cliente de fato confirmou -- no-op se geracao_id nao foi informado (fluxo antigo/direto)
    ou nao pertence a essa conta."""
    if geracao_id is None:
        return
    registro = db.query(GeracaoIA).filter_by(id=geracao_id, account_id=account.id).first()
    if registro is None:
        return
    registro.aceita = True
    registro.proposta_final = proposta_final
    db.commit()


def _avisos_coerencia(
    db: Session,
    account: Account,
    programa_dados: "ProgramaRequest",
    radialista_dados: "RadialistaRequest | None" = None,
    roster_existente: list[dict] | None = None,
) -> list[str]:
    """Avisos NAO bloqueantes sobre a proposta gerada via IA, pra destacar na tela de revisao
    do preview (ver Fase 5 do plano de melhoria). Ao contrario da sanitizacao/defaults (Fase 6),
    aqui o dado nao esta errado o bastante pra corrigir sozinho -- so' merece uma segunda olhada
    do cliente antes de confirmar."""
    avisos: list[str] = []

    for outro, radialista_outro in _conflitos_horario(db, account.id, programa_dados):
        avisos.append(
            f"Horário conflita com '{outro.nome}' de {radialista_outro.nome_locutor} "
            f"({outro.horario_inicio}-{outro.horario_fim})."
        )

    blocos = {b.strip().lower() for b in programa_dados.estrutura_blocos}
    if programa_dados.generos_musicais and not (blocos & _BLOCOS_MUSICA):
        avisos.append("Tem gêneros musicais definidos mas nenhum bloco de música na estrutura.")
    if programa_dados.tipos_noticias and not (blocos & _BLOCOS_NOTICIA):
        avisos.append(
            "Tem tipos de notícia definidos mas nenhum bloco de notícia/escalada/giro/serviço/"
            "plantão na estrutura."
        )

    if radialista_dados is not None and radialista_dados.voz_id:
        for radialista in roster_existente or []:
            if radialista.get("voz_id") == radialista_dados.voz_id:
                avisos.append(f"A voz escolhida já é usada por '{radialista.get('nome_locutor')}' nessa conta.")
                break

    return avisos


def _validar_limite_agentes(db: Session, account: Account) -> None:
    limite = limite_agentes_efetivo(account)
    total_atual = db.query(RadioConfig).filter_by(account_id=account.id).count()
    if total_atual >= limite:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=(
                f"Seu plano permite no maximo {limite} agente(s). "
                "Adicione um agente extra ou faca upgrade em /billing."
            ),
        )


def _validar_limite_radialistas_programa(db: Session, account: Account, programa: Programa) -> None:
    limite = limite_radialistas_por_programa(account)
    total_atual = 1 + (  # 1 = o dono, sempre conta
        db.query(ProgramaRadialista)
        .filter(
            ProgramaRadialista.programa_id == programa.id,
            ProgramaRadialista.radio_config_id != programa.radio_config_id,
        )
        .count()
    )
    if total_atual >= limite:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=(
                f"Seu plano permite no maximo {limite} radialista(s) por programa. "
                "Faca upgrade em /billing pra adicionar mais."
            ),
        )


def _resposta_vinculo_radialista(
    radialista: RadioConfig, vinculo: ProgramaRadialista | None, e_dono: bool
) -> RadialistaProgramaResponse:
    return RadialistaProgramaResponse(
        radio_config_id=radialista.id,
        nome_locutor=radialista.nome_locutor,
        voz_id=radialista.voz_id,
        papel=vinculo.papel if vinculo else "Apresentador principal",
        comportamento=vinculo.comportamento if vinculo else "",
        e_dono=e_dono,
    )


_CHAVE_LIMITE_GERACAO = "gerar_config_ia"
_LIMITE_GERACAO_IA = 5
_JANELA_LIMITE_GERACAO_IA = 3600


def _validar_limite_geracao_ia(account: Account) -> None:
    """So VERIFICA o limite, sem consumir cota -- chame antes de tentar a geracao. Cota so' e'
    de fato consumida em _registrar_geracao_ia, depois que o LLM responde com sucesso (ver Fase
    2/6 do plano de melhoria: uma tentativa que falha no LLM nao pode queimar cota do cliente)."""
    if limite_atingido(
        f"{_CHAVE_LIMITE_GERACAO}:{account.id}", limite=_LIMITE_GERACAO_IA, janela_segundos=_JANELA_LIMITE_GERACAO_IA
    ):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Limite de geracoes por IA atingido. Tenta de novo daqui a pouco.",
        )


def _registrar_geracao_ia(account: Account) -> None:
    """Consome uma unidade da cota de geracao via IA -- chame so depois que o LLM respondeu
    com sucesso (ver _validar_limite_geracao_ia)."""
    registrar_consumo(f"{_CHAVE_LIMITE_GERACAO}:{account.id}", janela_segundos=_JANELA_LIMITE_GERACAO_IA)


@router.get("/tipos-radio", response_model=list[TipoRadioResponse])
def listar_tipos_radio():
    return TIPOS_RADIO


@router.get("/radio", response_model=RadioContaResponse)
def obter_radio(account: Account = Depends(get_current_account)):
    return account


@router.put("/radio", response_model=RadioContaResponse)
def atualizar_radio(
    dados: RadioContaRequest,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    if dados.tipo_radio and not tipo_radio_valido(dados.tipo_radio):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tipo de radio invalido")
    for campo, valor in dados.model_dump().items():
        setattr(account, campo, valor)
    db.commit()
    db.refresh(account)
    return account


@router.get("/radialistas", response_model=list[RadialistaResponse])
def listar_radialistas(account: Account = Depends(get_current_account), db: Session = Depends(get_db)):
    return db.query(RadioConfig).filter_by(account_id=account.id).order_by(RadioConfig.id.asc()).all()


@router.post("/radialistas", response_model=RadialistaResponse, status_code=status.HTTP_201_CREATED)
def criar_radialista(
    dados: RadialistaRequest,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    _validar_voz(db, account, dados.voz_id)
    _validar_limite_agentes(db, account)
    radialista = RadioConfig(account_id=account.id, **dados.model_dump())
    db.add(radialista)
    db.commit()
    db.refresh(radialista)
    logger.info("Radialista criado: id=%s account_id=%s", radialista.id, account.id)
    return radialista


@router.post(
    "/radialistas/gerar-ia",
    response_model=ConfiguracaoIAResponse,
    status_code=status.HTTP_201_CREATED,
)
def gerar_radialista_ia(
    dados: GerarConfiguracaoIARequest,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    """Gera e cria um radialista + programa completos a partir do tipo de radio da conta
    e/ou de uma descricao livre, via LLM.

    Excecao: se a conta tem exatamente um radialista e ele ainda nao foi configurado (sem
    voz definida -- e' o placeholder criado automaticamente no cadastro), a geracao PREENCHE
    esse radialista e seu programa em vez de criar um novo. Sem isso, toda conta nova no plano
    de entrada (1 agente) bateria o limite de agentes na primeira geracao, ja' que o placeholder
    do cadastro conta como o unico agente disponivel."""
    if not account.tipo_radio and not dados.descricao.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Escolha um tipo de radio ou descreva o programa",
        )

    # falha rapido, sem gastar LLM nem cota de geracao, se o plano ja esta no limite de agentes
    # e a conta nao tem placeholder pra reaproveitar (_commitar_radialista_gerado confere de
    # novo depois -- essa checagem aqui e' so' pra nao desperdicar a chamada).
    radialistas_da_conta = db.query(RadioConfig).filter_by(account_id=account.id).all()
    tem_placeholder = len(radialistas_da_conta) == 1 and radialistas_da_conta[0].voz_id is None
    if not tem_placeholder:
        _validar_limite_agentes(db, account)
    _validar_limite_geracao_ia(account)

    # roster inclui o proprio placeholder quando ele existe, mas _linha_roster_existente (no
    # gerador) ja descarta entradas sem personalidade e sem programas, entao ele nao polui o
    # contexto -- so os radialistas/programas ja configurados de verdade entram no prompt.
    roster_existente = _montar_roster_existente(db, account)

    try:
        dados_radialista, dados_programa = gerar_configuracao_ia(
            dados.descricao, account.tipo_radio, account, roster_existente
        )
    except ValueError:
        logger.exception("Falha ao gerar radialista+programa via IA: account_id=%s", account.id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Nao foi possivel gerar a configuracao agora. Tenta de novo em instantes.",
        )
    _registrar_geracao_ia(account)  # LLM respondeu -- so agora a tentativa consome cota

    try:
        radialista_dados = RadialistaRequest(**dados_radialista)
        programa_dados = ProgramaRequest(**dados_programa)
    except ValidationError as exc:
        try:
            dados_radialista, dados_programa = reparar_configuracao_ia(
                account.tipo_radio, account, roster_existente, dados_radialista, dados_programa, exc.errors()
            )
            radialista_dados = RadialistaRequest(**dados_radialista)
            programa_dados = ProgramaRequest(**dados_programa)
        except (ValueError, ValidationError):
            logger.exception("Reparo de radialista+programa tambem falhou: account_id=%s", account.id)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Nao foi possivel gerar a configuracao agora. Tenta de novo em instantes.",
            )

    return _commitar_radialista_gerado(db, account, radialista_dados, programa_dados)


def _commitar_radialista_gerado(
    db: Session, account: Account, radialista_dados: "RadialistaRequest", programa_dados: "ProgramaRequest"
) -> "ConfiguracaoIAResponse":
    """Grava radialista+programa (ja validados) no banco -- usado tanto pelo endpoint atomico
    gerar_radialista_ia (gera e grava numa tacada so) quanto por commitar_radialista_ia_gerado
    (grava a proposta que o cliente revisou/ajustou na tela de preview, ver Fase 2 do plano).

    Excecao: se a conta tem exatamente um radialista sem voz definida (placeholder do
    cadastro), PREENCHE esse radialista/programa em vez de criar um novo -- sem isso toda conta
    nova (1 agente) bateria o limite de agentes nessa primeira geracao."""
    _validar_voz(db, account, radialista_dados.voz_id)

    radialistas_da_conta = db.query(RadioConfig).filter_by(account_id=account.id).all()
    radialista_placeholder = (
        radialistas_da_conta[0]
        if len(radialistas_da_conta) == 1 and radialistas_da_conta[0].voz_id is None
        else None
    )
    if radialista_placeholder is None:
        _validar_limite_agentes(db, account)

    if radialista_placeholder is not None:
        radialista = radialista_placeholder
        for campo, valor in radialista_dados.model_dump().items():
            setattr(radialista, campo, valor)
        db.flush()

        programa_existente = (
            db.query(Programa).filter_by(radio_config_id=radialista.id).order_by(Programa.id).first()
        )
        _validar_conflito_horario(
            db, account.id, programa_dados, programa_id=programa_existente.id if programa_existente else None
        )
        if programa_existente is not None:
            for campo, valor in programa_dados.model_dump().items():
                setattr(programa_existente, campo, valor)
            programa = programa_existente
        else:
            programa = Programa(radio_config_id=radialista.id, **programa_dados.model_dump())
            db.add(programa)
    else:
        radialista = RadioConfig(account_id=account.id, **radialista_dados.model_dump())
        db.add(radialista)
        db.flush()

        _validar_conflito_horario(db, account.id, programa_dados)
        programa = Programa(radio_config_id=radialista.id, **programa_dados.model_dump())
        db.add(programa)

    db.commit()
    db.refresh(radialista)
    db.refresh(programa)

    logger.info(
        "Radialista+programa gravados: radialista_id=%s programa_id=%s account_id=%s reaproveitado=%s",
        radialista.id,
        programa.id,
        account.id,
        radialista_placeholder is not None,
    )
    return ConfiguracaoIAResponse(radialista=radialista, programa=programa)


@router.post("/radialistas/gerar-ia/preview", response_model=ConfiguracaoIAPreviewResponse)
def gerar_radialista_ia_preview(
    dados: GerarConfiguracaoIARequest,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    """Gera radialista+programa via IA SEM gravar nada no banco e SEM consumir slot de agente
    do plano (ver Fase 2 do plano de melhoria) -- so depois de revisar/ajustar a proposta e'
    que o cliente commita via POST /config/radialistas + POST .../{id}/programas. Uma geracao
    ruim aqui nao vira lixo no banco nem queima o slot pago de agente.

    Campo com erro de validacao vira default marcado em campos_corrigidos em vez de derrubar a
    proposta inteira (ver Fase 6) -- so' depois de uma tentativa de reparo via LLM falhar."""
    if not account.tipo_radio and not dados.descricao.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Escolha um tipo de radio ou descreva o programa",
        )

    _validar_limite_geracao_ia(account)
    roster_existente = _montar_roster_existente(db, account)

    try:
        dados_radialista, dados_programa = gerar_configuracao_ia(
            dados.descricao, account.tipo_radio, account, roster_existente
        )
    except ValueError:
        logger.exception("Falha ao gerar preview de radialista+programa via IA: account_id=%s", account.id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Nao foi possivel gerar a configuracao agora. Tenta de novo em instantes.",
        )
    _registrar_geracao_ia(account)

    try:
        radialista_dados = RadialistaRequest(**dados_radialista)
        programa_dados = ProgramaRequest(**dados_programa)
        campos_corrigidos: list[str] = []
    except ValidationError as exc:
        try:
            dados_radialista, dados_programa = reparar_configuracao_ia(
                account.tipo_radio, account, roster_existente, dados_radialista, dados_programa, exc.errors()
            )
        except ValueError:
            logger.warning("Reparo de preview radialista+programa falhou -- caindo pra defaults", exc_info=True)
        radialista_dados, corrigidos_r = _construir_com_defaults(RadialistaRequest, dados_radialista)
        programa_dados, corrigidos_p = _construir_com_defaults(ProgramaRequest, dados_programa)
        campos_corrigidos = corrigidos_r + corrigidos_p

    avisos = _avisos_coerencia(db, account, programa_dados, radialista_dados, roster_existente)
    geracao_id = _registrar_geracao(
        db,
        account,
        "radialista",
        dados.descricao,
        {"tipo_radio": account.tipo_radio, "qtd_radialistas_existentes": len(roster_existente)},
        {
            "radialista": radialista_dados.model_dump(mode="json"),
            "programa": programa_dados.model_dump(mode="json"),
        },
    )
    return ConfiguracaoIAPreviewResponse(
        radialista=radialista_dados,
        programa=programa_dados,
        campos_corrigidos=campos_corrigidos,
        avisos=avisos,
        geracao_id=geracao_id,
    )


class ConfiguracaoIACommitRequest(BaseModel):
    radialista: RadialistaRequest
    programa: ProgramaRequest
    # Id devolvido pelo preview (ver ConfiguracaoIAPreviewResponse.geracao_id) -- opcional, fecha
    # o loop de aprendizado (Fase 10) marcando a geracao como aceita com o payload final.
    geracao_id: int | None = None


@router.post(
    "/radialistas/gerar-ia/commit",
    response_model=ConfiguracaoIAResponse,
    status_code=status.HTTP_201_CREATED,
)
def commitar_radialista_ia(
    dados: ConfiguracaoIACommitRequest,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    """Grava o radialista+programa que o cliente revisou/ajustou depois de um POST em
    /radialistas/gerar-ia/preview (ver Fase 2 do plano de melhoria) -- sem chamar o LLM de novo,
    so aplica a mesma logica de reaproveitamento de placeholder e limite de agentes do endpoint
    atomico gerar_radialista_ia."""
    resultado = _commitar_radialista_gerado(db, account, dados.radialista, dados.programa)
    _marcar_geracao_aceita(
        db,
        account,
        dados.geracao_id,
        {
            "radialista": resultado.radialista.model_dump(mode="json"),
            "programa": resultado.programa.model_dump(mode="json"),
        },
    )
    return resultado


class RefinarConfiguracaoIARequest(BaseModel):
    """Corpo do refinamento parcial da tela de revisao (ver Fase 7 do plano de melhoria):
    escopo='persona' regenera so' nome/personalidade/voz mantendo o programa; escopo='programa'
    regenera so' o programa mantendo a persona; escopo='ajuste' aplica `instrucao` (texto livre)
    em cima do par atual. `radialista`/`programa` sao sempre o estado ATUAL da tela de revisao
    (ja pode ter sido editado a mao), nunca a proposta original."""

    descricao: str = ""
    escopo: Literal["persona", "programa", "ajuste"]
    instrucao: str = ""
    radialista: RadialistaRequest
    programa: ProgramaRequest


@router.post("/radialistas/gerar-ia/refinar", response_model=ConfiguracaoIAPreviewResponse)
def refinar_radialista_ia_preview(
    dados: RefinarConfiguracaoIARequest,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    """Refinamento parcial da proposta ainda em revisao (ver Fase 7) -- mais barato e preciso
    que "gerar tudo de novo": troca so' a persona, so' o programa, ou aplica um ajuste em texto
    livre sobre o que ja esta na tela. Nada e' gravado aqui (mesma garantia do preview)."""
    _validar_limite_geracao_ia(account)
    roster_existente = _montar_roster_existente(db, account)

    try:
        if dados.escopo == "persona":
            dados_radialista = gerar_persona_ia(dados.descricao, account.tipo_radio, account, roster_existente)
            dados_programa = dados.programa.model_dump(mode="json")
        elif dados.escopo == "programa":
            programas_existentes = programas_existentes_do_roster(roster_existente)
            dados_radialista = dados.radialista.model_dump(mode="json")
            dados_programa = gerar_programa_ia(
                dados.descricao,
                dados.radialista.nome_locutor,
                dados.radialista.personalidade,
                account.tipo_radio,
                account,
                dados.radialista.voz_id,
                programas_existentes,
            )
        else:
            dados_radialista, dados_programa = ajustar_configuracao_ia(
                dados.instrucao,
                dados.radialista.model_dump(mode="json"),
                dados.programa.model_dump(mode="json"),
                account.tipo_radio,
                account,
            )
    except ValueError:
        logger.exception("Falha ao refinar radialista+programa via IA: account_id=%s escopo=%s", account.id, dados.escopo)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Nao foi possivel gerar a configuracao agora. Tenta de novo em instantes.",
        )
    _registrar_geracao_ia(account)

    try:
        radialista_dados = RadialistaRequest(**dados_radialista)
        programa_dados = ProgramaRequest(**dados_programa)
        campos_corrigidos: list[str] = []
    except ValidationError as exc:
        try:
            dados_radialista, dados_programa = reparar_configuracao_ia(
                account.tipo_radio, account, roster_existente, dados_radialista, dados_programa, exc.errors()
            )
            radialista_dados = RadialistaRequest(**dados_radialista)
            programa_dados = ProgramaRequest(**dados_programa)
        except (ValueError, ValidationError):
            logger.warning("Reparo de refinamento falhou -- caindo pra defaults", exc_info=True)
        radialista_dados, corrigidos_r = _construir_com_defaults(RadialistaRequest, dados_radialista)
        programa_dados, corrigidos_p = _construir_com_defaults(ProgramaRequest, dados_programa)
        campos_corrigidos = corrigidos_r + corrigidos_p

    avisos = _avisos_coerencia(db, account, programa_dados, radialista_dados, roster_existente)
    geracao_id = _registrar_geracao(
        db,
        account,
        "refinamento",
        dados.instrucao or dados.descricao,
        {"escopo": dados.escopo},
        {
            "radialista": radialista_dados.model_dump(mode="json"),
            "programa": programa_dados.model_dump(mode="json"),
        },
    )
    return ConfiguracaoIAPreviewResponse(
        radialista=radialista_dados,
        programa=programa_dados,
        campos_corrigidos=campos_corrigidos,
        avisos=avisos,
        geracao_id=geracao_id,
    )


@router.get("/radialistas/{radialista_id}", response_model=RadialistaResponse)
def obter_radialista(
    radialista_id: int,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    return _buscar_radialista(db, account, radialista_id)


@router.put("/radialistas/{radialista_id}", response_model=RadialistaResponse)
def atualizar_radialista(
    radialista_id: int,
    dados: RadialistaRequest,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    _validar_voz(db, account, dados.voz_id)
    radialista = _buscar_radialista(db, account, radialista_id)
    for campo, valor in dados.model_dump().items():
        setattr(radialista, campo, valor)
    db.commit()
    db.refresh(radialista)
    return radialista


@router.delete("/radialistas/{radialista_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir_radialista(
    radialista_id: int,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    radialista = _buscar_radialista(db, account, radialista_id)
    programas_do_radialista = [p.id for p in db.query(Programa.id).filter_by(radio_config_id=radialista.id).all()]
    # remove vinculos onde ele participa como co-apresentador em programas de outros
    # radialistas, e os vinculos dos programas dele que estao pra ser excluidos.
    db.query(ProgramaRadialista).filter_by(radio_config_id=radialista.id).delete()
    if programas_do_radialista:
        db.query(ProgramaRadialista).filter(ProgramaRadialista.programa_id.in_(programas_do_radialista)).delete(
            synchronize_session=False
        )
    from app.models.mensagem_ouvinte import MensagemOuvinte
    db.query(MensagemOuvinte).filter_by(radio_config_id=radialista.id).delete()
    db.query(InteractionLog).filter_by(radio_config_id=radialista.id).delete()
    db.query(FilaAoVivo).filter_by(radio_config_id=radialista.id).delete()
    if programas_do_radialista:
        db.query(MusicaHistorico).filter(MusicaHistorico.programa_id.in_(programas_do_radialista)).delete(
            synchronize_session=False
        )
        db.query(TemaHistorico).filter(TemaHistorico.programa_id.in_(programas_do_radialista)).delete(
            synchronize_session=False
        )
    db.query(Programa).filter_by(radio_config_id=radialista.id).delete()
    db.delete(radialista)
    db.commit()
    logger.info("Radialista excluido: id=%s account_id=%s", radialista_id, account.id)


@router.get("/radialistas/{radialista_id}/programas", response_model=list[ProgramaResponse])
def listar_programas(
    radialista_id: int,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    radialista = _buscar_radialista(db, account, radialista_id)
    return (
        db.query(Programa)
        .filter_by(radio_config_id=radialista.id)
        .order_by(Programa.horario_inicio.asc())
        .all()
    )


@router.post(
    "/radialistas/{radialista_id}/programas",
    response_model=ProgramaResponse,
    status_code=status.HTTP_201_CREATED,
)
def criar_programa(
    radialista_id: int,
    dados: ProgramaRequest,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    radialista = _buscar_radialista(db, account, radialista_id)
    _validar_conflito_horario(db, account.id, dados)
    programa = Programa(radio_config_id=radialista.id, **dados.model_dump())
    db.add(programa)
    db.commit()
    db.refresh(programa)
    logger.info("Programa criado: id=%s radialista_id=%s", programa.id, radialista.id)
    return programa


@router.post(
    "/radialistas/{radialista_id}/programas/gerar-ia",
    response_model=ProgramaResponse,
    status_code=status.HTTP_201_CREATED,
)
def gerar_programa_ia_endpoint(
    radialista_id: int,
    dados: GerarConfiguracaoIARequest,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    """Gera e cria um programa completo pra um radialista ja existente, a partir do tipo de
    radio da conta e/ou de uma descricao livre, via LLM."""
    if not account.tipo_radio and not dados.descricao.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Escolha um tipo de radio ou descreva o programa",
        )
    radialista = _buscar_radialista(db, account, radialista_id)
    _validar_limite_geracao_ia(account)

    programas_existentes = _montar_programas_existentes(db, account, radialista)

    try:
        dados_programa = gerar_programa_ia(
            dados.descricao,
            radialista.nome_locutor,
            radialista.personalidade,
            account.tipo_radio,
            account,
            radialista.voz_id,
            programas_existentes,
        )
    except ValueError:
        logger.exception("Falha ao gerar programa via IA: radialista_id=%s", radialista_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Nao foi possivel gerar a configuracao agora. Tenta de novo em instantes.",
        )
    _registrar_geracao_ia(account)

    try:
        programa_dados = ProgramaRequest(**dados_programa)
    except ValidationError as exc:
        try:
            dados_programa = reparar_programa_ia(
                radialista.nome_locutor,
                radialista.personalidade,
                account.tipo_radio,
                account,
                radialista.voz_id,
                programas_existentes,
                dados_programa,
                exc.errors(),
            )
            programa_dados = ProgramaRequest(**dados_programa)
        except (ValueError, ValidationError):
            logger.exception("Reparo de programa via IA tambem falhou: radialista_id=%s", radialista_id)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Nao foi possivel gerar a configuracao agora. Tenta de novo em instantes.",
            )

    _validar_conflito_horario(db, account.id, programa_dados)
    programa = Programa(radio_config_id=radialista.id, **programa_dados.model_dump())
    db.add(programa)
    db.commit()
    db.refresh(programa)
    logger.info("Programa gerado via IA: id=%s radialista_id=%s", programa.id, radialista.id)
    return programa


@router.post(
    "/radialistas/{radialista_id}/programas/gerar-ia/preview",
    response_model=ProgramaIAPreviewResponse,
)
def gerar_programa_ia_preview(
    radialista_id: int,
    dados: GerarConfiguracaoIARequest,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    """Como gerar_radialista_ia_preview, mas pra um programa novo de um radialista ja existente
    -- gera SEM gravar, quem chama commita via POST /config/radialistas/{id}/programas depois
    de revisar (ver Fase 2 do plano de melhoria)."""
    if not account.tipo_radio and not dados.descricao.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Escolha um tipo de radio ou descreva o programa",
        )
    radialista = _buscar_radialista(db, account, radialista_id)
    _validar_limite_geracao_ia(account)

    programas_existentes = _montar_programas_existentes(db, account, radialista)

    try:
        dados_programa = gerar_programa_ia(
            dados.descricao,
            radialista.nome_locutor,
            radialista.personalidade,
            account.tipo_radio,
            account,
            radialista.voz_id,
            programas_existentes,
        )
    except ValueError:
        logger.exception("Falha ao gerar preview de programa via IA: radialista_id=%s", radialista_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Nao foi possivel gerar a configuracao agora. Tenta de novo em instantes.",
        )
    _registrar_geracao_ia(account)

    try:
        programa_dados = ProgramaRequest(**dados_programa)
        campos_corrigidos: list[str] = []
    except ValidationError as exc:
        try:
            dados_programa = reparar_programa_ia(
                radialista.nome_locutor,
                radialista.personalidade,
                account.tipo_radio,
                account,
                radialista.voz_id,
                programas_existentes,
                dados_programa,
                exc.errors(),
            )
        except ValueError:
            logger.warning("Reparo de preview de programa falhou -- caindo pra defaults", exc_info=True)
        programa_dados, campos_corrigidos = _construir_com_defaults(ProgramaRequest, dados_programa)

    avisos = _avisos_coerencia(db, account, programa_dados)
    geracao_id = _registrar_geracao(
        db,
        account,
        "programa",
        dados.descricao,
        {"tipo_radio": account.tipo_radio, "radialista_id": radialista_id},
        {"programa": programa_dados.model_dump(mode="json")},
    )
    return ProgramaIAPreviewResponse(
        programa=programa_dados, campos_corrigidos=campos_corrigidos, avisos=avisos, geracao_id=geracao_id
    )


class AjustarProgramaIARequest(BaseModel):
    instrucao: str
    programa: ProgramaRequest


@router.post("/programas/gerar-ia/ajustar", response_model=ProgramaIAPreviewResponse)
def ajustar_programa_ia_preview(
    dados: AjustarProgramaIARequest,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    """Aplica um ajuste em texto livre (ex.: "mais serio", "tira o bloco de noticia") sobre um
    programa que ja esta na tela (gerado por IA ou nao, novo ou ja existente -- ver Fase 7 do
    plano de melhoria). Nao grava nada; quem chama salva via POST/PUT normal depois."""
    if not dados.instrucao.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Descreva o ajuste que voce quer")

    _validar_limite_geracao_ia(account)
    try:
        dados_programa = ajustar_programa_ia(
            dados.instrucao, dados.programa.model_dump(mode="json"), account.tipo_radio, account
        )
    except ValueError:
        logger.exception("Falha ao ajustar programa via IA: account_id=%s", account.id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Nao foi possivel aplicar o ajuste agora. Tenta de novo em instantes.",
        )
    _registrar_geracao_ia(account)

    try:
        programa_dados = ProgramaRequest(**dados_programa)
        campos_corrigidos: list[str] = []
    except ValidationError:
        logger.warning("Ajuste de programa devolveu campo invalido -- caindo pra defaults", exc_info=True)
        programa_dados, campos_corrigidos = _construir_com_defaults(ProgramaRequest, dados_programa)

    avisos = _avisos_coerencia(db, account, programa_dados)
    geracao_id = _registrar_geracao(
        db,
        account,
        "refinamento",
        dados.instrucao,
        {"escopo": "ajuste"},
        {"programa": programa_dados.model_dump(mode="json")},
    )
    return ProgramaIAPreviewResponse(
        programa=programa_dados, campos_corrigidos=campos_corrigidos, avisos=avisos, geracao_id=geracao_id
    )


@router.get("/programas/{programa_id}", response_model=ProgramaResponse)
def obter_programa(
    programa_id: int,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    return _buscar_programa(db, account, programa_id)


@router.put("/programas/{programa_id}", response_model=ProgramaResponse)
def atualizar_programa(
    programa_id: int,
    dados: ProgramaRequest,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    programa = _buscar_programa(db, account, programa_id)
    _validar_conflito_horario(db, account.id, dados, programa_id=programa.id)
    for campo, valor in dados.model_dump().items():
        setattr(programa, campo, valor)
    db.commit()
    db.refresh(programa)
    return programa


@router.delete("/programas/{programa_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir_programa(
    programa_id: int,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    programa = _buscar_programa(db, account, programa_id)
    from app.models.mensagem_ouvinte import MensagemOuvinte
    from app.whatsapp.atendimento import registrar_evento
    for pedido in db.query(FilaAoVivo).filter_by(programa_id=programa.id).all():
        if pedido.estado in ("recebido", "em_fila", "aguardando_revisao", "selecionado"):
            pedido.estado = "nao_atendido"
            pedido.motivo = "Programa excluído"
            pedido.selecao_token = None
        registrar_evento(pedido, "programa_excluido", programa_anterior=programa.id)
        pedido.programa_id = None
    db.query(MensagemOuvinte).filter_by(programa_id=programa.id, estado="pendente").update({"estado": "expirada"})
    db.query(MensagemOuvinte).filter_by(programa_id=programa.id).update({"programa_id": None})
    db.flush()
    db.query(ProgramaRadialista).filter_by(programa_id=programa.id).delete()
    db.query(MusicaHistorico).filter_by(programa_id=programa.id).delete()
    db.query(TemaHistorico).filter_by(programa_id=programa.id).delete()
    # FK pra programas.id sem ON DELETE CASCADE (ver app.models.noticia_historico/
    # assunto_programa) -- sem isso o DELETE de baixo estoura ForeignKeyViolation em qualquer
    # programa que ja' tenha historico de noticia ou assunto casado (achado testando o fluxo
    # ao vivo do banco de assuntos, ver plano-assuntos.md).
    db.query(NoticiaHistorico).filter_by(programa_id=programa.id).delete()
    db.query(AssuntoPrograma).filter_by(programa_id=programa.id).delete()
    db.delete(programa)
    db.commit()
    logger.info("Programa excluido: id=%s account_id=%s", programa_id, account.id)


@router.get("/programas/{programa_id}/radialistas", response_model=list[RadialistaProgramaResponse])
def listar_radialistas_programa(
    programa_id: int,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    """Roster completo do programa (dono + co-apresentadores) pro dialogo multi-voz do ao vivo."""
    programa = _buscar_programa(db, account, programa_id)
    dono = _buscar_radialista(db, account, programa.radio_config_id)
    vinculos = (
        db.query(ProgramaRadialista)
        .filter_by(programa_id=programa.id)
        .order_by(ProgramaRadialista.ordem.asc(), ProgramaRadialista.id.asc())
        .all()
    )
    vinculo_dono = next((v for v in vinculos if v.radio_config_id == dono.id), None)

    resultado = [_resposta_vinculo_radialista(dono, vinculo_dono, True)]
    for vinculo in vinculos:
        if vinculo.radio_config_id == dono.id:
            continue
        co_apresentador = _buscar_radialista(db, account, vinculo.radio_config_id)
        resultado.append(_resposta_vinculo_radialista(co_apresentador, vinculo, False))
    return resultado


@router.put("/programas/{programa_id}/radialistas/{radio_config_id}", response_model=RadialistaProgramaResponse)
def definir_radialista_programa(
    programa_id: int,
    radio_config_id: int,
    dados: RadialistaProgramaRequest,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    """Cria ou atualiza o papel/comportamento de um radialista dentro do programa.

    Funciona tanto pro dono (customiza papel/comportamento dele) quanto pra
    co-apresentadores novos -- so estes ultimos contam pro limite do plano.
    """
    programa = _buscar_programa(db, account, programa_id)
    radialista = _buscar_radialista(db, account, radio_config_id)
    e_dono = radialista.id == programa.radio_config_id

    vinculo = (
        db.query(ProgramaRadialista)
        .filter_by(programa_id=programa.id, radio_config_id=radialista.id)
        .first()
    )
    if vinculo is None:
        if not e_dono:
            if not radialista.ativo:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Radialista inativo")
            _validar_limite_radialistas_programa(db, account, programa)
        vinculo = ProgramaRadialista(programa_id=programa.id, radio_config_id=radialista.id)
        db.add(vinculo)

    vinculo.papel = dados.papel
    vinculo.comportamento = dados.comportamento
    db.commit()
    db.refresh(vinculo)
    return _resposta_vinculo_radialista(radialista, vinculo, e_dono)


@router.delete("/programas/{programa_id}/radialistas/{radio_config_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover_radialista_programa(
    programa_id: int,
    radio_config_id: int,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    programa = _buscar_programa(db, account, programa_id)
    if radio_config_id == programa.radio_config_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nao e possivel remover o radialista dono do programa",
        )
    vinculo = (
        db.query(ProgramaRadialista).filter_by(programa_id=programa.id, radio_config_id=radio_config_id).first()
    )
    if vinculo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vinculo nao encontrado")
    db.delete(vinculo)
    db.commit()


class FonteNoticiaRequest(BaseModel):
    nome: str
    url_feed: str = ""
    tipo: Literal["oficial", "imprensa", "assessoria"] = "imprensa"
    peso: float = 1.0
    ativa: bool = True


class FonteNoticiaResponse(FonteNoticiaRequest):
    id: int

    model_config = {"from_attributes": True}


def _buscar_fonte_noticia(db: Session, account: Account, fonte_id: int) -> FonteNoticia:
    fonte = db.query(FonteNoticia).filter_by(id=fonte_id, account_id=account.id).first()
    if fonte is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fonte de notícia não encontrada")
    return fonte


@router.get("/fontes-noticia", response_model=list[FonteNoticiaResponse])
def listar_fontes_noticia(account: Account = Depends(get_current_account), db: Session = Depends(get_db)):
    return db.query(FonteNoticia).filter_by(account_id=account.id).order_by(FonteNoticia.id.asc()).all()


@router.post("/fontes-noticia", response_model=FonteNoticiaResponse, status_code=status.HTTP_201_CREATED)
def criar_fonte_noticia(
    dados: FonteNoticiaRequest,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    fonte = FonteNoticia(account_id=account.id, **dados.model_dump())
    db.add(fonte)
    db.commit()
    db.refresh(fonte)
    logger.info("Fonte de notícia criada: id=%s account_id=%s", fonte.id, account.id)
    return fonte


@router.post(
    "/fontes-noticia/seeds",
    response_model=list[FonteNoticiaResponse],
    status_code=status.HTTP_201_CREATED,
)
def criar_fontes_noticia_seed(account: Account = Depends(get_current_account), db: Session = Depends(get_db)):
    """Cria o conjunto padrão de fontes oficiais a partir da cidade da conta (ver
    app.news.seeds_fontes) -- nasce sem URL de feed, cabe à rádio completar antes de entrar na
    coleta do worker (ver app.news.worker)."""
    return criar_seeds_fontes(db, account)


@router.put("/fontes-noticia/{fonte_id}", response_model=FonteNoticiaResponse)
def atualizar_fonte_noticia(
    fonte_id: int,
    dados: FonteNoticiaRequest,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    fonte = _buscar_fonte_noticia(db, account, fonte_id)
    for campo, valor in dados.model_dump().items():
        setattr(fonte, campo, valor)
    db.commit()
    db.refresh(fonte)
    return fonte


@router.delete("/fontes-noticia/{fonte_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir_fonte_noticia(
    fonte_id: int,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    fonte = _buscar_fonte_noticia(db, account, fonte_id)
    db.delete(fonte)
    db.commit()
