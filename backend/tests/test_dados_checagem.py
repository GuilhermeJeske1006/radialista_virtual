"""U3 da F5 (docs/melhoria-radio/f5/auditoria.md §8): detector de afirmação de dado e checagem da fala.

Inclui o benchmark docs/benchmarks/2026-11-06-formatos/casos.json (dado_sem_fonte 6/6, dado_vencido 1/1, nenhum falso
positivo nas outras falas), as falas gravadas na simulação da linha de base e as falas de resposta dos goldens de
/proxima (nenhum achado: a F5 não muda nada sem dado)."""

import datetime
import json
import pathlib
from zoneinfo import ZoneInfo

import pytest

from app.dados import checagem as c
from app.dados.texto_externo import limpar
from app.dados.verificavel import DadoVerificavel

TZ = "America/Sao_Paulo"
LOCAL = ZoneInfo(TZ)
AGORA = datetime.datetime(2026, 11, 10, 14, 30, tzinfo=LOCAL)
RAIZ = pathlib.Path(__file__).resolve().parents[2]
CASOS = RAIZ / "docs" / "benchmarks" / "2026-11-06-formatos" / "casos.json"
SIMULACOES = RAIZ / "docs" / "melhoria-radio" / "f5" / "simulacao" / "linha_de_base"
GOLDENS = pathlib.Path(__file__).resolve().parent / "fixtures" / "caracterizacao_proxima"


def _dado(tipo="clima", valor="vinte e seis graus, céu limpo", minutos=10, validade_min=60, **campos):
    base = dict(id=f"{tipo}:1", tipo=tipo, valor=valor, fonte="Fonte de teste",
                atualizado_em=AGORA - datetime.timedelta(minutes=minutos),
                valido_ate=AGORA - datetime.timedelta(minutes=minutos) + datetime.timedelta(minutes=validade_min))
    base.update(campos)
    return DadoVerificavel(**base)


def _regras(fala, dados=(), **kw):
    return [v.regra for v in c.checar_fala(fala, list(dados), AGORA, TZ, **kw)]


def _categorias(texto):
    return [a.categoria for a in c.afirmacoes(texto)]


# --- detector, por categoria ---------------------------------------------------------------------------------

@pytest.mark.parametrize("texto,categoria", [
    ("Faz trinta graus lá fora.", "temperatura"),
    ("Os termômetros marcam 28 graus.", "temperatura"),
    ("Está 30° agora.", "temperatura"),
    ("Menos dois graus na serra.", "temperatura"),
    ("Lá fora está chovendo.", "condicao_tempo"),
    ("Faz um calor danado hoje.", "condicao_tempo"),
    ("O céu está limpo nesta tarde.", "condicao_tempo"),
    ("Vai chover no fim da tarde.", "previsao"),
    ("A previsão do tempo é de frio.", "previsao"),
    ("Uma frente fria chega amanhã.", "previsao"),
    ("O trânsito está parado na avenida principal.", "transito"),
    ("A ponte foi interditada para obra.", "transito"),
    ("Tem congestionamento na saída da cidade.", "transito"),
    ("A BR está liberada.", "transito"),
    ("O time está ganhando por dois a zero.", "placar"),
    ("A partida terminou 2 x 1.", "placar"),
    ("Todas as lojas com desconto de metade do preço.", "comercial"),
    ("Entrada grátis no sábado.", "comercial"),
    ("Você pode ganhar o prêmio!", "comercial"),
    ("Trinta por cento de abatimento, só hoje.", "comercial"),
    ("Tudo com 30% a menos.", "comercial"),
])
def test_positivos_por_categoria(texto, categoria):
    assert categoria in _categorias(texto)


