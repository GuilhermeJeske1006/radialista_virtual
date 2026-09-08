
import pytest
from freezegun import freeze_time

from app.llm.prompt_builder import ParticipantePrograma, montar_system_prompt
from app.models.account import Account
from app.models.programa import Programa
from app.models.radio_config import RadioConfig


@pytest.fixture(autouse=True)
def _sem_clima_real(monkeypatch):
    monkeypatch.setattr("app.llm.prompt_builder.obter_clima_atual", lambda cidade: None)


def _account(**kwargs):
    padrao = dict(nome_radio="Radio Teste")
    padrao.update(kwargs)
    return Account(**padrao)


def _radialista(**kwargs):
    padrao = dict(nome_locutor="Ze do Radio", personalidade="", timezone="America/Sao_Paulo")
    padrao.update(kwargs)
    return RadioConfig(**padrao)


def _programa(**kwargs):
    padrao = dict(
        nome="Programa Principal",
        tom="animado",
        topicos_permitidos=[],
        topicos_proibidos=[],
        generos_musicais=[],
        musicas_permitidas=[],
        musicas_bloqueadas=[],
        criterios_busca_musicas="",
        assuntos_ao_vivo=[],
        tipos_noticias=[],
        fontes_noticias=[],
        pode_pesquisar=False,
        fontes_pesquisa=[],
        instrucoes_pesquisa="",
        estrutura_blocos=[],
        ia_pode_adicionar_blocos=True,
        descricao="",
    )
    padrao.update(kwargs)
    return Programa(**padrao)


@freeze_time("2026-08-10 15:00:00")
def test_prompt_single_voz_inclui_nome_do_locutor_e_da_radio():
    prompt = montar_system_prompt(_account(), _radialista(), _programa())
    assert "Ze do Radio" in prompt
    assert "Radio Teste" in prompt
    assert "Programa Principal" in prompt


@freeze_time("2026-08-10 15:00:00")
def test_prompt_inclui_personalidade_quando_definida():
    radialista = _radialista(personalidade="animado e brincalhao")
    prompt = montar_system_prompt(_account(), radialista, _programa())
    assert "animado e brincalhao" in prompt


@freeze_time("2026-08-10 15:00:00")
def test_prompt_inclui_detalhe_de_conhecimento_local_quando_definido():
    account = _account(
        conhecimento_local={"bairros": ["Centro"], "pontos_referencia": [], "eventos_recorrentes": [], "gentilico": ""}
    )
    prompt = montar_system_prompt(account, _radialista(), _programa(id=1))
    assert "Centro" in prompt


@freeze_time("2026-08-10 15:00:00")
def test_prompt_sem_conhecimento_local_nao_quebra():
    prompt = montar_system_prompt(_account(), _radialista(), _programa(id=1))
    assert "Ze do Radio" in prompt


@freeze_time("2026-08-10 15:00:00")
def test_prompt_inclui_historia_da_radio_quando_definida():
    account = _account(biblia_radio={"historia": "Fundada em 1998 por seu Ze.", "rotina": [], "programas_grade": []})
    prompt = montar_system_prompt(account, _radialista(), _programa(id=1))
    assert "Fundada em 1998 por seu Ze." in prompt


@freeze_time("2026-08-10 15:00:00")
def test_prompt_inclui_detalhe_de_rotina_da_radio_quando_definida():
    account = _account(
        biblia_radio={"historia": "", "rotina": ["toda sexta tem jogo do time local"], "programas_grade": []}
    )
    prompt = montar_system_prompt(account, _radialista(), _programa(id=1))
    assert "toda sexta tem jogo do time local" in prompt


@freeze_time("2026-08-10 15:00:00")
def test_prompt_sem_biblia_radio_nao_quebra():
    prompt = montar_system_prompt(_account(), _radialista(), _programa(id=1))
    assert "Ze do Radio" in prompt


