import pytest

from app.live.music import MusicaEncontrada, buscar_musica, buscar_musica_fundo
from app.config.settings import settings


def _item(video_id, titulo, canal):
    return {
        "id": {"videoId": video_id},
        "snippet": {"title": titulo, "channelTitle": canal},
    }


@pytest.fixture(autouse=True)
def _sem_metadados_por_padrao(request, monkeypatch):
    """buscar_musica agora busca metadados (descricao/tags/ano) do video escolhido, o que faria
    todo teste que nao mocka isso bater na rede de verdade -- por padrao devolve vazio. Testes
    marcados com @pytest.mark.usa_metadados_reais testam _buscar_metadados_musica em si, entao
    nao podem ter essa funcao substituida antes de rodar."""
    if "usa_metadados_reais" in request.keywords:
        return
    monkeypatch.setattr("app.live.music._buscar_metadados_musica", lambda video_id: {})


def test_buscar_musica_sem_api_key_devolve_none(monkeypatch):
    monkeypatch.setattr(settings, "youtube_api_key", "")
    assert buscar_musica("qualquer coisa") is None


def test_buscar_musica_com_genero_ignora_genero_vizinho(monkeypatch):
    """Pedir 'xote' nao pode devolver 'chamame' so' porque o YouTube relacionou os dois --
    ver _palavras_chave_genero/genero_invalido em app.live.music."""
    monkeypatch.setattr(settings, "youtube_api_key", "fake-key")
    itens = [
        _item("id1", "Chamame Bem Tocado", "Canal Gaucho"),
        _item("id2", "Xote da Saudade", "Canal Gaucho"),
    ]
    monkeypatch.setattr("app.live.music._buscar_itens", lambda query: itens)
    monkeypatch.setattr("app.live.music._buscar_duracoes", lambda ids: {})

    resultado = buscar_musica("xote musica", genero="xote")
    assert resultado.video_id == "id2"


def test_buscar_musica_com_genero_ignora_acento(monkeypatch):
    monkeypatch.setattr(settings, "youtube_api_key", "fake-key")
    itens = [_item("id1", "Chamamé de Verdade", "Canal Gaucho")]
    monkeypatch.setattr("app.live.music._buscar_itens", lambda query: itens)
    monkeypatch.setattr("app.live.music._buscar_duracoes", lambda ids: {})

    resultado = buscar_musica("chamame musica", genero="chamamé")
    assert resultado.video_id == "id1"


def test_buscar_musica_com_genero_sem_match_relaxa_como_ultimo_recurso(monkeypatch):
    """Sem nenhum resultado do genero pedido, relaxa em vez de travar a busca -- mesma
    logica de preferencia (nao bloqueio duro) que ja existe pra duracao/limite de canal."""
    monkeypatch.setattr(settings, "youtube_api_key", "fake-key")
    itens = [_item("id1", "Chamame Bem Tocado", "Canal Gaucho")]
    monkeypatch.setattr("app.live.music._buscar_itens", lambda query: itens)
    monkeypatch.setattr("app.live.music._buscar_duracoes", lambda ids: {})

    resultado = buscar_musica("xote musica", genero="xote")
    assert resultado.video_id == "id1"


def test_buscar_musica_prioriza_canal_oficial_topic(monkeypatch):
    monkeypatch.setattr(settings, "youtube_api_key", "fake-key")
    itens = [
        _item("id1", "Musica Generica", "Canal Qualquer"),
        _item("id2", "Musica Oficial", "Artista - Topic"),
    ]
    monkeypatch.setattr("app.live.music._buscar_itens", lambda query: itens)
    monkeypatch.setattr("app.live.music._buscar_duracoes", lambda ids: {})

    resultado = buscar_musica("minha musica")
    assert resultado.video_id == "id2"
    assert resultado.canal == "Artista - Topic"


