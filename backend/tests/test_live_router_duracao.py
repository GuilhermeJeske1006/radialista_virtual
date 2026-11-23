"""Duração real da fala em /proxima e /tts (F2 do plano de melhoria de rádio).

Desenho em docs/melhoria-radio/f2/auditoria.md (§4 e §6). Mesmo padrão de tests/test_live_router.py:
freeze_time, fakeredis do conftest e dublês por nome em app.live.router. A primeira parte caracteriza o
comportamento anterior à F2 (reescrita única, formato padrão sem orçamento e registros com o texto da
resposta) e foi escrita verde antes de mexer no router.
"""

import datetime

import pytest
from freezegun import freeze_time

from app.live.music import MusicaEncontrada
from app.models.noticia import Noticia
from app.models.noticia_historico import NoticiaHistorico
from app.models.programa import Programa
from app.models.radio_config import RadioConfig

AGORA_UTC = "2026-08-10 15:00:00"  # 12:00 em São Paulo, dentro de um programa 10:00-14:00


def _url(radialista_id, programa_id):
    return f"/live/{radialista_id}/programas/{programa_id}/proxima"


@pytest.fixture()
def radialista_e_programa(db_session, account):
    radio_config = RadioConfig(account_id=account.id, timezone="America/Sao_Paulo")
    db_session.add(radio_config)
    db_session.commit()
    programa = Programa(radio_config_id=radio_config.id, nome="Programa Principal",
                        horario_inicio=datetime.time(10, 0), horario_fim=datetime.time(14, 0),
                        estrutura_blocos=[], ia_pode_adicionar_blocos=False)
    db_session.add(programa)
    db_session.commit()
    return radio_config, programa


@pytest.fixture()
def sem_sorteio(monkeypatch):
    monkeypatch.setattr("app.live.router.random.random", lambda: 1.0)
    monkeypatch.setattr("app.live.router.classificar_fio_condutor", lambda _: "")
    monkeypatch.setattr("app.live.router.resumir_contexto_musica", lambda *_: "")


@pytest.fixture()
def programa_musical(radialista_e_programa, db_session, sem_sorteio):
    radialista, programa = radialista_e_programa
    programa.perfil_programacao = "musical_companhia"
    db_session.commit()
    return radialista, programa


def _gerador(prompts: list, *respostas: str):
    """gerar_resposta falso: devolve as respostas na ordem (a última se repete) e guarda os prompts."""
    def gerar(system, mensagem):
        prompts.append(system)
        return respostas[min(len(prompts), len(respostas)) - 1]
    return gerar


def _criar_noticia(db_session, account) -> Noticia:
    noticia = Noticia(
        account_id=account.id, fonte_nome="Defesa Civil", fonte_tipo="oficial",
        titulo="Rua das Acácias interditada para obra na rede de água",
        resumo="Trecho de trezentos metros fechado desde a manhã.", url="https://exemplo.invalid/materia",
        url_hash="hash-f2-duracao", publicado_em=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1),
        categoria="transito", cidade="Vila Serena", score=90.0, ativa=True,
        detalhes={"servico": "Desvio pela avenida do Lago"},
    )
    db_session.add(noticia)
    db_session.commit()
    return noticia


# ---------------------------------------------------------------------------------------------
# Caracterização (verde antes da F2)
# ---------------------------------------------------------------------------------------------

_LONGA_MUSICAL = "Esta seleção acompanha a sua tarde com música boa. " * 10


@freeze_time(AGORA_UTC)
def test_reescrita_unica_combina_repeticao_e_orcamento(client, account, auth_headers, programa_musical,
                                                      monkeypatch):
    from app.live.router import _registrar_fala_gerada

    radialista, programa = programa_musical
    _registrar_fala_gerada(programa.id, "abertura", _LONGA_MUSICAL.strip())
    prompts: list[str] = []
    curta = "Seguimos juntos com a seleção da tarde."
    monkeypatch.setattr("app.live.router.gerar_resposta", _gerador(prompts, _LONGA_MUSICAL.strip(), curta))
    r = client.post(_url(radialista.id, programa.id), headers=auth_headers(account.id),
                    json={"total_falas": 6, "historico": ["musica: faixa anterior"], "incluir_audio": False})
    assert r.status_code == 200, r.text
    assert r.json()["tipo"] == "retomada"
    assert r.json()["fala"] == curta
    assert len(prompts) == 2
    assert "ficou muito parecida" in prompts[1]
    assert "Reescreva com no máximo 25 palavras" in prompts[1]


