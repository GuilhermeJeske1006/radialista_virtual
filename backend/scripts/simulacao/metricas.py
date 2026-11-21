"""Detectores e métricas do resumo.json (auditoria F0 §5.7 e §5.8).

Música anunciada: desde a F3, o mesmo detector do backend (app.live.validacao_fala.mencoes_musica). Promessa e
participação: desde a F4, os do backend (app.live.promessas.detectar e app.live.participacao.mencoes_participacao),
importados na função; não existe um segundo detector aqui. Com os dados do backend no as-run (`promessas`, a
tabela promessas_no_ar ao fim), promessa vencida é a que venceu ou ficou aberta, ou cuja resolução não foi ao ar;
sem eles (as-runs antigos ou artificiais), vale a regra da F0 (promessa de música fechada pela faixa seguinte).
Dado sem fonte e vencido: desde a F5, o detector do backend (app.dados.checagem.afirmacoes e checar_fala) sobre a
fala que foi ao ar e os dados do bloco gravados no as-run, no instante em que a fala começou.
Abertura repetida continua heurística da F0 (F8). Coerência com o formato (F6): `metricas_formato` só leva o as-run
para `app.live.formatos.coerencia` (convite, tema, reorientação e unidade são detectados lá, não aqui). Este módulo
não importa app.* no carregamento.
"""

import collections
import re
import unicodedata

CONFIG_METRICAS = {
    "promessas": {
        # Prazo por classe (app.live.promessas.CONFIG_PROMESSAS), só para as-runs sem dados do backend.
        "prazo_s": {"imediato": 300, "curto": 900},
        # Estas vencem só no fim do programa.
        "ate_fim_do_programa": ["intervalo", "fim", "fora"],
    },
    # Construções que o banco de falas do dublê só usa com pedido real (tests/test_simular_hora.py).
    "pedido_indevido": {"padroes": ["toca agora", "pediu"]},
    "abertura_repetida": {"palavras": 3, "seguidas": 3},
    # F8 (passo 2): mesma construção de abertura (app.live.memoria.abertura_da_fala) em N falas seguidas.
    "repeticao_estrutura": {"seguidas": 3},
    "hard_time": {"tolerancia_s": 5.0},
    # F2: teto do orçamento (app.config.settings.fala_teto_orcamento) e quantas falas medidas contam como
    # "antes da calibração" (fala_calibracao_min_amostras). Repetidos aqui para o módulo não importar app.*.
    "orcamento": {"teto": 0.30, "amostras_calibracao": 5},
    "tipos_fala": ["fala"],
    "tipos_silencio": ["bloco_vazio", "erro"],
    # F5: fuso só para o texto da instrução do validador (a checagem não depende dele).
    "dados": {"tz": "America/Sao_Paulo"},
}


