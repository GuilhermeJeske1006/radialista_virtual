"""Fluxo completo de ponta a ponta do plano de "profundidade de lugar/rádio e indistinguibilidade
de fala": configura rádio + radialista via API real (mesmo payload que o frontend manda), simula
um programa inteiro rodando bloco a bloco (abertura -> música -> comentário -> notícia -> chamada
ao ouvinte), e confere que cada feature das Frentes F/G/H/I/J aparece de fato no prompt que vai
pro LLM em algum ponto da transmissão."""

import datetime

from freezegun import freeze_time

from app.live.music import MusicaEncontrada
from app.models.fila_ao_vivo import FilaAoVivo
from app.models.programa import Programa
from app.models.tema_historico import TemaHistorico

AGORA_UTC = "2026-08-10 15:00:00"  # 12:00 local, meio de um programa 10:00-14:00


@freeze_time(AGORA_UTC)
def test_fluxo_completo_profundidade_de_lugar_e_radio(client, account, auth_headers, db_session, monkeypatch):
    headers = auth_headers(account.id)

    # 1) Configura a rádio inteira via API real -- ConhecimentoLocal (F.1) + BibliaRadio (G.1/G.2/G.3).
    payload_radio = {
        "nome_radio": "Rádio Serra Viva",
        "slogan": "A rádio da nossa gente",
        "frequencia": "98,5",
        "telefone": "5511999990000",
        "endereco": "Praça Central, 100",
        "cidade": "Gramado",
        "tipo_radio": "",
        "conhecimento_local": {
            "bairros": ["Centro"],
            "pontos_referencia": ["Praça das Etnias"],
            "eventos_recorrentes": ["Natal Luz em dezembro"],
            "expressoes_regionais": ["tchê"],
            "gentilico": "gramadense",
        },
        "biblia_radio": {
            "historia": "Fundada em 1998 por seu Zé, começou como rádio comunitária de bairro.",
            "rotina": ["toda sexta tem transmissão do jogo do time local"],
            "programas_grade": ["Bom dia Serra, das 6h às 8h, não é gerado por IA"],
            "equipe": ["Marcos, técnico de som"],
            "habitos_trabalho": ["confere o trânsito antes de entrar no ar"],
        },
    }
    resposta_radio = client.put("/config/radio", json=payload_radio, headers=headers)
    assert resposta_radio.status_code == 200
    corpo_radio = resposta_radio.json()
    assert corpo_radio["conhecimento_local"]["gentilico"] == "gramadense"
    assert corpo_radio["biblia_radio"]["equipe"] == ["Marcos, técnico de som"]

    # 2) Cria radialista com biografia (H.1), traços marcantes (H.3) e fatos do dia (H.2) via API.
    payload_radialista = {
        "nome_locutor": "Zé da Serra",
        "personalidade": "animado e caloroso",
        "biografia": "Nascido em Gramado, trabalha nessa rádio há 12 anos.",
        "tracos_marcantes": ["sempre implica com quem não gosta de frio"],
        "fatos_do_dia": ["hoje eu vim de bicicleta porque o carro não pegou"],
        "voz_id": None,
        "timezone": "America/Sao_Paulo",
        "resposta_automatica_whatsapp": False,
    }
    resposta_radialista = client.post("/config/radialistas", json=payload_radialista, headers=headers)
    assert resposta_radialista.status_code == 201
    radialista_id = resposta_radialista.json()["id"]

    # 3) Programa cobrindo 10h-14h, com tipos_noticias definido (senão categoria "noticia" cai
    # automaticamente pra "musica" por falta de fonte -- ver gerar_proxima_fala).
    programa = Programa(
        radio_config_id=radialista_id,
        nome="Programa da Manhã",
        horario_inicio=datetime.time(10, 0),
        horario_fim=datetime.time(14, 0),
        estrutura_blocos=[],
        tipos_noticias=["geral"],
    )
    db_session.add(programa)
    db_session.commit()
    db_session.refresh(programa)

    # 4) Estado pré-existente pra callback de tema anterior (J.1) e ouvinte recorrente entre dias (J.2).
    db_session.add(TemaHistorico(programa_id=programa.id, tema="Chuva forte na serra semana passada"))
    agora = datetime.datetime.now(datetime.timezone.utc)
    db_session.add(
        FilaAoVivo(
            radio_config_id=radialista_id,
            telefone="5511977776666",
            nome="Roberto",
            tipo="abraco",
            mensagem_usuario="voltei",
            atendido=False,
            criado_em=agora - datetime.timedelta(seconds=5),
        )
    )
    db_session.add(
        FilaAoVivo(
            radio_config_id=radialista_id,
            telefone="5511977776666",
            nome="Roberto",
            tipo="musica",
            mensagem_usuario="toca uma antiga",
            atendido=True,
            atendido_em=agora - datetime.timedelta(days=5),
            criado_em=agora - datetime.timedelta(days=5),
        )
    )
    # pedido "recente" (I.2) -- chega enquanto outro tipo de bloco está sendo gerado.
    db_session.add(
        FilaAoVivo(
            radio_config_id=radialista_id,
            telefone="5511988887777",
            nome="Carla",
            tipo="abraco",
            mensagem_usuario="cheguei agora",
            atendido=False,
            criado_em=agora,
        )
    )
    db_session.commit()

    monkeypatch.setattr("app.live.router.random.random", lambda: 0.0)
    monkeypatch.setattr(
        "app.live.router.buscar_musica",
        lambda query, **kwargs: MusicaEncontrada(video_id="abc123", titulo="Música Teste", canal="Canal Teste"),
    )
    # Evita chamadas reais de LLM pra classificacao (nao mockadas por padrao) alterarem o estado
    # controlado do teste (historico de temas / fio condutor).
    monkeypatch.setattr("app.live.router.classificar_tema_fala", lambda texto: "")
    monkeypatch.setattr("app.live.router.classificar_fio_condutor", lambda texto: "")

    prompts = []
    monkeypatch.setattr(
        "app.live.router.gerar_resposta", lambda system, msg: prompts.append(system) or "Seguimos no ar."
    )

    historico: list[str] = []
    for total_falas in range(0, 6):
        resposta = client.post(
            f"/live/{radialista_id}/programas/{programa.id}/proxima",
            json={"historico": historico, "total_falas": total_falas},
            headers=headers,
        )
        assert resposta.status_code == 200, resposta.text
        corpo = resposta.json()
        historico.append(f"{corpo['tipo']}: {corpo.get('fala', '')}")

    tipos_gerados = [linha.split(":")[0] for linha in historico]
    assert tipos_gerados == ["abertura", "musica", "abertura", "comentario", "noticia", "chamada_ouvinte"]

    prompt_completo = "\n---\n".join(prompts)

    # F.1 -- conhecimento local: pool de 4 itens rotaciona 1 por chamada, 6 chamadas cobrem todos.
    assert "gramadense" in prompt_completo
    assert "Centro" in prompt_completo
    assert "Praça das Etnias" in prompt_completo
    assert "Natal Luz em dezembro" in prompt_completo

    # F.2 -- gíria regional oferecida como opção de fala natural (categoria != noticia).
    assert "tchê" in prompt_completo

    # G.1 -- história da rádio, fato fixo, presente em toda chamada.
    assert "Fundada em 1998 por seu Zé" in prompt_completo

    # G.1/G.2/G.3 -- rotina, grade, equipe e hábitos: pool de 4 itens, mesma lógica de rotação.
    assert "toda sexta tem transmissão do jogo do time local" in prompt_completo
    assert "Bom dia Serra, das 6h às 8h" in prompt_completo
    assert "Marcos, técnico de som" in prompt_completo
    assert "confere o trânsito antes de entrar no ar" in prompt_completo

    # H.1 -- biografia fixa, presente em toda chamada.
    assert "Nascido em Gramado" in prompt_completo

    # H.3 -- traço marcante do radialista.
    assert "sempre implica com quem não gosta de frio" in prompt_completo

    # H.2 -- fato do dia, sorteado e estável pela sessão.
    assert "hoje eu vim de bicicleta" in prompt_completo

    # I.1 -- gate de mudança genuína de ideia (forçado via random.random = 0.0).
    assert "genuinamente mudar de ideia" in prompt_completo

    # I.4 -- gate de imperfeição gramatical calibrada.
    assert "concordância um pouco mais coloquial" in prompt_completo

    # I.2 -- pedido da Carla "acabou de chegar" durante outro tipo de bloco (nunca é consumido de
    # verdade por esse peek).
    assert "Acabou de chegar uma mensagem nova" in prompt_completo

    # I.3 -- ajuste de energia no miolo do programa (12:00 de um programa 10:00-14:00).
    assert "energia um pouco mais contida" in prompt_completo

    # J.1 -- callback explícito pra tema de transmissão anterior (TemaHistorico pré-existente).
    assert "callback explícito" in prompt_completo
    assert "Chuva forte na serra semana passada" in prompt_completo

    # J.2 -- Roberto reconhecido como ouvinte de uma transmissão de outro dia (5 dias atrás,
    # mesmo telefone), não como recorrente "desta transmissão".
    assert "já apareceu em uma transmissão de outro dia" in prompt_completo
    assert "já apareceu antes nesta transmissão" not in prompt_completo

    # Features já existentes (B.4/hora certa) continuam funcionando junto com as novas.
    assert "marque a hora certa" in prompt_completo


