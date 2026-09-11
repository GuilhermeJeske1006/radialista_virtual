from app.news.curadoria import curar_item
from app.news.feeds import ItemFeed


def _item(titulo="Rua interditada apos obra", resumo="Trecho de 300 metros fechado") -> ItemFeed:
    import datetime
    return ItemFeed(titulo=titulo, resumo=resumo, url="https://x.com/n", publicado_em=datetime.datetime.now(datetime.timezone.utc))


def test_curar_item_bloqueia_por_termo_universal_sem_chamar_llm(monkeypatch):
    def _nao_deveria_chamar(*a, **k):
        raise AssertionError("termo sempre bloqueado não precisa de chamada ao LLM")
    monkeypatch.setattr("app.news.curadoria.gerar_classificacao", _nao_deveria_chamar)

    resultado = curar_item(_item(titulo="Homem é preso com arma na Rua X"), fonte_nome="Portal", fonte_tipo="imprensa", cidade="Blumenau")

    assert resultado is None


def test_curar_item_extrai_categoria_score_e_lauda(monkeypatch):
    resposta_json = (
        '{"bloqueada": false, "categoria": "transito", "score": 82, "quando": "hoje de manha", '
        '"onde": "Itoupava Seca", "numeros": "300 metros", "pessoas": "", "impacto": "desvio necessario", '
        '"servico": "desvio pela Antonio da Veiga", "proximo_passo": "novo boletim as 17h", '
        '"ainda_nao_divulgado": ""}'
    )
    monkeypatch.setattr("app.news.curadoria.gerar_classificacao", lambda system, msg: resposta_json)

    resultado = curar_item(_item(), fonte_nome="Prefeitura", fonte_tipo="oficial", cidade="Blumenau", peso_fonte=1.0)

    assert resultado is not None
    assert resultado.categoria == "transito"
    assert resultado.score == 82.0
    assert resultado.servico == "desvio pela Antonio da Veiga"
    assert resultado.proximo_passo == "novo boletim as 17h"


def test_curar_item_aplica_peso_da_fonte_no_score(monkeypatch):
    resposta_json = '{"bloqueada": false, "categoria": "geral", "score": 40}'
    monkeypatch.setattr("app.news.curadoria.gerar_classificacao", lambda system, msg: resposta_json)

    resultado = curar_item(_item(), fonte_nome="Assessoria", fonte_tipo="assessoria", cidade="Blumenau", peso_fonte=0.5)

    assert resultado.score == 20.0


def test_curar_item_respeita_bloqueio_do_llm_por_disputa_partidaria(monkeypatch):
    resposta_json = '{"bloqueada": true, "categoria": "geral", "score": 50}'
    monkeypatch.setattr("app.news.curadoria.gerar_classificacao", lambda system, msg: resposta_json)

    resultado = curar_item(_item(titulo="Candidato ataca adversario em debate"), fonte_nome="Portal", fonte_tipo="imprensa", cidade="Blumenau")

    assert resultado is None


def test_curar_item_categoria_invalida_do_llm_cai_para_geral(monkeypatch):
    resposta_json = '{"bloqueada": false, "categoria": "categoria-que-nao-existe", "score": 60}'
    monkeypatch.setattr("app.news.curadoria.gerar_classificacao", lambda system, msg: resposta_json)

    resultado = curar_item(_item(), fonte_nome="Portal", fonte_tipo="imprensa", cidade="Blumenau")

    assert resultado.categoria == "geral"


def test_curar_item_falha_do_llm_descarta_por_seguranca(monkeypatch):
    def _levantar(*a, **k):
        raise RuntimeError("timeout")
    monkeypatch.setattr("app.news.curadoria.gerar_classificacao", _levantar)

    resultado = curar_item(_item(), fonte_nome="Portal", fonte_tipo="imprensa", cidade="Blumenau")

    assert resultado is None


def test_curar_item_resposta_nao_json_descarta_por_seguranca(monkeypatch):
    monkeypatch.setattr("app.news.curadoria.gerar_classificacao", lambda system, msg: "isso nao e json")

    resultado = curar_item(_item(), fonte_nome="Portal", fonte_tipo="imprensa", cidade="Blumenau")

    assert resultado is None