def test_buscar_musica_ignora_bloqueados(monkeypatch):
    monkeypatch.setattr(settings, "youtube_api_key", "fake-key")
    itens = [
        _item("id1", "Musica Proibida", "Canal Ruim"),
        _item("id2", "Musica Permitida", "Canal Bom"),
    ]
    monkeypatch.setattr("app.live.music._buscar_itens", lambda query: itens)
    monkeypatch.setattr("app.live.music._buscar_duracoes", lambda ids: {})

    resultado = buscar_musica("minha musica", bloqueados=["proibida"])
    assert resultado.video_id == "id2"


def test_buscar_musica_evita_video_ids_ja_tocados(monkeypatch):
    monkeypatch.setattr(settings, "youtube_api_key", "fake-key")
    itens = [_item("id1", "Musica A", "Canal A"), _item("id2", "Musica B", "Canal B")]
    monkeypatch.setattr("app.live.music._buscar_itens", lambda query: itens)
    monkeypatch.setattr("app.live.music._buscar_duracoes", lambda ids: {})

    resultado = buscar_musica("minha musica", evitar_video_ids={"id1"})
    assert resultado.video_id == "id2"


def test_buscar_musica_respeita_limite_por_canal(monkeypatch):
    monkeypatch.setattr(settings, "youtube_api_key", "fake-key")
    itens = [_item("id1", "Musica A", "Canal Saturado"), _item("id2", "Musica B", "Canal Livre")]
    monkeypatch.setattr("app.live.music._buscar_itens", lambda query: itens)
    monkeypatch.setattr("app.live.music._buscar_duracoes", lambda ids: {})

    resultado = buscar_musica(
        "minha musica", canais_recentes={"canal saturado": 2}, limite_por_canal=2
    )
    assert resultado.video_id == "id2"


def test_buscar_musica_pula_conteudo_sobre_a_musica(monkeypatch):
    monkeypatch.setattr(settings, "youtube_api_key", "fake-key")
    itens = [
        _item("id1", "A historia de uma musica famosa", "Canal Documentario"),
        _item("id2", "Musica de verdade", "Canal Normal"),
    ]
    monkeypatch.setattr("app.live.music._buscar_itens", lambda query: itens)
    monkeypatch.setattr("app.live.music._buscar_duracoes", lambda ids: {})

    resultado = buscar_musica("minha musica")
    assert resultado.video_id == "id2"


def test_buscar_musica_pula_cover_caseiro_e_karaoke(monkeypatch):
    """Cover/karaoke amador (audio duvidoso) nunca deve substituir a faixa oficial, mesmo
    passando nos outros filtros -- ver TERMOS_QUALIDADE_DUVIDOSA em app.live.music."""
    monkeypatch.setattr(settings, "youtube_api_key", "fake-key")
    itens = [
        _item("id1", "Minha Musica (cover caseiro voz e violão)", "Canal Amador"),
        _item("id2", "Minha Musica - Karaokê", "Canal Karaoke"),
        _item("id3", "Minha Musica de verdade", "Canal Normal"),
    ]
    monkeypatch.setattr("app.live.music._buscar_itens", lambda query: itens)
    monkeypatch.setattr("app.live.music._buscar_duracoes", lambda ids: {})

    resultado = buscar_musica("minha musica")
    assert resultado.video_id == "id3"


def test_buscar_musica_preferir_cantada_pula_instrumental(monkeypatch):
    """preferir_cantada=True evita versao instrumental quando a musica vai tocar pros ouvintes
    -- ver docstring de buscar_musica em app.live.music."""
    monkeypatch.setattr(settings, "youtube_api_key", "fake-key")
    itens = [
        _item("id1", "Minha Musica (Instrumental)", "Canal Instrumental"),
        _item("id2", "Minha Musica", "Canal Normal"),
    ]
    monkeypatch.setattr("app.live.music._buscar_itens", lambda query: itens)
    monkeypatch.setattr("app.live.music._buscar_duracoes", lambda ids: {})

    resultado = buscar_musica("minha musica", preferir_cantada=True)
    assert resultado.video_id == "id2"