@pytest.mark.parametrize("texto", [
    "Você está na Rádio Serra Clara, e a tarde segue com música.",
    "Futebol é assunto que rende conversa boa em qualquer esquina.",
    "Se for sair de carro, vai com calma e atenção.",
    "Para quem está no trânsito agora, um abraço.",
    "A viagem leva de duas a três horas.",
    "Ganhei dois a três presentes no aniversário.",
    "O sorteio fica para quem mandar mensagem.",
    "Agora são catorze e trinta e cinco aqui na rádio.",
    "A gente toca de tudo um pouco, de três a quatro músicas seguidas.",
    "A rua da minha infância tinha um pé de manga enorme.",
    "Uma canção que fala de chuva e de saudade.",
])
def test_negativos(texto):
    assert c.afirmacoes(texto) == []


def test_uma_afirmacao_por_categoria_e_frase_com_numeros():
    achadas = c.afirmacoes("Faz vinte e seis graus. O placar está dois a um para o time da casa.")
    assert [(a.categoria, a.numeros) for a in achadas] == [("temperatura", (26,)), ("placar", (2, 1))]
    assert achadas[0].frase == "Faz vinte e seis graus."


# --- cobertura -------------------------------------------------------------------------------------------

def test_sem_dado_toda_categoria_vira_sem_fonte():
    fala = ("Faz trinta graus lá fora. Está chovendo. Vai chover forte. O trânsito está parado na avenida. "
            "O time está ganhando por dois a zero. Tudo com desconto.")
    violacoes = c.checar_fala(fala, [], AGORA, TZ)
    assert [v.regra for v in violacoes] == ["dado_sem_fonte"] * 6
    assert [v.ref_id for v in violacoes] == ["temperatura", "condicao_tempo", "previsao", "transito", "placar",
                                             "comercial"]
    assert all(v.remediacao == "remover_frase" and v.instrucao_retry for v in violacoes)


def test_temperatura_com_numero_igual_passa_e_diferente_nao():
    clima = _dado()
    assert _regras("Segundo o serviço de meteorologia, faz vinte e seis graus.", [clima]) == []
    assert _regras("Faz trinta e dois graus.", [clima]) == ["dado_sem_fonte"]


def test_temperatura_em_algarismo_no_dado():
    assert _regras("Faz vinte e três graus.", [_dado(valor="23°C, céu limpo")]) == []


def test_condicao_coberta_por_clima_valido():
    assert _regras("O céu está limpo.", [_dado()]) == []


def test_previsao_coberta_por_aviso_com_chuva_no_texto():
    aviso = _dado(tipo="aviso", valor="Defesa Civil alerta para chuva forte à tarde.")
    assert _regras("Segundo a Defesa Civil, vai chover forte à tarde.", [aviso]) == []
    assert _regras("Vai chover forte à tarde.", [_dado(tipo="noticia", valor="Feira abre sábado.")]) == \
        ["dado_sem_fonte"]


def test_transito_coberto_por_dado_de_transito_ou_pelo_texto():
    assert _regras("A avenida principal está interditada.", [_dado(tipo="transito", valor="Obra fecha avenida.")]) \
        == []
    noticia = _dado(tipo="noticia", valor="Ponte do Rio Claro fica interditada para obra até sexta.")
    assert _regras("A ponte está interditada para obra.", [noticia]) == []


def test_placar_com_o_mesmo_par_passa_e_outro_nao():
    esporte = _dado(tipo="esporte", valor="O Serrano venceu o Vale por 2 a 1 neste domingo.")
    assert _regras("O Serrano venceu por dois a um.", [esporte]) == []
    assert _regras("O Serrano venceu por três a zero.", [esporte]) == ["dado_sem_fonte"]


def test_comercial_so_pelo_gatilho_no_texto_ou_cobertura_extra():
    promocao = _dado(tipo="noticia", valor="Comércio faz semana de descontos no centro.")
    assert _regras("O comércio está com desconto no centro.", [promocao]) == []
    assert _regras("Participe e concorra a um prêmio.", []) == ["dado_sem_fonte"]
    assert _regras("Participe e concorra a um prêmio.", [], cobertura_extra=["Sorteio de prêmio toda sexta"]) == []


def test_dado_sem_fonte_ou_nao_aprovado_nao_cobre():
    assert _regras("Faz vinte e seis graus.", [_dado(fonte="")]) == ["dado_sem_fonte"]
    assert _regras("Faz vinte e seis graus.", [_dado(aprovado=False)]) == ["dado_sem_fonte"]


