import datetime

from app.models.account import Account
from app.models.compra_excedente import CompraExcedente
from app.models.fila_ao_vivo import FilaAoVivo
from app.models.interaction_log import InteractionLog
from app.models.password_reset_token import PasswordResetToken
from app.models.patrocinador import Patrocinador
from app.models.programa import Programa
from app.models.programa_radialista import ProgramaRadialista
from app.models.radio_config import RadioConfig
from app.models.usuario import Usuario
from app.models.voz_clonada import VozClonada


def test_account_tem_defaults_esperados(db_session):
    account = Account()
    db_session.add(account)
    db_session.commit()
    db_session.refresh(account)

    assert account.plano == "starter"
    assert account.plano_status == "trial"
    assert account.agentes_extras == 0
    assert account.criado_em is not None


def test_usuario_defaults(db_session):
    account = Account()
    db_session.add(account)
    db_session.flush()

    usuario = Usuario(email="a@a.com", senha_hash="hash", account_id=account.id)
    db_session.add(usuario)
    db_session.commit()
    db_session.refresh(usuario)

    assert usuario.role == "membro"
    assert usuario.ativo is True
    assert usuario.criado_em is not None


def test_account_email_reflete_usuario_admin(db_session):
    account = Account()
    db_session.add(account)
    db_session.flush()

    db_session.add(Usuario(email="membro@a.com", senha_hash="hash", account_id=account.id, role="membro"))
    db_session.add(Usuario(email="admin@a.com", senha_hash="hash", account_id=account.id, role="admin"))
    db_session.commit()
    db_session.refresh(account)

    assert account.email == "admin@a.com"


def test_radio_config_defaults(db_session):
    account = Account()
    db_session.add(account)
    db_session.commit()

    radio_config = RadioConfig(account_id=account.id)
    db_session.add(radio_config)
    db_session.commit()
    db_session.refresh(radio_config)

    assert radio_config.nome_locutor == "Ze do Radio"
    assert radio_config.ativo is True
    assert radio_config.timezone == "America/Sao_Paulo"


def test_programa_listas_json_persistem(db_session):
    account = Account()
    db_session.add(account)
    db_session.commit()
    radio_config = RadioConfig(account_id=account.id)
    db_session.add(radio_config)
    db_session.commit()

    programa = Programa(
        radio_config_id=radio_config.id,
        nome="Programa Teste",
        dias_semana=[0, 1, 2],
        horario_inicio=datetime.time(8, 0),
        horario_fim=datetime.time(10, 0),
        topicos_permitidos=["musica", "noticia"],
    )
    db_session.add(programa)
    db_session.commit()
    db_session.refresh(programa)

    recarregado = db_session.query(Programa).filter_by(id=programa.id).first()
    assert recarregado.dias_semana == [0, 1, 2]
    assert recarregado.topicos_permitidos == ["musica", "noticia"]


def test_programa_radialista_unique_constraint(db_session):
    account = Account()
    db_session.add(account)
    db_session.commit()
    radio_config = RadioConfig(account_id=account.id)
    db_session.add(radio_config)
    db_session.commit()
    programa = Programa(
        radio_config_id=radio_config.id,
        nome="P",
        horario_inicio=datetime.time(8, 0),
        horario_fim=datetime.time(10, 0),
    )
    db_session.add(programa)
    db_session.commit()

    db_session.add(ProgramaRadialista(programa_id=programa.id, radio_config_id=radio_config.id))
    db_session.commit()

    db_session.add(ProgramaRadialista(programa_id=programa.id, radio_config_id=radio_config.id))
    try:
        db_session.commit()
        assert False, "deveria ter levantado erro de unique constraint"
    except Exception:
        db_session.rollback()


def test_interaction_log_wuzapi_message_id_e_unico(db_session):
    account = Account()
    db_session.add(account)
    db_session.commit()
    radio_config = RadioConfig(account_id=account.id)
    db_session.add(radio_config)
    db_session.commit()

    db_session.add(
        InteractionLog(
            radio_config_id=radio_config.id,
            wuzapi_message_id="msg-1",
            telefone="5511999999999",
            mensagem_usuario="oi",
            status="ok",
        )
    )
    db_session.commit()

    db_session.add(
        InteractionLog(
            radio_config_id=radio_config.id,
            wuzapi_message_id="msg-1",
            telefone="5511999999999",
            mensagem_usuario="oi de novo",
            status="ok",
        )
    )
    try:
        db_session.commit()
        assert False, "deveria ter levantado erro de unique constraint"
    except Exception:
        db_session.rollback()


def test_fila_ao_vivo_default_nao_atendido(db_session):
    account = Account()
    db_session.add(account)
    db_session.commit()
    radio_config = RadioConfig(account_id=account.id)
    db_session.add(radio_config)
    db_session.commit()

    pedido = FilaAoVivo(
        radio_config_id=radio_config.id, telefone="5511999999999", tipo="musica", mensagem_usuario="toca ai"
    )
    db_session.add(pedido)
    db_session.commit()
    db_session.refresh(pedido)

    assert pedido.atendido is False
    assert pedido.atendido_em is None


def test_patrocinador_default_tipo_texto(db_session):
    account = Account()
    db_session.add(account)
    db_session.commit()

    patrocinador = Patrocinador(account_id=account.id, nome="Loja X")
    db_session.add(patrocinador)
    db_session.commit()
    db_session.refresh(patrocinador)

    assert patrocinador.tipo_conteudo == "texto"
    assert patrocinador.ativo is True


def test_voz_clonada_voz_id_e_unico(db_session):
    account = Account()
    db_session.add(account)
    db_session.commit()

    db_session.add(VozClonada(account_id=account.id, nome="Minha voz", voz_id="voz-abc"))
    db_session.commit()

    db_session.add(VozClonada(account_id=account.id, nome="Outra", voz_id="voz-abc"))
    try:
        db_session.commit()
        assert False, "deveria ter levantado erro de unique constraint"
    except Exception:
        db_session.rollback()


def test_compra_excedente_guarda_mes_referencia(db_session):
    account = Account()
    db_session.add(account)
    db_session.commit()

    compra = CompraExcedente(account_id=account.id, quantidade=1000, mes_referencia="2026-08")
    db_session.add(compra)
    db_session.commit()
    db_session.refresh(compra)

    assert compra.quantidade == 1000
    assert compra.mes_referencia == "2026-08"


def test_password_reset_token_hash_e_unico(db_session):
    account = Account()
    db_session.add(account)
    db_session.flush()

    usuario = Usuario(email="a@a.com", senha_hash="hash", account_id=account.id)
    db_session.add(usuario)
    db_session.commit()

    expira_em = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=30)
    db_session.add(PasswordResetToken(usuario_id=usuario.id, token_hash="hash-1", expira_em=expira_em))
    db_session.commit()

    db_session.add(PasswordResetToken(usuario_id=usuario.id, token_hash="hash-1", expira_em=expira_em))
    try:
        db_session.commit()
        assert False, "deveria ter levantado erro de unique constraint"
    except Exception:
        db_session.rollback()