def test_buscar_musica_preferir_cantada_relaxa_como_ultimo_recurso(monkeypatch):
    """So' instrumental disponivel: relaxa em vez de travar a busca -- preferencia,
    nunca bloqueio duro, mesma logica ja usada pra genero/duracao/limite de canal."""
    monkeypatch.setattr(settings, "youtube_api_key", "fake-key")
    itens = [_item("id1", "Minha Musica (Instrumental)", "Canal Instrumental")]
    monkeypatch.setattr("app.live.music._buscar_itens", lambda query: itens)
    monkeypatch.setattr("app.live.music._buscar_duracoes", lambda ids: {})

    resultado = buscar_musica("minha musica", preferir_cantada=True)
    assert resultado.video_id == "id1"


def test_buscar_musica_sem_preferir_cantada_aceita_instrumental(monkeypatch):
    """Default (preferir_cantada=False, ex: buscar_musica_fundo) nao filtra instrumental --
    musica de fundo QUER instrumental."""
    monkeypatch.setattr(settings, "youtube_api_key", "fake-key")
    itens = [_item("id1", "Minha Musica (Instrumental)", "Canal Instrumental")]
    monkeypatch.setattr("app.live.music._buscar_itens", lambda query: itens)
    monkeypatch.setattr("app.live.music._buscar_duracoes", lambda ids: {})

    resultado = buscar_musica("minha musica")
    assert resultado.video_id == "id1"


def test_buscar_musica_ao_vivo_de_canal_qualquer_e_rejeitado(monkeypatch):
    """Ao vivo so' e' aceitavel de canal oficial/grande produtora -- gravacao de show por
    canal qualquer nao pode substituir a faixa de estudio nem como ultimo recurso."""
    monkeypatch.setattr(settings, "youtube_api_key", "fake-key")
    itens = [_item("id1", "Minha Musica Ao Vivo", "Canal De Fã")]
    monkeypatch.setattr("app.live.music._buscar_itens", lambda query: itens)
    monkeypatch.setattr("app.live.music._buscar_duracoes", lambda ids: {})

    assert buscar_musica("minha musica") is None


def test_buscar_musica_exigir_canal_oficial_rejeita_canal_qualquer(monkeypatch):
    """Com exigir_canal_oficial=True, canal que nao e' selo/VEVO/"- Topic" nunca vence, mesmo
    sem nenhum outro problema (sem bloqueado, duracao valida, titulo limpo) -- bloqueio duro,
    ao contrario do resto da funcao que so' prioriza canal oficial (ver
    test_buscar_musica_prioriza_canal_oficial_topic)."""
    monkeypatch.setattr(settings, "youtube_api_key", "fake-key")
    itens = [_item("id1", "Minha Musica - Artista", "Canal De Fã Qualquer")]
    monkeypatch.setattr("app.live.music._buscar_itens", lambda query: itens)
    monkeypatch.setattr("app.live.music._buscar_duracoes", lambda ids: {})

    assert buscar_musica("minha musica", exigir_canal_oficial=True) is None


def test_buscar_musica_exigir_canal_oficial_aceita_topic_e_vevo(monkeypatch):
    monkeypatch.setattr(settings, "youtube_api_key", "fake-key")
    itens = [
        _item("id1", "Minha Musica - Artista", "Canal De Fã Qualquer"),
        _item("id2", "Minha Musica - Artista", "Artista - Topic"),
    ]
    monkeypatch.setattr("app.live.music._buscar_itens", lambda query: itens)
    monkeypatch.setattr("app.live.music._buscar_duracoes", lambda ids: {})

    resultado = buscar_musica("minha musica", exigir_canal_oficial=True)
    assert resultado.video_id == "id2"


