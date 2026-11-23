# Plano de execução — humanização da fala

Base: [`Locufy — Plano de humanização da fala.md`](Locufy%20—%20Plano%20de%20humanização%20da%20fala.md)
(20/11/2026), cruzado com o código da branch `melhoria/f12-14-expansao` (último commit `a9cc8f1`,
21/11/2026). O documento original foi escrito sem acesso ao repositório e cita módulos genéricos
(`llm`, `live`, `guardrails`, `tts`, `whatsapp`, `patrocinadores`). Este plano traduz cada item para
os arquivos reais, separa o que já existe do que falta e organiza a execução em frentes **H0–H9**,
no mesmo fluxo do `/melhoria-radio` (auditar → implementar → testar → avaliar → portão).

Execução: skill `/humanizar-fala` (`.claude/skills/humanizar-fala/SKILL.md`), com os agentes
`auditor-radio`, `implementador-locufy`, `testador-locufy` e `juiz-locucao`. Relatórios em
`docs/humanizacao/<frente>/`.

---

## 1. O que o código já faz

Boa parte do documento original já está implementada pelas frentes F2–F14. O ponto de integração
não é `app/guardrails/` (que hoje é filtro de tópico, rate limit e agenda), e sim o pipeline
pós-geração do ao vivo.

| Item do documento | Onde está | Estado |
|---|---|---|
| Uma reescrita no máximo, com todos os motivos juntos | `app/live/geracao.py:178` (`gerar_fala`, `MotivosRevisao`), teto de 2 chamadas por fala testado | **pronto** — o detector novo entra aqui, sem chamada extra |
| Fala de transição segura quando a correção falha | `app/live/validacao_fala.py:487` (`fala_reserva_neutra`) | **pronto** — reaproveitar como substituta do bloqueio |
| Checagens determinísticas pós-geração | `validacao_fala.py:375` (`CHECAGENS_POS_GERACAO`, `Violacao`, modo por regra em `settings`) | **pronto** — ponto de registro dos bloqueios |
| Frase longa, mais de uma ideia, sigla, número longo, burocratês | `app/live/oralidade.py` (F7), `settings.oralidade_modo` (padrão `desligado`) | **pronto, desligado** — nunca medido com LLM real |
| Remover markdown antes do TTS | `geracao.py:45,66` (`_limpar_fala`) | **parcial** — tira só `** * __ _ \``; não tira `#`, listas, links, emoji |
| Placeholder `[NOME]` nunca vai ao ar | `app/tts/client.py:125` (`_sanitizar_tags_v3`) apaga colchete fora da lista | **parcial** — some do áudio, mas deixa a frase quebrada ("Um abraço para .") |
| Recusa do modelo, data de corte, "como IA" | — | **ausente** |
| Números, horas, telefone, preço, data, FM, % por extenso | `app/numeros.py:101` (`normalizar_texto_fala`), aplicado em `tts/client.py:301` | **pronto** |
| Travessão vira pausa estranha | — (o próprio prompt usa `--` o tempo todo e o modelo imita) | **ausente** |
| Pausa entre ideias | `tts/client.py:151` (`......` → `[pause]` no v3) | **pronto** |
| `stability`/`style` por tom | `tts/client.py:93` (`_AJUSTE_TOM`), jitter por take | **pronto** |
| Contexto concreto: hora, dia, feriado, cidade, clima com fonte | `app/llm/prompt_builder.py:166` (`_contexto_atual`), clima como dado verificável (F5) | **pronto** |
| Música anterior e próxima, nome do ouvinte | `ContextoEmissao` (F3), `_musica`, `_participacao` em `prompt_emissao.py` | **pronto** |
| Passar as 5 últimas aberturas e fechamentos | `app/live/memoria.py:44`, `prompt_emissao.py:303` | **pronto** |
| Repetição por palavras | `memoria.py:78` (Jaccard 0,6) | **pronto** |
| Repetição por estrutura | `memoria.py:132` (classes de abertura e fechamento), métrica `repeticao_estrutura` | **parcial** — só mede; F8 passo 2c não feito |
| Limite de bordão por janela de tempo | — | **ausente** |
| Persona por programa com exemplos | `app/live/persona.py` (F7): 5 escalas + até 5 exemplos | **pronto** — base do "guia de estilo" |
| Glossário de pronúncia | `app/tts/glossario.py` (F9), rádio + voz | **pronto** (painel pendente) |
| Revisão humana de falas | `app/live/roteamento_revisao.py` (F12) | **pronto** (painel pendente) |

