"""Validador pós-geração da fala (F3, U3, U4 e U5 da auditoria §6).

Regra editorial 1 (não anunciar música que não está confirmada) e o fragmento que o encurtamento deixa abaixo do
mínimo do tipo (achado do juiz da F2).
"""

import dataclasses
import datetime
import json
import pathlib
from types import SimpleNamespace

import pytest

from app.live.contexto import (
    Chamadas,
    ContextoEmissao,
    EstadoMusical,
    Jornalismo,
    Memoria,
    MusicaRef,
    Participacao,
    Tempo,
    Variacoes,
)
from app.live.orcamento import OrcamentoFala
from app.live.validacao_fala import (
    CHECAGENS_POS_GERACAO,
    Violacao,
    checar_musicas,
    confirmada,
    corrigir,
    fala_reserva_neutra,
    mencoes_musica,
    remover_frases,
    validar,
)

RAIZ = pathlib.Path(__file__).resolve().parents[2]
CASOS = RAIZ / "docs" / "benchmarks" / "2026-11-06-formatos" / "casos.json"
FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures" / "programas"

CONFIRMADA = MusicaRef("Rua das Acácias", "Duo Estrada Velha", "v1")
ORCAMENTO_MUSICAL = OrcamentoFala(6, 9, 12, 25, "formato", True)


def _ctx(confirmada_=CONFIRMADA, *, tocou=(), bloco=(), citaveis=(), resolvido=True, resolve_citadas=True,
         nao_resolvidas=(), nomes=(), orcamento=ORCAMENTO_MUSICAL, categoria="abertura", pedido=None):
    agora = datetime.datetime(2026, 8, 10, 12, 0, tzinfo=datetime.timezone.utc)
    return ContextoEmissao(
        request_id="t", account=SimpleNamespace(nome_radio="Rádio Serra Clara", cidade="Vale Verde"),
        radialista=SimpleNamespace(nome_locutor="Caio Ventania"),
        programa=SimpleNamespace(nome="Tarde Serena", quadros_fixos={}, id=1),
        tipo=categoria, categoria=categoria, primeira_fala=False, total_falas=3, passos_roteiro=1,
        formato_musical=True, multi_voz=False, roster=(), roteiro=("musica",), categorias_roteiro=("musica",),
        tempo=Tempo(agora_local=agora, instante=agora, origem_instante="agora", plano=None, preset_relogio=None,
                    inicio_previsto_aceito=False),
        musica=EstadoMusical(tocou=tuple(tocou), confirmada=confirmada_, bloco=tuple(bloco), citaveis=tuple(citaveis),
                             resolvido=resolvido, resolve_citadas=resolve_citadas,
                             citadas_nao_resolvidas=tuple(nao_resolvidas)),
        participacao=Participacao(novo_atendimento=False, pedido_musica=pedido, pedido_ouvinte=None,
                                  ouvinte_recorrente=None, ouvinte_recorrente_dias=None, pedido_recente=None,
                                  nomes_autorizados=tuple(nomes)),
        chamadas=Chamadas(fio_condutor=None),
        memoria=Memoria(historico=(), historico_prompt="", ultima_categoria=None),
        variacoes=Variacoes(verbo_identificacao="aqui é a"), jornalismo=Jornalismo(),
        orcamento=orcamento, wpm_fala=150.0, categoria_voz="padrao", limite_palavras=25, prompt_base="",
        modelo_com_tags=False,
    )


# ---------------------------------------------------------------------------------------------
# Detector
# ---------------------------------------------------------------------------------------------

@pytest.mark.parametrize("texto", [
    "Agora, Varanda de Pedra, com Trio Ventania.",                 # título e artista
    "Quem chega agora é Trio Ventania, com Varanda de Pedra.",     # artista e título
    "Pode esperar Varanda de Pedra nesta tarde.",                  # marcador
    "Na sequência, Varanda de Pedra.",
    "E falando nisso, Varanda de Pedra, de Trio Ventania, é linda.",  # forma canônica sem marcador
])
def test_detecta_anuncio_nas_duas_ordens_e_nos_marcadores(texto):
    violacoes = checar_musicas(texto, _ctx())
    assert [v.regra for v in violacoes] == ["musica_nao_confirmada"]
    assert "Varanda de Pedra" in violacoes[0].trecho or "Trio Ventania" in violacoes[0].ref_id