@freeze_time("2026-08-10 15:00:00")
def test_prompt_inclui_traco_marcante_quando_definido():
    radialista = _radialista(tracos_marcantes=["sempre implica com segunda-feira"])
    prompt = montar_system_prompt(_account(), radialista, _programa(id=1))
    assert "sempre implica com segunda-feira" in prompt


@freeze_time("2026-08-10 15:00:00")
def test_prompt_inclui_fato_do_dia_quando_definido_e_e_estavel_na_mesma_sessao():
    radialista = _radialista(id=7, fatos_do_dia=["hoje eu vim de bicicleta"])
    programa = _programa(id=1)
    primeiro = montar_system_prompt(_account(), radialista, programa)
    segundo = montar_system_prompt(_account(), radialista, programa)
    assert "hoje eu vim de bicicleta" in primeiro
    assert "hoje eu vim de bicicleta" in segundo


@freeze_time("2026-08-10 15:00:00")
def test_prompt_inclui_colega_de_equipe_quando_definido():
    account = _account(biblia_radio={"equipe": ["Marcos, técnico de som"]})
    prompt = montar_system_prompt(account, _radialista(), _programa(id=1))
    assert "Marcos, técnico de som" in prompt


@freeze_time("2026-08-10 15:00:00")
def test_prompt_inclui_habito_de_trabalho_quando_definido():
    account = _account(biblia_radio={"habitos_trabalho": ["confere o trânsito antes de entrar no ar"]})
    prompt = montar_system_prompt(account, _radialista(), _programa(id=1))
    assert "confere o trânsito antes de entrar no ar" in prompt


@freeze_time("2026-08-10 15:00:00")
def test_prompt_comenta_clima_com_tom_regional_quando_ha_clima(monkeypatch):
    monkeypatch.setattr("app.llm.prompt_builder.obter_clima_atual", lambda cidade: "23°C, ensolarado")
    account = _account(cidade="Porto Alegre")
    prompt = montar_system_prompt(account, _radialista(), _programa(id=1))
    assert "tom regional" in prompt


@freeze_time("2026-08-10 15:00:00")
def test_prompt_multi_voz_inclui_traco_e_fato_do_dia_por_participante():
    dono = _radialista(id=1, nome_locutor="Ze", tracos_marcantes=["odeia segunda-feira, sempre brinca disso"])
    convidado = _radialista(id=2, nome_locutor="Maria", fatos_do_dia=["hoje é aniversário dela"])
    roster = [
        ParticipantePrograma(dono, "Apresentador principal", "sempre animado"),
        ParticipantePrograma(convidado, "Comentarista", "mais calma"),
    ]
    prompt = montar_system_prompt(_account(), dono, _programa(id=1), roster=roster)
    assert "odeia segunda-feira, sempre brinca disso" in prompt
    assert "hoje é aniversário dela" in prompt


@freeze_time("2026-08-10 15:00:00")
def test_prompt_multi_voz_lista_todos_os_participantes():
    dono = _radialista(nome_locutor="Ze")
    convidado = _radialista(nome_locutor="Maria")
    roster = [
        ParticipantePrograma(dono, "Apresentador principal", "sempre animado"),
        ParticipantePrograma(convidado, "Comentarista", "mais calma"),
    ]
    prompt = montar_system_prompt(_account(), dono, _programa(), roster=roster)
    assert "Ze" in prompt
    assert "Maria" in prompt
    assert '"linhas"' in prompt


@freeze_time("2026-08-10 15:00:00")
def test_prompt_com_um_unico_participante_no_roster_nao_e_multi_voz():
    dono = _radialista(nome_locutor="Ze")
    roster = [ParticipantePrograma(dono, "Apresentador principal", "")]
    prompt = montar_system_prompt(_account(), dono, _programa(), roster=roster)
    assert '"linhas"' not in prompt


@freeze_time("2026-08-10 15:00:00")
def test_prompt_inclui_topicos_proibidos_quando_definidos():
    programa = _programa(topicos_proibidos=["politica", "religiao"])
    prompt = montar_system_prompt(_account(), _radialista(), programa)
    assert "politica, religiao" in prompt


