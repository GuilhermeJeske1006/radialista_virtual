"""Coerência com o formato (F6, U11 da auditoria §8; §6.14, §9, D20 e D21).

`app.live.formatos.coerencia` é pura e só mede: avisos `fora_da_unidade`, `bloco_fora_do_formato`,
`convite_fora_da_politica`, `tema_revisao` e `reorientacao`, com positivo e negativo para cada um, e as métricas do §9
que decidem `coerencia_automatica`. Nada é reescrito nem removido (D21): no `/proxima` vira só o log
`live_formato_aviso`, com ids e códigos (nunca trecho de fala).
"""

import dataclasses
import json
import pathlib
import re

import pytest

from app.live import formatos as f
from app.live.formatos import FalaNoAr

MUSICAL, POPULAR, VARIEDADES = (f.FORMATOS[i] for i in ("musical_adulto", "popular_sertanejo", "variedades_leves"))
NOMES = ("Tarde Serena", "Rádio Serra Clara")
RAIZ = pathlib.Path(__file__).resolve().parents[2]
FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures" / "programas"


def _fala(bloco="retomada", texto="Você está na Rádio Serra Clara.", duracao_s=9.0, **extra) -> FalaNoAr:
    categoria = extra.pop("categoria", "abertura" if bloco in ("retomada", "identificacao") else bloco)
    return FalaNoAr(bloco=bloco, categoria=categoria, texto=texto, duracao_s=duracao_s, **extra)


def _codigos(formato, fala, nomes=NOMES):
    return [a.codigo for a in f.avisos_da_fala(formato, fala, nomes=nomes)]


# ---------------------------------------------------------------------------------------------------------
# Configuração e catálogo
# ---------------------------------------------------------------------------------------------------------

def test_tolerancia_da_unidade_e_a_do_orcamento():
    from app.config.settings import settings

    assert f.CONFIG_COERENCIA.tolerancia_unidade == settings.fala_tolerancia_orcamento


def test_todo_tema_do_catalogo_tem_palavras_de_deteccao():
    temas = {tema for formato in f.FORMATOS.values() for tema in formato.temas_revisao}
    assert temas <= set(f.CONFIG_COERENCIA.temas)
    assert all(f.CONFIG_COERENCIA.temas[tema] for tema in temas)


def test_limites_do_musical_e_dos_novos():
    assert MUSICAL.limites.sequencia_musical_min_s == 540 and MUSICAL.limites.interrupcoes_max_hora == 10
    assert {"comentario", "noticia"} <= set(MUSICAL.limites.categorias_fora)
    for formato in (POPULAR, VARIEDADES, f.FORMATOS["padrao"]):
        assert formato.limites == f.LimitesCoerencia()


# ---------------------------------------------------------------------------------------------------------
# Avisos por fala: positivo e negativo de cada um
# ---------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("formato, bloco, dentro, abaixo, acima", [
    (MUSICAL, "retomada", 9.0, 4.0, 15.0),            # 6 a 12 s, tolerância de 15% em cima
    (POPULAR, "comentario", 35.0, 12.0, 75.0),        # 20 a 60 s
    (VARIEDADES, "chamada_ouvinte", 40.0, 10.0, 80.0),  # 20 a 60 s
])
def test_fora_da_unidade(formato, bloco, dentro, abaixo, acima):
    texto = "Você está no Tarde Serena, na Rádio Serra Clara."
    assert "fora_da_unidade" not in _codigos(formato, _fala(bloco, texto, dentro))
    assert "fora_da_unidade" in _codigos(formato, _fala(bloco, texto, abaixo))
    assert "fora_da_unidade" in _codigos(formato, _fala(bloco, texto, acima))
    # Dentro da tolerância de cima: não avisa.
    maximo = formato.unidades[f.papel_do_bloco(formato, bloco, False)].max_s
    assert "fora_da_unidade" not in _codigos(formato, _fala(bloco, texto, maximo * 1.1))


def test_fora_da_unidade_ignora_fala_reduzida_pelo_relogio_e_o_padrao():
    # O relógio deu só 8 s a um comentário do popular (unidade 20 a 60): a fala curta é do relógio, não do formato.
    assert "fora_da_unidade" not in _codigos(POPULAR, _fala("comentario", "Seguimos.", 5.0, teto_s=8.0))
    assert "fora_da_unidade" in _codigos(POPULAR, _fala("comentario", "Seguimos.", 5.0, teto_s=60.0))
    assert _codigos("padrao", _fala("comentario", "Seguimos.", 200.0)) == []