@pytest.mark.parametrize("texto", [
    "Agora, Rua das Acácias, com Duo Estrada Velha.",
    "Quem chega agora é Duo Estrada Velha, com Rua das Acácias.",
    "Você está na Rádio Serra Clara, com Caio Ventania, no Tarde Serena.",
    "Agora vem um abraço para Joana Lis, de Vale Verde.",
    "Agora é hora de aproveitar a tarde.",
])
def test_nao_acusa_confirmada_nem_nomes_da_radio_e_ouvintes(texto):
    assert checar_musicas(texto, _ctx(nomes=("Joana Lis",))) == []


def test_mesma_musica_com_sotaque_de_titulo_conta_como_confirmada():
    ctx = _ctx(MusicaRef("Chitaozinho & Xororo - Evidencias", "C&X - Topic", "v9"))
    assert checar_musicas("Agora vem Evidencias, com Chitãozinho e Xororó.", ctx) == []


def test_ja_tocada_e_bloco_confirmam_e_pedido_em_fila_nao():
    tocou = (MusicaRef("Cais do Entardecer", "Banda Fio de Prata", origem="historico"),)
    bloco = (MusicaRef("Outra Citada", "Banda Y", "c1", origem="citada"),)
    ctx = _ctx(tocou=tocou, bloco=bloco)
    assert checar_musicas("Que beleza, Cais do Entardecer, de Banda Fio de Prata.", ctx) == []
    assert checar_musicas("E depois vem Outra Citada, com Banda Y.", ctx) == []
    # Pedido em fila não entra em nenhuma das listas permitidas: o título dele é anúncio sem confirmação.
    assert checar_musicas("Rosa pediu, e toca agora Lenço no Portão.", _ctx(nomes=("Rosa",)))


def test_camada_conhecida_exige_inicial_maiuscula():
    citaveis = (MusicaRef("Evidências", "Chitãozinho e Xororó", origem="conhecida"),)
    ctx = _ctx(citaveis=citaveis)
    assert checar_musicas("As evidências mostram que a tarde vai ser boa.", ctx) == []
    assert [v.ref_id for v in checar_musicas("Lembrei de Evidências agora há pouco.", ctx)] == ["Evidências"]


def test_camada_c_citada_que_nao_se_resolveu():
    ctx = _ctx(nao_resolvidas=("Banda Z - Musica Inexistente",))
    violacoes = checar_musicas("Lembrei de musica inexistente. Seguimos.", ctx)
    assert [(v.ref_id, v.trecho) for v in violacoes] == [("Musica Inexistente", "Lembrei de musica inexistente.")]


def test_fase_pre_so_quando_a_citada_nao_vai_tocar():
    texto = "Agora vem Varanda de Pedra."
    assert checar_musicas(texto, _ctx(resolvido=False, resolve_citadas=True)) == []
    violacoes = checar_musicas(texto, _ctx(resolvido=False, resolve_citadas=False))
    assert violacoes and "A única faixa confirmada é 'Rua das Acácias' de 'Duo Estrada Velha'" \
        in violacoes[0].instrucao_retry
    sem_faixa = checar_musicas(texto, _ctx(None, resolvido=False, resolve_citadas=False))
    assert sem_faixa[0].instrucao_retry.endswith("Não cite música pelo nome.")


# ---------------------------------------------------------------------------------------------
# U4: casos de avaliação do benchmark (7 anúncios sem confirmação, 63 falas limpas)
# ---------------------------------------------------------------------------------------------

def _nomes_do_formato(formato: str) -> list[str]:
    dados = json.loads((FIXTURES / f"{formato}.json").read_text(encoding="utf-8"))
    return [dados["conta"]["nome_radio"], dados["programa"]["nome"], dados["radialista"]["nome_locutor"]]


