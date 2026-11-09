"""Detectores e métricas do resumo.json (auditoria F0 §5.7 e §5.8).

Música anunciada: desde a F3, o mesmo detector do backend (app.live.validacao_fala.mencoes_musica), importado
na função; não existe um segundo validador aqui. Promessa e abertura repetida continuam heurísticas da F0, que a
F4 e a F8 trocam por código em app/live. Este módulo não importa app.* no carregamento: as métricas são
recalculáveis só com o as_run.json (os nomes que não são música vão em `nomes_nao_musica`).
"""

import collections
import re
import unicodedata

CONFIG_METRICAS = {
    "promessas": {
        "padroes": [
            "daqui a pouco", "depois do intervalo", "já já", "ainda hoje", "logo mais", "mais tarde",
            "em instantes", "a seguir", "na sequência", "volto já",
        ],
        "prazo_padrao_s": 900,
        # Estes vencem só no fim do programa.
        "ate_fim_do_programa": ["ainda hoje", "mais tarde", "logo mais"],
    },
    "pedido_indevido": {"padroes": ["toca agora", "pediu"]},
    "abertura_repetida": {"palavras": 3, "seguidas": 3},
    "hard_time": {"tolerancia_s": 5.0},
    # F2: teto do orçamento (app.config.settings.fala_teto_orcamento) e quantas falas medidas contam como
    # "antes da calibração" (fala_calibracao_min_amostras). Repetidos aqui para o módulo não importar app.*.
    "orcamento": {"teto": 0.30, "amostras_calibracao": 5},
    "tipos_fala": ["fala"],
    "tipos_silencio": ["bloco_vazio", "erro"],
}


def normalizar(texto: str) -> str:
    sem_acento = "".join(c for c in unicodedata.normalize("NFD", (texto or "").lower()) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", sem_acento).strip()


def _contem(texto_normalizado: str, trecho: str) -> bool:
    alvo = normalizar(trecho)
    return bool(alvo) and f" {alvo} " in f" {texto_normalizado} "


def _frase_com(texto: str, padrao: str) -> str:
    for frase in re.split(r"(?<=[.!?])\s+", texto):
        if _contem(normalizar(frase), padrao):
            return frase.strip()[:120]
    return texto.strip()[:120]


def detectar_promessas(texto: str, inicio_s: float, fim_programa_s: float, n: int, config: dict | None = None) -> list[dict]:
    cfg = (config or CONFIG_METRICAS)["promessas"]
    normalizado = normalizar(texto)
    achadas = []
    for padrao in cfg["padroes"]:
        if _contem(normalizado, padrao):
            prazo = max(0.0, fim_programa_s - inicio_s) if padrao in cfg["ate_fim_do_programa"] else cfg["prazo_padrao_s"]
            achadas.append({"id": f"p{n}.{len(achadas) + 1}", "padrao": padrao, "trecho": _frase_com(texto, padrao),
                            "prazo_s": round(prazo, 2)})
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
    """Preenche musicas_citadas, musica_anunciada, musica_tocada e promessas de cada evento."""
    eventos = as_run["eventos"]
    fim_programa_s = float(as_run["duracao_programa_s"])
    nao_musica = list(nao_musica if nao_musica is not None else as_run.get("nomes_nao_musica") or [])
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
        evento["promessas_abertas"] = detectar_promessas(evento["texto"], evento["inicio_s"], fim_programa_s,
                                                         evento["n"], config)
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


def _pedido_indevido(evento: dict, nomes: list[str], config: dict) -> bool:
    normalizado = normalizar(evento["texto"])
    menciona = any(_contem(normalizado, p) for p in config["pedido_indevido"]["padroes"])
    menciona = menciona or any(_contem(normalizado, nome) for nome in nomes)
    if not menciona:
        return False
    if evento.get("pedido_id") is None or evento.get("pedido_estado") != "selecionado":
        return True
    if evento.get("pedido_tipo") == "musica":
        faixa_do_pedido = (evento.get("musicas_bloco") or [None])[0]
        return faixa_do_pedido is None or evento.get("musica_tocada") != faixa_do_pedido
    return False


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
    blocos = {e["bloco_n"]: e["validacao_fala"] for e in eventos if e.get("validacao_fala")}
    return {
        "blocos": len(blocos),
        "acoes": dict(sorted(collections.Counter(v["acao"] for v in blocos.values()).items())),
        "regras": dict(sorted(collections.Counter(x["regra"] for v in blocos.values()
                                                  for x in v["violacoes"]).items())),
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
        "promessa_vencida": sum(1 for p in abertas if p["id"] not in fechadas),
        "promessas_abertas": len(abertas),
        "pedido_indevido": sum(1 for f in falas if _pedido_indevido(f, nomes_fixture + nomes_inexistentes, config)),
        "ouvinte_inexistente": sum(
            1 for f in falas if any(_contem(normalizar(f["texto"]), n) for n in nomes_inexistentes if n not in nomes_fixture)
        ),
        "abertura_repetida": _abertura_repetida(falas, config),
        "silencio_s": silencio,
        "silencio_editorial_s": silencio_editorial,
        "aviso_oralidade": _aviso_oralidade(falas),
        "repeticao_estrutura": None,
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
        "relogio_acoes": dict(sorted(collections.Counter(r["acao"] for r in blocos_relogio.values()).items())),
        "etapas_puladas": sorted({p for r in blocos_relogio.values() for p in r.get("puladas") or []}),
        "adiantamentos": sum(1 for r in blocos_relogio.values() if r["acao"] == "adiantamento"),
        "fechamentos_curtos": sum(1 for r in blocos_relogio.values() if r["acao"] == "fechamento_curto"),
        "hard_times_dispensados": sum(1 for h in hard_times if h["status"] == "dispensado"),
        "pedidos": _pedidos(as_run.get("pedidos") or []),
        "eventos_por_tipo": dict(sorted(collections.Counter(e["tipo"] for e in eventos).items())),
        "falas_por_bloco": dict(sorted(collections.Counter(f["bloco"] for f in falas).items())),
    }