@freeze_time(AGORA_UTC)
def test_padrao_sem_relogio_nao_revisa_fala_longa(client, account, auth_headers, radialista_e_programa,
                                                  db_session, sem_sorteio, monkeypatch):
    radialista, programa = radialista_e_programa
    programa.estrutura_blocos = ["comentario"]
    db_session.commit()
    longa = " ".join(f"palavra{i}" for i in range(119)) + " fim."
    prompts: list[str] = []
    monkeypatch.setattr("app.live.router.gerar_resposta", _gerador(prompts, longa))
    monkeypatch.setattr("app.live.router._registrar_tema_em_background", lambda *a: None)
    r = client.post(_url(radialista.id, programa.id), headers=auth_headers(account.id),
                    json={"total_falas": 1, "historico": ["musica: faixa anterior"], "incluir_audio": False})
    assert r.status_code == 200, r.text
    assert r.json()["tipo"] == "comentario"
    assert r.json()["fala"] == longa
    assert len(prompts) == 1


@freeze_time(AGORA_UTC)
@pytest.mark.parametrize("caminho", ["comentario", "noticia", "abertura"])
def test_registros_usam_fala_da_resposta(caminho, client, account, auth_headers, radialista_e_programa, db_session,
                                         sem_sorteio, monkeypatch):
    """Histórico de falas, tema, NoticiaHistorico e fio condutor gravam o texto que a resposta devolve."""
    from app.live.router import _historico_falas

    radialista, programa = radialista_e_programa
    temas, fios = [], []
    monkeypatch.setattr("app.live.router._registrar_tema_em_background", lambda pid, texto: temas.append(texto))
    monkeypatch.setattr("app.live.router.classificar_fio_condutor", lambda texto: fios.append(texto) or "")
    corpo = {"total_falas": 1, "historico": ["musica: faixa anterior"], "incluir_audio": False}
    if caminho == "noticia":
        programa.estrutura_blocos = ["noticia"]
        _criar_noticia(db_session, account)
        fala = "Segundo a Defesa Civil, a Rua das Acácias segue interditada até o fim da tarde."
    elif caminho == "abertura":
        programa.estrutura_blocos = ["abertura", "comentario"]
        corpo = {"total_falas": 0, "historico": [], "incluir_audio": False}
        fala = "Boa tarde! Começa agora o Programa Principal, com música e conversa boa."
    else:
        programa.estrutura_blocos = ["comentario"]
        fala = "Tem gente que organiza a semana no domingo à noite, e isso muda o humor da segunda."
    db_session.commit()
    monkeypatch.setattr("app.live.router.gerar_resposta", lambda *a: fala)
    r = client.post(_url(radialista.id, programa.id), headers=auth_headers(account.id), json=corpo)
    assert r.status_code == 200, r.text
    resposta = r.json()
    assert resposta["fala"] == fala
    categoria = {"comentario": "comentario", "noticia": "noticia", "abertura": "abertura"}[caminho]
    assert _historico_falas(programa.id, categoria)[0] == resposta["fala"]
    if caminho in ("comentario", "noticia"):
        assert temas == [resposta["fala"]]
    if caminho == "noticia":
        historico = db_session.query(NoticiaHistorico).filter_by(programa_id=programa.id).all()
        assert [h.fala for h in historico] == [resposta["fala"]]
    if caminho == "abertura":
        assert fios == [resposta["fala"]]


@freeze_time(AGORA_UTC)
def test_musica_sem_pedido_no_musical_continua_sem_llm(client, account, auth_headers, programa_musical,
                                                       monkeypatch):
    radialista, programa = programa_musical
    monkeypatch.setattr("app.live.router.gerar_resposta", lambda *a: pytest.fail("não gerar fala"))
    monkeypatch.setattr("app.live.router._buscar_musica_para_bloco", lambda *_: MusicaEncontrada(
        video_id="faixa123", titulo="Clássico", canal="Artista", duracao_segundos=240))
    r = client.post(_url(radialista.id, programa.id), headers=auth_headers(account.id),
                    json={"total_falas": 2, "historico": ["musica: faixa anterior"], "incluir_audio": False})
    assert r.status_code == 200
    assert r.json()["fala"] == ""
    assert r.json()["video_id"] == "faixa123"


# ---------------------------------------------------------------------------------------------
# Integração: orçamento de duração em /proxima (F2)
# ---------------------------------------------------------------------------------------------

def _mp3(segundos: float) -> bytes:
    import io

    from pydub import AudioSegment

    buffer = io.BytesIO()
    AudioSegment.silent(duration=int(segundos * 1000)).export(buffer, format="mp3")
    return buffer.getvalue()


def _semear_ritmo(db_session, wpm: float, amostras: int = 5, categoria: str = "padrao"):
    """Calibração já existente para a voz padrão do servidor (sem voz configurada: 'padrao')."""
    from app.config.settings import settings
    from app.models.perfil_voz import RitmoVoz

    db_session.add(RitmoVoz(voz_id=settings.elevenlabs_voice_id or "padrao", modelo=settings.elevenlabs_model,
                            perfil="atual", categoria=categoria,
                            amostras=amostras, palavras=wpm * amostras, segundos=60.0 * amostras))
    db_session.commit()


