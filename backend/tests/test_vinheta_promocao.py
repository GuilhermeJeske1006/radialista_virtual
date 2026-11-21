"""Natureza do bloco (F10): vinheta de promocao nao entra colada a noticia; generica segue normal."""

from types import SimpleNamespace

import pytest

from app.live.roteiro import vinheta_bloqueada_pela_natureza
from app.models.biblioteca_audio import BibliotecaAudioItem


@pytest.mark.parametrize("categoria", ["noticia", "escalada", "servico", "plantao", "reporter"])
def test_promocao_bloqueada_depois_de_bloco_de_noticia(categoria):
    assert vinheta_bloqueada_pela_natureza(SimpleNamespace(uso="promocao"), categoria) is True


@pytest.mark.parametrize("categoria", ["musica", "comentario", "vinheta", None])
def test_promocao_liberada_fora_de_noticia(categoria):
    assert vinheta_bloqueada_pela_natureza(SimpleNamespace(uso="promocao"), categoria) is False


def test_generica_nunca_e_bloqueada():
    assert vinheta_bloqueada_pela_natureza(SimpleNamespace(uso="generica"), "noticia") is False


def test_vinheta_sem_atributo_uso_trata_como_generica():
    assert vinheta_bloqueada_pela_natureza(object(), "noticia") is False


def test_coluna_uso_tem_default_generica(db_session, account):
    item = BibliotecaAudioItem(account_id=account.id, nome="x", audio_path="a.mp3")
    db_session.add(item)
    db_session.commit()
    db_session.refresh(item)
    assert item.uso == "generica"
