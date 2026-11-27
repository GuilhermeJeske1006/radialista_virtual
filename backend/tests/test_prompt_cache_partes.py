"""Divisão do system em parte estável (cacheável) e variável: mesma informação, só reorganizada para o cache."""
from collections import Counter
from types import SimpleNamespace

from app.live.prompt_emissao import _partes_do_system
from app.llm import client as llm
from app.llm import economia
from app.llm.system_partes import SystemComPartes, blocos_para_cache
from app.config.settings import settings


def test_linhas_variaveis_vao_para_o_fim_e_nada_se_perde():
    abertura = ["Persona fixa da rádio.\nContexto atual (hora): agora é 10:15.", "Regra de pontuação fixa.",
                "Esta é aproximadamente a fala número 3 desde que o programa entrou no ar."]
    regras = ["Regra geral A.", "Regra geral B."]
    editorial = ["Comece anúncios pelo artista.", "Grade cadastrada, não invente.", "Fatos verificados: nenhum."]
    variaveis = [["Este bloco é um COMENTÁRIO."], ["O bloco anterior foi música."]]
    estavel, variavel = _partes_do_system([abertura, regras, editorial], variaveis)
    assert "Contexto atual" not in estavel and "fala número" not in estavel and "Grade cadastrada" not in estavel
    assert estavel.splitlines() == ["Persona fixa da rádio.", "Regra de pontuação fixa.", "Regra geral A.", "Regra geral B.",
                                    "Comece anúncios pelo artista."]
    todas = [linha for bloco in (abertura, regras, editorial, *variaveis) for item in bloco for linha in item.split("\n")]
    assert Counter(estavel.splitlines() + variavel.splitlines()) == Counter(todas)


def test_estavel_nao_muda_quando_so_o_variavel_muda():
    fixo = ["Regra fixa 1.", "Regra fixa 2."]
    a = _partes_do_system([fixo + ["Contexto atual: 10:15."]], [["Este bloco é a ABERTURA."]])
    b = _partes_do_system([fixo + ["Contexto atual: 10:19."]], [["Este bloco é um COMENTÁRIO."]])
    assert a[0] == b[0] and a[1] != b[1]


def test_blocos_para_cache_so_o_estavel_leva_cache_control():
    system = SystemComPartes("original\nvariável", "original", "variável")
    assert isinstance(system, str) and system == "original\nvariável"
    blocos = blocos_para_cache(system)
    assert blocos == [{"type": "text", "text": "original", "cache_control": {"type": "ephemeral"}},
                      {"type": "text", "text": "variável"}]
    assert blocos_para_cache("string comum") is None
    assert blocos_para_cache(SystemComPartes("só estável", "só estável", "")) == [
        {"type": "text", "text": "só estável", "cache_control": {"type": "ephemeral"}}]


def _capturar(monkeypatch, system):
    chamadas = []

    def responder(**kwargs):
        chamadas.append(kwargs)
        return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text="ok")])

    monkeypatch.setattr(llm._client.messages, "create", responder)
    monkeypatch.setattr(economia, "reservar", lambda *a, **k: object())
    monkeypatch.setattr(economia, "concluir", lambda *a, **k: None)
    monkeypatch.setattr(economia, "falhar", lambda *_: None)
    assert llm.gerar_resposta(system, "Pedido") == "ok"
    return chamadas[0]["system"]


def test_com_cache_desligado_o_system_segue_igual(monkeypatch):
    monkeypatch.setattr(settings, "llm_prompt_cache", False)
    enviado = _capturar(monkeypatch, SystemComPartes("original\nvariável", "original", "variável"))
    assert enviado == [{"type": "text", "text": "original\nvariável"}] or enviado == "original\nvariável"


def test_com_cache_ligado_envia_dois_blocos_e_so_o_estavel_e_cacheado(monkeypatch):
    monkeypatch.setattr(settings, "llm_prompt_cache", True)
    enviado = _capturar(monkeypatch, SystemComPartes("original\nvariável", "original", "variável"))
    assert enviado == [{"type": "text", "text": "original", "cache_control": {"type": "ephemeral"}},
                       {"type": "text", "text": "variável"}]


def test_com_cache_ligado_string_comum_mantem_o_comportamento_antigo(monkeypatch):
    monkeypatch.setattr(settings, "llm_prompt_cache", True)
    enviado = _capturar(monkeypatch, "prompt comum")
    assert enviado == [{"type": "text", "text": "prompt comum", "cache_control": {"type": "ephemeral"}}]


def test_prompt_real_mesmo_estavel_em_blocos_diferentes_e_cobre_a_maior_parte():
    from tests.test_live_formatos_prompt import contexto
    from app.live import formatos as f
    from app.live.prompt_emissao import montar_prompt

    import datetime

    def ctx_do(tipo):
        ctx = contexto(f.MUSICAL_CURADO, tipo)
        ctx.programa.horario_inicio, ctx.programa.horario_fim = datetime.time(12), datetime.time(14)
        ctx.programa.dias_semana = [0, 1, 2, 3, 4]
        return ctx

    prompts = [montar_prompt(ctx_do(tipo)) for tipo in ("abertura", "musica", "comentario", "identificacao")]
    assert all(isinstance(p.system, SystemComPartes) for p in prompts)
    assert len({p.system.estatico for p in prompts}) == 1  # o que muda por bloco ficou fora do prefixo cacheável
    assert len(prompts[0].system.estatico) >= 0.5 * len(str(prompts[0].system))
    for p in prompts:  # nada some: o system completo continua o mesmo texto de antes
        assert Counter(p.system.estatico.splitlines() + p.system.dinamico.splitlines()) == Counter(str(p.system).splitlines())