def test_casos_benchmark_musica():
    casos = json.loads(CASOS.read_text(encoding="utf-8"))["casos"]
    detectados, falsos, perdidos, total = 0, [], [], 0
    for caso in casos:
        contexto = caso["contexto"]
        ref = lambda rotulo, origem: MusicaRef(*rotulo.rsplit(" - ", 1), origem=origem)  # noqa: E731
        confirmada_ = ref(contexto["proxima_confirmada"], "bloco") if contexto.get("proxima_confirmada") else None
        selecionados = [ref(p["musica"], "pedido") for p in contexto.get("pedidos") or []
                        if p.get("estado") == "selecionado" and p.get("musica")]
        ctx = _ctx(confirmada_, tocou=[ref(t, "historico") for t in contexto.get("tocou") or []], bloco=selecionados,
                   nomes=[p["nome"] for p in contexto.get("pedidos") or []])
        ctx = dataclasses.replace(ctx, account=SimpleNamespace(nome_radio=_nomes_do_formato(caso["formato"])[0],
                                                               cidade=""),
                                  programa=SimpleNamespace(nome=_nomes_do_formato(caso["formato"])[1], quadros_fixos={},
                                                           id=1),
                                  radialista=SimpleNamespace(nome_locutor=_nomes_do_formato(caso["formato"])[2]))
        for fala in caso["falas_rotuladas"]:
            total += 1
            esperado = bool(fala["esperado"].get("anuncio_sem_confirmacao"))
            achou = bool(checar_musicas(fala["texto"], ctx))
            if esperado and achou:
                detectados += 1
            elif esperado:
                perdidos.append((caso["id"], fala["texto"]))
            elif achou:
                falsos.append((caso["id"], fala["texto"]))
    assert total == 96  # 35 casos da F0 à F5 e 13 da F6, duas falas cada
    assert (detectados, perdidos, falsos) == (7, [], [])


# ---------------------------------------------------------------------------------------------
# Remediação
# ---------------------------------------------------------------------------------------------

def test_remover_frases_preserva_ouvinte_e_titulo_confirmado():
    fala = ("Agora vem Rua das Acácias, com Duo Estrada Velha, e depois Varanda de Pedra. "
            "Pode esperar Moinho Antigo, de Trio Ventania, nesta tarde. Fica com a gente.")
    violacoes = checar_musicas(fala, _ctx())
    assert len(violacoes) == 2
    assert remover_frases(fala, violacoes, ["Rua das Acácias"]) == \
        "Agora vem Rua das Acácias, com Duo Estrada Velha. Fica com a gente."


def test_fala_vazia_vira_so_musica_ou_reserva_neutra():
    ctx = _ctx()
    fala = "Pode esperar Moinho Antigo, de Trio Ventania."
    musica = corrigir(fala, [], ctx, preservar=[], modo="corrigir", so_musica_se_vazia=True, alterada=False,
                      wpm=150)
    assert (musica.fala, musica.acao) == ("", "fala_removida")
    neutra = corrigir(fala, [], ctx, preservar=[], modo="corrigir", so_musica_se_vazia=False, alterada=False,
                      wpm=150)
    assert (neutra.fala, neutra.acao) == ("Você está no Tarde Serena, na Rádio Serra Clara.", "fala_neutra")
    assert fala_reserva_neutra(ctx) == neutra.fala
    avisar = corrigir(fala, [], ctx, preservar=[], modo="avisar", so_musica_se_vazia=False, alterada=False, wpm=150)
    assert (avisar.fala, avisar.acao, len(avisar.violacoes)) == (fala, "nenhuma", 1)


