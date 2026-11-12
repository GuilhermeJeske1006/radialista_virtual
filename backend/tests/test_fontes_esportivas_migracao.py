import json

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db.migrations.fontes_esportivas_20261111 import aplicar
from app.models.esportes import FonteEsportiva


@pytest.mark.parametrize("tem_revisao", [False, True])
def test_migracao_corrige_consulta_preserva_dados_e_revisao_e_pode_repetir(tem_revisao):
    engine = create_engine("sqlite://")
    assert aplicar(engine) is False
    revisao = ", revisao INTEGER NOT NULL DEFAULT 7" if tem_revisao else ""
    with engine.begin() as conn:
        conn.execute(text(f"CREATE TABLE fontes_esportivas (id INTEGER PRIMARY KEY, account_id INTEGER, dominio VARCHAR, dados JSON{revisao})"))
        conn.execute(text("INSERT INTO fontes_esportivas (id, account_id, dominio, dados) VALUES (1, 3, 'federacao.example.com', :dados)"),
                     {"dados": json.dumps({"organizacao": "Federação"})})
    with Session(engine) as db:
        # Reproduz a falha do banco antigo: o ORM já consulta a coluna nova.
        with pytest.raises(OperationalError, match="historico"):
            db.query(FonteEsportiva).all()
    assert aplicar(engine) is True
    assert aplicar(engine) is False
    assert {"historico", "revisao"} <= {c["name"] for c in inspect(engine).get_columns("fontes_esportivas")}
    with Session(engine) as db:
        fonte = db.get(FonteEsportiva, 1)
        assert fonte.account_id == 3
        assert fonte.dominio == "federacao.example.com"
        assert fonte.dados == {"organizacao": "Federação"}
        assert fonte.historico == []
        assert fonte.revisao == (7 if tem_revisao else 1)
        fonte.historico = [{"acao": "revisao"}]
        db.commit()
        assert fonte.revisao == (8 if tem_revisao else 2)
    engine.dispose()


def test_fontes_do_programa_carregam_apos_migracao_do_banco_antigo(client, account, auth_headers, db_session):
    dados = {
        "dominio": "federacao.example.com", "organizacao": "Federação", "temas": "Futebol",
        "ultima_revisao": "2026-11-11", "condicoes_uso": "Consulta editorial",
    }
    headers = auth_headers(account.id)
    criada = client.post("/esportes/fontes", json=dados, headers=headers)
    assert criada.status_code == 201
    db_session.execute(text("ALTER TABLE fontes_esportivas DROP COLUMN historico"))
    db_session.commit()
    db_session.expire_all()
    assert aplicar(db_session.get_bind()) is True
    resposta = client.get("/esportes/fontes", headers=headers)
    assert resposta.status_code == 200
    assert resposta.json() == [criada.json()]