@freeze_time(AGORA_UTC)
def test_musical_devolve_orcamento_e_estimativa_sem_audio(client, account, auth_headers, programa_musical,
                                                          monkeypatch):
    from app.config.settings import settings
    from app.live.orcamento import estimar_duracao_s, wpm_padrao

    radialista, programa = programa_musical
    fala = "Seguimos juntos nesta tarde, com a seleção de clássicos que você conhece."
    monkeypatch.setattr("app.live.router.gerar_resposta", lambda *a: fala)
    r = client.post(_url(radialista.id, programa.id), headers=auth_headers(account.id),
                    json={"total_falas": 6, "historico": ["musica: faixa anterior"], "incluir_audio": False})
    assert r.status_code == 200, r.text
    dados = r.json()
    assert dados["orcamento_fala_s"] == {"min_s": 6, "alvo_s": 9, "max_s": 12, "fonte": "formato", "aplicado": True}
    assert dados["duracao_fala_estimada_s"] == pytest.approx(
        estimar_duracao_s(fala, wpm_padrao(settings.elevenlabs_model)), abs=0.01)
    assert dados["duracao_fala_s"] is None
    assert dados["duracao_alvo_segundos"] == [6, 12]
    assert dados["fala_ajuste"] == "nenhum"


@freeze_time(AGORA_UTC)
def test_padrao_sem_relogio_so_observa(client, account, auth_headers, radialista_e_programa, db_session,
                                       sem_sorteio, monkeypatch):
    radialista, programa = radialista_e_programa
    programa.estrutura_blocos = ["comentario"]
    db_session.commit()
    longa = " ".join(f"palavra{i}" for i in range(119)) + " fim."
    prompts: list[str] = []
    monkeypatch.setattr("app.live.router.gerar_resposta", _gerador(prompts, longa))
    monkeypatch.setattr("app.live.router._registrar_tema_em_background", lambda *a: None)
    r = client.post(_url(radialista.id, programa.id), headers=auth_headers(account.id),
                    json={"total_falas": 1, "historico": ["musica: faixa anterior"], "incluir_audio": False})
    dados = r.json()
    assert dados["fala"] == longa and len(prompts) == 1
    assert dados["orcamento_fala_s"]["fonte"] == "observacao"
    assert dados["orcamento_fala_s"]["aplicado"] is False
    assert dados["duracao_fala_estimada_s"] > dados["orcamento_fala_s"]["max_s"] * 1.3
    assert dados["fala_ajuste"] == "nenhum"


@freeze_time(AGORA_UTC)
def test_estimativa_acima_da_tolerancia_pede_uma_reescrita(client, account, auth_headers, programa_musical,
                                                           db_session, monkeypatch, caplog):
    """Palavras dentro do limite, mas o ritmo calibrado da voz (lento) e os números por extenso levam a
    estimativa acima de 115% do máximo: o motivo duração entra na reescrita única."""
    radialista, programa = programa_musical
    _semear_ritmo(db_session, wpm=100)
    # 18 palavras escritas, 24 faladas ("dois mil e vinte e seis"): a 100 palavras/min, 14,4 s > 13,8 s.
    longa = ("Em 2026 a seleção da tarde segue com calma, música boa e companhia para quem está chegando "
             "agora mesmo.")
    curta = "Seguimos juntos com a seleção da tarde."
    prompts: list[str] = []
    monkeypatch.setattr("app.live.router.gerar_resposta", _gerador(prompts, longa, curta))
    with caplog.at_level("INFO", logger="radialista.live"):
        r = client.post(_url(radialista.id, programa.id), headers=auth_headers(account.id),
                        json={"total_falas": 6, "historico": ["musica: faixa anterior"], "incluir_audio": False})
    dados = r.json()
    assert len(prompts) == 2
    # Voz lenta: 12 s a 100 palavras/min = 20 palavras, no prompt e na reescrita (mesma frase de sempre).
    assert "no máximo 20 palavras" in prompts[0]
    assert "Reescreva com no máximo 20 palavras" in prompts[1]
    assert "tempo de locução" in prompts[1]
    assert dados["fala"] == curta
    assert dados["fala_ajuste"] == "reescrita"
    assert "live_fala_revisada motivo=duracao" in caplog.text