## 2. Achados que o documento original não previa

1. **O prompt do ao vivo diz ao modelo que ele é um bot de WhatsApp.** `montar_system_prompt`
   (`prompt_builder.py:227`) é a base dos dois canais. No ao vivo entram
   "Você é X, um locutor de rádio virtual que conversa com ouvintes pelo WhatsApp" (`:282`) e
   "Responda de forma curta e natural, como uma mensagem de WhatsApp" (`:341`). É a causa mais
   provável do tom de atendimento no ar. Corrigir isso vem antes de qualquer léxico.
2. **Conflito de regra sobre tamanho de frase.** O documento pede frases de até 15 palavras. O
   prompt atual (`prompt_emissao.py:253`) manda "NUNCA encadeie várias frases curtas seguidas",
   regra que nasceu de uma medição de TTS (ponto final sem respiro soa como lista lida). O
   verificador de oralidade usa 25 palavras. Não dá para seguir os dois: é a decisão **D1**.
3. **A "naturalidade encenada" pode ser o próprio sinal de IA.** `prompt_emissao.py:193` sorteia
   maneirismos, hesitação ("é... deixa eu ver aqui") e autocorreção encenada. Repetidos ao longo de
   horas, viram tique. O detector precisa contar esses recursos por janela, não só o léxico.
4. **Patrocínio não passa pelo LLM.** `Patrocinador.texto` (`app/models/patrocinador.py:29`) é lido
   como está, ou vai como áudio gravado. O "prompt de patrocínio" do documento não se aplica: o
   ganho está em checar o texto no cadastro e em permitir variações de leitura.
5. **O WhatsApp tem dois caminhos de geração e nenhum filtro de saída.**
   `whatsapp/webhook.py:103` (`_gerar_e_enviar_resposta`) e `whatsapp/atendimento.py:289`
   (`gerar_resposta_chat`). Nada limpa markdown, conta emoji ou barra frase de atendimento. As
   respostas fixas de `atendimento.py:192–272` ("Registrei sua solicitação para…; o atendimento
   depende da programação") soam de protocolo, mas carregam regra editorial (não prometer
   execução): só podem mudar de forma, nunca de sentido.
6. **O simulador `--modo fake` não mede prompt.** As falas vêm de `scripts/simulacao/banco_falas.py`
   (texto fixo). Ele serve para testar o detector e a mecânica; a queda de 50% na nota exige
   `--modo llm`, que consome créditos e precisa de aprovação.
7. **`oralidade.BUROCRATICO` já tem "ademais", "outrossim", "bem como".** O léxico novo não pode
   contar esses termos duas vezes.

## 3. Decisões para o usuário

Cada frente segue com o padrão indicado até a decisão chegar. O padrão vale como provisório e fica
registrado no relatório.