def test_multivoz_remove_por_linha():
    from app.live.geracao import FalaItem

    linhas = [FalaItem(radio_config_id=1, nome_locutor="Caio Ventania", voz_id=None, texto="Que tarde boa."),
              FalaItem(radio_config_id=2, nome_locutor="Maria", voz_id=None,
                       texto="Pode esperar Moinho Antigo, de Trio Ventania.")]
    resultado = corrigir(" ".join(item.texto for item in linhas), linhas, _ctx(), preservar=[], modo="corrigir",
                         so_musica_se_vazia=False, alterada=False, wpm=150)
    assert [item.texto for item in resultado.falas_bloco] == ["Que tarde boa."]
    assert (resultado.fala, resultado.acao) == ("Que tarde boa.", "mencao_removida")


def test_fragmento_abaixo_do_minimo_nao_vai_ao_ar():
    """Achado do juiz da F2: o encurtamento deixou "Rádio." (0,4 s) numa identificação de 3 s."""
    ctx = _ctx(orcamento=OrcamentoFala(3, 3, 3, None, "relogio", True), categoria="identificacao")
    sem_musica = corrigir("Rádio.", [], ctx, preservar=[], modo="corrigir", so_musica_se_vazia=False,
                          alterada=True, wpm=150)
    # A reorientação mais longa que cabe nos 3 s do orçamento.
    assert sem_musica.fala == "Você está na Rádio Serra Clara."
    assert sem_musica.acao == "fala_neutra"
    assert [(v.regra, v.trecho) for v in sem_musica.violacoes] == [("fala_abaixo_do_minimo", "Rádio.")]
    com_musica = corrigir("Rádio.", [], ctx, preservar=[], modo="corrigir", so_musica_se_vazia=True, alterada=True,
                          wpm=150)
    assert (com_musica.fala, com_musica.acao) == ("", "fala_removida")
    # Fala curta que o LLM escreveu assim (sem encurtamento) e orçamento só observado não mudam.
    assert corrigir("Rádio.", [], ctx, preservar=[], modo="corrigir", so_musica_se_vazia=False, alterada=False,
                    wpm=150).fala == "Rádio."
    observado = dataclasses.replace(ctx, orcamento=OrcamentoFala(15, 22, 30, None, "observacao", False))
    assert corrigir("Rádio.", [], observado, preservar=[], modo="corrigir", so_musica_se_vazia=False,
                    alterada=True, wpm=150).fala == "Rádio."


# ---------------------------------------------------------------------------------------------
# U5: checagem extra registrada (gancho da F5/F4)
# ---------------------------------------------------------------------------------------------

def test_checagem_extra_registrada_e_chamada_e_remove_a_frase(monkeypatch):
    chamadas = []

    def checar_dado(fala, ctx):
        chamadas.append(fala)
        return [Violacao("tema_sem_dado", "Faz trinta graus agora.", "clima",
                         "Não cite temperatura sem dado verificado.")]

    monkeypatch.setattr("app.live.validacao_fala.CHECAGENS_POS_GERACAO", [*CHECAGENS_POS_GERACAO, checar_dado])
    fala = "Boa tarde. Faz trinta graus agora."
    ctx = _ctx(orcamento=OrcamentoFala(15, 22, 30, None, "observacao", False))
    assert [v.regra for v in validar(fala, ctx, "final")] == ["tema_sem_dado"]
    resultado = corrigir(fala, [], ctx, preservar=[], modo="corrigir", so_musica_se_vazia=False, alterada=False,
                         wpm=150)
    assert (resultado.fala, resultado.acao) == ("Boa tarde.", "mencao_removida")
    assert chamadas == [fala, fala]


def test_checagem_que_quebra_nao_derruba_a_fala():
    def quebrada(fala, ctx):
        raise RuntimeError("boom")

    assert validar("Agora vem Varanda de Pedra.", _ctx(), "final", checagens=[quebrada, checar_musicas])


def test_mencoes_musica_e_o_detector_do_simulador():
    citaveis = [MusicaRef("Estrada de Chão Batido", "Irmãos Taquara", origem="conhecida")]
    mencoes = mencoes_musica("Quem chega agora é Irmãos Taquara, com Estrada de Chão Batido.", citaveis)
    assert [m.rotulo for m in mencoes] == ["Estrada de Chão Batido - Irmãos Taquara"]
    assert confirmada(mencoes[0], ["Estrada de Chão Batido"])