@freeze_time(AGORA_UTC)
def test_reescrita_usada_e_texto_ainda_longo_encurta_sem_terceira_chamada(client, account, auth_headers,
                                                                         programa_musical, monkeypatch):
    from app.live.router import _historico_falas, _registrar_fala_gerada

    radialista, programa = programa_musical
    _registrar_fala_gerada(programa.id, "abertura", _LONGA_MUSICAL.strip())
    # 45 palavras: a estimativa passa de 115% do máximo mesmo depois da reescrita (usada pela repetição).
    ainda_longa = ("Que bom ter você por aqui nesta tarde. A seleção segue com calma e muita música boa. "
                   "Fique com a gente, que a tarde segue mansa, sem pressa nenhuma, com o violão, a voz macia, "
                   "o café passado e a janela aberta para o vento.")
    prompts: list[str] = []
    monkeypatch.setattr("app.live.router.gerar_resposta", _gerador(prompts, _LONGA_MUSICAL.strip(), ainda_longa))
    r = client.post(_url(radialista.id, programa.id), headers=auth_headers(account.id),
                    json={"total_falas": 6, "historico": ["musica: faixa anterior"], "incluir_audio": False})
    dados = r.json()
    assert len(prompts) == 2
    assert dados["fala_ajuste"] == "encurtada"
    assert dados["fala"] == "Que bom ter você por aqui nesta tarde. A seleção segue com calma e muita música boa."
    assert _historico_falas(programa.id, "abertura")[0] == dados["fala"]


@freeze_time(AGORA_UTC)
def test_texto_sem_frase_que_caiba_fica_e_marca_acima_do_teto(client, account, auth_headers, programa_musical,
                                                              monkeypatch):
    radialista, programa = programa_musical
    uma_frase = ("Esta tarde a seleção segue com calma, com música boa, com companhia, com conversa curta, "
                 "com o sol entrando pela janela e a cidade inteira desacelerando devagar junto com a gente, "
                 "enquanto o rádio toca baixinho na cozinha e o cheiro de bolo invade a casa inteira")
    prompts: list[str] = []
    monkeypatch.setattr("app.live.router.gerar_resposta", _gerador(prompts, uma_frase))
    r = client.post(_url(radialista.id, programa.id), headers=auth_headers(account.id),
                    json={"total_falas": 6, "historico": ["musica: faixa anterior"], "incluir_audio": False})
    dados = r.json()
    assert len(prompts) == 2
    assert dados["fala"] == uma_frase
    assert dados["fala_ajuste"] == "acima_do_teto"


def test_ajuste_corta_a_fala_so_no_bloco_de_musica_sem_pedido():
    from app.live.orcamento import ajustar_ao_orcamento, orcamento_para

    orc = orcamento_para("musical_companhia", "musica", primeira=False)
    longa = ("Uma frase muito comprida que não cabe de jeito nenhum no pouco tempo que o anúncio da faixa tem "
             "agora, nem que a gente fale bem depressa sem respirar")
    assert ajustar_ao_orcamento(longa, orc, 150, pode_cortar=True) == ("", "cortada")
    assert ajustar_ao_orcamento(longa, orc, 150, pode_cortar=False) == (longa, "acima_do_teto")
    assert ajustar_ao_orcamento("Vem aí.", orc, 150, pode_cortar=True) == ("Vem aí.", "nenhum")
    observacao = orcamento_para("padrao", "comentario", primeira=False)
    assert ajustar_ao_orcamento(longa * 5, observacao, 150, pode_cortar=True) == (longa * 5, "nenhum")


def _sintese_falsa(chamadas: list, *duracoes_s: float):
    audios = [_mp3(d) for d in duracoes_s]

    def sintetizar(texto, voz_id=None, **kwargs):
        chamadas.append({"texto": texto, **kwargs})
        return audios[min(len(chamadas), len(audios)) - 1]
    return sintetizar


@freeze_time(AGORA_UTC)
def test_audio_embutido_acima_do_teto_encurta_e_sintetiza_de_novo_sem_acelerar(
    client, account, auth_headers, programa_musical, monkeypatch
):
    from app.live.router import _historico_falas

    radialista, programa = programa_musical
    fala = ("Que bom ter você por aqui nesta tarde. A seleção segue com calma e boa música. "
            "Fique com a gente que tem mais.")
    chamadas: list[dict] = []
    monkeypatch.setattr("app.live.router.gerar_resposta", lambda *a: fala)
    monkeypatch.setattr("app.live.router.tts_habilitado", lambda *a: True)
    monkeypatch.setattr("app.live.router.sintetizar_audio", _sintese_falsa(chamadas, 20.0, 6.0))
    monkeypatch.setattr("app.live.router.processar_audio", lambda audio, perfil: audio)
    r = client.post(_url(radialista.id, programa.id), headers=auth_headers(account.id),
                    json={"total_falas": 6, "historico": ["musica: faixa anterior"], "perfil_pos_producao": "radio_fm"})
    dados = r.json()
    assert dados["audio_status"] == "pronto"
    assert len(chamadas) == 2
    assert dados["fala"] == "Que bom ter você por aqui nesta tarde."
    assert chamadas[1]["texto"] == dados["fala"]
    # Mesma voz, tom, modelo, perfil e pronúncias: encurta o texto, nunca acelera a voz.
    sem_texto = [{k: v for k, v in c.items() if k != "texto"} for c in chamadas]
    assert sem_texto[0] == sem_texto[1]
    assert dados["duracao_fala_s"] == pytest.approx(6.0, abs=0.1)
    assert dados["fala_ajuste"] == "encurtada"
    assert _historico_falas(programa.id, "abertura")[0] == dados["fala"]


