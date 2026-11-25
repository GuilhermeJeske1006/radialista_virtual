# Encerramento pontual — reta final, backtiming sem relógio e despedida no horário

Frente fora da numeração do plano: fecha a pendência **D4 da F1** (programa sem relógio decidia o encerramento por
`now()`, dois blocos antes, e a despedida era cortada) e trata o pedido "quando está chegando perto do fim, as
palavras do radialista e a música se dirigem ao encerramento, e o programa acaba pontualmente".

Branch `melhoria/encerramento-pontual`, a partir de `master` (`394168f`).

## 1. O que a simulação mostrava antes

`scripts/simular_hora.py --formato fixture`, modo fake (sem rede), relógio da fixture ou `--relogio-backend nenhum`.
O relógio é opcional (`programas.relogio_hora` nulo por padrão), então o caminho **sem relógio** é o da maioria
dos programas.

| Programa | Com relógio | Sem relógio |
|---|---|---|
| musical_adulto | despedida no ar, **88 s antes** do fim (ar parado) | **despedida cortada**: música cortada no `horario_fim` |
| popular_sertanejo | despedida no ar, 18 s antes | despedida no ar, 42 s antes |
| variedades_leves | despedida no ar, 7 s antes | **despedida cortada** |

Causas encontradas no código:

1. **Sem relógio não havia backtiming.** `roteiro.decidir_bloco` só virava encerramento com
   `minutos_restantes(now) ≤ 3`. O painel gera cada bloco ~2 blocos antes de tocar, então o `now()` da geração fica
   minutos atrás do ar: a despedida era gerada cedo e ficava na fila atrás de músicas sem teto de duração; o
   watchdog do painel corta tudo em `horario_fim + 1 s`.
2. **Despedida curta demais para o espaço.** A etapa de encerramento tem 45 s e o compromisso pode adiantar até
   45 s, mas a fala respeitava o máximo do formato (10 a 18 s no musical). O resto virava ar parado, porque o painel
   pausa a transmissão logo depois da vinheta de encerramento.
3. **O texto não conduzia ao fim.** O prompt proibia qualquer "final", "último" ou "última música" fora do bloco de
   encerramento; não havia aviso de reta final, a última música não era tratada como tal e, logo antes da
   despedida, a reserva dizia "Bom te ter aqui". O encerramento pedia "se souber quando o programa volta, convide a
   voltar", mas nenhum dado de grade chegava ao prompt.

## 2. Pesquisa

