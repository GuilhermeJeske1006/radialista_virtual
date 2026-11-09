"""Portas da emissão com ligação tardia (F3, auditoria §5.3)."""

from app.live.portas import PortasEmissao, ligar


def test_portas_procuram_o_nome_no_router_na_hora_da_chamada(monkeypatch):
    from app.live import router

    portas = router._portas()
    monkeypatch.setattr("app.live.router.gerar_resposta", lambda system, mensagem: f"trocado:{mensagem}")
    monkeypatch.setattr("app.live.router._historico_falas", lambda programa_id, categoria: ["uma", "duas"])
    assert portas.gerar_resposta("s", "m") == "trocado:m"
    assert portas.historico_falas(1, "comentario") == ["uma", "duas"]


def test_todas_as_portas_existem_no_router():
    from app.live import router

    faltando = [campo for campo in PortasEmissao.nomes()
                if PortasEmissao.NO_ROUTER.get(campo, campo) not in vars(router)]
    assert faltando == []


def test_ligar_aceita_um_namespace_qualquer():
    chamadas = []
    namespace = {nome: (lambda *a, nome=nome, **k: chamadas.append(nome) or nome)
                 for nome in [PortasEmissao.NO_ROUTER.get(c, c) for c in PortasEmissao.nomes()]}
    portas = ligar(namespace)
    assert portas.buscar_musica_para_bloco() == "_buscar_musica_para_bloco"
    namespace["gerar_resposta"] = lambda *a: "novo"
    assert portas.gerar_resposta() == "novo"
