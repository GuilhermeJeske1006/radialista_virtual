"""Regressões observadas no flashback de produção em 26/11/2026."""
import datetime
from types import SimpleNamespace as NS

import pytest

from app.live import flashback
from app.live.identidade_musical import corresponde, versao_de_estudio
from app.live.music import MusicaEncontrada
from app.live.router import _selecionar_musica_para_bloco, _tipo_proximo_bloco
from app.live.orcamento import orcamento_para
from app.models.programa import Programa
from app.models.radio_config import RadioConfig
from app.models.musica_historico import MusicaHistorico
from app.llm.json_utils import extrair_json
from freezegun import freeze_time


@pytest.fixture
def programa_flashback(db_session, account):
    radio = RadioConfig(account_id=account.id, nome_locutor="Rick")
    db_session.add(radio)
    db_session.flush()
    p = Programa(radio_config_id=radio.id, nome="Flashback", perfil_programacao="flashback",
                 horario_inicio=datetime.time(12), horario_fim=datetime.time(14),
                 estrutura_blocos=list(flashback.ROTEIRO), generos_musicais=["flashback"])
    db_session.add(p)
    db_session.commit()
    return p


@pytest.mark.parametrize("artista,titulo,encontrado,canal", [
    ("Tony! Toni! Toné!", "Feels Good", "Body and Soul", "Tony Bennett - Topic"),
    ("Cyndi Lauper", "Girls Just Want to Have Fun", "Time After Time", "CyndiLauperVEVO"),
    ("Furacão 2000", "Dreamin", "I'm Still Waiting", "Furacão 2000 - Topic"),
    ("Milli Vanilli", "Blame It on the Rain", "Girl You Know It's True / Blame It on the Rain", "MilliVanilliVEVO"),
])
def test_nao_substitui_obra_ou_artista(artista, titulo, encontrado, canal):
    assert not corresponde(artista, titulo, encontrado, canal)


@pytest.mark.parametrize("titulo", ["Billie Jean (1981 Home Demo)", "Blame It On The Rain (Wogan, 1989)",
                                    "Girls Just Want to Have Fun (Live)", "LUNA BALA (Super Slowed)"])
def test_reserva_rejeita_versoes_alternativas(titulo):
    assert not versao_de_estudio(titulo)


def test_remaster_nao_muda_identidade_nem_epoca_da_obra():
    assert corresponde("Cher", "If I Could Turn Back Time", "If I Could Turn Back Time (2024 Remaster)", "Cher - Topic")
    assert versao_de_estudio("If I Could Turn Back Time (2024 Remaster)")
    assert corresponde("Jorge & Mateus", "Propaganda", "Propaganda", "Jorge e Mateus Oficial")
    assert not corresponde("Prince", "1999", "1979", "Prince - Topic")
    assert corresponde("Prince", "1999", "1999", "Prince - Topic")
    assert versao_de_estudio("Madonna - Live to Tell (Official Video)", "Live to Tell")
    assert not versao_de_estudio("Madonna - Live to Tell (Live)", "Live to Tell")


def test_classificacao_aceita_objeto_cercado_e_rejeita_respostas_conflitantes():
    assert extrair_json('```json\n{"fora": [1]}\n```\n') == {"fora": [1]}
    assert extrair_json('{"fora": [1]}\nExplicação breve.') == {"fora": [1]}
    with pytest.raises(ValueError):
        extrair_json('{"fora": []}\n{"fora": [1]}')
    with pytest.raises(ValueError):
        extrair_json('{"fora": [')


def test_extrair_json_aceita_lista_do_derivador():
    assert extrair_json('[{"titulo": "a"}, {"titulo": "b"}]') == [{"titulo": "a"}, {"titulo": "b"}]
    assert extrair_json('```json\n[{"titulo": "a"}]\n```') == [{"titulo": "a"}]
    with pytest.raises(ValueError):
        extrair_json('[{"titulo": "a"}')