def test_quadro_do_variedades_usa_a_unidade_de_quadro():
    longa = _fala("Cantinho da Casa", "Hoje o tema é a gaveta.", 150.0, categoria="comentario")
    assert "fora_da_unidade" in _codigos(VARIEDADES, longa)  # comentário: até 60 s
    assert "fora_da_unidade" not in _codigos(VARIEDADES, dataclasses.replace(longa, quadro=True))


def test_bloco_fora_do_formato():
    comentario = _fala("comentario", "Que tarde boa para conversar sobre a feira.", 15.0)
    assert "bloco_fora_do_formato" in _codigos(MUSICAL, comentario)
    assert "bloco_fora_do_formato" in _codigos(MUSICAL, _fala("noticia", "A ponte foi liberada.", 15.0))
    assert "bloco_fora_do_formato" not in _codigos(MUSICAL, _fala("retomada", "Você está na Rádio Serra Clara."))
    assert "bloco_fora_do_formato" not in _codigos(POPULAR, comentario)


@pytest.mark.parametrize("texto", [
    "Mande sua mensagem pelo WhatsApp da rádio.",
    "Quer mandar um alô para alguém? A rádio recebe pelo WhatsApp.",
    "Conta de onde você está ouvindo, pelo WhatsApp da rádio.",
    "O WhatsApp da Rádio Serra Clara está aberto para o seu recado.",
    "Qual música você gostaria de ouvir por aqui? Mande seu pedido pelo canal da rádio.",
])
def test_convite_detectado(texto):
    assert f.convites_no_texto(texto) >= 1


@pytest.mark.parametrize("texto", [
    "Joana pediu pelo WhatsApp, e toca agora Rua das Acácias.",
    "Seu Valdir passou pelo WhatsApp e deixou um recado.",
    "Obrigado a quem mandou recado e a quem só ouviu.",
    "Você está na Rádio Serra Clara.",
    "A conta de luz chega mais cedo neste mês.",
])
def test_nao_e_convite(texto):
    assert f.convites_no_texto(texto) == 0


def test_convite_fora_da_politica():
    convite = "Você está na Rádio Serra Clara. Mande sua mensagem pelo WhatsApp da rádio."
    assert "convite_fora_da_politica" in _codigos(MUSICAL, _fala("retomada", convite, 9.0))
    assert "convite_fora_da_politica" not in _codigos(MUSICAL, _fala("chamada_ouvinte", convite, 15.0))
    assert "convite_fora_da_politica" in _codigos(VARIEDADES, _fala("comentario", convite, 30.0))
    assert "convite_fora_da_politica" not in _codigos(VARIEDADES, _fala("chamada_ouvinte", convite, 30.0))
    assert "convite_fora_da_politica" not in _codigos(POPULAR, _fala("comentario", convite, 30.0))


def test_tema_revisao():
    remedio = "Quem toma remédio para pressão deve conversar com o médico antes de mudar a dose."
    avisos = f.avisos_da_fala(POPULAR, _fala("comentario", remedio, 30.0), nomes=NOMES)
    assert [(a.codigo, a.detalhe) for a in avisos if a.codigo == "tema_revisao"] == \
        [("tema_revisao", "saúde e medicamento")]
    assert "tema_revisao" not in _codigos(POPULAR, _fala("comentario", "A tarde está bonita para um café.", 30.0))
    assert "tema_revisao" in _codigos(VARIEDADES, _fala("comentario", "Dá para emagrecer com essa dieta.", 30.0))
    # Tema que o formato não declara não avisa (aposta é do popular, não do musical).
    aposta = "Fazer aposta no fim de semana virou moda."
    assert "tema_revisao" in _codigos(POPULAR, _fala("comentario", aposta, 30.0))
    assert "tema_revisao" not in _codigos(MUSICAL, _fala("retomada", aposta, 9.0))