@freeze_time(AGORA_UTC)
def test_audio_dentro_do_teto_mede_e_nao_sintetiza_de_novo(client, account, auth_headers, programa_musical,
                                                           db_session, monkeypatch):
    from app.models.perfil_voz import RitmoVoz

    radialista, programa = programa_musical
    fala = "Que bom ter você por aqui nesta tarde. A seleção segue com calma e boa música. Fique com a gente."
    chamadas: list[dict] = []
    monkeypatch.setattr("app.live.router.gerar_resposta", lambda *a: fala)
    monkeypatch.setattr("app.live.router.tts_habilitado", lambda *a: True)
    monkeypatch.setattr("app.live.router.sintetizar_audio", _sintese_falsa(chamadas, 14.0))
    monkeypatch.setattr("app.live.router.processar_audio", lambda audio, perfil: audio)
    r = client.post(_url(radialista.id, programa.id), headers=auth_headers(account.id),
                    json={"total_falas": 6, "historico": ["musica: faixa anterior"], "perfil_pos_producao": "radio_fm"})
    dados = r.json()
    assert len(chamadas) == 1
    assert dados["fala"] == fala
    assert dados["duracao_fala_s"] == pytest.approx(14.0, abs=0.1)
    assert dados["fala_ajuste"] == "nenhum"        # 117%: acima da tolerância, abaixo do teto, só registra
    # A medida vira amostra de ritmo da voz (20 palavras em 14 s).
    linha = db_session.query(RitmoVoz).one()
    assert (linha.amostras, linha.palavras) == (1, 20)


@freeze_time(AGORA_UTC)
def test_audio_que_nao_decodifica_nao_mede_nem_reescreve(client, account, auth_headers, programa_musical,
                                                         db_session, monkeypatch):
    from app.models.perfil_voz import RitmoVoz

    radialista, programa = programa_musical
    fala = "Seguimos juntos nesta tarde de música boa."
    prompts: list[str] = []
    chamadas: list[str] = []
    monkeypatch.setattr("app.live.router.gerar_resposta", _gerador(prompts, fala))
    monkeypatch.setattr("app.live.router.tts_habilitado", lambda *a: True)
    monkeypatch.setattr("app.live.router.sintetizar_audio", lambda texto, *a, **k: chamadas.append(texto) or b"mp3")
    r = client.post(_url(radialista.id, programa.id), headers=auth_headers(account.id),
                    json={"total_falas": 6, "historico": ["musica: faixa anterior"]})
    dados = r.json()
    assert dados["audio_status"] == "pronto"
    assert dados["duracao_fala_s"] is None
    assert (len(prompts), len(chamadas)) == (1, 1)
    assert db_session.query(RitmoVoz).count() == 0


@freeze_time(AGORA_UTC)
def test_falha_de_audio_nao_tenta_segunda_sintese(client, account, auth_headers, programa_musical, monkeypatch):
    radialista, programa = programa_musical
    chamadas: list[str] = []

    def falhar(texto, *a, **k):
        chamadas.append(texto)
        raise RuntimeError("provedor indisponível")

    monkeypatch.setattr("app.live.router.gerar_resposta", lambda *a: "Seguimos juntos nesta tarde de música boa.")
    monkeypatch.setattr("app.live.router.tts_habilitado", lambda *a: True)
    monkeypatch.setattr("app.live.router.sintetizar_audio", falhar)
    r = client.post(_url(radialista.id, programa.id), headers=auth_headers(account.id),
                    json={"total_falas": 6, "historico": ["musica: faixa anterior"]})
    assert r.json()["audio_status"] == "falhou"
    assert len(chamadas) == 1
    assert r.json()["duracao_fala_s"] is None


# --- relógio e multivoz -------------------------------------------------------------------------