| Id | Pergunta | Padrão provisório |
|---|---|---|
| D1 | Frase curta (≤ 15 palavras) ou a regra atual contra frases curtas seguidas? | Alvo de 12–20 palavras com variação; limite duro de 25 (o da F7); medir as duas versões no `--modo llm` antes de fixar |
| D2 | Modo formal aceita "pra" e "tá"? | Não no formal (persona `formalidade` ≥ 4); sim do 3 para baixo |
| D3 | "18h30" vira "dezoito e trinta" ou "seis e meia da tarde"? | Manter a norma atual ("dezoito horas e trinta"); forma coloquial só com persona `formalidade` ≤ 2 |
| D4 | O que conta como bordão? | Traço marcante do radialista, slogan, frases de identificação e bordões cadastrados no guia de estilo (H8) |
| D5 | Limite de pontuação para reescrita | 30 pontos por 100 palavras, em `settings`, calibrado na H0 |
| D6 | Ligar `oralidade_modo` e `sinais_ia_modo` em `reescrever` em produção? | Não até a medição da H4 com LLM real; antes disso, `avisar` |
| D7 | Respostas fixas do WhatsApp podem ser reescritas? | Sim, mantendo o sentido (sem prometer execução); textos novos revisados pelo usuário antes do merge |
| D8 | Patrocinador ganha variações de texto (nova coluna)? | Sim, até 4 textos alternativos, migração aditiva; sem LLM na leitura |
| D9 | Orçamento para as rodadas `--modo llm` | Pedir aprovação a cada rodada, com estimativa de chamadas e custo antes de rodar |

## 4. Skills e agentes por etapa

| Etapa | Skill / agente | Uso |
|---|---|---|
| Regras de rádio e oralidade | `referencia-radio` | Carregada por todo agente antes de mexer em prompt, detector ou fala |
| Auditoria da frente | agente `auditor-radio` | Reconfirma o "estado atual" com `arquivo:linha` e desenha a mudança |
| Implementação | agente `implementador-locufy` | Testes primeiro, commits pequenos, flags desligadas por padrão |
| Portão de qualidade | agente `testador-locufy` | ruff, pytest, vitest, `simular_hora.py --modo fake` nos três perfis |
| Avaliação das falas | agente `juiz-locucao` + `avaliar-locucao` + `llm-evaluation` | Métricas automáticas sempre; rubrica só com `--modo llm` aprovado |
| Conjunto de testes e método de juiz | `llm-evaluation` | Desenho do conjunto de 60 entradas, juiz cego, concordância |
| Áudio real (H2, H9) | `text-to-speech`, `speech-to-text` | Ouvir a normalização; conferir por STT que nada de "asterisco" ou placeholder foi falado. Créditos: só com aprovação |
| Conversa de WhatsApp (H6) | `conversa-teste` | Simula o webhook sem enviar pelo WuzAPI. Chama o LLM real: só com aprovação |
| Painel (H8) | `web-design-guidelines`, `playwright` | Revisão da tela do guia de estilo e conferência no navegador |
| Revisão do diff | `code-review`, `simplify` | Ao fim de cada fase, antes do merge |

## 5. Frentes

Ordem: H0 → Fase 1 (H1, H2, H3, H6) → Fase 2 (H4, H5, H7) → Fase 3 (H8, H9). As fases são as do
documento original. Branch por frente, `melhoria/h<n>-<slug>`, encadeada a partir da anterior.

### H0 — Linha de base e conjunto de testes

**Estado atual:** `docs/benchmarks/2026-11-06-formatos/casos.json` tem 35 casos de regra editorial
(música, promessa, pedido, dado), nenhum de sinais de IA. O simulador já calcula `aviso_oralidade`
(`scripts/simulacao/metricas.py:323`).

**Entrega:**
1. Corpus determinístico `backend/tests/fixtures/humanizacao/corpus.json`: cerca de 150 textos curtos
   rotulados, sem LLM. Três grupos:
   - **vazamentos** (placeholder em colchetes, chaves e maiúsculas; recusa; data de corte; "como IA";
     markdown; emoji; links);
   - **sinais** (cada categoria do léxico, paralelismo negativo, tríade, gerúndio final,
     fechamento-resumo, frase de atendimento);
   - **não corrigir** (formal correto de notícia, um "além disso" isolado, mistura de casual e
     formal, reorientação "Você está na…" permitida).
   Todos os textos são originais; nenhum transcreve radialista real.