def test_reorientacao_com_memoria_da_ultima():
    """A frequência é do formato (reorientacao_s): o aviso só sai com a memória de quando foi a última reorientação,
    depois de fator × reorientacao_s, numa fala que também não diz o nome do programa nem da rádio."""
    sem_nome, com_nome = "Seguimos juntos nesta tarde.", "Você está no Tarde Serena."
    atrasada = 1.5 * MUSICAL.reorientacao_s + 1
    assert "reorientacao" in _codigos(MUSICAL, _fala("retomada", sem_nome, 8.0, desde_reorientacao_s=atrasada))
    assert "reorientacao" not in _codigos(MUSICAL, _fala("retomada", com_nome, 8.0, desde_reorientacao_s=atrasada))
    assert "reorientacao" not in _codigos(MUSICAL, _fala("retomada", sem_nome, 8.0, desde_reorientacao_s=600))
    assert "reorientacao" not in _codigos(MUSICAL, _fala("retomada", sem_nome, 8.0))  # sem memória (/proxima)
    assert "reorientacao" in _codigos(POPULAR, _fala("comentario", sem_nome, 30.0, desde_reorientacao_s=1801))
    assert "reorientacao" not in _codigos(POPULAR, _fala("comentario", sem_nome, 30.0, desde_reorientacao_s=1799))
    assert "reorientacao" not in _codigos("padrao", _fala("retomada", sem_nome, 8.0, desde_reorientacao_s=9999))
    assert "reorientacao" not in _codigos(MUSICAL, _fala("retomada", sem_nome, 8.0, desde_reorientacao_s=atrasada),
                                          nomes=())


def test_duracao_desconhecida_nao_avalia_a_unidade():
    assert "fora_da_unidade" not in _codigos(MUSICAL, _fala("retomada", "Você está no Tarde Serena.", None))


def test_avisos_nunca_levam_trecho_da_fala():
    texto = "Mande sua mensagem pelo WhatsApp da rádio. Quem toma remédio deve falar com o médico."
    for aviso in f.avisos_da_fala(MUSICAL, _fala("comentario", texto, 60.0), nomes=NOMES):
        assert aviso.detalhe not in texto or len(aviso.detalhe) < 25
        assert "WhatsApp" not in aviso.detalhe and "remédio" not in aviso.detalhe


# ---------------------------------------------------------------------------------------------------------
# coerencia(): métricas da hora e coerencia_automatica
# ---------------------------------------------------------------------------------------------------------

def _hora_musical(reorientar_a_cada=1):
    falas, eventos = [], []
    for i, inicio in enumerate(range(0, 3600, 600)):
        texto = "Você está na Rádio Serra Clara." if i % reorientar_a_cada == 0 else "Seguimos."
        bloco = "abertura" if i == 0 else "retomada"
        falas.append(_fala(bloco, texto, 25.0 if i == 0 else 8.0, inicio_s=float(inicio), primeira=i == 0))
        eventos.append(("fala", float(inicio), inicio + (25.0 if i == 0 else 8.0)))
        eventos.append(("musica", inicio + 30.0, inicio + 590.0))
    return falas, eventos


def test_coerencia_de_uma_hora_musical_dentro_dos_limites():
    falas, eventos = _hora_musical()
    relatorio = f.coerencia(MUSICAL, falas, duracao_programa_s=3600, nomes=NOMES, eventos=eventos,
                            instrucao={"blocos": 6, "com_formato": 6, "com_outro": 0})
    assert relatorio.formato == "musical_adulto"
    assert relatorio.fala_pct == round(100 * (25 + 5 * 8) / 3600, 1)
    assert relatorio.instrucao_no_prompt_pct == 100.0 and relatorio.instrucao_de_outro_formato == 0
    assert relatorio.maior_sequencia_musical_s == 560.0 and relatorio.interrupcoes_por_hora == 6.0
    assert relatorio.reorientacoes == 6 and relatorio.maior_intervalo_sem_reorientacao_s == 600.0
    assert relatorio.convites == 0 and relatorio.convites_fora_da_politica == 0
    assert relatorio.temas_revisao_no_ar == 0 and relatorio.falas_fora_da_unidade == 0
    assert all(relatorio.itens.values()) and relatorio.coerencia_automatica is True


