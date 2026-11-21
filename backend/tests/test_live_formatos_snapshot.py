"""Snapshot das instruções de cada formato no prompt (F6, U6 da auditoria §8: o critério de aceite do plano).

Para cada formato com promessa × papel do bloco (abertura da largada, retomada, identificação, música com pedido,
chamada, comentário, quadro fixo no variedades e encerramento), `montar_prompt(ctx)` sobre um `ContextoEmissao` montado
à mão; as linhas do formato (a seção `_formato` e a direção do formato) vão para
`tests/fixtures/formatos/<formato>__<papel>.txt`. Regravar com `ATUALIZAR_GOLDEN=1` e revisar o diff no mesmo commit.

Para o mesmo papel, os três formatos dão instruções distintas duas a duas; o `padrao` não tem nenhuma linha de formato.
"""

import os
import pathlib

import pytest

from test_live_formatos_prompt import contexto, linhas_do_formato_no_system

DIR = pathlib.Path(__file__).resolve().parent / "fixtures" / "formatos"
ATUALIZAR = os.environ.get("ATUALIZAR_GOLDEN") == "1"
FORMATOS = ("musical_adulto", "popular_sertanejo", "variedades_leves")
# papel -> argumentos de `contexto` (tipo, primeira, categoria, quadro, pedido)
PAPEIS = {
    "abertura_primeira": dict(tipo="abertura", primeira=True),
    "retomada": dict(tipo="retomada"),
    "identificacao": dict(tipo="identificacao", categoria="abertura"),
    "musica_com_pedido": dict(tipo="musica", pedido=True),
    "chamada": dict(tipo="chamada_ouvinte"),
    "comentario": dict(tipo="comentario"),
    "quadro": dict(tipo="comentario", quadro=True),
    "encerramento": dict(tipo="encerramento"),
}
CASOS = [(formato, papel) for formato in FORMATOS for papel in PAPEIS
         if papel != "quadro" or formato == "variedades_leves"]


def _texto(formato: str, papel: str) -> str:
    return "\n".join(linhas_do_formato_no_system(contexto(formato, **PAPEIS[papel]))) + "\n"


@pytest.mark.parametrize("formato, papel", CASOS, ids=[f"{f}__{p}" for f, p in CASOS])
def test_u6_instrucoes_do_formato_no_prompt(formato, papel):
    texto = _texto(formato, papel)
    caminho = DIR / f"{formato}__{papel}.txt"
    if ATUALIZAR:
        DIR.mkdir(parents=True, exist_ok=True)
        caminho.write_text(texto, encoding="utf-8")
        return
    assert caminho.exists(), f"snapshot ausente: {caminho.name} (rode com ATUALIZAR_GOLDEN=1)"
    assert texto == caminho.read_text(encoding="utf-8")


@pytest.mark.parametrize("papel", [p for p in PAPEIS if p != "quadro"])
def test_u6_mesmo_papel_tres_formatos_distintos_dois_a_dois(papel):
    textos = {formato: _texto(formato, papel) for formato in FORMATOS}
    assert all(t.strip() for t in textos.values()), textos
    assert len(set(textos.values())) == len(FORMATOS)
    # Cada formato traz o próprio cabeçalho e nenhum outro.
    from app.live.formatos import FORMATOS as CATALOGO

    for formato, texto in textos.items():
        for outro in FORMATOS:
            assert (CATALOGO[outro].direcao_cabecalho in texto) is (outro == formato), (formato, outro)


@pytest.mark.parametrize("papel", list(PAPEIS))
def test_u6_padrao_nao_tem_linha_de_formato(papel):
    assert _texto("padrao", papel) == "\n"


def test_u6_snapshots_cobrem_todos_os_casos():
    if ATUALIZAR:
        pytest.skip("regravando")
    assert sorted(p.name for p in DIR.glob("*.txt")) == sorted(f"{f}__{p}.txt" for f, p in CASOS)