def test_buscar_musica_ao_vivo_de_canal_oficial_e_aceito(monkeypatch):
    """Ao vivo publicado por canal oficial (selo/VEVO/"- Topic") e' aceitavel -- grande
    produtora do mercado, sinal de qualidade mesmo sem ser a faixa de estudio."""
    monkeypatch.setattr(settings, "youtube_api_key", "fake-key")
    itens = [_item("id1", "Minha Musica Ao Vivo", "Artista - Topic")]
    monkeypatch.setattr("app.live.music._buscar_itens", lambda query: itens)
    monkeypatch.setattr("app.live.music._buscar_duracoes", lambda ids: {})

    resultado = buscar_musica("minha musica")
    assert resultado.video_id == "id1"


def test_buscar_musica_combina_inicio_segundos_com_deteccao_de_fala(monkeypatch):
    """inicio_segundos final e' o MAIOR entre a heuristica da escolha (ex.: SEGUNDOS_PULAR_AO_VIVO
    pra versao ao vivo) e o que a deteccao de fala/silencio no comeco achar (ver
    obter_inicio_seguro) -- a deteccao e' mais um sinal de onde cortar, nunca reduz um corte que
    ja se sabia necessario."""
    monkeypatch.setattr(settings, "youtube_api_key", "fake-key")
    itens = [_item("id1", "Minha Musica Ao Vivo", "Artista - Topic")]
    monkeypatch.setattr("app.live.music._buscar_itens", lambda query: itens)
    monkeypatch.setattr("app.live.music._buscar_duracoes", lambda ids: {"id1": 200})
    monkeypatch.setattr("app.live.music.obter_inicio_seguro", lambda video_id, duracao: 25)

    resultado = buscar_musica("minha musica")
    assert resultado.inicio_segundos == 25  # deteccao (25) > heuristica ao vivo (15)


def test_buscar_musica_prefere_duracao_curta_quando_ha_alternativa(monkeypatch):
    """Duracao muito longa e' preferencia, nao bloqueio duro -- se existe alternativa dentro do
    teto (_DURACAO_MAX_SEGUNDOS), ela vence mesmo que a faixa longa aparecesse primeiro na lista."""
    monkeypatch.setattr(settings, "youtube_api_key", "fake-key")
    itens = [
        _item("id_longo", "Minha Musica Estendida - Artista", "Canal Qualquer"),
        _item("id_curto", "Minha Musica - Artista", "Canal Qualquer"),
    ]
    monkeypatch.setattr("app.live.music._buscar_itens", lambda query: itens)
    monkeypatch.setattr("app.live.music._buscar_duracoes", lambda ids: {"id_longo": 3600, "id_curto": 200})

    resultado = buscar_musica("minha musica")
    assert resultado.video_id == "id_curto"


def test_buscar_musica_aceita_duracao_longa_como_ultimo_recurso(monkeypatch):
    """Sem alternativa nenhuma dentro do teto de preferencia, a faixa longa ainda toca --
    preferencia relaxa no ultimo recurso em vez de deixar o bloco sem musica nenhuma (busca ja
    parte de titulo+artista resolvido via Spotify/catalogo, o YouTube so' precisa achar ESSE
    audio). 900s (15min) fica acima do teto de preferencia (_DURACAO_MAX_SEGUNDOS, 8min) mas
    dentro do teto absoluto (_DURACAO_MAX_ABSOLUTA_SEGUNDOS, 20min) -- ver teste seguinte pro
    caso do teto absoluto, esse sim nunca relaxado. Medley/coletanea sem palavra reveladora no
    titulo continua barrado por titulo (ver TERMOS_COLETANEA/PADRAO_TOP_N), e o corte por
    fala/silencio no fim/comeco (obter_fim_seguro/obter_inicio_seguro) cobre a reproducao em si."""
    monkeypatch.setattr(settings, "youtube_api_key", "fake-key")
    itens = [_item("id1", "Minha Musica - Artista", "Canal Qualquer")]
    monkeypatch.setattr("app.live.music._buscar_itens", lambda query: itens)
    monkeypatch.setattr("app.live.music._buscar_duracoes", lambda ids: {"id1": 900})

    resultado = buscar_musica("minha musica")
    assert resultado.video_id == "id1"