def test_reserva_nunca_cai_em_busca_generica(db_session, programa_flashback, monkeypatch):
    chamadas = []
    monkeypatch.setattr("app.live.router.resolver_musica_catalogada", lambda *a, **k: chamadas.append(k) or None)
    monkeypatch.setattr("app.live.router.buscar_musica", lambda *a, **k: pytest.fail("busca genérica proibida"))
    resultado, origem = _selecionar_musica_para_bloco(db_session, programa_flashback)
    assert resultado is None and origem == "reserva_flashback"
    assert len(chamadas) == 6 and all(k["somente_estudio"] for k in chamadas)


def test_rotacao_por_artista_independe_de_video(db_session, programa_flashback, monkeypatch):
    programa_flashback.musicas_permitidas = ["Madonna - Like a Prayer", "Queen - Under Pressure"]
    db_session.add(MusicaHistorico(programa_id=programa_flashback.id, titulo="Into the Groove", canal="Madonna - Topic",
                                 video_id="outro-video", query="Madonna - Into the Groove", query_normalizada="madonna", origem="auto"))
    db_session.commit()
    escolhidas = []
    def resolver(db, titulo, artista, **kwargs):
        escolhidas.append(artista)
        return MusicaEncontrada(video_id="reserva", titulo=titulo, canal=f"{artista} - Topic")
    monkeypatch.setattr("app.live.router.resolver_musica_catalogada", resolver)
    musica, _ = _selecionar_musica_para_bloco(db_session, programa_flashback)
    assert escolhidas == ["Queen"] and musica.video_id == "reserva"


def test_orcamento_por_funcao_e_sem_comentarios_extras(programa_flashback):
    assert orcamento_para("flashback", "identificacao", False).max_s == 8
    assert orcamento_para("flashback", "musica", False).max_s == 15
    assert orcamento_para("flashback", "comentario", False).aplicar
    programa_flashback.estrutura_blocos = ["comentario"]
    assert _tipo_proximo_bloco(programa_flashback, 5, "comentario") == "musica"
    programa_flashback.estrutura_blocos = []
    assert _tipo_proximo_bloco(programa_flashback, 0) == "abertura"
    assert _tipo_proximo_bloco(programa_flashback, 1, "abertura") == "musica"


def test_direcao_usa_grade_real_e_detecta_expressoes_saturadas(programa_flashback):
    programa_flashback.dias_semana = [0, 1, 2, 3, 4]
    memoria = NS(historico=("pista da malharia", "outra pista na malharia"))
    ctx = NS(programa=programa_flashback, memoria=memoria)
    instrucao = "\n".join(flashback.instrucao_editorial(ctx))
    assert "segunda, terça, quarta, quinta, sexta" in instrucao
    assert "Evite nesta entrada" in instrucao
    assert flashback.avisos_editoriais("Vamos para a pista!", memoria.historico)


def test_credito_inventado_nao_sobrevive_a_revisao_editorial():
    texto = "Like a Prayer teve produção de Bill Bottrell. Essa energia muda a nossa tarde!"
    resultado = flashback.restringir_fatos(texto, ("musica: Like a Prayer",), "Flashback")
    assert "Bill Bottrell" not in resultado
    assert "Essa energia" in resultado
    fato = flashback.FATOS[0][1]
    assert flashback.restringir_fatos(fato, ("musica: Like a Prayer",), "Flashback") == fato


def test_pedido_de_ouvinte_tambem_respeita_repertorio_verificado(programa_flashback):
    assert flashback.pedido_aprovado(programa_flashback, "Madonna - Like a Prayer") == ("Madonna", "Like a Prayer")
    assert flashback.pedido_aprovado(programa_flashback, "Zé Felipe - Sua Boca Mente") is None


@freeze_time("2026-11-26 15:00:00")
def test_configuracao_tem_previa_backup_e_nao_interrompe_player(db_session, account, programa_flashback,
                                                             tmp_path, monkeypatch):
    from app.live.configurar_flashback import configurar
    from app.models.canal_whatsapp import EstadoTransmissao
    from app.config.settings import settings
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    programa_flashback.perfil_programacao = "padrao"
    db_session.commit()
    assert not configurar(db_session, account.id, programa_flashback.id)["aplicado"]
    assert programa_flashback.perfil_programacao == "padrao"
    estado = EstadoTransmissao(programa_id=programa_flashback.id, ocorrencia="teste", player_id="player-teste")
    db_session.add(estado)
    db_session.commit()
    with pytest.raises(ValueError, match="player ativo"):
        configurar(db_session, account.id, programa_flashback.id, aplicar=True)
    db_session.delete(estado)
    db_session.commit()
    resultado = configurar(db_session, account.id, programa_flashback.id, aplicar=True)
    assert resultado["aplicado"] and (tmp_path / resultado["backup"]).is_file()
    assert programa_flashback.perfil_programacao == "flashback"
    assert programa_flashback.ia_pode_adicionar_blocos is False


