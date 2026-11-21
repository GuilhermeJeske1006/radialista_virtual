"""Contrato do piloto: evidência, isolamento, revisão, validade e áudio real."""
import copy
import datetime as dt
import io
from functools import lru_cache

import pytest
from pydantic import ValidationError
from pydub import AudioSegment

from app.esportes import editorial
from app.esportes.schemas import ConteudoEdicao, Fonte, Perfil
from app.models.esportes import EdicaoEsportiva
from app.models.programa import Programa
from app.models.radio_config import RadioConfig


@pytest.fixture
def redacao(client, account, auth_headers, db_session):
    radialista = RadioConfig(account_id=account.id, nome_locutor="Apresentador")
    db_session.add(radialista)
    db_session.flush()
    programa = Programa(radio_config_id=radialista.id, nome="Esporte", horario_inicio=dt.time(10), horario_fim=dt.time(11))
    db_session.add(programa)
    db_session.commit()
    h = auth_headers(account.id)
    fonte = dict(dominio="www.federacao.com.br", organizacao="Federação de teste", temas="Futebol", ultima_revisao=editorial.agora().date().isoformat(), condicoes_uso="Consulta manual autorizada no piloto")
    r = client.post("/esportes/fontes", json=fonte, headers=h)
    assert r.status_code == 201, r.text
    r2 = client.post(f"/esportes/programas/{programa.id}/edicoes", headers=h,
                     json={"modelo": "boletim_2", "exibicao_em": (editorial.agora() + dt.timedelta(hours=2)).isoformat()})
    assert r2.status_code == 201, r2.text
    return h, r.json(), r2.json(), programa.id


def _fato(fonte):
    agora = editorial.agora() - dt.timedelta(minutes=1)
    return dict(id="f1", texto="O organizador confirmou a alteração de horário.", tipo="agenda", evento="Evento editorial de teste",
                ocorrido_em=(agora + dt.timedelta(days=1)).isoformat(), publicado_em=agora.isoformat(),
                coletado_em=agora.isoformat(), valido_ate=(agora + dt.timedelta(days=2)).isoformat(),
                fonte_id=fonte['id'], fonte_revisao=fonte['revisao'], url="https://www.federacao.com.br/nota",
                evidencia="Trecho conferido sobre a alteração de horário.", origem_comum="Comunicado do organizador",
                confirmacao="confirmado", oficial=True, revisado=True)