def test_buscar_musica_rejeita_duracao_acima_do_teto_absoluto_mesmo_sem_alternativa(monkeypatch):
    """Teto absoluto (_DURACAO_MAX_ABSOLUTA_SEGUNDOS) NUNCA relaxa, nem no ultimo recurso --
    diferente do teto de preferencia (ver teste anterior). Cobre o caso real que motivou esse
    teto: busca sem pedido especifico (query generica tipo "musica instrumental") devolvendo
    quase so' mix ambiente de horas, onde SEM esse teto o unico candidato conhecido (por mais
    que fosse um mix de horas, nao uma musica) acabava tocando como ultimo recurso."""
    monkeypatch.setattr(settings, "youtube_api_key", "fake-key")
    itens = [_item("id1", "Music for Deep Focus and Concentration - 10 Hours", "Canal Qualquer")]
    monkeypatch.setattr("app.live.music._buscar_itens", lambda query: itens)
    monkeypatch.setattr("app.live.music._buscar_duracoes", lambda ids: {"id1": 36000})

    resultado = buscar_musica("musica instrumental")
    assert resultado is None


def test_buscar_musica_rejeita_duracao_conhecida_abaixo_do_minimo_mesmo_relaxando(monkeypatch):
    """O passo relaxado (ultimo recurso, quando nenhuma combinacao estrita deu resultado) so'
    deveria perdoar duracao DESCONHECIDA (falha/cota da API) -- duracao CONHECIDA abaixo do
    minimo (trailer/teaser/Short) continua invalida mesmo nesse ultimo recurso."""
    monkeypatch.setattr(settings, "youtube_api_key", "fake-key")
    itens = [_item("id1", "Minha Musica - Artista (Trailer)", "Canal Qualquer")]
    monkeypatch.setattr("app.live.music._buscar_itens", lambda query: itens)
    monkeypatch.setattr("app.live.music._buscar_duracoes", lambda ids: {"id1": 30})

    assert buscar_musica("minha musica") is None


def test_buscar_musica_duracao_desconhecida_ainda_e_aceita_como_ultimo_recurso(monkeypatch):
    """Duracao DESCONHECIDA (falha/cota da API de videos.list) continua sendo aceita no passo
    relaxado -- e' o unico caso que o 'ultimo recurso' deve perdoar, pra nao travar a busca
    inteira so' porque a API de duracao falhou."""
    monkeypatch.setattr(settings, "youtube_api_key", "fake-key")
    itens = [_item("id1", "Musica sem duracao conhecida", "Canal Qualquer")]
    monkeypatch.setattr("app.live.music._buscar_itens", lambda query: itens)
    monkeypatch.setattr("app.live.music._buscar_duracoes", lambda ids: {})

    resultado = buscar_musica("minha musica")
    assert resultado.video_id == "id1"


def test_buscar_musica_sem_resultado_nenhum_devolve_none(monkeypatch):
    monkeypatch.setattr(settings, "youtube_api_key", "fake-key")
    monkeypatch.setattr("app.live.music._buscar_itens", lambda query: [])
    monkeypatch.setattr("app.live.music._buscar_duracoes", lambda ids: {})

    assert buscar_musica("nada encontrado") is None


def test_buscar_musica_fundo_usa_genero_aleatorio(monkeypatch):
    monkeypatch.setattr(settings, "youtube_api_key", "fake-key")
    capturado = {}

    def _fake_buscar_musica(query, bloqueados=None, **kwargs):
        capturado["query"] = query
        return MusicaEncontrada(video_id="id1", titulo="Instrumental", canal="Canal X")

    monkeypatch.setattr("app.live.music.buscar_musica", _fake_buscar_musica)
    resultado = buscar_musica_fundo(["sertanejo"])
    assert "sertanejo" in capturado["query"]
    assert resultado.video_id == "id1"