2. Conjunto de geração `docs/benchmarks/<data>-humanizacao/casos.json`: 60 entradas, 10 por tipo
   (recado, pedido de música, aniversário, clima e trânsito, patrocínio lido, resposta no WhatsApp),
   cada uma nos tons formal e informal. Formato compatível com o simulador e com a skill
   `conversa-teste`.
3. Métricas novas no simulador: `vazamento_grave`, `sinais_ia_media`, `sinais_ia_p90`,
   `bordao_repetido`, contadas sobre o mesmo detector do backend (nada de segundo detector, como já
   é a regra da F3).
4. Linha de base em `docs/humanizacao/baseline.md`: modo fake (mecânica) e, com aprovação (D9),
   uma rodada `--modo llm` dos três perfis para a nota real de partida.
5. Seção "Sinais de IA na fala" na skill `referencia-radio` e dimensão "Soa como pessoa" na rubrica
   de `avaliar-locucao` (5 = não dá para dizer que é IA; 1 = tique de chatbot evidente).

**Aceite:** corpus versionado com rótulos; baseline registrada; `test_simular_hora.py` cobre as
métricas novas.

**Skills:** `llm-evaluation`, `avaliar-locucao`, `referencia-radio`; agente `testador-locufy`.

### H1 — Travas: nada constrangedor vai ao ar (Fase 1)

**Estado atual:** ver tabela da seção 1 (markdown parcial, placeholder parcial, recusa ausente).

**Entrega:**
1. Módulo novo `app/live/sinais_ia.py`, puro e sem rede, com `vazamentos(texto) -> list[Aviso]`:
   placeholder (`[…]` que não seja tag v3 permitida, `{…}`, `<…>`, "FULANO", "XXX", "NOME DO"),
   recusa ("não posso ajudar", "como uma inteligência artificial", "sou um modelo de linguagem"),
   data de corte ("até minha última atualização", "meus dados vão até"), markdown residual.
2. Checagem `checar_vazamentos` registrada em `CHECAGENS_POS_GERACAO` (`validacao_fala.py:375`):
   - na fase `pre`, entra na reescrita única com instrução específica;
   - na fase `final`, remediação `fala_inteira`: a fala sai e entra `fala_reserva_neutra`, ou só
     música quando `so_musica_se_vazia`. Hoje `corrigir()` (`validacao_fala.py:526`) só age sobre
     `remover_frase`; precisa tratar `fala_inteira` vinda de checagem.
   - vale também para cada linha do diálogo multivoz (`falas_bloco`).
3. `_limpar_fala` (`geracao.py:66`) passa a remover cabeçalho `#`, marcador de lista no começo da
   linha, link markdown (fica só o texto), URL solta e emoji.
4. `settings.validacao_vazamento_modo` = `corrigir` por padrão: a trava não custa chamada nova, e
   no pior caso troca a fala pela reorientação neutra.
5. Registro `live_vazamento_bloqueado` com regra e trecho, e contagem no as-run e no relatório
   pós-programa (`app/live/relatorio_programa.py`).

**Aceite:** 100% dos vazamentos do corpus bloqueados; 0 falsos positivos no grupo "não corrigir";
simulação fake com `vazamento_grave = 0` nos três perfis; teto de 2 chamadas por fala mantido.

**Testes:** `tests/test_sinais_ia.py` (corpus), `tests/test_live_validacao_fala.py` (remediação
`fala_inteira`, multivoz), caracterização de `/proxima` intacta.

### H2 — Texto preparado para a voz (Fase 1)

**Estado atual:** `normalizar_texto_fala` (`app/numeros.py:101`) cobre números, horas, telefone,
preço, data, FM e porcentagem para fala, patrocinador e vinheta.

**Entrega:**
1. Em `normalizar_texto_fala`: emoji removido; `—`, `–` e ` -- ` entre palavras viram vírgula (ou
   ponto, quando separam orações completas); asterisco e cerquilha soltos removidos.
2. Opção coloquial de hora ("seis e meia da tarde") ligada à persona, conforme D3.
3. Limpeza do próprio prompt: trocar os `--` das instruções em `prompt_emissao.py` e
   `prompt_builder.py` por pontuação comum, para o modelo parar de imitar. Muda os goldens de prompt
   de propósito; atualizar e registrar.
