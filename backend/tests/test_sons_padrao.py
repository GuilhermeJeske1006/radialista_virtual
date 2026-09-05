import pytest

from app.biblioteca_audio.sons_padrao import SONS_PADRAO, criar_sons_padrao
from app.categorias_vinheta.defaults import criar_categorias_padrao
from app.config.settings import settings
from app.models.biblioteca_audio import BibliotecaAudioItem
from app.models.categoria_vinheta import CategoriaVinheta
from app.storage import get_storage


@pytest.fixture(autouse=True)
def _storage_local(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "storage_backend", "local")
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))


def test_criar_sons_padrao_cria_categoria_e_itens(db_session, account_factory):
    account = account_factory(email="sons1@a.com")

    criar_sons_padrao(db_session, account.id)
    db_session.commit()

    categoria = db_session.query(CategoriaVinheta).filter_by(account_id=account.id, nome="Cartwall").first()
    assert categoria is not None
    assert categoria.tipo == "biblioteca"

    itens = db_session.query(BibliotecaAudioItem).filter_by(account_id=account.id).all()
    assert len(itens) == len(SONS_PADRAO)
    assert {i.nome for i in itens} == {s["nome"] for s in SONS_PADRAO}
    assert all(i.categoria_id == categoria.id for i in itens)
    assert all(i.ativo is True for i in itens)
    assert all(i.duracao_segundos is not None for i in itens)

    storage = get_storage()
    for item in itens:
        conteudo = storage.read(item.audio_path)
        assert conteudo is not None
        assert len(conteudo) > 0


def test_criar_sons_padrao_e_idempotente(db_session, account_factory):
    account = account_factory(email="sons2@a.com")

    criar_sons_padrao(db_session, account.id)
    db_session.commit()
    criar_sons_padrao(db_session, account.id)
    db_session.commit()

    itens = db_session.query(BibliotecaAudioItem).filter_by(account_id=account.id).all()
    assert len(itens) == len(SONS_PADRAO)

    categorias = (
        db_session.query(CategoriaVinheta).filter_by(account_id=account.id, nome="Cartwall").all()
    )
    assert len(categorias) == 1


def test_criar_sons_padrao_reaproveita_categoria_padrao_pendente_na_sessao(db_session, account_factory):
    """Reproduz o fluxo real de registro (app/auth/router.py): criar_categorias_padrao roda
    na mesma sessao, sem commit, antes de criar_sons_padrao -- a sessao do app usa
    autoflush=False, entao sem o db.flush() em criar_sons_padrao a "Cartwall" criada
    aqui nao apareceria na query e duplicaria a categoria.
    """
    account = account_factory(email="sons3@a.com")

    criar_categorias_padrao(db_session, account.id)
    criar_sons_padrao(db_session, account.id)
    db_session.commit()

    categorias = (
        db_session.query(CategoriaVinheta).filter_by(account_id=account.id, nome="Cartwall").all()
    )
    assert len(categorias) == 1

    itens = db_session.query(BibliotecaAudioItem).filter_by(account_id=account.id).all()
    assert len(itens) == len(SONS_PADRAO)


def test_criar_sons_padrao_nao_duplica_item_ja_renomeado_ou_existente(db_session, account_factory):
    """So' cria o que falta por nome -- conta que ja tem um som com o mesmo nome (ex.: seed
    rodado de novo apos o operador ja ter customizado a biblioteca) nao ganha duplicata."""
    account = account_factory(email="sons4@a.com")
    criar_sons_padrao(db_session, account.id)
    db_session.commit()

    total_antes = db_session.query(BibliotecaAudioItem).filter_by(account_id=account.id).count()

    criar_sons_padrao(db_session, account.id)
    db_session.commit()

    total_depois = db_session.query(BibliotecaAudioItem).filter_by(account_id=account.id).count()
    assert total_antes == total_depois