@pytest.fixture()
def com_relogio(radialista_e_programa, account, db_session, sem_sorteio, monkeypatch):
    from app.live import relogio as r
    from app.models.patrocinador import Patrocinador

    radialista, programa = radialista_e_programa
    patrocinadores = [Patrocinador(account_id=account.id, nome=n, texto=f"{n}, perto de você.", ativo=True,
                                   tipo_conteudo="audio", audio_path=f"p/{n}.mp3", duracao_segundos=d)
                      for n, d in (("Loja Um", 30), ("Loja Dois", 20))]
    db_session.add_all(patrocinadores)
    db_session.flush()
    programa.horario_inicio, programa.horario_fim = datetime.time(12, 0), datetime.time(13, 0)
    programa.estrutura_blocos = ["comentario", *[f"patrocinador:{p.id}" for p in patrocinadores]]
    programa.relogio_hora = r.PRESETS["A"].model_dump()
    db_session.commit()
    monkeypatch.setattr("app.live.router._registrar_tema_em_background", lambda *a: None)
    return radialista, programa


def _abertura_feita(programa):
    """Marca a abertura do relógio como executada (dentro do freeze_time: o estado tem TTL no Redis)."""
    from app.live import relogio as r

    instante = datetime.datetime(2026, 11, 10, 12, 0, tzinfo=datetime.timezone(datetime.timedelta(hours=-3)))
    r.marcar_executada(programa.id, r.ocorrencia_em(programa, "America/Sao_Paulo", instante), "0:0:fala:abertura")