4. Com aprovação (créditos), skill `text-to-speech` em 10 frases do corpus antes e depois e
   `speech-to-text` para conferir que nada de "asterisco", "hashtag" ou placeholder foi falado.

**Aceite:** `tests/test_numeros.py` cobre cada caso novo; nenhum texto do corpus chega ao payload do
TTS com emoji, markdown ou travessão.

### H3 — Prompt de locução, não de redação (Fase 1)

**Estado atual:** achados 1, 2 e 3 da seção 2. Exemplos por tipo de fala: só os da persona (até 5,
por programa).

**Entrega:**
1. `montar_system_prompt` ganha `canal: Literal["ao_vivo", "whatsapp"]`. No ao vivo, a identidade
   vira "locutor do programa X, no ar agora" e sai a linha "como uma mensagem de WhatsApp". O
   WhatsApp mantém o comportamento atual (H6 cuida dele). O ponto de chamada é
   `contexto.py:563` (via `portas.montar_system_prompt`).
2. Bloco "Guia de locução" no system do ao vivo: falar com uma pessoa ("você"), uma ideia por
   frase, sem lista, sem fechamento-resumo, sem frase de atendimento, sem ressalva ("vale
   ressaltar"), sem inflar importância. Tamanho de frase conforme D1.
3. Pares ruim → bom por tipo de fala em `app/live/exemplos_fala.py` (recado, pedido, aniversário,
   serviço, chamada de música), 3 a 5 por tipo, originais, escolhidos pelo tipo do bloco atual.
   Só entram quando o programa não tem exemplos de persona, que têm prioridade.
4. Registro coloquial por persona: `formalidade` ≤ 2 libera "tá", "pra", "a gente"; ≥ 4 mantém a
   norma culta com frase curta (D2).
5. Recursos de "naturalidade encenada" (`prompt_emissao.py:193`) passam a contar na memória da H5
   e ficam limitados por janela; enquanto a H5 não existir, nada muda.

**Aceite:** testes de snapshot das instruções por canal e por formalidade; nenhuma menção a
WhatsApp no system do ao vivo; juiz (com `--modo llm` aprovado) com "Soa como pessoa" e
naturalidade ≥ linha de base e nenhuma dimensão abaixo dela.

**Skills:** `referencia-radio` (regra 7: exemplo não imita apresentador real), `avaliar-locucao`.

### H4 — Detector de sinais de IA com reescrita (Fase 2)

**Entrega:**
1. Em `app/live/sinais_ia.py`: `CONFIG_SINAIS` declarativo com o léxico PT-BR do documento
   original (categorias e pesos), sem repetir os termos de `oralidade.BUROCRATICO`.
2. Padrões estruturais: paralelismo negativo ("não é só… é…"), tríade por fala, gerúndio no fim de
   frase ("…, reforçando…"), fechamento-resumo, "evitar o é" ("se destaca como"), atribuição vaga
   ("especialistas apontam"), conectivo de redação no começo de frase.
3. `pontuar(texto) -> Pontuacao(nota, violacoes)`: soma dos pesos por 100 palavras. Palavra isolada
   pesa pouco; o peso cresce com densidade e repetição. Formalidade não é punida.
4. Integração igual à da oralidade (`geracao.py:162`): `settings.sinais_ia_modo` =
   `desligado | avisar | reescrever`, padrão `avisar`. Acima do limite (D5), as violações viram
   instrução específica na **mesma** reescrita única ("tire 'vale ressaltar' e o fechamento 'em
   resumo'").
5. Nota e violações por fala no log, no as-run e no relatório pós-programa.
6. Palavras proibidas do guia de estilo da rádio (H8) entram com peso de reescrita.

**Aceite:** corpus com precisão ≥ 0,9 e revocação ≥ 0,8 por categoria; grupo "não corrigir" com
nota abaixo do limite; com `--modo llm` aprovado, `sinais_ia_media` 50% menor que a linha de base
da H0 e nenhuma dimensão do juiz abaixo dela.

### H5 — Memória de bordões e de estrutura (Fase 2)

**Estado atual:** memória por sessão e por tipo de bloco (`memoria.py`); as pendências 2c e 3 da
F8 cobrem parte disto e são absorvidas aqui.

**Entrega:**
1. Janela por rádio no Redis (`app/config/redis_client.py`, com o disjuntor da F3): falas das
   últimas 3 h com instante, abertura, fechamento, bordões e recursos de naturalidade usados.
   TTL de 3 h, teto de entradas.
2. Detector de bordão (D4): cada bordão no máximo 1 vez a cada 30 min (configurável por rádio).
   Bordão estourado vira instrução na reescrita única ou, se ela já tiver sido gasta, remoção
   extrativa da frase (`remover_frases`).
3. F8 passo 2c: mesma classe de abertura em N falas seguidas entra na reescrita (flag desligada por
   padrão).
4. F8 passo 3: reorientação "Você está no…" conta como repetição permitida, na frequência do
   formato (`reorientacao_s` do catálogo da F6).

**Aceite:** simulação fake com `bordao_repetido = 0`; com `--modo llm`, nenhuma abertura igual em
3 seguidas (aceite pendente da F8).

### H6 — Respostas no WhatsApp (Fase 1)

**Entrega:**
1. Pós-filtro determinístico comum aos dois caminhos (`webhook.py:121` e `atendimento.py:289`):
   remove markdown e listas; emoji só se o ouvinte usou algum, e no máximo 1; corta frases de
   atendimento ("Fico à disposição", "Posso ajudar em algo mais?") no começo ou no fim; no máximo
   2 frases curtas. Sem chamada extra ao LLM.
2. Instrução de canal no `montar_system_prompt(canal="whatsapp")`: responder primeiro, espelhar o
   registro do ouvinte, sem saudação pronta.
3. Respostas fixas de `atendimento.py` com redação mais falada, mesmo sentido (D7). Ex.: "Anotei
   seu pedido pro programa X. A equipe confere antes, e depende da programação." Os testes de
   `test_atendimento_ouvintes.py` mudam junto.
4. Com aprovação: skill `conversa-teste` nas 10 entradas de WhatsApp do conjunto da H0.

**Aceite:** nenhuma resposta do conjunto com markdown, lista, mais de 1 emoji ou frase de
atendimento; regras de não prometer execução preservadas (testes atuais verdes).

### H7 — Patrocínio sem tom de folheto (Fase 2)

**Entrega:**
1. No cadastro (`app/patrocinadores/router.py`), devolver a nota do detector e os trechos de
   folheto como aviso (sem bloquear) e mostrar no painel.
2. Campos de fatos (endereço, oferta, horário, diferencial) e até 4 textos alternativos
   (`textos_alternativos`, migração aditiva, D8), rotacionados sem repetir o último. O cache de
   áudio (`audio_cache`) passa a ser por texto.
3. Sem LLM na leitura. Sugestão de texto por LLM a partir dos fatos fica como pendência, com
   aprovação.

**Aceite:** testes de rotação e de cache por variação; painel com o aviso (vitest).

### H8 — Guia de estilo por rádio (Fase 3)

**Estado atual:** persona por programa (F7) com formalidade, energia e exemplos; tópicos proibidos
por programa; glossário de pronúncia por rádio (F9).

**Entrega:**
1. `Account.guia_estilo` (JSON, migração aditiva): bordões permitidos, gírias regionais, palavras
   proibidas, limite de repetição de bordão e até 3 trechos de locução da própria rádio como
   referência de estilo, com aviso de que não podem ser transcrição de apresentador real de outra
   emissora.
2. O controle formal ↔ informal reaproveita a escala `formalidade` da persona; não cria campo
   novo.
3. Coleta no onboarding (`app/onboarding/`, `app/llm/config_generator.py`) e editor no painel, junto
   com o CRUD do glossário pendente da F9.
4. Palavras proibidas alimentam o detector (H4); bordões alimentam a memória (H5).

**Aceite:** testes de validação (limites, vazio, duplicata); vitest da tela; conferência no
navegador com `playwright`.

### H9 — Medição contínua e teste cego (Fase 3)

**Entrega:**
1. Painel: nota média de sinais de IA, bloqueios por semana e taxa de repetição no relatório
   pós-programa (endpoint da F11).
2. Sinal do cliente: contar falas puladas, editadas ou rejeitadas (revisão da F12 e player).
3. Protocolo do teste cego em `docs/humanizacao/teste-cego.md`: 20 falas do Locufy + 20 de
   locutores humanos, com autorização por escrito dos autores; avaliadores de uma rádio cliente;
   meta de acerto entre 40% e 60%.
4. Revisão mensal do léxico com as violações registradas em produção (falsos positivos primeiro).

**Aceite:** relatório mostra as três métricas; protocolo aprovado pelo usuário antes de qualquer
contato com rádio cliente.

## 6. Metas por fase

| Fase | Frentes | Critério para avançar |
|---|---|---|
| 0 | H0 | Corpus e linha de base registrados |
| 1 | H1, H2, H3, H6 | Zero vazamento grave no corpus e na simulação; nenhum WhatsApp com markdown ou frase de atendimento; juiz sem queda |
| 2 | H4, H5, H7 | `sinais_ia_media` 50% menor que a linha de base (`--modo llm`); `bordao_repetido = 0` |
| 3 | H8, H9 | Teste cego com acerto entre 40% e 60% |

## 7. Portão de qualidade de cada frente

1. `ruff check app tests` sem erro novo.
2. `pytest` completo sem falha nova; cobertura não cai.
3. `vitest run` e `tsc` se a frente tocou o painel.
4. `simular_hora.py --modo fake` nos três perfis: métricas anteriores iguais (o detector não pode
   piorar música, promessa, pedido, dado ou orçamento) e as novas dentro do aceite.
5. Juiz de locução nas frentes H3, H4 e H5. Rubrica só com `--modo llm` aprovado.
6. Relatório da frente em `docs/humanizacao/RELATORIO.md`.

## 8. Regras de execução

- Nenhuma chamada real a Anthropic, ElevenLabs ou WuzAPI sem aprovação no chat, com estimativa de
  custo (D9).
- Toda trava nova entra com modo em `settings`. As que só barram (H1) começam em `corrigir`; as que
  reescrevem (H4, H5) começam em `avisar`.
- O teto de duas chamadas de LLM por fala continua valendo. Nenhuma frente cria uma terceira.
- Detector único: backend e simulador importam o mesmo `app/live/sinais_ia.py`.
- Migrações aditivas no padrão de `app/db/migrations/`.
- Falas de exemplo são originais. Não transcrever nem imitar radialista real.
- A branch atual tem alterações não commitadas (painel de bancada, tarifas). A H0 só começa depois
  que elas forem commitadas ou guardadas.

## 9. Riscos

- **Correção exagerada:** léxico demais deixa a fala sem sabor. Mitigação: grupo "não corrigir" no
  corpus como teste de regressão e pesos baixos para palavra isolada.
- **Goldens de prompt:** H2 e H3 mudam o texto do prompt de propósito. Atualizar os snapshots num
  commit separado e explicar no relatório.
- **Latência:** o detector é local; a reescrita já existe. O risco está em a H4 disparar a
  reescrita com mais frequência. Medir a taxa de reescrita na simulação `--modo llm`.
- **Custo de TTS:** variações de patrocínio (H7) multiplicam o cache de áudio. Medir antes de
  ligar.
- **Fala de reserva repetitiva:** muitos bloqueios fazem a reorientação neutra se repetir. A H5
  conta a reorientação na memória e o relatório alerta quando ela passa da frequência do formato.