def test_coerencia_falha_cada_item():
    falas, eventos = _hora_musical(reorientar_a_cada=4)  # nomes só em 0 e 2400 s
    relatorio = f.coerencia(MUSICAL, falas, duracao_programa_s=3600, nomes=NOMES, eventos=eventos,
                            instrucao={"blocos": 6, "com_formato": 5, "com_outro": 1})
    assert relatorio.maior_intervalo_sem_reorientacao_s == 2400.0
    assert relatorio.itens["reorientacao"] is False
    assert relatorio.itens["instrucao_no_prompt"] is False and relatorio.itens["instrucao_de_outro_formato"] is False
    assert relatorio.coerencia_automatica is False
    assert [a.codigo for a in relatorio.avisos].count("reorientacao") >= 1
    # Pouca música entre falas: a sequência musical e as interrupções saem do limite do musical.
    picado = [("fala", float(t), t + 8.0) if i % 2 == 0 else ("musica", float(t), t + 200.0)
              for i, t in enumerate(range(0, 3600, 210))]
    falas_picado = [_fala("retomada", "Você está na Rádio Serra Clara.", 8.0, inicio_s=float(t))
                    for t in range(0, 3600, 300)]
    picado_rel = f.coerencia(MUSICAL, falas_picado, duracao_programa_s=3600, nomes=NOMES, eventos=picado)
    assert picado_rel.itens["maior_sequencia_musical"] is False and picado_rel.itens["interrupcoes_por_hora"] is False


def test_coerencia_fala_pct_e_faixa_do_formato():
    falas = [_fala("comentario", "Você está no Tarde Serena.", 30.0, inicio_s=float(t)) for t in range(0, 3600, 600)]
    popular = f.coerencia(POPULAR, falas, duracao_programa_s=3600, nomes=NOMES)
    assert popular.fala_pct == 5.0 and popular.itens["fala_pct"] is True
    variedades = f.coerencia(VARIEDADES, falas, duracao_programa_s=3600, nomes=NOMES)
    assert variedades.itens["fala_pct"] is False  # 5% < 15%


def test_coerencia_do_padrao_so_confere_instrucao():
    falas = [_fala("comentario", "Mande sua mensagem pelo WhatsApp.", 200.0, inicio_s=0.0)]
    relatorio = f.coerencia("padrao", falas, duracao_programa_s=3600, nomes=NOMES,
                            instrucao={"blocos": 1, "com_formato": 0, "com_outro": 0})
    assert relatorio.avisos == () and relatorio.coerencia_automatica is True
    assert relatorio.instrucao_no_prompt_pct == 0.0
    assert f.coerencia("padrao", falas, duracao_programa_s=3600,
                       instrucao={"blocos": 1, "com_formato": 1, "com_outro": 0}).coerencia_automatica is False


def test_como_dict_e_serializavel():
    falas, eventos = _hora_musical()
    dados = f.coerencia(MUSICAL, falas, duracao_programa_s=3600, nomes=NOMES, eventos=eventos).como_dict()
    json.dumps(dados, ensure_ascii=False)
    for chave in ("fala_pct", "falas_fora_da_unidade", "blocos_fora_do_formato", "maior_sequencia_musical_s",
                  "interrupcoes_por_hora", "reorientacoes", "maior_intervalo_sem_reorientacao_s", "convites",
                  "convites_fora_da_politica", "temas_revisao_no_ar", "coerencia_automatica", "avisos", "itens"):
        assert chave in dados, chave
    assert all(set(a) == {"codigo", "fala", "detalhe"} for a in dados["avisos"])


# ---------------------------------------------------------------------------------------------------------
# Falsos positivos: banco de falas do dublê e textos das fixtures (as linhas de base)
# ---------------------------------------------------------------------------------------------------------

def _frases_do_banco() -> list[str]:
    from scripts.simulacao import banco_falas

    frases = []
    for modelo in banco_falas.BANCO.values():
        for parte in modelo.values():
            frases.extend(parte)
    return frases


def test_banco_do_duble_e_fixtures_nao_disparam_tema_de_revisao():
    temas = tuple(f.CONFIG_COERENCIA.temas)
    textos = _frases_do_banco()
    for caminho in FIXTURES.glob("*.json"):
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        textos += [p["texto"] for p in dados.get("patrocinadores", [])] + [v["texto"] for v in dados.get("vinhetas", [])]
        textos += [p["mensagem"] for p in dados.get("pedidos", [])] + [p["texto_autorizado"] for p in dados.get("pedidos", [])]
        textos += [i["frase"] for i in dados.get("injecoes", []) if i.get("frase")]
        textos += [t for pool in dados["programa"].get("quadros_fixos", {}).values() for t in pool]
    achados = {texto: f.temas_no_texto(texto, temas) for texto in textos}
    assert {t: v for t, v in achados.items() if v} == {}


