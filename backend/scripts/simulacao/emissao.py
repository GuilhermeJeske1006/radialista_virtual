"""Laço da hora: fila de preparo, reprodução, watchdog de corte e pedidos (auditoria F0 §5.4).

Espelha o player do painel, não o backend: o bloco N+2 é gerado quando o bloco N começa a tocar
(FilaPreparo com antecedência 2), o histórico avança na geração e o programa iniciado pelo
agendamento é cortado em horario_fim + 1 s. O GET /preparo (preparo prévio no servidor) fica de
fora: a primeira fala sai do /proxima normal.

Desde a F1, cada pedido leva `inicio_previsto` como o painel (lib/relogioAoVivo.ts): a cadeia bruta
(início agendado + pausa + duração prevista de cada bloco gerado) mais o desvio medido quando o bloco
anterior começou a tocar. `enviar_inicio_previsto=False` imita o painel antigo.

Importa app.*: só carregue este módulo depois de preparar o ambiente.
"""

import collections
import dataclasses
import datetime
import math
from typing import Any

from app.live.formato import contar_palavras
from app.live.orcamento import estimar_duracao_s
from app.models.fila_ao_vivo import FilaAoVivo
from app.models.programa import Programa

from scripts.simulacao.dubles import categoria_do_tipo

# Constantes do player (frontend-painel), guardadas como configuração com a origem de cada uma.
PLAYER = {
    "teto_fila": 12,                # lib/filaPreparo.ts: Math.max(12, antecedencia)
    "pausa_padrao_ms": 350,         # lib/continuidadeAudio.ts: pausaAntesDoBloco(null)
    "pausa_max_ms": 5000,           # lib/continuidadeAudio.ts: clamp 0-5000
    "retentativa_falha_s": 5.0,     # hooks/useLiveEngine.ts: INTERVALO_RETENTATIVA_FALHA_MS
    "watchdog_tolerancia_s": 1.0,   # hooks/useLiveEngine.ts: verificarFimPontual a cada 1 s
    "perfil_pos_producao": "radio_fm",
    "historico_max": 8,             # hooks/useLiveEngine.ts: historicoBase.slice(0, 8)
    "historico_guardado": 20,       # hooks/useLiveEngine.ts: avancar, slice(0, 20)
    "palavras_por_segundo": 2.5,    # lib/duracaoBloco.ts: estimativa sem duracao_prevista_s
}
TRAVAS = {"chamadas_proxima": 400, "apos_fim_s": 1800}


def linha_historico(segmento: dict) -> str:
    """Mesmo texto de prepararTexto + linhaMusicasHistorico (hooks/useLiveEngine.ts:1241, :1315)."""
    musicas = segmento.get("musicas") or []
    sufixo = ""
    if musicas:
        lista = ", ".join(f"{m['titulo']} - {m['canal']}" if m.get("canal") else m["titulo"] for m in musicas)
        sufixo = f" [Música(s) tocada(s) nesse bloco: {lista}]"
    return f"{segmento['tipo']}: {segmento.get('fala') or ''}{sufixo}"


def rotulo_musica(musica: dict) -> str:
    return f"{musica['titulo']} - {musica['canal']}" if musica.get("canal") else musica.get("titulo", "")


@dataclasses.dataclass
class Bloco:
    n: int
    gerado_em_s: float
    status: int
    segmento: dict | None
    erro: str = ""
    pedido_id: int | None = None
    pedido_estado: str | None = None
    pedido_tipo: str | None = None
    chamadas_llm: int = 0
    revisada: bool = False
    duracao_medida_s: float | None = None
    inicio_bruto_s: float | None = None
    inicio_previsto_s: float | None = None