# --- vencido -------------------------------------------------------------------------------------------------

def _vencido():
    return _dado(valor="vinte e dois graus", minutos=150, validade_min=60, id="clima:campo-alegre")


def test_vencido_sem_horario_vira_dado_vencido():
    violacoes = c.checar_fala("Faz vinte e dois graus agora na cidade.", [_vencido()], AGORA, TZ)
    assert [(v.regra, v.ref_id) for v in violacoes] == [("dado_vencido", "clima:campo-alegre")]
    assert "na última atualização" in violacoes[0].instrucao_retry and "ao meio-dia" in violacoes[0].instrucao_retry


@pytest.mark.parametrize("fala", [
    "Na última atualização, ao meio-dia, o serviço de meteorologia marcava vinte e dois graus.",
    "O boletim das doze horas registrava vinte e dois graus.",
    "Ao meio-dia faziam vinte e dois graus.",
])
def test_vencido_com_horario_passa(fala):
    assert _regras(fala, [_vencido()]) == []


def test_valido_mais_velho_que_a_idade_maxima_precisa_de_horario():
    velho = _dado(valor="vinte e seis graus", minutos=70, validade_min=120)
    assert _regras("Faz vinte e seis graus.", [velho]) == ["dado_vencido"]
    assert _regras("Na última atualização faziam vinte e seis graus.", [velho]) == []
    transito = _dado(tipo="transito", valor="Avenida com trânsito parado.", minutos=40, validade_min=600)
    assert _regras("O trânsito está parado na avenida.", [transito]) == ["dado_vencido"]


def test_idade_maxima_so_na_afirmacao_de_momento():
    obra = _dado(tipo="aviso", valor="obra na rua principal", minutos=400, validade_min=60 * 24 * 10)
    assert _regras("Segundo a prefeitura, o trânsito vai mudar na rua principal por causa de uma obra.", [obra]) == []
    jogo = _dado(tipo="esporte", valor="O Serrano venceu o Vale por 2 a 1.", minutos=60, validade_min=600)
    assert _regras("O Serrano venceu por dois a um.", [jogo]) == []
    assert _regras("O Serrano está ganhando por dois a um.", [jogo]) == ["dado_vencido"]


def test_vencido_e_valido_juntos_vale_o_valido():
    assert _regras("Faz vinte e dois graus.", [_vencido(), _dado(valor="vinte e dois graus")]) == []


# --- isentas ------------------------------------------------------------------------------------------------

def test_frases_de_ausencia_e_contingencia_isentas():
    assert _regras("Não temos atualização confirmada sobre trânsito agora.") == []
    assert _regras("Sem informação confirmada sobre o placar do jogo de dois a um.") == []
    assert _regras("A ponte está fechada.", isentas=["A ponte está fechada."]) == []


def test_reorientacao_neutra_isenta():
    assert _regras("Você está no Tarde Viva, na Rádio Teste.") == []


# --- benchmark --------------------------------------------------------------------------------------------

def _dados_do_caso(contexto: dict) -> list[DadoVerificavel]:
    dados = []
    for i, d in enumerate(contexto.get("dados") or []):
        texto, _ = limpar(d.get("valor") or d.get("titulo") or "")
        dados.append(DadoVerificavel(
            id=f"caso:{i}", tipo=d["tipo"], valor=texto, fonte=d.get("fonte", ""),
            atualizado_em=datetime.datetime.fromisoformat(d["atualizado_em"]) if d.get("atualizado_em") else None,
            valido_ate=datetime.datetime.fromisoformat(d["valido_ate"]) if d.get("valido_ate") else None))
    return dados