@freeze_time("2026-08-10 15:00:00")
def test_prompt_inclui_pesquisa_habilitada():
    programa = _programa(pode_pesquisar=True, fontes_pesquisa=["g1.com"])
    prompt = montar_system_prompt(_account(), _radialista(), programa)
    assert "Pesquisa externa habilitada" in prompt
    assert "g1.com" in prompt


@freeze_time("2026-08-10 15:00:00")
def test_prompt_pesquisa_desabilitada_por_padrao():
    prompt = montar_system_prompt(_account(), _radialista(), _programa())
    assert "Pesquisa externa desabilitada" in prompt


@freeze_time("2026-08-10 15:00:00")
def test_prompt_inclui_estrutura_de_blocos_quando_ia_pode_adicionar():
    programa = _programa(estrutura_blocos=["abertura", "musica"], ia_pode_adicionar_blocos=True)
    prompt = montar_system_prompt(_account(), _radialista(), programa)
    assert "abertura -> musica" in prompt
    assert "fique livre pra inserir blocos extras" in prompt


@freeze_time("2026-08-10 15:00:00")
def test_prompt_estrutura_de_blocos_estrita_quando_ia_nao_pode_adicionar():
    programa = _programa(estrutura_blocos=["abertura", "musica"], ia_pode_adicionar_blocos=False)
    prompt = montar_system_prompt(_account(), _radialista(), programa)
    assert "siga estritamente" in prompt


@freeze_time("2026-08-10 15:00:00")
def test_prompt_clima_vai_por_extenso(monkeypatch):
    monkeypatch.setattr("app.llm.prompt_builder.obter_clima_atual", lambda cidade: "23°C, céu limpo")
    prompt = montar_system_prompt(_account(cidade="Porto Alegre"), _radialista(), _programa())
    assert "vinte e três graus, céu limpo" in prompt
    assert "23°C" not in prompt


@freeze_time("2026-08-10 15:00:00")
def test_prompt_clima_negativo_vai_por_extenso(monkeypatch):
    monkeypatch.setattr("app.llm.prompt_builder.obter_clima_atual", lambda cidade: "-5°C, neve")
    prompt = montar_system_prompt(_account(cidade="Bom Jesus"), _radialista(), _programa())
    assert "menos cinco graus, neve" in prompt


@freeze_time("2026-08-10 15:00:00")
def test_prompt_frequencia_com_ponto_usa_separador_ponto():
    prompt = montar_system_prompt(_account(frequencia="87.5"), _radialista(), _programa())
    assert "diga 'ponto'" in prompt


@freeze_time("2026-08-10 15:00:00")
def test_prompt_frequencia_com_virgula_usa_separador_virgula():
    prompt = montar_system_prompt(_account(frequencia="87,5"), _radialista(), _programa())
    assert "diga 'vírgula'" in prompt


@freeze_time("2026-08-10 15:00:00")
def test_prompt_frequencia_sem_decimal_nao_menciona_separador():
    prompt = montar_system_prompt(_account(frequencia="780"), _radialista(), _programa())
    assert "separador decimal" not in prompt


# 2026-08-12 e' quarta-feira -- nao cai em nenhuma das condicoes de dia da semana (B.2), pra
# testar perfil editorial (B.1) isolado.
@freeze_time("2026-08-12 10:00:00")  # 07:00 local (America/Sao_Paulo)
def test_perfil_editorial_inicio_de_manha():
    prompt = montar_system_prompt(_account(), _radialista(), _programa())
    assert "leve e energético" in prompt


@freeze_time("2026-08-12 15:00:00")  # 12:00 local
def test_perfil_editorial_almoco():
    prompt = montar_system_prompt(_account(), _radialista(), _programa())
    assert "entretenimento leve, horário de almoço" in prompt