def test_convites_do_banco_so_nos_modelos_de_chamada_e_um_do_quadro():
    """Registro (fato 7 da auditoria): o banco do dublê tem convite nos modelos de chamada e uma frase de convite no
    meio do quadro, que o variedades (convite só na chamada) acusa se ela for ao ar."""
    from scripts.simulacao import banco_falas

    fora = []
    for nome, modelo in banco_falas.BANCO.items():
        if nome.startswith("chamada"):
            continue
        for parte in modelo.values():
            fora += [frase for frase in parte if f.convites_no_texto(frase)]
    assert fora == ["Quem testar pode contar pelo WhatsApp da rádio como foi."]


def test_padroes_de_convite_compilam():
    for padrao in f.CONFIG_COERENCIA.convite:
        re.compile(padrao)


# ---------------------------------------------------------------------------------------------------------
# Benchmark (commit 8): casos F6 em docs/benchmarks/2026-11-06-formatos/casos.json
# ---------------------------------------------------------------------------------------------------------

CASOS = RAIZ / "docs" / "benchmarks" / "2026-11-06-formatos" / "casos.json"


def _fala_do_caso(caso: dict, texto: str, wpm: float) -> tuple[FalaNoAr, tuple[str, ...]]:
    """A fala do caso para a coerência. Sem `formato_coerencia` (casos de outras frentes), só os avisos do texto:
    a duração e a memória de reorientação não são conhecidas."""
    from app.live.formato import contar_palavras
    from scripts.simulacao.dubles import categoria_do_tipo

    contexto = caso["contexto"].get("formato_coerencia") or {}
    fixture = json.loads((FIXTURES / f"{caso['formato']}.json").read_text(encoding="utf-8"))
    nomes = tuple(contexto.get("nomes") or (fixture["programa"]["nome"], fixture["conta"]["nome_radio"]))
    fala = FalaNoAr(
        bloco=caso["bloco"], categoria=categoria_do_tipo(caso["bloco"]), texto=texto,
        duracao_s=contar_palavras(texto) / wpm * 60 if contexto.get("medir_unidade") else None,
        primeira=bool(contexto.get("primeira")), quadro=bool(contexto.get("quadro")),
        retorno=bool(contexto.get("retorno")), desde_reorientacao_s=contexto.get("segundos_desde_reorientacao"),
    )
    return fala, nomes


def test_benchmark_coerencia_acha_todos_os_positivos_sem_falso_positivo():
    dados = json.loads(CASOS.read_text(encoding="utf-8"))
    wpm = dados["regras"]["wpm_referencia"]
    assert set(f.AVISOS) <= set(dados["regras"]["esperado"])
    acertos, perdidos, falsos = {codigo: 0 for codigo in f.AVISOS}, [], []
    casos_f6 = [c for c in dados["casos"] if "F6" in c["frentes"]]
    for caso in dados["casos"]:
        for rotulada in caso["falas_rotuladas"]:
            fala, nomes = _fala_do_caso(caso, rotulada["texto"], wpm)
            achados = {a.codigo for a in f.avisos_da_fala(caso["formato"], fala, nomes=nomes)}
            esperados = {codigo for codigo in f.AVISOS if rotulada["esperado"].get(codigo)}
            for codigo in achados & esperados:
                acertos[codigo] += 1
            perdidos += [(caso["id"], codigo) for codigo in esperados - achados]
            falsos += [(caso["id"], codigo) for codigo in achados - esperados]
    assert perdidos == [] and falsos == []
    assert all(acertos[codigo] >= 2 for codigo in f.AVISOS), acertos
    # Positivo e negativo por formato e "coerencia" como dimensão de todo caso F6.
    assert {c["formato"] for c in casos_f6} == {"musical_adulto", "popular_sertanejo", "variedades_leves"}
    for formato in ("musical_adulto", "popular_sertanejo", "variedades_leves"):
        rotulos = [any(r["esperado"].get(codigo) for codigo in f.AVISOS)
                   for c in casos_f6 if c["formato"] == formato for r in c["falas_rotuladas"]]
        assert True in rotulos and False in rotulos, formato
    assert all("coerencia" in c["dimensoes"] for c in casos_f6)