def _preencher(client, redacao):
    h, fonte, e, _ = redacao
    conteudo = copy.deepcopy(e['conteudo'])
    conteudo['fatos'] = [_fato(fonte), {**_fato(fonte), 'id': 'f2', 'tipo': 'noticia', 'evento': 'Outro acontecimento'}]
    for b in conteudo['blocos']:
        b['texto'] = "Fala preparada para revisão editorial."
    conteudo['blocos'][1]['fato_ids'] = ['f2']
    conteudo['blocos'][2]['fato_ids'] = ['f1']
    r = client.put(f"/esportes/edicoes/{e['id']}", json={'revisao': e['revisao'], 'conteudo': conteudo}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()['alertas'] == []
    return r.json()


def _aprovar(client, h, e):
    r = client.post(f"/esportes/edicoes/{e['id']}/aprovar-roteiro", headers=h, json={'revisao': e['revisao'], 'conferido': True})
    assert r.status_code == 200, r.text
    return r.json()


def test_modelos_e_perfil(client, redacao):
    h, _, _, pid = redacao
    modelos = client.get('/esportes/modelos', headers=h).json()
    assert [m['duracao_s'] for m in modelos] == [120, 180, 1800]
    for m in modelos:
        assert sum(b['duracao_s'] for b in m['blocos']) == m['duracao_s']
        assert m['blocos'][0]['tipo'] == 'abertura' and m['blocos'][-1]['tipo'] == 'encerramento'
    assert sum(b['duracao_s'] for b in modelos[-1]['blocos'] if b['tipo'] == 'intervalo') == 120
    perfil = Perfil(nome="Esporte da rádio", clubes=['Brusque'], regiao='Vale do Itajaí').model_dump()
    assert client.put(f'/esportes/programas/{pid}/perfil', headers=h, json=perfil).status_code == 200
    assert client.get(f'/esportes/programas/{pid}/perfil', headers=h).json()['clubes'] == ['Brusque']
    with pytest.raises(ValidationError):
        Perfil(fuso='Fuso/Inexistente')
    with pytest.raises(ValidationError):
        Perfil(distribuicao={'regional': 90, 'nacional': 90, 'internacional': 0, 'outras': 0})


def test_isolamento_e_autenticacao(client, redacao, account_factory, auth_headers):
    _, fonte, e, pid = redacao
    h = auth_headers(account_factory(email='outra@radio.test').id)
    for caminho in [f'/esportes/edicoes/{e["id"]}', f'/esportes/programas/{pid}/edicoes', f'/esportes/programas/{pid}/perfil', f'/esportes/edicoes/{e["id"]}/manifesto']:
        assert client.get(caminho, headers=h).status_code == 404
    assert client.get('/esportes/fontes', headers=h).json() == []
    assert client.put(f'/esportes/fontes/{fonte["id"]}', headers=h, json={k: v for k, v in fonte.items() if k != 'id'}).status_code == 404
    assert client.get('/esportes/modelos').status_code == 401


def test_revisao_e_invalida_audio(client, redacao, db_session):
    h, _, _, _ = redacao
    e = _preencher(client, redacao)
    antes = e['revisao']
    e = _aprovar(client, h, e)
    assert e['estado'] == 'roteiro_aprovado'
    assert client.put(f'/esportes/edicoes/{e["id"]}', headers=h, json={'revisao': antes, 'conteudo': e['conteudo']}).status_code == 409
    salvo = db_session.get(EdicaoEsportiva, e['id'])
    salvo.audios = {'bloco_1': {'path': 'antigo.mp3', 'duracao_s': 10, 'assinatura': editorial.assinatura(salvo.dados)}}
    db_session.commit()
    e = client.get(f'/esportes/edicoes/{e["id"]}', headers=h).json()
    e['conteudo']['fatos'][0]['texto'] = 'Horário foi corrigido após a aprovação.'
    r = client.put(f'/esportes/edicoes/{e["id"]}', headers=h, json={'revisao': e['revisao'], 'conteudo': e['conteudo']}).json()
    assert r['audios'] == {} and r['aprovacao_roteiro'] is None and r['aprovacao_audio'] is None
    manifesto = client.get(f'/esportes/edicoes/{e["id"]}/manifesto', headers=h).json()
    assert manifesto['historico'][-1]['retrato']['audios']['bloco_1']['path'] == 'antigo.mp3'
    assert client.get(f'/esportes/edicoes/{e["id"]}/exportar', headers=h).status_code == 409


@pytest.mark.parametrize(('mudanca', 'esperado'), [
    ({'confirmacao': 'adiado'}, 'adiada'),
    ({'ocorrido_em': (editorial.agora() - dt.timedelta(hours=1)).isoformat()}, 'agenda vencida'),
    ({'confirmacao': 'contestado'}, 'divergentes'), ({'revisado': False}, 'não revisada'),
    ({'tipo': 'transferencia', 'confirmacao': 'negociacao'}, 'negociação'),
    ({'tipo': 'escalacao', 'oficial': False}, 'oficialmente'), ({'sensivel': True}, 'sensível'),
    ({'url': 'https://falso.www.federacao.com.br/nota'}, 'domínio exato'),
    ({'url': 'https://www.federacao.com.br.evil.com/nota'}, 'domínio exato'),
    ({'valido_ate': (editorial.agora() + dt.timedelta(hours=1)).isoformat()}, 'validade'),
    ({'coletado_em': lambda: (editorial.agora() + dt.timedelta(minutes=1)).isoformat()}, 'futuro'),
])
def test_bloqueios(client, redacao, mudanca, esperado, db_session):
    from app.models.esportes import FonteEsportiva
    _, fonte, _, _ = redacao
    e = _preencher(client, redacao)
    e['conteudo']['fatos'][0].update({k: v() if callable(v) else v for k, v in mudanca.items()})
    erros = editorial.alertas(ConteudoEdicao(**e['conteudo']), {fonte['id']: db_session.get(FonteEsportiva, fonte['id'])})
    assert any(esperado in erro.lower() for erro in erros), erros


def test_resultados_divergentes_e_mesma_origem(client, redacao, db_session):
    from app.models.esportes import FonteEsportiva
    _, fonte, _, _ = redacao
    e = _preencher(client, redacao)
    fatos = e['conteudo']['fatos']
    fatos[0].update(tipo='resultado', participantes=['Azul', 'Verde'], placar=[1, 0], competicao='Copa de teste', confirmacao='encerrado')
    fatos.append({**fatos[0], 'id': 'f3', 'placar': [0, 1], 'origem_comum': 'Outra apuração'})
    e['conteudo']['blocos'][2]['fato_ids'].append('f3')
    fontes = {fonte['id']: db_session.get(FonteEsportiva, fonte['id'])}
    assert any('resultados divergentes' in a for a in editorial.alertas(ConteudoEdicao(**e['conteudo']), fontes))
    fatos[2]['placar'] = [1, 0]
    fatos[2]['origem_comum'] = fatos[0]['origem_comum']
    assert any('já usado' in a for a in editorial.alertas(ConteudoEdicao(**e['conteudo']), fontes))
    fatos[0]['confirmacao'] = 'confirmado'
    assert any('evento encerrado' in a for a in editorial.alertas(ConteudoEdicao(**e['conteudo']), fontes))


def test_fonte_alterada_apos_aprovacao(client, redacao):
    h, fonte, _, _ = redacao
    e = _aprovar(client, h, _preencher(client, redacao))
    payload = {k: v for k, v in fonte.items() if k != 'id'}
    payload['ativa'] = False
    assert client.put(f'/esportes/fontes/{fonte["id"]}', json=payload, headers=h).status_code == 200
    lida = client.get(f'/esportes/edicoes/{e["id"]}', headers=h).json()
    assert lida['estado'] == 'bloqueado'
    assert any('bloqueada' in a for a in lida['alertas'])
    payload['ativa'] = True
    payload['revisao'] += 1
    assert client.put(f'/esportes/fontes/{fonte["id"]}', json=payload, headers=h).status_code == 200
    assert any('cadastro da fonte mudou' in a for a in client.get(f'/esportes/edicoes/{e["id"]}', headers=h).json()['alertas'])


def test_insuficiente_e_revisao_obrigatoria(client, redacao):
    h, _, e, _ = redacao
    assert client.post(f'/esportes/edicoes/{e["id"]}/aprovar-roteiro', headers=h, json={'revisao': e['revisao'], 'conferido': True}).status_code == 409
    e = _preencher(client, redacao)
    assert client.post(f'/esportes/edicoes/{e["id"]}/aprovar-roteiro', headers=h, json={'revisao': e['revisao']}).status_code == 422
    e['conteudo']['blocos'][0]['duracao_s'] = 9
    assert client.put(f'/esportes/edicoes/{e["id"]}', headers=h, json={'revisao': e['revisao'], 'conteudo': e['conteudo']}).status_code == 422


@pytest.mark.parametrize('dominio', ['https://www.federacao.com.br', 'www.federacao.com.br/path', '127.0.0.1', 'radio.local', 'radio..com', '-radio.com'])
def test_dominios_invalidos(dominio):
    with pytest.raises(ValidationError):
        Fonte(dominio=dominio, organizacao='Organização', temas='Esporte', ultima_revisao=editorial.agora().date(), condicoes_uso='Verificadas')


def test_sugestao_recebe_so_fatos_do_bloco(client, redacao, monkeypatch):
    h, _, _, _ = redacao
    e = _preencher(client, redacao)
    pacotes = []
    def gerar(system, pacote):
        import json
        pacotes.append(json.loads(pacote))
        return '{"texto": "Fala sugerida para revisão.", "fato_ids": ["f2"]}'
    monkeypatch.setattr('app.esportes.router.gerar_configuracao', gerar)
    url = f'/esportes/edicoes/{e["id"]}/blocos/bloco_2/sugerir'
    r = client.post(url, headers=h, json={'revisao': e['revisao']})
    assert r.status_code == 200, r.text
    assert [f['id'] for f in pacotes[0]['fatos']] == ['f2']
    assert client.get(f'/esportes/edicoes/{e["id"]}', headers=h).json()['aprovacao_roteiro'] is None
    monkeypatch.setattr('app.esportes.router.gerar_configuracao', lambda *a: '{"texto":"Inventada", "fato_ids":["desconhecido"]}')
    assert client.post(url, headers=h, json={'revisao': e['revisao']}).status_code == 502


@lru_cache
def _mp3(segundos):
    b = io.BytesIO()
    AudioSegment.silent(duration=segundos * 1000).export(b, format='mp3')
    return b.getvalue()


@pytest.mark.parametrize("modelo", ["boletim_2", "programa_30"])
def test_audio_real_exportacao_e_expiracao(client, redacao, tmp_path, monkeypatch, modelo):
    from app.storage.local import LocalStorage
    monkeypatch.setattr('app.esportes.router.get_storage', lambda: LocalStorage(str(tmp_path)))
    h, _, _, _ = redacao
    if modelo == 'programa_30':
        _, fonte, original, pid = redacao
        e = client.post(f'/esportes/programas/{pid}/edicoes', headers=h, json={'modelo': modelo, 'exibicao_em': original['conteudo']['exibicao_em']}).json()
        for i, b in enumerate(e['conteudo']['blocos']):
            b['texto'] = 'Conteúdo fictício de teste, previamente revisado.'
            if b['tipo'] not in ('abertura', 'encerramento', 'intervalo'):
                fato = {**_fato(fonte), 'id': f'f_{i}', 'evento': f'Acontecimento {i}'}
                e['conteudo']['fatos'].append(fato)
                b['fato_ids'] = [fato['id']]
        e = client.put(f'/esportes/edicoes/{e["id"]}', headers=h, json={'revisao': e['revisao'], 'conteudo': e['conteudo']}).json()
        e = _aprovar(client, h, e)
    else:
        e = _aprovar(client, h, _preencher(client, redacao))
    for b in e['conteudo']['blocos']:
        r = client.post(f'/esportes/edicoes/{e["id"]}/blocos/{b["id"]}/audio?revisao={e["revisao"]}', headers=h, files={'arquivo': ('fala.mp3', _mp3(b['duracao_s']), 'audio/mpeg')})
        assert r.status_code == 200, r.text
        e = r.json()
    assert e['alertas_audio'] == [] and e['estado'] == 'audio_pronto'
    assert client.get(f'/esportes/edicoes/{e["id"]}/exportar', headers=h).status_code == 409
    r = client.post(f'/esportes/edicoes/{e["id"]}/aprovar-audio', headers=h, json={'revisao': e['revisao'], 'conferido': True})
    assert r.status_code == 200, r.text
    e = r.json()
    r = client.get(f'/esportes/edicoes/{e["id"]}/exportar', headers=h)
    assert r.status_code == 200 and r.headers['content-type'] == 'audio/mpeg'
    assert abs(AudioSegment.from_file(io.BytesIO(r.content), format='mp3').duration_seconds - (1800 if modelo == 'programa_30' else 120)) <= 5
    assert r.headers['cache-control'] == 'no-store'
    futuro = dt.datetime.fromisoformat(e['conteudo']['fatos'][0]['valido_ate']) + dt.timedelta(seconds=1)
    monkeypatch.setattr(editorial, 'agora', lambda: futuro)
    assert client.get(f'/esportes/edicoes/{e["id"]}/exportar', headers=h).status_code == 409
    assert client.get(f'/esportes/edicoes/{e["id"]}/blocos/bloco_1/audio', headers=h).status_code == 409


def test_audio_fora_do_tempo_corrompido_e_falha_tts(client, redacao, tmp_path, monkeypatch):
    from app.storage.local import LocalStorage
    monkeypatch.setattr('app.esportes.router.get_storage', lambda: LocalStorage(str(tmp_path)))
    h, _, _, _ = redacao
    e = _aprovar(client, h, _preencher(client, redacao))
    assert client.post(f'/esportes/edicoes/{e["id"]}/blocos/bloco_1/audio?revisao={e["revisao"]}', headers=h, files={'arquivo': ('falso.mp3', b'nao e audio', 'audio/mpeg')}).status_code == 422
    for b in e['conteudo']['blocos']:
        e = client.post(f'/esportes/edicoes/{e["id"]}/blocos/{b["id"]}/audio?revisao={e["revisao"]}', headers=h, files={'arquivo': ('curto.mp3', _mp3(1), 'audio/mpeg')}).json()
    assert any('tolerância' in a for a in e['alertas_audio'])
    assert client.post(f'/esportes/edicoes/{e["id"]}/aprovar-audio', headers=h, json={'revisao': e['revisao'], 'conferido': True}).status_code == 409
    monkeypatch.setattr('app.esportes.router.tts_habilitado', lambda *a: True)
    monkeypatch.setattr('app.esportes.router.parametros_sintese', lambda *a: {})
    def falhar(*a, **kw):
        raise RuntimeError('Falha simulada')
    monkeypatch.setattr('app.esportes.router.sintetizar_audio', falhar)
    assert client.post(f'/esportes/edicoes/{e["id"]}/blocos/bloco_1/gerar-audio', headers=h, json={'revisao': e['revisao']}).status_code == 502
    assert client.get(f'/esportes/edicoes/{e["id"]}', headers=h).json()['aprovacao_audio'] is None


def test_voz_usa_texto_e_configuracao_da_edicao(client, redacao, tmp_path, monkeypatch):
    from app.storage.local import LocalStorage
    monkeypatch.setattr('app.esportes.router.get_storage', lambda: LocalStorage(str(tmp_path)))
    monkeypatch.setattr('app.esportes.router.tts_habilitado', lambda voz: True)
    monkeypatch.setattr('app.esportes.router.parametros_sintese', lambda *a: {'perfil': 'natural'})
    chamadas = []
    def sintetizar(texto, **kwargs):
        chamadas.append((texto, kwargs))
        return _mp3(10)
    monkeypatch.setattr('app.esportes.router.sintetizar_audio', sintetizar)
    h, _, _, _ = redacao
    e = _aprovar(client, h, _preencher(client, redacao))
    r = client.post(f'/esportes/edicoes/{e["id"]}/blocos/bloco_1/gerar-audio', headers=h, json={'revisao': e['revisao']})
    assert r.status_code == 200, r.text
    e = r.json()
    assert chamadas[0][0] == e['conteudo']['blocos'][0]['texto']
    assert chamadas[0][1]['perfil'] == 'natural'
    assert e['audios']['bloco_1']['duracao_s'] == 10
    assert e['aprovacao_audio'] is None


def test_arquivo_modificado_nao_pode_ser_reproduzido(client, redacao, tmp_path, monkeypatch, db_session):
    from app.storage.local import LocalStorage
    storage = LocalStorage(str(tmp_path))
    monkeypatch.setattr('app.esportes.router.get_storage', lambda: storage)
    h, _, _, _ = redacao
    e = _aprovar(client, h, _preencher(client, redacao))
    r = client.post(f'/esportes/edicoes/{e["id"]}/blocos/bloco_1/audio?revisao={e["revisao"]}', headers=h,
                    files={'arquivo': ('fala.mp3', _mp3(10), 'audio/mpeg')})
    assert r.status_code == 200
    caminho = db_session.get(EdicaoEsportiva, e['id']).audios['bloco_1']['path']
    storage.save(caminho, _mp3(1))
    r = client.get(f'/esportes/edicoes/{e["id"]}/blocos/bloco_1/audio', headers=h)
    assert r.status_code == 409
    assert 'mudou após a revisão' in r.json()['detail']


def test_perfil_inicial_e_edicao_herdam_programa_e_fuso_do_radialista(client, redacao, db_session):
    h, _, _, pid = redacao
    programa = db_session.get(Programa, pid)
    programa.nome = 'Bola na rede da emissora'
    programa.tom = 'Direto e com energia moderada'
    radialista = db_session.get(RadioConfig, programa.radio_config_id)
    radialista.timezone = 'America/Manaus'
    db_session.commit()
    perfil = client.get(f'/esportes/programas/{pid}/perfil', headers=h).json()
    assert perfil['nome'] == programa.nome
    assert perfil['estilo'] == programa.tom
    assert perfil['fuso'] == radialista.timezone
    r = client.post(f'/esportes/programas/{pid}/edicoes', headers=h,
                    json={'modelo': 'boletim_3', 'exibicao_em': (editorial.agora() + dt.timedelta(hours=2)).isoformat()})
    assert r.status_code == 201, r.text
    assert r.json()['conteudo']['titulo'] == programa.nome
    assert r.json()['conteudo']['perfil']['fuso'] == radialista.timezone