def test_buscar_musica_fundo_sem_generos_usa_query_generica(monkeypatch):
    capturado = {}

    def _fake_buscar_musica(query, bloqueados=None, **kwargs):
        capturado["query"] = query
        return None

    monkeypatch.setattr("app.live.music.buscar_musica", _fake_buscar_musica)
    buscar_musica_fundo([])
    assert capturado["query"] == "musica instrumental radio fundo"


def test_buscar_musica_preenche_descricao_tags_ano_do_video_escolhido(monkeypatch):
    """Contexto real (descricao/tags/ano) precisa vir preenchido no resultado final -- e' o
    que alimenta resumir_contexto_musica antes do locutor falar da musica (ver _contexto_musica
    em app.live.router)."""
    monkeypatch.setattr(settings, "youtube_api_key", "fake-key")
    itens = [_item("id1", "Musica Teste", "Canal Teste")]
    monkeypatch.setattr("app.live.music._buscar_itens", lambda query: itens)
    monkeypatch.setattr("app.live.music._buscar_duracoes", lambda ids: {})
    monkeypatch.setattr(
        "app.live.music._buscar_metadados_musica",
        lambda video_id: {"descricao": "Uma musica sobre o interior", "tags": ["sertanejo", "raiz"], "ano": "1998"},
    )

    resultado = buscar_musica("minha musica")
    assert resultado.descricao == "Uma musica sobre o interior"
    assert resultado.tags == ["sertanejo", "raiz"]
    assert resultado.ano == "1998"


def test_buscar_musica_metadados_so_busca_pro_video_escolhido(monkeypatch):
    """So' gasta cota da API de metadados no video que VENCEU a escolha, nao em todo candidato
    descartado -- ao contrario da duracao, que precisa ser checada pra todo mundo antes de
    decidir quem vence."""
    monkeypatch.setattr(settings, "youtube_api_key", "fake-key")
    itens = [
        _item("id_descartado", "Historia da musica", "Canal Documentario"),
        _item("id_escolhido", "Musica de Verdade", "Canal Normal"),
    ]
    monkeypatch.setattr("app.live.music._buscar_itens", lambda query: itens)
    monkeypatch.setattr("app.live.music._buscar_duracoes", lambda ids: {})

    chamadas = []

    def _fake_metadados(video_id):
        chamadas.append(video_id)
        return {}

    monkeypatch.setattr("app.live.music._buscar_metadados_musica", _fake_metadados)

    resultado = buscar_musica("minha musica")
    assert resultado.video_id == "id_escolhido"
    assert chamadas == ["id_escolhido"]


@pytest.mark.usa_metadados_reais
def test_buscar_metadados_musica_cacheia_por_video_id(monkeypatch):
    """Metadados de um video_id nao mudam depois de publicado -- so' bate na API do YouTube
    uma vez, chamadas seguintes vem do cache (mesma logica de _buscar_duracoes)."""
    from app.live.music import _buscar_metadados_musica

    monkeypatch.setattr(settings, "youtube_api_key", "fake-key")

    chamadas_http = []

    class _RespostaFake:
        def raise_for_status(self):
            pass

        def json(self):
            chamadas_http.append(1)
            return {"items": [{"snippet": {"description": "desc", "tags": ["a"], "publishedAt": "2020-01-01"}}]}

    monkeypatch.setattr("app.live.music.httpx.get", lambda *a, **k: _RespostaFake())

    primeira = _buscar_metadados_musica("id-cache")
    segunda = _buscar_metadados_musica("id-cache")
    assert primeira == segunda == {"descricao": "desc", "tags": ["a"], "ano": "2020"}
    assert len(chamadas_http) == 1  # segunda chamada veio do cache, nao bateu na API de novo