@freeze_time("2026-11-26 15:00:00")
def test_reproducao_guarda_motivo_tempo_e_faixa_real(client, account, auth_headers, db_session, programa_flashback):
    from app.models.canal_whatsapp import BlocoReproduzido
    bloco = BlocoReproduzido(account_id=account.id, programa_id=programa_flashback.id,
        ocorrencia=f"{programa_flashback.id}:2026-11-26", token="teste", tipo="musica", musica={"titulo": "Original"})
    db_session.add(bloco)
    db_session.commit()
    url = f"/ouvintes/transmissao/blocos/{bloco.id}/eventos"
    dados = {"token": "teste", "player_id": "player-teste"}
    assert client.post(url, headers=auth_headers(account.id), json={**dados, "estado": "reproduzindo"}).status_code == 200
    resp = client.post(url, headers=auth_headers(account.id), json={**dados, "estado": "concluido", "duracao_s": 203.5,
        "motivo": "erro_150", "falhas": ["erro_150"],
        "faixas_executadas": [{"video_id": "reserva", "titulo": "Outra faixa", "canal": "Queen"}]})
    assert resp.status_code == 200
    db_session.refresh(bloco)
    assert bloco.reproducao["inicio_em"] and bloco.reproducao["fim_em"]
    assert bloco.reproducao["duracao_s"] == 203.5
    assert bloco.reproducao["motivo"] == "erro_150"
    assert bloco.musica["titulo"] == "Outra faixa"


def test_migracao_telemetria_idempotente():
    from sqlalchemy import create_engine, inspect, text
    from app.db.migrations.reproducao_20261126 import aplicar
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE blocos_reproduzidos (id INTEGER PRIMARY KEY)"))
    assert aplicar(engine)
    assert not aplicar(engine)
    assert "reproducao" in {c["name"] for c in inspect(engine).get_columns("blocos_reproduzidos")}


def test_gravacao_arquivada_respeita_conta_e_retencao(client, account, account_factory, auth_headers,
                                                   db_session, programa_flashback, tmp_path, monkeypatch):
    from app.config.settings import settings
    from app.models.gravacao_programa import GravacaoPrograma
    from app.live.gravacao import limpar_gravacoes_expiradas
    from test_live_gravacao import _webm_de_um_segundo
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    resp = client.post(f"/live/gravacao/mp3?programa_id={programa_flashback.id}", content=_webm_de_um_segundo(),
                       headers=auth_headers(account.id))
    assert resp.status_code == 200 and resp.headers["X-Gravacao-Arquivada"] == "true"
    gravacao = db_session.query(GravacaoPrograma).one()
    arquivo = tmp_path / gravacao.audio_path
    assert arquivo.is_file()
    base = f"/live/programas/{programa_flashback.id}/gravacoes"
    listado = client.get(base, headers=auth_headers(account.id)).json()
    assert len(listado) == 1 and "audio_path" not in listado[0]
    outra = account_factory(email="outra-radio@example.com")
    assert client.get(f"{base}/{gravacao.id}/audio", headers=auth_headers(outra.id)).status_code == 404
    audio = client.get(f"{base}/{gravacao.id}/audio", headers=auth_headers(account.id))
    assert audio.status_code == 200 and audio.content == resp.content
    gravacao.expira_em = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=1)
    db_session.commit()
    assert client.get(f"{base}/{gravacao.id}/audio", headers=auth_headers(account.id)).status_code == 404
    limpar_gravacoes_expiradas(db_session)
    assert not arquivo.exists() and db_session.query(GravacaoPrograma).count() == 0