class Emissao:
    def __init__(self, *, client, headers: dict, sessao, fixture, cenario, dubles, relogio, base: datetime.datetime,
                 modo: str, wpm: float, antecedencia: int, preparo_antecipado_s: float, corte: str,
                 enviar_inicio_previsto: bool = True):
        self.client, self.headers, self.sessao = client, headers, sessao
        self.fixture, self.cenario, self.dubles = fixture, cenario, dubles
        self.relogio, self.base = relogio, base
        self.modo, self.wpm, self.antecedencia = modo, wpm, antecedencia
        self.preparo_antecipado_s, self.corte = preparo_antecipado_s, corte
        self.enviar_inicio_previsto = enviar_inicio_previsto
        # Cadeia do horário previsto (painel): início bruto do próximo bloco a gerar e desvio medido.
        self.inicio_bruto_s = 0.0
        self.desvio_s = 0.0
        self.fim_s = float(fixture.duracao_programa_s())
        self.fila: collections.deque[Bloco] = collections.deque()
        self.ctx: dict | None = {"historico": [], "total_falas": 0, "ultima_fala": None}
        self.gerando = True
        self.blocos: list[Bloco] = []
        self.eventos: list[dict] = []
        self.pedidos = [{"fixture": p, "id": None} for p in sorted(fixture.pedidos, key=lambda p: p.chega_em_s)]
        self.contagem: collections.Counter = collections.Counter()
        self.nao_tocados: list[dict] = []
        self.t_final = 0.0
        self._url_proxima = f"/live/{cenario.radialista_id}/programas/{cenario.programa_id}/proxima"

    # --- relógio virtual ---------------------------------------------------------------------------

    def _instante(self, t_s: float) -> datetime.datetime:
        return self.base + datetime.timedelta(seconds=t_s)

    def _mover(self, t_s: float) -> None:
        self.relogio.move_to(self._instante(t_s))

    # --- laço principal ----------------------------------------------------------------------------

    def executar(self) -> None:
        self.preencher(-self.preparo_antecipado_s)
        t = 0.0
        while self.fila:
            # FilaPreparo.retirar: preenche, tira o próximo e preenche de novo.
            self.preencher(t)
            bloco = self.fila.popleft()
            self.preencher(t)
            if bloco.inicio_bruto_s is not None:
                # Como o painel: o desvio é medido quando o bloco começa e corrige os pedidos seguintes.
                self.desvio_s = t - bloco.inicio_bruto_s
            pausa = self._pausa(bloco)
            fim, cortado, foi_ao_ar = self._reproduzir(bloco, t + pausa, pausa)
            if foi_ao_ar:
                self._confirmar_pedido(bloco, fim, cortado)
            t = fim
            if cortado:
                break
            if bloco.segmento and bloco.segmento.get("tipo") == "encerramento":
                break
            if t > self.fim_s + TRAVAS["apos_fim_s"]:
                self.contagem["trava_tempo"] += 1
                break
        for bloco in self.fila:
            self._registrar_nao_tocado(bloco)
            self.contagem["segundos_nao_tocados"] += sum(p["duracao"] for p in self._planejar(bloco))
        self.fila.clear()
        self._inserir_pedidos_ate(min(t, self.fim_s))
        self.t_final = t

    def _na_antecedencia(self) -> int:
        return sum(1 for b in self.fila if not (b.segmento and b.segmento.get("tipo") == "vinheta"))

    def preencher(self, t: float) -> None:
        limite_fila = max(PLAYER["teto_fila"], self.antecedencia)
        while self.gerando and self.ctx is not None and self._na_antecedencia() < self.antecedencia \
                and len(self.fila) < limite_fila:
            if self.contagem["chamadas_proxima"] >= TRAVAS["chamadas_proxima"]:
                self.contagem["trava_chamadas"] += 1
                self.gerando = False
                break
            self._mover(t)
            self._inserir_pedidos_ate(t)
            bloco = self._gerar(t)
            self.fila.append(bloco)
            segmento = bloco.segmento
            if segmento is None:
                continue
            self.inicio_bruto_s += self._pausa(bloco) + self._duracao_prevista(segmento)
            if segmento.get("tipo") == "encerramento":
                self.ctx, self.gerando = None, False
            else:
                self.ctx = {
                    "historico": [*self.ctx["historico"], segmento][-PLAYER["historico_guardado"]:],
                    "total_falas": self.ctx["total_falas"] + (segmento.get("passos_roteiro") or 1),
                    "ultima_fala": segmento.get("fala"),
                }

    # --- geração (POST /proxima real) ---------------------------------------------------------------

    def _estados_pedidos(self) -> dict[int, str]:
        return {id_: estado for id_, estado in self.sessao.query(FilaAoVivo.id, FilaAoVivo.estado).all()}

    def _gerar(self, t: float) -> Bloco:
        n = len(self.blocos) + 1
        retrato = self._estados_pedidos()
        self.dubles.estado.nova_chamada(bloco_n=n, total_falas=self.ctx["total_falas"], retrato_pedidos=retrato)
        antes = collections.Counter(self.dubles.llm.contadores)
        payload = {
            "incluir_audio": False,
            "historico": [linha_historico(s) for s in self.ctx["historico"][-PLAYER["historico_max"]:]],
            "total_falas": self.ctx["total_falas"],
            "perfil_pos_producao": PLAYER["perfil_pos_producao"],
            "ultima_fala": self.ctx["ultima_fala"],
        }
        inicio_previsto = max(t, self.inicio_bruto_s + self.desvio_s)
        if self.enviar_inicio_previsto:
            payload["inicio_previsto"] = self._instante(inicio_previsto).isoformat()
        resposta = self.client.post(self._url_proxima, json=payload, headers=self.headers)
        self.contagem["chamadas_proxima"] += 1
        delta = collections.Counter(self.dubles.llm.contadores)
        delta.subtract(antes)
        bloco = Bloco(
            n=n, gerado_em_s=round(t, 3), status=resposta.status_code,
            segmento=resposta.json() if resposta.status_code == 200 else None,
            chamadas_llm=delta["gerar_resposta"] + delta["gerar_dialogo_multivoz"],
            revisada=delta["revisoes"] > 0,
            inicio_bruto_s=round(self.inicio_bruto_s, 3), inicio_previsto_s=round(inicio_previsto, 3),
        )
        if resposta.status_code != 200:
            self.contagem["erros_http"] += 1
            bloco.erro = resposta.text[:300]
        depois = self._estados_pedidos()
        mudaram = sorted(i for i, estado in depois.items() if retrato.get(i) != estado)
        if mudaram:
            bloco.pedido_id = mudaram[0]
            bloco.pedido_estado = depois[mudaram[0]]
            bloco.pedido_tipo = self.sessao.get(FilaAoVivo, mudaram[0]).tipo
        if self.modo == "completo" and bloco.segmento is not None:
            self._medir_tts(bloco)
        self.blocos.append(bloco)
        return bloco

    def _medir_tts(self, bloco: Bloco) -> None:
        """Modo completo: TTS real pelo POST /live/{rid}/tts, como o player faz, e duração medida."""
        segmento = bloco.segmento
        fala = (segmento.get("fala") or "").strip()
        if not fala or segmento.get("tipo") in ("vinheta", "patrocinador") or segmento.get("falas"):
            return
        resposta = self.client.post(f"/live/{self.cenario.radialista_id}/tts", headers=self.headers, json={
            "texto": fala, "tom": segmento.get("tom"), "tipo": segmento.get("tipo"),
            "perfil_pos_producao": PLAYER["perfil_pos_producao"], "texto_anterior": self.ctx["ultima_fala"],
            "programa_id": self.cenario.programa_id,
        })
        self.contagem["chamadas_tts"] += 1
        self.contagem["caracteres_tts"] += len(fala)
        if resposta.status_code != 200:
            self.contagem["erros_http"] += 1
            return
        from app.postprod.audio_io import mp3_bytes_para_array

        amostras, taxa, _ = mp3_bytes_para_array(resposta.content)
        bloco.duracao_medida_s = round(amostras.shape[1] / taxa, 2)

    # --- reprodução ----------------------------------------------------------------------------------

    def _pausa(self, bloco: Bloco) -> float:
        if bloco.segmento is None:
            return 0.0
        ms = bloco.segmento.get("pausa_antes_ms")
        ms = PLAYER["pausa_padrao_ms"] if ms is None else max(0, min(PLAYER["pausa_max_ms"], ms))
        return ms / 1000

    def _estimar(self, texto: str) -> float:
        return estimar_duracao_s(texto or "", self.wpm)

    @staticmethod
    def _duracao_prevista(segmento: dict) -> float:
        """lib/relogioAoVivo.ts (estimarDuracaoSegmento): a estimativa do backend; sem ela, palavras ÷ 2,5
        mais as músicas, como o painel antigo."""
        if segmento.get("duracao_prevista_s") is not None:
            return float(segmento["duracao_prevista_s"])
        texto = " ".join(f.get("texto", "") for f in segmento.get("falas") or []) or segmento.get("fala") or ""
        musicas = segmento.get("musicas") or ([segmento] if segmento.get("video_id") else [])
        return contar_palavras(texto) / PLAYER["palavras_por_segundo"] + sum(
            max(0, (m.get("fim_segundos") or m.get("duracao_segundos") or 0) - (m.get("inicio_segundos") or 0))
            for m in musicas)

    def _planejar(self, bloco: Bloco) -> list[dict[str, Any]]:
        """O que o player toca para o bloco: fala, músicas e, no encerramento, a vinheta de fechamento."""
        segmento = bloco.segmento
        if segmento is None:
            return [{"tipo": "erro", "duracao": PLAYER["retentativa_falha_s"], "texto": bloco.erro}]
        tipo = segmento.get("tipo")
        fala = segmento.get("fala") or ""
        if tipo == "vinheta":
            vinheta = self.cenario.vinhetas.get(segmento.get("vinheta_id"))
            com_audio = segmento.get("vinheta_audio") and vinheta is not None and vinheta.duracao_s
            return [{"tipo": "vinheta", "duracao": vinheta.duracao_s if com_audio else self._estimar(fala), "texto": fala}]
        if tipo == "patrocinador":
            patrocinador = self.cenario.patrocinadores.get(segmento.get("patrocinador_id"))
            com_audio = segmento.get("patrocinador_audio") and patrocinador is not None and patrocinador.duracao_s
            duracao = patrocinador.duracao_s if com_audio else self._estimar(fala)
            return [{"tipo": "patrocinador", "duracao": duracao, "texto": fala}]

        planejados: list[dict[str, Any]] = []
        if fala.strip():
            duracao = bloco.duracao_medida_s if bloco.duracao_medida_s is not None else self._estimar(fala)
            planejados.append({"tipo": "fala", "duracao": duracao, "texto": fala})
        musicas = segmento.get("musicas") or ([{
            "video_id": segmento["video_id"], "titulo": segmento.get("titulo_musica") or "", "canal": "",
            "inicio_segundos": segmento.get("inicio_segundos") or 0, "fim_segundos": segmento.get("fim_segundos"),
            "duracao_segundos": segmento.get("duracao_segundos"),
        }] if segmento.get("video_id") else [])
        for musica in musicas:
            duracao = (musica.get("fim_segundos") or musica.get("duracao_segundos") or 0) - (musica.get("inicio_segundos") or 0)
            planejados.append({"tipo": "musica", "duracao": max(0, duracao), "musica": musica})
        if tipo == "encerramento" and segmento.get("vinheta_encerramento_id"):
            vinheta = self.cenario.vinhetas.get(segmento["vinheta_encerramento_id"])
            texto = segmento.get("vinheta_encerramento_texto") or ""
            com_audio = segmento.get("vinheta_encerramento_audio") and vinheta is not None and vinheta.duracao_s
            planejados.append({"tipo": "vinheta", "duracao": vinheta.duracao_s if com_audio else self._estimar(texto),
                               "texto": texto})
        if not planejados:
            planejados.append({"tipo": "bloco_vazio", "duracao": PLAYER["retentativa_falha_s"], "texto": ""})
        return planejados

    def _reproduzir(self, bloco: Bloco, inicio: float, pausa: float) -> tuple[float, bool, bool]:
        limite = self.fim_s + PLAYER["watchdog_tolerancia_s"] if self.corte == "agendado" else math.inf
        t, cortado, foi_ao_ar = inicio, False, False
        for indice, plano in enumerate(self._planejar(bloco)):
            if t >= limite:
                cortado = True
                self.contagem["segundos_nao_tocados"] += plano["duracao"]
                continue
            fim = t + plano["duracao"]
            evento = self._evento(bloco, plano, t, min(fim, limite), pausa if indice == 0 else 0.0)
            if fim > limite:
                evento["cortado"], evento["cortado_s"] = True, round(fim - limite, 2)
                cortado, fim = True, limite
            self.eventos.append(evento)
            foi_ao_ar = True
            t = fim
        if not foi_ao_ar:
            self._registrar_nao_tocado(bloco)
        return t, cortado, foi_ao_ar

    def _registrar_nao_tocado(self, bloco: Bloco) -> None:
        """Bloco gerado que não foi ao ar (corte do watchdog ou fila descartada no fim)."""
        self.contagem["blocos_nao_tocados"] += 1
        self.nao_tocados.append({
            "bloco_n": bloco.n, "bloco": (bloco.segmento or {}).get("tipo") or "erro",
            "gerado_em_s": bloco.gerado_em_s,
            "duracao_planejada_s": round(sum(p["duracao"] for p in self._planejar(bloco)), 2),
            "texto": ((bloco.segmento or {}).get("fala") or "")[:200],
        })

    def _orcamentos(self, segmento: dict, tipo: str, categoria: str) -> tuple[dict, dict]:
        alvo = segmento.get("duracao_alvo_segundos")
        if alvo and segmento.get("relogio"):
            # Com relógio, o orçamento é o do backend (backtiming) nos dois formatos.
            orcamento = self.fixture.unidade_fala if self.fixture.formato_musical else \
                self.fixture.orcamento_para(tipo, categoria)
            return {"min": alvo[0], "max": alvo[1], "fonte": "relogio"}, \
                {"min": orcamento.min, "max": orcamento.max, "fonte": "formato"}
        if self.fixture.formato_musical:
            referencia = self.fixture.unidade_fala
            ref = {"min": referencia.min, "max": referencia.max, "fonte": "formato"}
            alvo = segmento.get("duracao_alvo_segundos")
            return ({"min": alvo[0], "max": alvo[1], "fonte": "backend"} if alvo else dict(ref)), ref
        orcamento = self.fixture.orcamento_para(tipo, categoria)
        ref = {"min": orcamento.min, "max": orcamento.max, "fonte": "formato"}
        return dict(ref), ref

    def _evento(self, bloco: Bloco, plano: dict, inicio: float, fim: float, pausa: float) -> dict:
        segmento = bloco.segmento or {}
        tipo_bloco = segmento.get("tipo") or "erro"
        categoria = categoria_do_tipo(tipo_bloco)
        texto = plano.get("texto") or ""
        eh_fala = plano["tipo"] == "fala"
        orcamento, referencia = self._orcamentos(segmento, tipo_bloco, categoria) if eh_fala else (None, None)
        musica = plano.get("musica")
        prevista = self._estimar(texto) if eh_fala else plano["duracao"]
        relogio = segmento.get("relogio")
        tipo_evento = plano["tipo"]
        if tipo_evento == "patrocinador" and relogio and relogio["etapa"]["tipo"] == "intervalo":
            tipo_evento = "intervalo"
        return {
            "n": len(self.eventos) + 1,
            "bloco_n": bloco.n,
            "inicio": self._instante(inicio).isoformat(timespec="seconds"),
            "fim": self._instante(fim).isoformat(timespec="seconds"),
            "inicio_s": round(inicio, 2),
            "fim_s": round(fim, 2),
            "gerado_em_s": bloco.gerado_em_s,
            "pausa_antes_s": round(pausa, 3),
            "tipo": tipo_evento,
            "bloco": tipo_bloco,
            "categoria": categoria,
            "formato": self.fixture.formato,
            "texto": texto,
            "palavras": contar_palavras(texto),
            "duracao_prevista_s": round(prevista, 2),
            "duracao_medida_s": bloco.duracao_medida_s if eh_fala else None,
            "orcamento_s": orcamento,
            "orcamento_ref_s": referencia,
            "musicas_citadas": [],
            "musica_anunciada": [],
            "musica_tocada": rotulo_musica(musica) if musica else None,
            "musicas_bloco": [rotulo_musica(m) for m in segmento.get("musicas") or []],
            "promessas_abertas": [],
            "promessas_fechadas": [],
            "pedido_id": bloco.pedido_id,
            "pedido_estado": bloco.pedido_estado,
            "pedido_estado_final": None,
            "pedido_tipo": bloco.pedido_tipo,
            "audio_status": segmento.get("audio_status") if eh_fala else None,
            "tom": segmento.get("tom") if eh_fala else None,
            "passos_roteiro": segmento.get("passos_roteiro", 1),
            "chamadas_llm": bloco.chamadas_llm,
            "revisada": bloco.revisada,
            "cortado": False,
            "cortado_s": 0.0,
            "video_id": musica.get("video_id") if musica else None,
            "inicio_previsto_s": bloco.inicio_previsto_s,
            "duracao_prevista_backend_s": segmento.get("duracao_prevista_s"),
            "relogio": relogio,
        }

    # --- pedidos -------------------------------------------------------------------------------------

    def _inserir_pedidos_ate(self, t: float) -> None:
        """Pedido entra direto em FilaAoVivo no instante virtual de chegada, sem passar pelo webhook."""
        from app.whatsapp.atendimento import ocorrencia

        inseriu = False
        for item in self.pedidos:
            pedido = item["fixture"]
            if item["id"] is not None or pedido.chega_em_s > t:
                continue
            self._mover(pedido.chega_em_s)
            novo_fluxo = self.fixture.conta.atendimento_ouvinte_ativo
            programa = self.sessao.get(Programa, self.cenario.programa_id)
            linha = FilaAoVivo(
                radio_config_id=self.cenario.radialista_id,
                programa_id=programa.id if novo_fluxo else None,
                transmissao=ocorrencia(programa, self.cenario.timezone) if novo_fluxo else None,
                estado="em_fila", eventos=[], texto_autorizado=pedido.texto_autorizado if novo_fluxo else "",
                telefone=pedido.telefone, nome=pedido.nome, tipo=pedido.tipo, natureza=pedido.natureza,
                mensagem_usuario=pedido.mensagem, musica_query=pedido.musica_query,
            )
            self.sessao.add(linha)
            self.sessao.commit()
            item["id"] = linha.id
            inseriu = True
        if inseriu:
            self._mover(t)

    def _confirmar_pedido(self, bloco: Bloco, fim: float, cortado: bool) -> None:
        """POST /ouvintes/pedidos/{id}/reproducao ao fim do bloco (useLiveEngine.ts:1572-1580)."""
        segmento = bloco.segmento or {}
        if not (segmento.get("pedido_id") and segmento.get("pedido_token") and segmento.get("pedido_programa_id")):
            return
        do_bloco = [e for e in self.eventos if e["bloco_n"] == bloco.n]
        if segmento.get("video_id"):
            concluida = any(e["tipo"] == "musica" and e["video_id"] == segmento["video_id"] and not e["cortado"]
                            for e in do_bloco)
        else:
            concluida = any(e["tipo"] == "fala" and not e["cortado"] for e in do_bloco)
        resultado = "executado" if concluida else ("interrompido" if cortado else "falhou")
        self._mover(fim)
        resposta = self.client.post(
            f"/ouvintes/pedidos/{segmento['pedido_id']}/reproducao", headers=self.headers,
            json={"token": segmento["pedido_token"], "programa_id": segmento["pedido_programa_id"],
                  "resultado": resultado},
        )
        self.contagem["confirmacoes_pedido"] += 1
        if resposta.status_code != 200:
            self.contagem["erros_http"] += 1

    def _segundos_desde_base(self, instante: datetime.datetime | None) -> float | None:
        if instante is None:
            return None
        if instante.tzinfo is None:
            instante = instante.replace(tzinfo=datetime.timezone.utc)
        return round((instante - self.base).total_seconds(), 2)

    def pedidos_finais(self) -> list[dict]:
        finais = []
        for item in self.pedidos:
            if item["id"] is None:
                continue
            linha = self.sessao.get(FilaAoVivo, item["id"])
            self.sessao.refresh(linha)
            bloco = next((b for b in self.blocos if b.pedido_id == item["id"]), None)
            eventos_bloco = [e for e in self.eventos if bloco is not None and e["bloco_n"] == bloco.n]
            finais.append({
                "id": linha.id, "nome": linha.nome, "tipo": linha.tipo,
                "chega_em_s": item["fixture"].chega_em_s, "musica_query": linha.musica_query,
                "bloco_n": bloco.n if bloco else None,
                "estado_selecao": bloco.pedido_estado if bloco else None,
                "estado_final": linha.estado, "atendido": linha.atendido,
                "atendido_em_s": self._segundos_desde_base(linha.atendido_em),
                "gerado_em_s": bloco.gerado_em_s if bloco else None,
                "tocou_em_s": eventos_bloco[0]["inicio_s"] if eventos_bloco else None,
            })
        estados = {p["id"]: p["estado_final"] for p in finais}
        for evento in self.eventos:
            if evento["pedido_id"] is not None:
                evento["pedido_estado_final"] = estados.get(evento["pedido_id"])
        return finais