@freeze_time(AGORA_UTC)
def test_fluxo_sem_nenhum_dado_de_profundidade_configurado_nao_quebra(
    client, account, auth_headers, db_session, monkeypatch
):
    """Conta/radialista/programa sem nenhum campo novo preenchido (caso mais comum: usuário ainda
    não configurou nada) precisa continuar funcionando normalmente, sem crash nem instrução vazia
    estranha no prompt."""
    headers = auth_headers(account.id)

    resposta_radialista = client.post(
        "/config/radialistas",
        json={"nome_locutor": "Locutor Padrão", "timezone": "America/Sao_Paulo"},
        headers=headers,
    )
    assert resposta_radialista.status_code == 201
    radialista_id = resposta_radialista.json()["id"]

    programa = Programa(
        radio_config_id=radialista_id,
        nome="Programa Simples",
        horario_inicio=datetime.time(10, 0),
        horario_fim=datetime.time(14, 0),
        estrutura_blocos=[],
    )
    db_session.add(programa)
    db_session.commit()
    db_session.refresh(programa)

    monkeypatch.setattr("app.live.router.classificar_tema_fala", lambda texto: "")
    monkeypatch.setattr("app.live.router.classificar_fio_condutor", lambda texto: "")
    monkeypatch.setattr(
        "app.live.router.buscar_musica",
        lambda query, **kwargs: MusicaEncontrada(video_id="abc123", titulo="Música Teste", canal="Canal Teste"),
    )
    prompts = []
    monkeypatch.setattr(
        "app.live.router.gerar_resposta", lambda system, msg: prompts.append(system) or "Seguimos no ar."
    )

    historico: list[str] = []
    for total_falas in range(0, 5):
        resposta = client.post(
            f"/live/{radialista_id}/programas/{programa.id}/proxima",
            json={"historico": historico, "total_falas": total_falas},
            headers=headers,
        )
        assert resposta.status_code == 200, resposta.text
        corpo = resposta.json()
        historico.append(f"{corpo['tipo']}: {corpo.get('fala', '')}")

    assert len(prompts) == 5
