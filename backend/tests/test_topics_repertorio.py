import pytest
from sqlalchemy import create_engine, inspect, text

from app.db.migrations.repertorio_20261125 import aplicar
from app.topics.repertorio import normalizar, recortes_parecidos


@pytest.mark.parametrize("valor", [None, [], "texto", 5, {"familia": []}, {"abordagens": "texto"}])
def test_repertorio_legado_ou_malformado_e_tolerado(valor):
    assert normalizar(valor) == {}


def test_limita_notas_e_descarta_campos_arbitrarios():
    resultado = normalizar({"familia": "cotidiano", "recorte": " x ", "fatos": ["inventado"],
                            "abordagens": ["uma", "uma", None, 2, "duas", "três", "quatro"],
                            "contextos": ["x" * 1000]})
    assert resultado == {"familia": "cotidiano", "recorte": "x", "abordagens": ["uma", "duas", "três"],
                         "contextos": ["x" * 600]}


def test_deduplicacao_lexical_reconhece_variacoes_sem_colapsar_toda_familia():
    assert recortes_parecidos("Música da infância!", "musica da infancia")
    assert recortes_parecidos("Reconhecer uma música conhecida pelos primeiros acordes", "Reconhecer música conhecida pelos primeiros acordes")
    assert not recortes_parecidos("Música na viagem", "Música no trabalho")
    assert not recortes_parecidos("", "")


def test_migracao_aditiva_preserva_assuntos_e_e_idempotente():
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE assuntos (id INTEGER PRIMARY KEY, titulo VARCHAR NOT NULL)"))
        conn.execute(text("INSERT INTO assuntos (id, titulo) VALUES (1, 'Pauta existente')"))
    assert aplicar(engine)
    assert not aplicar(engine)
    with engine.connect() as conn:
        assert conn.execute(text("SELECT titulo, repertorio FROM assuntos")).one() == ("Pauta existente", "{}")
    assert "repertorio" in {c["name"] for c in inspect(engine).get_columns("assuntos")}
    engine.dispose()


def test_migracao_antes_da_criacao_das_tabelas_nao_falha():
    engine = create_engine("sqlite://")
    assert not aplicar(engine)
    engine.dispose()
