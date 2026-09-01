import datetime
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_account
from app.db.database import get_db
from app.guardrails.http_rate_limit import limite_excedido
from app.llm.config_generator import gerar_configuracao_ia, gerar_programa_ia
from app.llm.tipos_radio import TIPOS_RADIO, tipo_radio_valido
from app.models.account import Account
from app.models.fila_ao_vivo import FilaAoVivo
from app.models.interaction_log import InteractionLog
from app.models.programa import Programa
from app.models.programa_radialista import ProgramaRadialista
from app.models.radio_config import RadioConfig
from app.billing.limites import limite_agentes_efetivo, limite_radialistas_por_programa
from app.tts.voices import voz_valida_para_conta

logger = logging.getLogger("radialista.config")

router = APIRouter(prefix="/config", tags=["config"])


class RadialistaRequest(BaseModel):
    nome_locutor: str
    personalidade: str = ""
    voz_id: str | None = None
    timezone: str = "America/Sao_Paulo"


class RadialistaResponse(RadialistaRequest):
    id: int
    ativo: bool

    model_config = {"from_attributes": True}


class RadioContaRequest(BaseModel):
    nome_radio: str = ""
    slogan: str = ""
    frequencia: str = ""
    telefone: str = ""
    endereco: str = ""
    cidade: str = ""
    tipo_radio: str = ""


class RadioContaResponse(RadioContaRequest):
    wuzapi_token: str | None

    model_config = {"from_attributes": True}


class TipoRadioResponse(BaseModel):
    value: str
    label: str


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
    ia_pode_adicionar_blocos: bool = True

    generos_musicais: list[str] = Field(default_factory=list)
    musicas_permitidas: list[str] = Field(default_factory=list)
    musicas_bloqueadas: list[str] = Field(default_factory=list)
    criterios_busca_musicas: str = ""

    assuntos_ao_vivo: list[str] = Field(default_factory=list)
    tipos_noticias: list[str] = Field(default_factory=list)
    fontes_noticias: list[str] = Field(default_factory=list)

    pode_pesquisar: bool = False
    fontes_pesquisa: list[str] = Field(default_factory=list)
    instrucoes_pesquisa: str = ""


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
    query = (
        db.query(Programa, RadioConfig)
        .join(RadioConfig, Programa.radio_config_id == RadioConfig.id)
        .filter(RadioConfig.account_id == account_id)
    )
    if programa_id is not None:
        query = query.filter(Programa.id != programa_id)
    for outro, radialista_outro in query.all():
        if _ocorrencias_conflitam(dados, outro) and _horarios_conflitam(
            dados.horario_inicio, dados.horario_fim, outro.horario_inicio, outro.horario_fim
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Horario conflita com o programa '{outro.nome}' de {radialista_outro.nome_locutor} "
                    f"({outro.horario_inicio}-{outro.horario_fim})"
                ),
            )


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


def _validar_limite_geracao_ia(account: Account) -> None:
    if limite_excedido(f"gerar_config_ia:{account.id}", limite=5, janela_segundos=3600):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Limite de geracoes por IA atingido. Tenta de novo daqui a pouco.",
        )


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

    radialistas_da_conta = db.query(RadioConfig).filter_by(account_id=account.id).all()
    radialista_placeholder = (
        radialistas_da_conta[0]
        if len(radialistas_da_conta) == 1 and radialistas_da_conta[0].voz_id is None
        else None
    )

    if radialista_placeholder is None:
        _validar_limite_agentes(db, account)
    _validar_limite_geracao_ia(account)

    try:
        dados_radialista, dados_programa = gerar_configuracao_ia(dados.descricao, account.tipo_radio)
        radialista_dados = RadialistaRequest(**dados_radialista)
        programa_dados = ProgramaRequest(**dados_programa)
    except (ValueError, ValidationError):
        logger.exception("Falha ao gerar radialista+programa via IA: account_id=%s", account.id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Nao foi possivel gerar a configuracao agora. Tenta de novo em instantes.",
        )

    _validar_voz(db, account, radialista_dados.voz_id)

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
        "Radialista+programa gerados via IA: radialista_id=%s programa_id=%s account_id=%s reaproveitado=%s",
        radialista.id,
        programa.id,
        account.id,
        radialista_placeholder is not None,
    )
    return ConfiguracaoIAResponse(radialista=radialista, programa=programa)


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
    db.query(InteractionLog).filter_by(radio_config_id=radialista.id).delete()
    db.query(FilaAoVivo).filter_by(radio_config_id=radialista.id).delete()
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

    try:
        dados_programa = gerar_programa_ia(
            dados.descricao, radialista.nome_locutor, radialista.personalidade, account.tipo_radio
        )
        programa_dados = ProgramaRequest(**dados_programa)
    except (ValueError, ValidationError):
        logger.exception("Falha ao gerar programa via IA: radialista_id=%s", radialista_id)
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
    db.query(ProgramaRadialista).filter_by(programa_id=programa.id).delete()
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