@freeze_time("2026-11-10 15:12:00")
def test_relogio_define_o_orcamento_e_as_palavras_pelo_ritmo(client, account, auth_headers, com_relogio,
                                                             monkeypatch):
    from app.config.settings import settings
    from app.live.orcamento import wpm_padrao

    radialista, programa = com_relogio
    _abertura_feita(programa)
    prompts: list[str] = []
    monkeypatch.setattr("app.live.router.gerar_resposta", _gerador(prompts, "Um assunto rápido entre as músicas."))
    r = client.post(_url(radialista.id, programa.id), headers=auth_headers(account.id),
                    json={"total_falas": 3, "historico": ["musica: faixa anterior"], "incluir_audio": False,
                          "inicio_previsto": "2026-11-10T12:12:00-03:00"})
    dados = r.json()
    assert dados["duracao_alvo_segundos"] == [10, 35]
    assert dados["orcamento_fala_s"] == {"min_s": 10, "alvo_s": 22.5, "max_s": 35, "fonte": "relogio",
                                         "aplicado": True}
    palavras = int(35 * wpm_padrao(settings.elevenlabs_model) // 60)
    assert f"Meta: 10 a 35 segundos, no máximo {palavras} palavras" in prompts[0]


@freeze_time("2026-11-10 15:12:00")
def test_multivoz_mede_as_linhas_e_retira_do_fim_sem_chamada_extra(
    client, account, auth_headers, com_relogio, db_session, monkeypatch
):
    import json

    from app.models.programa_radialista import ProgramaRadialista

    radialista, programa = com_relogio
    _abertura_feita(programa)
    radialista.nome_locutor = "Ze"
    convidada = RadioConfig(account_id=account.id, nome_locutor="Maria", timezone="America/Sao_Paulo")
    db_session.add(convidada)
    db_session.flush()
    db_session.add(ProgramaRadialista(programa_id=programa.id, radio_config_id=convidada.id))
    db_session.commit()
    linhas = [{"locutor": "Ze", "texto": "Boa tarde, Maria!"}, {"locutor": "Maria", "texto": "Boa tarde, Zé!"},
              {"locutor": "Ze", "texto": "Que calor hoje."}, {"locutor": "Maria", "texto": "Nem me fale."}]
    llm: list[str] = []
    monkeypatch.setattr("app.live.router.gerar_dialogo_multivoz",
                        lambda system, msg: llm.append(system) or json.dumps({"linhas": linhas}))
    chamadas: list[dict] = []
    monkeypatch.setattr("app.live.router.tts_habilitado", lambda *a: True)
    monkeypatch.setattr("app.live.router.sintetizar_audio", _sintese_falsa(chamadas, 16.0))
    r = client.post(_url(radialista.id, programa.id), headers=auth_headers(account.id),
                    json={"total_falas": 3, "historico": ["musica: faixa anterior"], "incluir_audio": False,
                          "inicio_previsto": "2026-11-10T12:12:00-03:00"})
    dados = r.json()
    # 4 linhas de 16 s (+ 3 pausas) = 64,8 s > 130% de 35 s: saem linhas do fim até caber, no mínimo 2.
    assert (len(llm), len(chamadas)) == (1, 4)
    assert [f["texto"] for f in dados["falas"]] == ["Boa tarde, Maria!", "Boa tarde, Zé!"]
    assert len(dados["audios_falas_base64"]) == 2
    assert dados["fala"] == "Boa tarde, Maria! Boa tarde, Zé!"
    assert dados["duracao_fala_s"] == pytest.approx(32.28, abs=0.2)
    assert dados["fala_ajuste"] == "encurtada"


# ---------------------------------------------------------------------------------------------
# /tts: mede, devolve o cabeçalho e calibra (não muda o áudio)
# ---------------------------------------------------------------------------------------------

_FALA_TTS = ("Que bom ter você por aqui nesta tarde. A seleção segue com calma e boa música para você e para "
             "toda a sua casa.")  # 24 palavras


@freeze_time(AGORA_UTC)
def test_tts_com_perfil_mede_devolve_cabecalho_e_grava_ritmo(client, account, auth_headers, programa_musical,
                                                            db_session, monkeypatch, caplog):
    from app.models.perfil_voz import RitmoVoz

    radialista, programa = programa_musical
    audio = _mp3(15.0)
    monkeypatch.setattr("app.live.router.gerar_resposta", lambda *a: _FALA_TTS)
    monkeypatch.setattr("app.live.router.tts_habilitado", lambda *a: True)
    monkeypatch.setattr("app.live.router.sintetizar_audio", lambda *a, **k: audio)
    monkeypatch.setattr("app.live.router.processar_audio", lambda audio, perfil: audio)
    headers = auth_headers(account.id)
    proxima = client.post(_url(radialista.id, programa.id), headers=headers,
                          json={"total_falas": 6, "historico": ["musica: faixa anterior"], "incluir_audio": False})
    assert proxima.json()["fala"] == _FALA_TTS
    corpo = {"texto": _FALA_TTS, "tipo": "retomada", "tom": "neutro", "perfil_pos_producao": "radio_fm",
             "programa_id": programa.id}
    with caplog.at_level("INFO", logger="radialista.live"):
        r = client.post(f"/live/{radialista.id}/tts", json=corpo, headers=headers)
    assert r.status_code == 200
    assert r.content == audio
    assert float(r.headers["X-Duracao-Fala-S"]) == pytest.approx(15.0, abs=0.1)
    linha = db_session.query(RitmoVoz).one()
    # palavras é float na coluna (RitmoVoz.palavras); após o musical com música antes, o bloco é "abertura" (h0).
    assert (linha.amostras, linha.palavras, linha.categoria) == (1, 24, "abertura")
    assert "live_fala_duracao" in caplog.text and "origem=tts" in caplog.text
    assert "excesso_pct=25" in caplog.text  # 15 s contra o máximo de 12 s guardado pelo /proxima
    # O mesmo áudio de novo (cache de TTS) não vira segunda amostra.
    client.post(f"/live/{radialista.id}/tts", json=corpo, headers=headers)
    db_session.refresh(linha)
    assert linha.amostras == 1


def test_tts_sem_perfil_ou_com_bytes_falsos_nao_mede(client, account, auth_headers, radialista_e_programa,
                                                     db_session, monkeypatch):
    from app.models.perfil_voz import RitmoVoz

    radialista, _ = radialista_e_programa
    monkeypatch.setattr("app.live.router.tts_habilitado", lambda *a: True)
    monkeypatch.setattr("app.live.router.classificar_tom_fala", lambda *a: "neutro")
    monkeypatch.setattr("app.live.router.sintetizar_audio_stream", lambda *a, **k: iter([_mp3(12.0)]))
    monkeypatch.setattr("app.live.router.sintetizar_audio", lambda *a, **k: b"audio-cru")
    monkeypatch.setattr("app.live.router.processar_audio", lambda audio, perfil: audio + b"-processado")
    headers = auth_headers(account.id)
    streaming = client.post(f"/live/{radialista.id}/tts", json={"texto": _FALA_TTS}, headers=headers)
    assert streaming.status_code == 200 and "X-Duracao-Fala-S" not in streaming.headers
    falso = client.post(f"/live/{radialista.id}/tts", json={"texto": _FALA_TTS, "perfil_pos_producao": "radio_fm"},
                        headers=headers)
    assert falso.status_code == 200
    assert falso.content == b"audio-cru-processado"
    assert "X-Duracao-Fala-S" not in falso.headers
    assert db_session.query(RitmoVoz).count() == 0


def test_cors_expoe_o_cabecalho_da_duracao():
    from app.main import app

    cors = next(m for m in app.user_middleware if m.cls.__name__ == "CORSMiddleware")
    assert "X-Duracao-Fala-S" in cors.kwargs["expose_headers"]


@freeze_time(AGORA_UTC)
def test_calibracao_do_tts_muda_a_estimativa_seguinte(client, account, auth_headers, programa_musical,
                                                      monkeypatch):
    """Cinco falas medidas a 100 palavras/min: a estimativa do /proxima seguinte usa esse ritmo."""
    from app.live.orcamento import estimar_duracao_s

    radialista, programa = programa_musical
    monkeypatch.setattr("app.live.router.tts_habilitado", lambda *a: True)
    monkeypatch.setattr("app.live.router.processar_audio", lambda audio, perfil: audio)
    headers = auth_headers(account.id)
    for n in range(5):
        texto = f"Fala número {n} da tarde, com a seleção de clássicos que segue com você agora mesmo."
        monkeypatch.setattr("app.live.router.sintetizar_audio",
                            lambda *a, _t=texto, **k: _mp3(len(_t.split()) * 0.6 + 0.01 * n))
        client.post(f"/live/{radialista.id}/tts", headers=headers,
                    json={"texto": texto, "tipo": "comentario", "tom": "neutro", "perfil_pos_producao": "radio_fm"})
    fala = "Seguimos juntos com a seleção da tarde."
    monkeypatch.setattr("app.live.router.gerar_resposta", lambda *a: fala)
    dados = client.post(_url(radialista.id, programa.id), headers=headers,
                        json={"total_falas": 6, "historico": ["musica: faixa anterior"], "incluir_audio": False}).json()
    assert dados["duracao_fala_estimada_s"] == pytest.approx(estimar_duracao_s(fala, 100), rel=0.05)


def test_prewarm_guarda_os_campos_de_duracao(monkeypatch, db_session, account, radialista_e_programa):
    import json

    from app.live import prewarm
    from app.live.router import LiveProgramResponse, OrcamentoFalaResponse

    radialista, programa = radialista_e_programa
    resposta = LiveProgramResponse(
        tipo="abertura", fala="Boa tarde!", criado_em=datetime.datetime.now(datetime.timezone.utc),
        duracao_fala_s=8.4, duracao_fala_estimada_s=7.9, fala_ajuste="encurtada",
        orcamento_fala_s=OrcamentoFalaResponse(min_s=20, alvo_s=30, max_s=40, fonte="relogio", aplicado=True),
    )
    monkeypatch.setattr(prewarm, "gerar_proxima_fala", lambda *a, **k: resposta)
    prewarm.preparar_programa(db_session, account, radialista, programa)
    payload = json.loads(prewarm.redis_client.get(prewarm._chave_cache(programa.id)))
    assert (payload["duracao_fala_s"], payload["duracao_fala_estimada_s"], payload["fala_ajuste"]) == (
        8.4, 7.9, "encurtada")
    assert payload["orcamento_fala_s"]["fonte"] == "relogio"


@freeze_time("2026-11-10 15:12:00")
def test_f13_bancada_com_papeis_cabe_no_orcamento_do_relogio(
    client, account, auth_headers, com_relogio, db_session, monkeypatch
):
    """F13: a conversa da bancada (com papéis de turno) passa pelo mesmo corte do multi-voz ao orçamento da etapa do
    relógio; o tempo total da conversa não estoura a etapa, sem chamada extra ao LLM."""
    import json

    from app.live.bancada import instrucao_de_turnos
    from app.models.programa_radialista import ProgramaRadialista

    radialista, programa = com_relogio
    _abertura_feita(programa)
    radialista.nome_locutor = "Ze"
    convidada = RadioConfig(account_id=account.id, nome_locutor="Maria", timezone="America/Sao_Paulo")
    db_session.add(convidada)
    db_session.flush()
    db_session.add(ProgramaRadialista(programa_id=programa.id, radio_config_id=convidada.id,
                                      papel_bancada="contraponto"))
    db_session.commit()
    linhas = [{"locutor": "Ze", "texto": "Maria, a feira mudou de lugar."},
              {"locutor": "Maria", "texto": "Mudou, mas ficou mais longe."},
              {"locutor": "Ze", "texto": "Longe para quem?"}, {"locutor": "Maria", "texto": "Para quem vai a pé."},
              {"locutor": "Ze", "texto": "Justo."}, {"locutor": "Maria", "texto": "Pois é."}]
    llm: list[str] = []
    monkeypatch.setattr("app.live.router.gerar_dialogo_multivoz",
                        lambda system, msg: llm.append(system) or json.dumps({"linhas": linhas}))
    chamadas: list[dict] = []
    monkeypatch.setattr("app.live.router.tts_habilitado", lambda *a: True)
    monkeypatch.setattr("app.live.router.sintetizar_audio", _sintese_falsa(chamadas, 12.0))
    dados = client.post(_url(radialista.id, programa.id), headers=auth_headers(account.id),
                        json={"total_falas": 3, "historico": ["musica: faixa anterior"], "incluir_audio": False,
                              "inicio_previsto": "2026-11-10T12:12:00-03:00"}).json()
    assert len(llm) == 1 and instrucao_de_turnos() in llm[0]
    maximo = dados["duracao_alvo_segundos"][1]
    assert len(dados["falas"]) < len(linhas)
    assert dados["duracao_fala_s"] <= maximo  # o corte retira linhas do fim até caber no máximo da etapa
    assert dados["fala_ajuste"] == "encurtada"