@freeze_time("2026-08-12 19:00:00")  # 16:00 local
def test_perfil_editorial_tarde():
    prompt = montar_system_prompt(_account(), _radialista(), _programa())
    assert "resumo do dia" in prompt


@freeze_time("2026-08-12 05:00:00")  # 02:00 local
def test_perfil_editorial_madrugada():
    prompt = montar_system_prompt(_account(), _radialista(), _programa())
    assert "calmo e reflexivo" in prompt


@freeze_time("2026-08-14 15:00:00")  # 2026-08-14 e' sexta-feira, 12:00 local
def test_dia_da_semana_sexta_sugere_fim_de_semana():
    prompt = montar_system_prompt(_account(), _radialista(), _programa())
    assert "Hoje é sexta-feira" in prompt
    assert "fim de semana" in prompt


@freeze_time("2026-08-10 15:00:00")  # 2026-08-10 e' segunda-feira, 12:00 local
def test_dia_da_semana_segunda_sugere_resumo_do_fim_de_semana():
    prompt = montar_system_prompt(_account(), _radialista(), _programa())
    assert "Hoje é segunda-feira" in prompt
    assert "resumo do fim de semana" in prompt


@freeze_time("2026-08-12 15:00:00")  # quarta-feira -- nenhuma das duas condicoes de dia
def test_dia_da_semana_meio_de_semana_nao_menciona_nada_especial():
    prompt = montar_system_prompt(_account(), _radialista(), _programa())
    assert "Hoje é sexta-feira" not in prompt
    assert "Hoje é segunda-feira" not in prompt


@freeze_time("2026-08-10 15:00:00")
def test_trilha_local_aparece_quando_cidade_preenchida():
    prompt = montar_system_prompt(_account(cidade="Porto Alegre"), _radialista(), _programa())
    assert "cidade (Porto Alegre)" in prompt
    assert "NUNCA invente trânsito, evento, time" in prompt


@freeze_time("2026-08-10 15:00:00")
def test_trilha_local_nao_aparece_sem_cidade():
    prompt = montar_system_prompt(_account(), _radialista(), _programa())
    assert "assunto local de" not in prompt


@freeze_time("2026-08-10 15:00:00")
def test_prompt_sempre_instrui_a_nunca_inventar_fato_sobre_cidade_ou_radio():
    prompt = montar_system_prompt(_account(), _radialista(), _programa())
    assert "NUNCA invente fato específico sobre a cidade, a rádio" in prompt


# 2026-09-07 e' feriado nacional (Independencia do Brasil).
@freeze_time("2026-09-07 15:00:00")
def test_feriado_nacional_aparece_no_contexto():
    prompt = montar_system_prompt(_account(), _radialista(), _programa())
    assert "Hoje é feriado nacional: Independência do Brasil" in prompt


@freeze_time("2026-08-10 15:00:00")
def test_feriado_nacional_ausente_em_dia_comum():
    prompt = montar_system_prompt(_account(), _radialista(), _programa())
    assert "feriado nacional" not in prompt


@freeze_time("2026-08-10 15:00:00")  # 10 de agosto
def test_feriado_municipal_configurado_aparece_no_contexto():
    programa = _programa(feriados_municipais=[{"data": "08-10", "nome": "Aniversário da cidade"}])
    prompt = montar_system_prompt(_account(), _radialista(), programa)
    assert "Hoje também é feriado municipal aqui: Aniversário da cidade" in prompt


@freeze_time("2026-08-10 15:00:00")
def test_feriado_municipal_de_outro_dia_nao_aparece():
    programa = _programa(feriados_municipais=[{"data": "12-08", "nome": "Aniversário da cidade"}])
    prompt = montar_system_prompt(_account(), _radialista(), programa)
    assert "feriado municipal" not in prompt


@freeze_time("2026-08-10 15:00:00")
def test_sem_feriados_municipais_configurados_nao_aparece_nada():
    prompt = montar_system_prompt(_account(), _radialista(), _programa())
    assert "feriado municipal" not in prompt