def normalizar(texto: str) -> str:
    sem_acento = "".join(c for c in unicodedata.normalize("NFD", (texto or "").lower()) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", sem_acento).strip()


def _contem(texto_normalizado: str, trecho: str) -> bool:
    alvo = normalizar(trecho)
    return bool(alvo) and f" {alvo} " in f" {texto_normalizado} "


def detectar_promessas(texto: str, inicio_s: float, fim_programa_s: float, n: int, config: dict | None = None) -> list[dict]:
    """Promessas a cumprir nesta transmissão: o detector do backend (app.live.promessas), sem as que a forma já
    resolve (despedida e volta do programa, continuidade, "mais música")."""
    from app.live.promessas import a_registrar, detectar

    cfg = (config or CONFIG_METRICAS)["promessas"]
    achadas = []
    for promessa in detectar(texto):
        if not a_registrar(promessa):
            continue
        prazo = max(0.0, fim_programa_s - inicio_s) if promessa.classe in cfg["ate_fim_do_programa"] \
            else cfg["prazo_s"][promessa.classe]
        achadas.append({"id": f"p{n}.{len(achadas) + 1}", "padrao": promessa.marcador, "classe": promessa.classe,
                        "tipo": promessa.tipo, "trecho": promessa.frase, "prazo_s": round(prazo, 2)})
    return achadas


def mencoes(texto: str, citaveis: list[tuple[str, str]], nao_musica: list[str] | tuple = (),
            confirmaveis: list[str] | tuple = ()) -> list[str]:
    """Rótulos das músicas citadas no texto, em ordem: 'Título - Artista' quando o título é do catálogo, senão o
    trecho da construção de anúncio. Uma menção que o backend aceita como uma das `confirmaveis` (outro sotaque de
    título, ou só o artista) leva o rótulo dela. Delegado ao detector do backend (app.live.validacao_fala)."""
    from app.live.contexto import MusicaRef
    from app.live.validacao_fala import confirmada, mencoes_musica

    refs = [MusicaRef(titulo, artista, origem="conhecida") for titulo, artista in citaveis]
    rotulos = []
    for mencao in mencoes_musica(texto, refs, nao_musica):
        rotulo = mencao.rotulo
        for candidata in (c for c in confirmaveis if c):
            titulo, _, artista = candidata.rpartition(" - ")
            if confirmada(mencao, [titulo or artista], [artista] if titulo else []):
                rotulo = candidata
                break
        rotulos.append(rotulo)
    return rotulos


def titulos_citados(texto: str, citaveis: list[tuple[str, str]]) -> list[str]:
    """Rótulos 'Título - Artista' dos títulos do catálogo citados no texto, em ordem (invólucro do detector do
    backend, sem os trechos de título desconhecido)."""
    rotulos = {f"{titulo} - {artista}" for titulo, artista in citaveis}
    return [r for r in mencoes(texto, citaveis) if r in rotulos]


def anotar_eventos(as_run: dict, citaveis: list[tuple[str, str]], config: dict | None = None,
                   nao_musica: list[str] | None = None) -> None:
    """Preenche musicas_citadas, musica_anunciada, musica_tocada, promessas e participação de cada evento."""
    eventos = as_run["eventos"]
    fim_programa_s = float(as_run["duracao_programa_s"])
    nao_musica = list(nao_musica if nao_musica is not None else as_run.get("nomes_nao_musica") or [])
    backend = as_run.get("promessas") is not None
    tocadas: set[str] = set()
    for indice, evento in enumerate(eventos):
        if evento["tipo"] == "musica":
            tocadas.add(evento["musica_tocada"])
            continue
        if evento["tipo"] != "fala":
            continue
        proxima = next((e for e in eventos[indice + 1:] if e["tipo"] == "musica"), None)
        evento["musica_tocada"] = proxima["musica_tocada"] if proxima else None
        confirmaveis = [*(evento.get("musicas_bloco") or []), evento["musica_tocada"], *sorted(tocadas)]
        citadas = mencoes(evento["texto"], citaveis, nao_musica, confirmaveis)
        evento["musicas_citadas"] = citadas
        evento["musica_anunciada"] = [c for c in citadas if c not in tocadas]
        promessas = detectar_promessas(evento["texto"], evento["inicio_s"], fim_programa_s, evento["n"], config)
        if backend:
            # Promessa de música é da F3 (anúncio sem confirmação); as outras casam com o registro do backend.
            promessas = [p for p in promessas if not mencoes(p["trecho"], citaveis, nao_musica)]
            _casar_com_registro(promessas, eventos, evento)
        evento["promessas_abertas"] = promessas
        evento["participacao"] = _participacao(evento, as_run, citaveis, nao_musica)
    if backend:
        for evento in eventos:
            for item in (evento.get("promessas") or {}).get("resolvidas") or []:
                evento["promessas_fechadas"].append(f"b{item['id']}")
        return
    # Na F0 só fecha a promessa de música cumprida pela próxima faixa, dentro do prazo. O resto vence.
    for indice, evento in enumerate(eventos):
        if evento["tipo"] != "fala" or not evento["promessas_abertas"] or not evento["musica_anunciada"]:
            continue
        proxima = next((e for e in eventos[indice + 1:] if e["tipo"] == "musica"), None)
        if proxima is None or proxima["musica_tocada"] not in evento["musica_anunciada"]:
            continue
        for promessa in evento["promessas_abertas"]:
            if proxima["inicio_s"] <= evento["inicio_s"] + promessa["prazo_s"]:
                proxima["promessas_fechadas"].append(promessa["id"])


def _casar_com_registro(promessas: list[dict], eventos: list[dict], evento: dict) -> None:
    """Marca as promessas detectadas no texto que o backend registrou no mesmo bloco (pela frase)."""
    primeiro = next((e for e in eventos if e["bloco_n"] == evento["bloco_n"]), evento)
    registradas = list((primeiro.get("promessas") or {}).get("registradas") or [])
    for promessa in promessas:
        casada = next((r for r in registradas if normalizar(r["trecho"]) == normalizar(promessa["trecho"])), None)
        promessa["registrada"] = casada is not None
        if casada is not None:
            promessa["id"] = f"b{casada['id']}"
            registradas.remove(casada)


def _nomes_participacao(evento: dict, as_run: dict, selecionado: bool, citaveis=(), nao_musica=()):
    from app.live.contexto import MusicaRef
    from app.live.participacao import NomesParticipacao

    ouvintes = as_run.get("ouvintes") or {}
    conhecidos = [n for n in ouvintes.get("fixture") or [] if n]
    pedidos = {p["id"]: p for p in as_run.get("pedidos") or []}
    pedido = pedidos.get(evento.get("pedido_id"))
    ja_atendidos = [p["nome"] for p in pedidos.values() if p.get("tocou_em_s") is not None
                    and p["tocou_em_s"] < evento["inicio_s"] and p.get("estado_final") == "executado"]
    inexistentes = set(ouvintes.get("inexistentes") or [])
    excluidos = [n for n in nao_musica if n not in conhecidos and n not in inexistentes]
    return NomesParticipacao(
        selecionados=(pedido["nome"],) if pedido is not None and selecionado else (),
        ja_atendidos=tuple(ja_atendidos), conhecidos=tuple(conhecidos), excluidos=tuple(excluidos),
        citaveis=tuple(MusicaRef(titulo, artista, origem="conhecida") for titulo, artista in citaveis))


def _participacao(evento: dict, as_run: dict, citaveis=(), nao_musica=()) -> dict:
    """Violações de participação da fala (o detector do backend) com o pedido do bloco como selecionado quando ele
    está "selecionado". `so_pelo_legado`: some se o pedido legado consumido na seleção ("historico_legado", antes da
    D1 da F4) contasse como selecionado."""
    from app.live.participacao import mencoes_participacao

    estado = evento.get("pedido_estado")
    nao_musica = list(nao_musica or as_run.get("nomes_nao_musica") or [])
    regras = [m.regra for m in mencoes_participacao(
        evento["texto"], _nomes_participacao(evento, as_run, estado == "selecionado", citaveis, nao_musica))]
    if not regras and estado == "selecionado" and evento.get("pedido_tipo") == "musica" \
            and any(_contem(normalizar(evento["texto"]), p) for p in CONFIG_METRICAS["pedido_indevido"]["padroes"]):
        faixa_do_pedido = (evento.get("musicas_bloco") or [None])[0]
        if faixa_do_pedido is None or evento.get("musica_tocada") != faixa_do_pedido:
            regras = ["pedido_faixa_trocada"]
    so_pelo_legado = bool(regras) and estado == "historico_legado" and not mencoes_participacao(
        evento["texto"], _nomes_participacao(evento, as_run, True, citaveis, nao_musica))
    return {"regras": regras, "so_pelo_legado": so_pelo_legado}


def _resumo_promessas(promessas: list[dict], eventos: list[dict]) -> dict:
    """Promessas do backend que foram ao ar: cumpridas, canceladas com a contingência no ar, vencidas, abertas
    no fim e resolvidas num bloco que não tocou (contam como vencidas: o ouvinte não ouviu a resolução)."""
    no_ar = [p for p in promessas if p.get("registro_no_ar", True)]
    estados = collections.Counter(p["estado"] for p in no_ar)
    cumpridas_sem_ar = sum(1 for p in no_ar if p["estado"] == "cumprida" and p.get("resolucao_no_ar") is False)
    canceladas_no_ar = sum(1 for p in no_ar if p["estado"] == "cancelada" and p.get("contingencia_no_ar"))
    return {
        "registradas": len(promessas),
        "registradas_sem_ar": len(promessas) - len(no_ar),
        "cumpridas": estados["cumprida"],
        "canceladas_com_contingencia": canceladas_no_ar,
        "canceladas_sem_contingencia_no_ar": estados["cancelada"] - canceladas_no_ar,
        "vencidas": estados["vencida"],
        "abertas_no_fim": estados["aberta"],
        "cumpridas_sem_ar": cumpridas_sem_ar,
        "contingencias_no_ar": [p["contingencia"] for p in no_ar if p.get("contingencia_no_ar")],
    }


def _duracao(evento: dict) -> float:
    if evento["tipo"] == "fala":
        medida = evento.get("duracao_medida_s")
        return float(medida if medida is not None else evento["duracao_prevista_s"])
    return float(evento["fim_s"]) - float(evento["inicio_s"])


def _razao(evento: dict) -> float:
    return _duracao(evento) / float(evento["orcamento_s"]["max"])


def _orcamento_observado(falas: list[dict], teto: float) -> dict:
    razoes = [_razao(f) for f in falas]
    return {
        "falas": len(falas),
        "fora_pct": round(100 * sum(1 for r in razoes if r > 1) / len(razoes), 1) if razoes else 0.0,
        "acima_teto": sum(1 for r in razoes if r > 1 + teto),
        "estouro_max_pct": round(max(0.0, (max(razoes) - 1) * 100), 1) if razoes else 0.0,
    }


def _duracao_fala(falas: list[dict], amostras_calibracao: int) -> dict:
    """Erro da estimativa do backend contra a duração medida no áudio (F2): todas as falas medidas e só as
    depois das primeiras amostras (quando a calibração por voz já pode valer)."""
    medidas = [f for f in falas if f.get("duracao_medida_s") and f.get("duracao_estimada_backend_s") is not None]

    def erro(lista: list[dict]) -> float | None:
        if not lista:
            return None
        return round(100 * sum(abs(f["duracao_estimada_backend_s"] - f["duracao_medida_s"]) / f["duracao_medida_s"]
                               for f in lista) / len(lista), 1)

    return {
        "medidas": len(medidas),
        "erro_estimativa_pct": erro(medidas),
        "erro_estimativa_calibrada_pct": erro(medidas[amostras_calibracao:]),
        "segundos_medidos": round(sum(f["duracao_medida_s"] for f in medidas), 2),
    }




def _etapa(evento: dict) -> tuple[int, int] | None:
    relogio = evento.get("relogio")
    return (relogio["etapa"]["hora"], relogio["etapa"]["inicio_s"]) if relogio else None


def _hard_times(eventos: list[dict], relogio: dict, tolerancia: float, backend: dict | None = None) -> list[dict]:
    """Casa cada hard time do relógio com o evento que o cumpriu. Com o relógio no backend (F1), pela etapa
    da resposta (hora 0, inicio_s); sem ele, por corresponde_a (F0). Hard time que o espelho efetivo do
    backend não tem (intervalo sem patrocinador) fica como "dispensado", não como perdido."""
    usados: set[int] = set()
    resultado = []
    efetivos = set((backend or {}).get("hard_times_efetivos") or [])
    for previsto in sorted((e for e in relogio.get("eventos", []) if e.get("hard_time")), key=lambda e: e["inicio_s"]):
        alvo = set(previsto.get("corresponde_a") or [])
        if backend:
            candidatos = [e for e in eventos if e["n"] not in usados and _etapa(e) == (0, previsto["inicio_s"])]
            candidatos = candidatos[:1]
        else:
            candidatos = [
                e for e in eventos
                if e["n"] not in usados and alvo & {e["tipo"], e.get("categoria"), e.get("bloco")}
                and (e["tipo"] != "musica" or "musica" in alvo)
            ]
        item = {"inicio_s": previsto["inicio_s"], "tipo": previsto["tipo"], "executado_em_s": None,
                "atraso_s": None, "status": "perdido", "cortado": False}
        if backend and previsto["inicio_s"] not in efetivos:
            item["status"] = "dispensado"
            resultado.append(item)
            continue
        if candidatos:
            escolhido = min(candidatos, key=lambda e: (abs(e["inicio_s"] - previsto["inicio_s"]), e["n"]))
            usados.add(escolhido["n"])
            atraso = round(escolhido["inicio_s"] - previsto["inicio_s"], 2)
            status = "ok" if abs(atraso) <= tolerancia else ("atrasado" if atraso > 0 else "adiantado")
            item.update(executado_em_s=escolhido["inicio_s"], atraso_s=atraso, status=status,
                        cortado=bool(escolhido.get("cortado")))
        resultado.append(item)
    return resultado


def _silencio(eventos: list[dict], config: dict) -> tuple[float, float]:
    involuntario, editorial, fim_anterior = 0.0, 0.0, 0.0
    for evento in eventos:
        pausa = float(evento.get("pausa_antes_s") or 0.0)
        editorial += pausa
        involuntario += max(0.0, float(evento["inicio_s"]) - fim_anterior - pausa)
        if evento["tipo"] in config["tipos_silencio"]:
            involuntario += float(evento["fim_s"]) - float(evento["inicio_s"])
        fim_anterior = float(evento["fim_s"])
    return round(involuntario, 2), round(editorial, 2)


def _abertura_repetida(falas: list[dict], config: dict) -> int:
    cfg = config["abertura_repetida"]
    chaves = [" ".join(normalizar(f["texto"]).split()[:cfg["palavras"]]) for f in falas]
    return sum(
        1 for i in range(cfg["seguidas"] - 1, len(chaves))
        if chaves[i] and len(set(chaves[i - cfg["seguidas"] + 1:i + 1])) == 1
    )


def _repeticao_estrutura(falas: list[dict], config: dict) -> int | None:
    """F8: janelas de falas seguidas com a mesma abertura reconhecida. None quando o módulo da F8 não existe."""
    try:
        from app.live.memoria import repeticao_estrutura  # type: ignore[attr-defined]
    except ImportError:
        return None
    return repeticao_estrutura([f["texto"] for f in falas], config["repeticao_estrutura"]["seguidas"])


def _aviso_oralidade(falas: list[dict]) -> int | None:
    """Contagem do verificador de oralidade da F7, quando app/live/oralidade.py existir."""
    try:
        from app.live import oralidade  # type: ignore[attr-defined]
    except ImportError:
        return None
    verificar = getattr(oralidade, "avisos", None) or getattr(oralidade, "verificar", None)
    if verificar is None:
        return None
    return sum(len(verificar(f["texto"]) or []) for f in falas)


def _validacao(eventos: list[dict]) -> dict:
    """Ações por bloco e regras por violação distinta: a mesma (regra, trecho) da fase "pre" (reescrita) e da
    "final" (remoção) conta uma vez (D18 da F5; até a F4 esta chave contava o dobro por remoção)."""
    blocos = {e["bloco_n"]: e["validacao_fala"] for e in eventos if e.get("validacao_fala")}
    distintas = [regra for v in blocos.values()
                 for regra, _trecho in dict.fromkeys((x["regra"], x["trecho"]) for x in v["violacoes"])]
    return {
        "blocos": len(blocos),
        "acoes": dict(sorted(collections.Counter(v["acao"] for v in blocos.values()).items())),
        "regras": dict(sorted(collections.Counter(distintas).items())),
    }


def _instante(texto: str | None):
    import datetime

    return datetime.datetime.fromisoformat(texto) if texto else None


def _dados_verificaveis(entradas: list[dict]) -> list:
    """DadoVerificavel a partir do que o as-run guardou (resposta do /proxima e o texto do bloco de dados)."""
    from app.dados.verificavel import DadoVerificavel

    return [DadoVerificavel(
        id=d["id"], tipo=d["tipo"], valor=d.get("texto") or "", fonte="" if d["estado"] == "sem_fonte" else "registro",
        atualizado_em=_instante(d.get("atualizado_em")), valido_ate=_instante(d.get("valido_ate")),
        aprovado=d["estado"] != "nao_aprovado", detalhes=d.get("detalhes") or {}, alertas=tuple(d.get("alertas") or ()))
        for d in entradas]


def _dados(eventos: list[dict], falas: list[dict], config: dict) -> dict:
    """F5: dados dos blocos e afirmações de dado no ar, pelo detector do backend (app.dados.checagem)."""
    import datetime

    from app.dados.checagem import afirmacoes, checar_fala, cobre
    from app.dados.verificavel import estado

    tz = config["dados"]["tz"]
    por_bloco = {e["bloco_n"]: _dados_verificaveis(e["dados"]) for e in eventos if e.get("dados")}
    entradas = [d for e in eventos for d in e.get("dados") or []]
    sem_fonte = vencido = com_horario = 0
    sem_integracao: collections.Counter = collections.Counter()
    for fala in falas:
        dados = por_bloco.get(fala["bloco_n"], [])
        # O instante em que a fala foi ao ar (as-runs artificiais sem horário: agora).
        instante = _instante(fala.get("inicio")) or datetime.datetime.now(datetime.timezone.utc)
        violacoes = checar_fala(fala["texto"], dados, instante, tz)
        sem_fonte += any(v.regra == "dado_sem_fonte" for v in violacoes)
        vencido += any(v.regra == "dado_vencido" for v in violacoes)
        sem_integracao.update(v.ref_id for v in violacoes if v.regra == "dado_sem_fonte")
        com_horario += sum(1 for a in afirmacoes(fala["texto"]) if a.com_horario and any(
            cobre(a, d) and estado(d, instante) == "vencido" for d in dados))
    removidos = 0
    for evento in eventos:
        legitimas = evento.get("dado_legitimo") or []
        trechos = [x["trecho"] for x in (evento.get("validacao_fala") or {}).get("violacoes") or []
                   if x["regra"] in ("dado_sem_fonte", "dado_vencido")]
        removidos += sum(1 for frase in legitimas if any(frase in t or t in frase for t in trechos))
    alertas = {d["id"] for d in entradas if "instrucao_removida" in (d.get("alertas") or [])}
    return {
        "dados": {
            "blocos_com_dado": len(por_bloco),
            "por_tipo": dict(sorted(collections.Counter(d["tipo"] for d in entradas).items())),
            "por_estado": dict(sorted(collections.Counter(d["estado"] for d in entradas).items())),
        },
        "dado_sem_fonte": sem_fonte,
        "dado_vencido": vencido,
        "sem_integracao": {c: sem_integracao.get(c, 0) for c in ("temperatura", "condicao_tempo", "previsao",
                                                                  "transito", "placar", "comercial")},
        "vencido_com_horario": com_horario,
        "dado_legitimo_removido": removidos,
        "injecao": {"instrucoes_removidas": len(alertas)},
    }


def _pedidos(pedidos: list[dict]) -> dict:
    estados = collections.Counter(p["estado_final"] for p in pedidos)
    return {
        "recebidos": len(pedidos),
        "selecionados": sum(1 for p in pedidos if p.get("bloco_n") is not None),
        "executados": estados["executado"],
        "nao_atendidos": estados["nao_atendido"],
        "expirados": estados["expirado"],
        "pendentes_fim": sum(estados[e] for e in ("recebido", "em_fila", "aguardando_revisao")),
        "selecionados_nao_tocados": sum(1 for p in pedidos if p.get("bloco_n") is not None and p.get("tocou_em_s") is None),
        "atendidos_antes_de_tocar": sum(
            1 for p in pedidos
            if p.get("atendido_em_s") is not None and (p.get("tocou_em_s") is None or p["atendido_em_s"] < p["tocou_em_s"])
        ),
        "por_estado": dict(sorted(estados.items())),
    }


def calcular_metricas(as_run: dict, config: dict | None = None) -> dict:
    config = config or CONFIG_METRICAS
    eventos = as_run["eventos"]
    falas = [e for e in eventos if e["tipo"] in config["tipos_fala"]]
    duracao_programa_s = float(as_run["duracao_programa_s"])
    nomes_fixture = list((as_run.get("ouvintes") or {}).get("fixture") or [])
    nomes_inexistentes = list((as_run.get("ouvintes") or {}).get("inexistentes") or [])

    com_orcamento = [f for f in falas if f.get("orcamento_s")]
    # Desde a F2 o orçamento vem do backend: as falas em observação (formato padrão sem relógio, aplicado
    # False) são relatadas à parte. As_runs anteriores não têm a chave e contam como aplicadas.
    aplicadas = [f for f in com_orcamento if f["orcamento_s"].get("aplicado", True)]
    razoes = [_razao(f) for f in aplicadas]
    fora = sum(1 for r in razoes if r > 1)

    anuncio_sem_confirmacao = 0
    for fala in falas:
        no_ar_no_bloco = {e["musica_tocada"] for e in eventos if e["tipo"] == "musica" and e["bloco_n"] == fala["bloco_n"]}
        confirmadas = no_ar_no_bloco | {fala.get("musica_tocada")}
        anuncio_sem_confirmacao += sum(1 for m in fala.get("musica_anunciada") or [] if m not in confirmadas)

    fechadas = {pid for e in eventos for pid in e.get("promessas_fechadas") or []}
    abertas = [p for e in eventos for p in e.get("promessas_abertas") or []]
    backend = as_run.get("promessas")
    if backend is not None:
        resumo_promessas = _resumo_promessas(backend, eventos)
        # Vencida para o ouvinte: venceu, ficou aberta, ou a resolução (cumprimento ou contingência) não foi ao ar.
        promessa_vencida = resumo_promessas["vencidas"] + resumo_promessas["abertas_no_fim"] + \
            resumo_promessas["cumpridas_sem_ar"] + resumo_promessas["canceladas_sem_contingencia_no_ar"]
    else:
        resumo_promessas = None
        promessa_vencida = sum(1 for p in abertas if p["id"] not in fechadas)
    participacao = [f.get("participacao") or _participacao(f, as_run) for f in falas]

    hard_times = _hard_times(eventos, as_run.get("relogio") or {}, config["hard_time"]["tolerancia_s"],
                             as_run.get("relogio_backend"))
    atrasos = [h["atraso_s"] for h in hard_times if h["atraso_s"] is not None and h["atraso_s"] > 0]
    silencio, silencio_editorial = _silencio(eventos, config)

    def soma(tipos) -> float:
        return round(sum(float(e["fim_s"]) - float(e["inicio_s"]) for e in eventos if e["tipo"] in tipos), 2)

    tipos_conhecidos = {"fala", "musica"}
    previsto = collections.Counter()
    for item in (as_run.get("relogio") or {}).get("eventos", []):
        previsto[item.get("grupo", "fala")] += item["duracao_s"]

    ultimo_fim = max((float(e["fim_s"]) for e in eventos), default=0.0)
    encerramentos = [f for f in falas if f.get("categoria") == "encerramento"]
    encerramento_no_ar = any(not f.get("cortado") for f in encerramentos)
    blocos_relogio = {e["bloco_n"]: e["relogio"] for e in eventos if e.get("relogio")}
    return {
        "fora_orcamento_pct": round(100 * fora / len(aplicadas), 1) if aplicadas else 0.0,
        "estouro_max_pct": round(max(0.0, (max(razoes) - 1) * 100), 1) if razoes else 0.0,
        "falas_com_orcamento_aplicado": len(aplicadas),
        "acima_teto_orcamento": sum(1 for r in razoes if r > 1 + config["orcamento"]["teto"]),
        "orcamento_observacao": _orcamento_observado(
            [f for f in com_orcamento if not f["orcamento_s"].get("aplicado", True)], config["orcamento"]["teto"]),
        "duracao_fala": _duracao_fala(falas, config["orcamento"]["amostras_calibracao"]),
        "ajustes_fala": dict(sorted(collections.Counter(f["fala_ajuste"] for f in falas if f.get("fala_ajuste")).items())),
        "atraso_hard_time_s": round(max(atrasos), 2) if atrasos else 0.0,
        "anuncio_sem_confirmacao": anuncio_sem_confirmacao,
        "promessa_vencida": promessa_vencida,
        "promessas_abertas": len(abertas),
        # F4: promessa detectada no texto que foi ao ar, nem livre nem registrada pelo backend.
        "promessa_sem_registro": sum(1 for p in abertas if p.get("registrada") is False),
        "promessas": resumo_promessas,
        # F4: o detector de participação do backend; a parcela que só existe por causa do legado consumido na
        # seleção ("historico_legado", antes da D1) fica à parte.
        "pedido_indevido": sum(1 for p in participacao if p["regras"]),
        "pedido_indevido_legado": sum(1 for p in participacao if p["so_pelo_legado"]),
        "ouvinte_inexistente": sum(
            1 for f in falas if any(_contem(normalizar(f["texto"]), n) for n in nomes_inexistentes if n not in nomes_fixture)
        ),
        "abertura_repetida": _abertura_repetida(falas, config),
        "silencio_s": silencio,
        "silencio_editorial_s": silencio_editorial,
        "aviso_oralidade": _aviso_oralidade(falas),
        "repeticao_estrutura": _repeticao_estrutura(falas, config),
        "tempo_fala_s": soma({"fala"}),
        "tempo_musica_s": soma({"musica"}),
        "tempo_outros_s": soma({e["tipo"] for e in eventos} - tipos_conhecidos),
        "relogio_previsto_s": {"fala": previsto["fala"], "musica": previsto["musica"], "intervalo": previsto["intervalo"]},
        "hard_times": hard_times,
        "hard_times_perdidos": sum(1 for h in hard_times if h["status"] == "perdido"),
        "encerramento_no_ar": encerramento_no_ar,
        "estouro_fim_programa_s": round(max(0.0, ultimo_fim - duracao_programa_s), 2),
        # F1: buraco no fim quando o encerramento foi ao ar antes do horário (com corte, não se aplica).
        "fim_antecipado_s": round(max(0.0, duracao_programa_s - ultimo_fim), 2) if encerramento_no_ar else None,
        # Fala com orçamento abaixo do mínimo do tipo: máximo < mínimo, ou espaço até o hard time menor
        # que o mínimo (o backend não deveria ter gerado a fala).
        "falas_abaixo_minimo": sum(
            1 for f in com_orcamento
            if float(f["orcamento_s"]["max"]) < float(f["orcamento_s"]["min"])
            or (f.get("relogio") and f["relogio"].get("espaco_s") is not None
                and float(f["relogio"]["espaco_s"]) < float(f["orcamento_s"]["min"]))
        ),
        # F3: o que o validador pós-geração fez (as-run de cada bloco, pela resposta do /proxima).
        "validacao_fala": _validacao(eventos),
        # F5: dados do bloco, afirmação sem fonte ou vencida no ar, injeção.
        **_dados(eventos, falas, config),
        "relogio_acoes": dict(sorted(collections.Counter(r["acao"] for r in blocos_relogio.values()).items())),
        "etapas_puladas": sorted({p for r in blocos_relogio.values() for p in r.get("puladas") or []}),
        "adiantamentos": sum(1 for r in blocos_relogio.values() if r["acao"] == "adiantamento"),
        "fechamentos_curtos": sum(1 for r in blocos_relogio.values() if r["acao"] == "fechamento_curto"),
        "hard_times_dispensados": sum(1 for h in hard_times if h["status"] == "dispensado"),
        "pedidos": _pedidos(as_run.get("pedidos") or []),
        "eventos_por_tipo": dict(sorted(collections.Counter(e["tipo"] for e in eventos).items())),
        "falas_por_bloco": dict(sorted(collections.Counter(f["bloco"] for f in falas).items())),
    }


def metricas_formato(as_run: dict, *, formato: str, quadros=(), nomes=(), instrucao: dict | None = None) -> dict:
    """Bloco `resumo.json["formato"]` (F6, auditoria §9): o as-run vira falas e eventos para a função do backend
    (`app.live.formatos.coerencia`, importação tardia como F3-F5); nenhum detector próprio. `instrucao`: o canal
    lateral do dublê (blocos de fala com a direção do formato no prompt)."""
    from app.live import formatos

    eventos = as_run["eventos"]
    falas, anterior = [], None
    for evento in eventos:
        if evento["tipo"] == "fala":
            orcamento = evento.get("orcamento_s") or {}
            etapa = (evento.get("relogio") or {}).get("etapa") or {}
            falas.append(formatos.FalaNoAr(
                bloco=evento["bloco"], categoria=evento.get("categoria") or "", texto=evento.get("texto") or "",
                duracao_s=_duracao(evento), inicio_s=float(evento["inicio_s"]),
                primeira=not falas and evento.get("categoria") == "abertura", quadro=evento["bloco"] in quadros,
                retorno=anterior in ("intervalo", "patrocinador") or etapa.get("tipo_efetivo") == "retorno",
                teto_s=float(orcamento["max"]) if orcamento.get("fonte") == "relogio" else None,
            ))
        anterior = evento["tipo"]
    relatorio = formatos.coerencia(
        formato, falas, duracao_programa_s=float(as_run["duracao_programa_s"]), nomes=tuple(n for n in nomes if n),
        eventos=[(e["tipo"], float(e["inicio_s"]), float(e["fim_s"])) for e in eventos], instrucao=instrucao,
    )
    resolvido = formatos.resolver_formato(formato)
    dados = relatorio.como_dict()
    dados.pop("formato", None)
    return {"id": resolvido.id, "relogio_padrao": resolvido.relogio_padrao, **dados}