- `docs/pesquisa-radio-locufy.md` §7 (hard time, backtiming), §8 ("Encerramento: Obrigado pela companhia. Amanhã,
  às [hora], tem mais [programa]. Agora a programação segue com [atração]."), §9 (relógio A: música de fechamento
  56:00–59:30 e passagem 59:30–60:00; relógio C: música 50:00–58:00 e fechamento 58:00–60:00) e a skill
  `referencia-radio` (não anunciar música não confirmada; não prometer sem evento agendado; "debate estourou → fechar e
  cumprir o hard time").
- Prática de backtiming (fóruns e colunas de rádio): escolher a última faixa pela duração para terminar na hora;
  ter um item "elástico" (ad-lib, identificação, serviço) que se estica ou encurta; reserva preparada caso o tempo
  não feche. [Radio World — Beat the clock](https://www.radioworld.com/columns-and-views/beat-the-clock-for-radio-success),
  [RadioDiscussions — The lost art of backtiming](https://radiodiscussions.com/threads/the-lost-art-of-backtiming.544479/),
  [RadioInsight — Honor the top of the hour](https://radioinsight.com/blogs/109356/honor-the-top-of-the-hour-and-keep-it-hot/).
- Fechamento do apresentador: "uma boa conversa não simplesmente para, ela conclui"; fechar como vírgula, não ponto
  (dar motivo para voltar), retomar algo do próprio programa, chamar o que vem a seguir; não anunciar o fim cedo e
  repetidamente (empurra o ouvinte para fora).
  [Dan O'Day — How to end a radio show](https://danoday.com/blog/2011/09/how-to-end-radio-show),
  [Barrett Media — teasing](https://barrettmedia.com/2026/02/05/from-casey-kasem-to-ppm-why-teasing-still-works-and-matters-for-music-radio/).

## 3. Decisões

| | Decisão | Onde |
|---|---|---|
| D1 | **Zona de fechamento sem relógio.** Nos últimos `zona_fechamento_s` (600 s, no máximo metade do programa), pelo horário em que o bloco vai ao ar (`inicio_previsto` do painel), o ao vivo monta um espelho sintético `[música ajustável até fim − 45 s, encerramento com hard time]` e decide com o mesmo `_Decisao` do relógio. O tipo do roteiro é respeitado: fala só se ainda couber uma música depois dela (orçamento reduzido); música pela janela (faixa que feche o espaço, sem sobra impossível); sem nada que caiba, reserva, link de preenchimento (formatos com preenchimento) e encerramento. Vinheta e patrocinador seguem enquanto há folga. Fora da zona nada muda (o sorteio do roteiro nem é feito antes). | `relogio.planejar_fechamento`, `router._planejar_fechamento`, `roteiro.decidir_bloco` |
| D2 | **Encerramento elástico.** A despedida ocupa o espaço até o fim (menos a vinheta), acima da unidade do formato, até `encerramento_max_s` (60 s); o teto de palavras do formato só vale se o máximo não subiu. | `relogio._Decisao._encerramento`, `orcamento.orcamento_para(teto_relogio_vence)` |
| D3 | **Última música.** Uma faixa é a última quando a sobra até o encerramento fica no piso da sobra proibida (o que o encerramento absorve) e abaixo da busca mínima: nenhuma outra música é buscada depois. Só então a fala pode dizer "pra fechar". Com relógio (música sem fala, D2 da F1), formatos que apresentam a faixa ganham uma fala curta que cabe na sobra. No musical não há fala na música; a despedida retoma a faixa que fechou. | `relogio.marcar_ultima_musica`, `Plano.ultima_musica` |
| D4 | **Reta final no texto.** Nos últimos `reta_final_s` (900 s; um quarto do programa, nunca menos que a zona), todo bloco de fala recebe: conduzir para o encerramento, sem assunto novo longo, sem prometer nada para depois do fim e sem se despedir. O aviso "reta final" vai **uma vez** (o histórico é conferido). Na zona, nenhum convite a mandar pedido ou mensagem. Notícia não recebe o aviso, só a proibição de prometer depois do fim. A regra geral anti-"final" passa a ceder só a essa instrução. | `fechamento.fase_do_bloco`, `prompt_emissao._reta_final`, `_REGRAS_GERAIS` |
| D5 | **Encerramento com dado de grade.** Quando o programa volta ("amanhã, às dez horas", "na segunda-feira…", "hoje, às vinte e duas horas" na madrugada; nada para programa avulso, e então "não diga até amanhã") e o programa da rádio que começa no fim deste (±2 min). O nome do programa seguinte entra nos nomes de continuidade do detector de promessas (F4), para "a programação segue com…" não virar promessa sem evento. | `fechamento.completar_encerramento`, `prompt_emissao._encerramento`, `promessas.situacao_do_contexto` |
| D6 | **Sem horário previsto** (transmissão fora da grade): fica o comportamento antigo por `minutos_restantes`. | `roteiro.decidir_bloco` |
| D7 | **Painel antigo** (sem `inicio_previsto`): perto do fim, todo bloco do programa sem relógio entra na cadeia de blocos gerados (F3), com plano ou sem, para o servidor estimar o horário do ar. Sem isso a despedida ainda era cortada. | `router._planejar_fechamento` (ocorrência da cadeia), `router._com_relogio(cadeia=…)` |
| D8 | **Coerência do formato:** fala que o relógio estendeu acima da unidade (encerramento elástico) não conta como fora da unidade, simétrico à fala reduzida que já não contava. | `formatos.avisos_da_fala` |

Números novos em `ConfigRelogio` (hipóteses de projeto): `encerramento_max_s=60`, `zona_fechamento_s=600`,
`reta_final_s=900`.

**Decisão aberta (musical):** o teto elástico é o mesmo para todos os formatos. Limitar o musical a 45 s (só a própria
etapa de encerramento, pela promessa "pouca conversa") foi medido: o fim antecipado sobe de 46 para 60 s com relógio e
de 9 para 26 s sem relógio. Ficou o teto único porque o pedido é acabar no horário e ar parado é pior que uma
despedida mais longa; se preferir o limite, é um campo por formato.

## 4. Resultado (simulação fake, mesma semente)

| Programa | Com relógio antes → depois | Sem relógio antes → depois | Sem relógio, painel antigo |
|---|---|---|---|
| musical_adulto | 88,4 s antes → **45,8 s** | cortada → **no ar, 9,4 s antes** | cortada → **9,4 s** |
| popular_sertanejo | 18,4 s → **2,2 s** | 42,1 s → **12,1 s** | **12,1 s** |
| variedades_leves | 7,4 s → **0,0 s** | cortada → **no ar, 17,1 s antes** | **17,1 s** |

Saídas em `simulacao/fake/<perfil>/{relogio,sem_relogio,sem_relogio_painel_antigo}`.

Em todas as rodadas: nada cortado no fim (`estouro_fim_s = 0`), nenhuma fala fora do orçamento, nenhum anúncio sem
confirmação, nenhuma promessa vencida, nenhum hard time do relógio atrasado (com relógio).

`atraso_hard_time_s` das rodadas **sem relógio** passou de 0 para 11–44 s: é a métrica comparando com os hard times
do relógio da fixture (59:30 no A, 58:00 no C), que o backend sem relógio não conhece. Antes a despedida nem ia ao
ar ("perdido"); agora ela começa no fim − 45 s do espelho sintético. Não há compromisso violado.

Testes e linhas de base: `tests/test_live_fechamento.py` (novo, puros + `/proxima` + prompt). Atualizados de propósito,
porque fixavam o comportamento antigo: os testes que congelavam o relógio a 2 min do fim esperando a despedida direta
(agora entra a reserva antes; foram para 40 s do fim), `test_proxima_sem_relogio_ignora_inicio_previsto[encerramento]`
(D4 da F1), os três da F0 que esperavam corte e estouro no fim, os goldens de planos (só campos novos e o encerramento
do musical) e de `/proxima` (texto da regra geral, cenário de encerramento), e as linhas de base de simulação da F5 e da
F6, regravadas com o ambiente do simulador (0 tentativas de rede). Valores medidos do dublê: `fora_orcamento_pct` do
popular 10,0 → 9,1 (a mesma identificação, agora 1 de 11), `falas_fora_da_unidade_pct` do musical sem relógio 12,5 →
10,0 (1 de 10) e a maior janela sem reorientação do popular com voz de 120/min 3475,35 → 3495,35 s (a identificação
antes da despedida, que diz o nome, entra 20 s depois).

O dublê do LLM ganhou oito frases de meio no banco do encerramento (`scripts/simulacao/banco_falas.py`): sem elas ele
não chegava ao alvo do encerramento elástico e a simulação subestimava a despedida.

### Texto real (LLM)

Rodada `--modo llm` aprovada (popular e musical, sem relógio). Detalhe em [`avaliacao.md`](avaliacao.md). O aviso de
reta final saiu uma vez em cada programa, a última música foi apresentada como tal só quando era a última, nenhuma
despedida antes da hora e o encerramento disse quando o programa volta pela grade. Três falhas, corrigidas depois no
prompt (com teste): o link antes da despedida abria pergunta e convidava ao WhatsApp (variação de comentário sorteada
na zona), o convite da reta final prometia "eu leio", e as despedidas saíam curtas para a meta (35 a 48 s para 50 a
60 s; agora o prompt pede a faixa de palavras).

## 5. Pendências

- **Musical com relógio ainda fecha 46 s antes na simulação.** A janela antes do encerramento (347 s) não fecha com
  nenhuma faixa do catálogo fictício (187 a 285 s): a escolha não estrita deixa 73 s de sobra, o encerramento
  elástico absorve 60 s + vinheta. Com catálogo real a escolha por duração tem mais opções; se continuar, avaliar
  preenchimento só no fechamento do musical ou um piso da sobra que considere o encerramento elástico.
- **Confirmar as três correções de texto com LLM.** Avaliação REPROVADO por 0,1 em Precisão no popular (promessa "eu
  leio"), já tratada no prompt; repetir `--modo llm` no popular sem relógio (custo, com aprovação).
- **Música de saída cortada no horário** (técnica de "dead-roll" com fade no hard time): não implementada; a pesquisa
  pede não cortar canções para encaixar.
- `_marco_tempo_programa` e `_ajuste_energia_meio_programa` continuam por `now()` (pendência da F1).