def test_benchmark_casos_json():
    casos = json.loads(CASOS.read_text(encoding="utf-8"))["casos"]
    contagem = {"sem_fonte": [0, 0], "vencido": [0, 0]}
    falsos, perdidos, total = [], [], 0
    for caso in casos:
        contexto = caso["contexto"]
        agora = datetime.datetime.fromisoformat(contexto.get("agora") or "2026-11-10T14:00:00-03:00")
        dados = _dados_do_caso(contexto)
        for fala in caso["falas_rotuladas"]:
            total += 1
            regras = {v.regra for v in c.checar_fala(fala["texto"], dados, agora, TZ)}
            for regra, chave in (("dado_sem_fonte", "sem_fonte"), ("dado_vencido", "vencido")):
                esperado, achou = bool(fala["esperado"][regra]), regra in regras
                if esperado:
                    contagem[chave][1] += 1
                    contagem[chave][0] += achou
                    if not achou:
                        perdidos.append((caso["id"], fala["texto"]))
                elif achou:
                    falsos.append((caso["id"], regra, fala["texto"]))
    assert total == 96  # 35 casos da F0 à F5 e 13 da F6, duas falas cada
    assert contagem == {"sem_fonte": [6, 6], "vencido": [1, 1]}, perdidos
    assert falsos == []


def test_falas_gravadas_da_linha_de_base_nao_tem_achado():
    falas = [e["texto"] for arquivo in sorted(SIMULACOES.rglob("as_run.json"))
             for e in json.loads(arquivo.read_text(encoding="utf-8"))["eventos"]
             if e.get("tipo") == "fala" and e.get("texto")]
    assert len(falas) >= 150
    achados = [(f, a.categoria) for f in falas for a in c.afirmacoes(f)]
    assert achados == []


def test_falas_dos_goldens_so_afirmam_dado_nos_blocos_com_pauta():
    """Só as três notícias com pauta afirmam algo (a ponte liberada), coberto pelo texto da pauta: os goldens ficam
    iguais quando a checagem entra no ar (C1). Os dois goldens de clima da F5 afirmam temperatura com o dado (válido,
    ou vencido com o horário) e passam pela rota sem violação."""
    falas = []
    for arquivo in sorted(GOLDENS.glob("*.json")):
        resposta = json.loads(arquivo.read_text(encoding="utf-8"))["resposta"]
        regras = {v["regra"] for v in (resposta.get("validacao_fala") or {}).get("violacoes", [])}
        assert not regras & {"dado_sem_fonte", "dado_vencido"}, arquivo.stem
        falas += [(arquivo.stem, f) for f in [resposta.get("fala") or ""]
                  + [linha["texto"] for linha in resposta.get("falas") or []] if f]
    assert len(falas) >= 30
    achados = sorted({(nome, a.categoria) for nome, f in falas for a in c.afirmacoes(f)})
    assert achados == [("clima_valido", "temperatura"), ("clima_vencido_com_horario", "temperatura"),
                       ("escalada", "transito"), ("noticia_correcao", "transito"),
                       ("noticia_pauta_com_retry", "transito")]
    pauta = _dado(tipo="noticia", valor="Ponte da Rua Nova é liberada após reparo.")
    for nome, fala in falas:
        if nome in ("escalada", "noticia_correcao", "noticia_pauta_com_retry"):
            assert _regras(fala, [pauta]) == []


def test_cobertura_extra_nao_casa_palavra_curta_pelo_radical():
    """Achado da simulação do cenário dedicado: o radical de "parado" casava "para" no slogan da rádio, e a frase de
    trânsito inventada ia ao ar."""
    fala = "O trânsito está parado na saída da cidade."
    assert _regras(fala, cobertura_extra=["Companhia para o seu dia"]) == ["dado_sem_fonte"]
    assert _regras(fala, cobertura_extra=["Avenida parada por obra, informe da prefeitura"]) == []
    assert _regras("Concorra a prêmios.", cobertura_extra=["Sorteio de prêmio toda sexta"]) == []
    assert _regras("Tudo com desconto.", cobertura_extra=["Semana de descontos"]) == []


def test_vocabulario_de_cobertura_ja_e_radical():
    """"interdi" não pode virar "inter" e casar "interior" ou "internet"."""
    noticia = _dado(tipo="noticia", valor="Escola do interior ganha internet nova.")
    assert _regras("A ponte está interditada.", [noticia]) == ["dado_sem_fonte"]
