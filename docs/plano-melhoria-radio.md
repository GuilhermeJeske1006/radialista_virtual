# Plano de melhoria — formatos radiofônicos e locução na Locufy

Base: `docs/pesquisa-radio-locufy.md` (pesquisa documental de 6/11/2026) cruzada com o código da
branch `master` (último commit analisado: 21/10/2026, PR #7). Este plano é executado pelo comando
`/melhoria-radio` no Claude Code, que usa os agentes `auditor-radio`, `implementador-locufy`,
`testador-locufy` e `juiz-locucao` e as skills `referencia-radio` e `avaliar-locucao`.

## Como ler cada frente

Cada frente tem: **pesquisa** (seção de origem), **estado atual** (o que já existe no código —
o auditor deve reconfirmar, porque o código pode ter mudado), **lacuna**, **entrega**,
**critérios de aceite** e **testes**. Os números (segundos, palavras por minuto) são hipóteses da
pesquisa: devem virar configuração, não constantes espalhadas.

Ordem de execução: F0 → P0 (F1–F5) → P1 (F6–F11) → P2 (F12–F14). Uma frente só começa depois que
a anterior passou no portão de qualidade (ver final).

---

## F0 — Linha de base e bancada de testes (pré-requisito)

**Pesquisa:** §14 (como avaliar) e "próxima pesquisa de campo".

**Estado atual:** 77 arquivos em `backend/tests`, CI com `ruff check app tests` e
`pytest --cov=app`; painel com `vitest run`. Scripts de benchmark (`scripts/benchmark_falas.py`,
`scripts/conversa_teste.py`) consomem créditos reais. Não há simulação de uma hora de programa.

**Lacuna:** não existe como medir, sem custo, se uma mudança melhora tempo, continuidade e
promessas de uma hora inteira.

**Entrega:**
1. Registrar a linha de base: resultado de `ruff`, `pytest` (total, falhas, cobertura) e
   `vitest` em `docs/melhoria-radio/baseline.md`.
2. Criar `backend/scripts/simular_hora.py`:
   - `--modo fake` (padrão, sem rede): LLM e TTS substituídos por dublês determinísticos; a duração
     do TTS é estimada por `palavras / wpm` (wpm configurável, padrão 145); músicas com durações de
     fixture. Testa mecânica: relógio, janelas, promessas, estados de pedidos.
   - `--modo llm` (consome créditos Anthropic, exige aprovação explícita do usuário): gera texto real
     para avaliação de qualidade; TTS continua estimado.
   - `--modo completo` (Anthropic + ElevenLabs, exige aprovação): mede duração real do áudio.
   - Saída: `as_run.json` (cada evento: início, fim, tipo, texto, duração prevista e medida,
     promessas abertas/fechadas, música anunciada x tocada) e `resumo.json`.
3. Fixtures em `backend/tests/fixtures/programas/`: um programa para cada perfil inicial
   (musical adulto, popular/sertanejo, variedades leves) e os relógios A, B e C da pesquisa §9.
4. Conjunto de casos de avaliação `docs/benchmarks/<data>-formatos/casos.json`.

**Aceite:** `simular_hora.py --modo fake` roda em < 30 s, sem rede, e é coberto por teste em
`tests/test_simular_hora.py`.

---

## P0 — Emissão confiável

### F1 — Relógio, espelho e hard time

**Pesquisa:** §2 (grade, programa, relógio, espelho), §4.3 (relógio de rede), §7 (hard time,
backtiming), §9 (modelos A/B/C), §12.3, §13 P0.

**Estado atual:** o programa tem `horario_inicio`, `horario_fim`, `estrutura_blocos` (lista de
tipos) e `perfil_programacao`. O ao vivo escolhe o próximo bloco por posição no roteiro
(`_tipo_proximo_bloco`, `ROTEIRO_PADRAO`, `ROTEIRO_MUSICAL` em `app/live/formato.py`) e por
contagem de falas (`total_falas`). Há marcos de tempo (`_marco_tempo_programa`,
`_ajuste_energia_meio_programa`). Não existe noção de horário fixo dentro da hora, janela,
conteúdo obrigatório x ajustável x reserva, nem cálculo de tempo restante. O próprio documento
`docs/analises/2026-09-09-implementacao-musical.md` registra que o ciclo é por quantidade de faixas,
não por duração.

**Lacuna:** a fala é gerada sem saber se há espaço; o programa pode estourar o horário ou deixar
buracos.

**Entrega:**
1. Modelo de relógio por programa (`relogio_hora`, JSON validado por Pydantic): lista de eventos
   `{minuto_inicio, duracao_s, tipo, natureza: obrigatorio|ajustavel|reserva, hard_time: bool}`.
2. Presets A (musical com companhia), B (jornal/revista) e C (morning/variedades) da pesquisa §9,
   com teste que garante soma exata de 3600 s.
3. Serviço `app/live/relogio.py`: dado o horário atual, devolve etapa atual, próximo compromisso,
   `segundos_ate_hard_time` e orçamento disponível para a fala (backtiming).
4. `gerar_proxima_fala` consulta o relógio **antes** de chamar o LLM: sem espaço → não gera fala
   (devolve próxima música ou peça de reserva); pouco espaço → orçamento reduzido.
5. Regra "debate estourou": se a fala prevista ultrapassa o hard time, gera fechamento curto.
6. Compatibilidade: programa sem relógio mantém o comportamento atual (`estrutura_blocos`).
7. Painel: editor simples do relógio em `frontend-painel/app/programas` (escolher preset e ajustar duração).

**Aceite:** na simulação fake de 1 h com cada preset, nenhum hard time atrasado > 5 s; nenhuma fala
gerada com orçamento < mínimo do tipo; programas sem relógio passam nos testes existentes sem
alteração.

**Testes:** unitários do serviço de relógio (virada de hora, programa que cruza meia-noite,
fuso da rádio, feriados), integração em `/proxima`, simulação.

### F2 — Duração real da fala

**Pesquisa:** §5 (ritmo 130–160 palavras/min como hipótese), §11 (medir após síntese), §12.8.

**Estado atual:** `ORCAMENTOS` em `formato.py` dá segundos e limite de palavras por tipo no perfil
musical; `contar_palavras` existe; `_limpar_fala` limpa o texto. A resposta de `/proxima` tem
`duracao_segundos` para a música, não para a fala. Não há medição da duração do áudio sintetizado
nem calibração por voz.

**Lacuna:** o orçamento é só uma instrução ao LLM; nada confere o áudio final.

**Entrega:**
1. Medir a duração do mp3 após TTS e pós-produção (`app/postprod/audio_io.py` ou ffprobe) e
   devolver `duracao_fala_s` na resposta.
2. Se exceder o orçamento em mais de 15 %: uma tentativa de reescrita mais curta (sem acelerar a
   voz além do perfil); persistindo, usar peça de reserva ou cortar a fala do bloco.
3. Registrar palavras/min observadas por voz (`perfil_voz`) para calibrar a estimativa de F0/F1.
4. Mover os orçamentos para o catálogo de formatos (F6), mantendo `ORCAMENTOS` como padrão.

**Aceite:** 95 % das falas simuladas dentro do orçamento; nenhuma fala acima de 130 % do máximo.

### F3 — Estado confiável da emissão (contexto da geração)

**Pesquisa:** §12.4 (o que a geração deve saber), §13 P0 (não anunciar o que não tocará), §8
(front-announce só com música confirmada).

**Estado atual:** o pedido traz `historico` (últimas 8), `total_falas` e `ultima_fala`. O roteador
monta contexto de músicas (`_contexto_musica`, `_musicas_citadas_na_fala`), tom anterior em Redis
(`_ultimo_tom`), fio condutor e temas recentes. `gerar_proxima_fala` tem cerca de 1000 linhas
(ver `docs/refatoracao.md`), o que dificulta testar o contexto isoladamente.

**Lacuna:** o contexto está espalhado; não há um objeto único e testável com o que tocou, o que vai
tocar confirmado, chamadas pendentes, participações aprovadas, dados válidos e tempo restante.

**Entrega:**
1. Extrair `ContextoEmissao` (dataclass) montado por `app/live/contexto.py`, seguindo a separação
   HTTP x regra de negócio proposta em `docs/refatoracao.md` (com testes de caracterização antes de
   mover código).
2. `prompt_builder` recebe só `ContextoEmissao`.
3. Validador pós-geração: toda música citada na fala precisa estar em `musica_confirmada` ou no
   histórico; caso contrário, reescrever ou remover a menção.

**Aceite:** testes de caracterização de `/proxima` continuam verdes; validador pega 100 % dos
casos de "música anunciada que não está confirmada" no conjunto de casos.

### F4 — Promessas, chamadas e participação de verdade

**Pesquisa:** §8 (antes do intervalo, tease, pergunta do dia, "quando não há pedido"), §10
(contingências), §12.7 (recebido → moderado → elegível → programado → executado), §13 P0/P1.

**Estado atual:** `FilaAoVivo` já tem `estado` (`em_fila`, `aguardando_revisao`, `selecionado`,
`executado`, `expirado`, `cancelado`), `eventos`, `texto_autorizado` e só marca atendido após
confirmação de reprodução (`app/whatsapp/atendimento.py`). `direcao_musical` proíbe prometer
retorno sem programação confirmada. Não há registro de promessas feitas no ar.

**Lacuna:** "daqui a pouco a gente lê as respostas" ou "depois do intervalo, fulano explica" podem
ser ditos sem que o sistema garanta o cumprimento.

**Entrega:**
1. Registro de promessas por transmissão (Redis + persistência): `{tipo, texto, prazo, evento_alvo,
   estado: aberta|cumprida|cancelada|vencida}`.
2. O LLM só pode fazer tease quando o relógio tem o evento-alvo agendado; o validador detecta
   promessas no texto (padrões "daqui a pouco", "depois do intervalo", "já já", "ainda hoje") e
   cruza com o relógio.
3. Promessa aberta vira obrigação do relógio; se o conteúdo cair (convidado não entrou, fonte
   falhou), gerar a fala de contingência da pesquisa §10.
4. Garantir por teste que a fala "pedido autêntico … toca agora" só ocorre com pedido `selecionado`
   para o próximo evento, e que nenhuma fala cita ouvinte inexistente.

**Aceite:** na simulação, 0 promessas vencidas sem fala de contingência; 0 pedidos anunciados como
"toca agora" fora do estado correto.

### F5 — Fontes, validade e dados verificáveis

**Pesquisa:** §6 (coluna verificação), §8 (jornal, serviço com horário), §10 (fonte não atualizou),
§12.5.

**Estado atual:** `app/news/pauta.py` tem janela de validade por categoria; `app/news/validacao.py`
tem `frase_proibida_em` e `tem_atribuicao`; há cliente de clima (`app/weather/client.py`). A
auditoria (`docs/auditoria.md`, item 3) aponta conteúdo de notícia entrando no system prompt sem
isolamento.

**Lacuna:** a regra de validade não é uniforme para clima, placar, trânsito, agenda; a fala nem
sempre declara o horário da última atualização.

**Entrega:**
1. Tipo comum `DadoVerificavel {valor, fonte, atualizado_em, valido_ate, local, aprovado}` para
   notícia, clima, agenda e qualquer integração nova.
2. Dado vencido é omitido ou dito com o horário ("atualizado às 14h"), nunca como atual.
3. Sem integração, não falar de temperatura, trânsito ou placar (teste de guardrail).
4. Corrigir o item 3 da auditoria se ainda aberto: conteúdo externo vai em bloco delimitado de
   dados, não em instruções.

**Aceite:** testes cobrindo dado dentro e fora da validade, dado sem fonte, e injeção em título de
notícia.

---

## P1 — Identidade e naturalidade

### F6 — Catálogo de formatos e perfis editoriais

**Pesquisa:** §3 (mapa dos formatos), §4 (lições dos cases), §12.1, §13 (primeiros perfis:
musical adulto, popular/sertanejo, variedades leves).

**Estado atual:** `perfil_programacao` aceita `padrao` e `musical_companhia`; `Programa` já tem
`perfil`, `dose_noticia`, `publico_alvo`, `densidade_assunto`, `quadros_fixos`, `generos_musicais`;
`app/llm/tipos_radio.py` existe.

**Entrega:**
1. Catálogo declarativo `app/live/formatos.py` (ou JSON) com, por formato: promessa, unidade de
   fala (min/alvo/máx em segundos por tipo de bloco), condução, roteiro/relógio padrão, temas que
   exigem revisão, política de participação, frequência de reorientação.
2. Implementar primeiro: `musical_adulto` (absorve `musical_companhia` como alias), `popular_sertanejo`,
   `variedades_leves`. Deixar estrutura pronta para hits, regional, noturno, religioso, morning,
   esportivo e jornalístico (este condicionado a F5).
3. `direcao_musical` vira `direcao_formato(formato, tipo, primeira)`.
4. Painel: seleção do formato com descrição da promessa; separar identidade da rádio (`RadioConfig`)
   da identidade do programa.

**Aceite:** os três perfis produzem relógio, orçamento e instruções distintos (teste de snapshot
das instruções); avaliação do juiz mostra coerência ≥ 4/5 para o formato em cada perfil.

### F7 — Persona e oralidade

**Pesquisa:** §5 inteira (conversa dirigida, oralidade, prosódia, energia, pausa), §12.2.

**Estado atual:** tom `calmo|neutro|energico`, `_tom_sintese_do_bloco`, instruções de reação por
natureza da mensagem; `normalizar_texto_fala` cuida de números/pronúncia para o TTS.

**Entrega:**
1. Persona configurável por programa: proximidade, formalidade, energia, humor e ritmo (escalas 1–5)
   + até 5 exemplos aprovados de fala.
2. Verificador determinístico de oralidade (`app/live/oralidade.py`): frases > 25 palavras, mais de
   uma ideia por frase (heurística de conectivos), siglas sem expansão na primeira ocorrência,
   números longos, vocabulário burocrático (lista: "municipalidade", "acarretar", "realizará" …).
   Avisos alimentam uma reescrita opcional e as métricas.
3. Regra: persona não pode imitar apresentador real (aviso no painel e no prompt).

**Aceite:** no conjunto de casos, redução ≥ 50 % de avisos de oralidade em relação à linha de base;
juiz: clareza e naturalidade ≥ 4/5.

### F8 — Memória e controle de repetição

**Pesquisa:** §8 ("variar só sinônimos mantém a repetição"), §12.6, §7 (reorientar quem chegou).

**Estado atual:** Redis guarda histórico de falas por categoria, temas, fio condutor, aberturas e
fechamentos (`_fala_semelhante_no_historico`, `_aberturas_e_fechamentos`, `_proxima_variacao`);
histórico persistente de músicas e temas por rádio; `app/topics/espelho.py` ajusta score por uso.

**Entrega:**
1. Consolidar em `app/live/memoria.py` (sem mudar comportamento primeiro).
2. Repetição por estrutura, não só por palavras: classificar a construção da fala (abertura,
   gancho, fechamento) e evitar a mesma estrutura em N falas.
3. Reorientação periódica configurável por formato ("Você está no …"), contada como exceção
   permitida à regra de não repetir.
4. Persistir promessas e correções feitas no ar (liga com F4).

**Aceite:** na simulação llm de 1 h, nenhuma abertura com a mesma estrutura em sequência de 3;
métrica de repetição registrada no `resumo.json`.

### F9 — Glossário de pronúncia

**Pesquisa:** §5 (pronúncia e nomes), §13 P1.

**Estado atual:** `perfil_voz.pronuncias` (até 30 entradas) editável em `VozConfigModal.tsx` e
aplicado por `normalizar_texto_fala`.

**Entrega:**
1. Glossário por rádio (artistas, bairros, siglas, patrocinadores, convidados), aplicado a todas as
   vozes; o glossário da voz sobrescreve o da rádio.
2. Sugestão automática de termos novos a partir de metadados de música, patrocinadores e cidade.
3. Verificação opcional por STT (skill `speech-to-text`): sintetizar a frase-teste e conferir se
   o termo transcrito bate (exige créditos; só com aprovação).

**Aceite:** testes de precedência rádio x voz e de limites; painel com CRUD e teste vitest.

### F10 — Direção de som

**Pesquisa:** §11, §7 (ramp, sweeper, bed).

**Estado atual:** pós-produção com perfis (`app/postprod/perfis/*.json`, `mastering.py`,
`naturalness.py`), vinhetas com trilha, intervalos de transição por categoria
(`_intervalo_transicao_ms`, `_pausa_antes_ms`), `app/live/audio_analysis.py`.

**Entrega:**
1. Transição por natureza do conteúdo: notícia grave nunca usa trilha/sweeper de promoção.
2. Fala sobre introdução (ramp) só se a análise de áudio fornecer o início do vocal; caso contrário,
   falar antes da música.
3. Medir loudness integrada de fala, vinheta e música por segmento e reportar a diferença entre eles
   (sem impor valor universal — alvo configurável por destino).

**Aceite:** testes com os áudios de `tests/fixtures`; relatório de loudness no `as_run.json`.

### F11 — Produção antes, durante e depois

**Pesquisa:** §4.1 (preparação), §10.

**Estado atual:** `/preparo` (preparo antecipado), `app/live/prewarm.py`, reservas semanais em
`app/topics/reserva.py`, histórico de fila.

**Entrega:**
1. As-run log persistente do que foi efetivamente ao ar (fala, música, vinheta, patrocinador,
   pedido, promessa).
2. Relatório pós-programa no painel: promessas cumpridas/vencidas, falas fora do orçamento, avisos de
   oralidade, pedidos atendidos, sugestões de continuidade para a próxima edição.
3. Plano de contingência automático (convidado, fonte, pedido, áudio, estouro) com peça de reserva
   aprovada.

**Aceite:** relatório gerado a partir do `as_run.json` da simulação; testes de cada contingência.

---

## P2 — Expansão

### F12 — Autonomia graduada e revisão humana

**Pesquisa:** §12.9. Por categoria de conteúdo: `automatico | revisao | proibido`. Cobertura urgente,
temas delicados e entrevistas reais entram em `aguardando_revisao` com aprovação no painel.
**Aceite:** testes de roteamento por categoria; tela de aprovação.

### F13 — Bancada com múltiplas personas

**Pesquisa:** §4.6, §5 (bancada). **Estado:** multivoz existe (`_sintetizar_falas_multivoz`,
`ParticipantePrograma`). **Entrega:** papéis (mediador, comentarista, contraponto), turnos que
respondem ao turno anterior, tempo total da conversa dentro do relógio. **Aceite:** juiz avalia
"resposta ao que acabou de ser dito" ≥ 4/5.

### F14 — Narrativos, especiais e cortes

**Pesquisa:** §4.10, §4.13, §3 (narrativo). Quadro com estrutura personagem → situação → mudança →
consequência; marcação de cortes que fazem sentido sozinhos no as-run log.

---

## Transversal — confiabilidade já apontada

Antes de P0, o auditor confere se continuam abertos os itens de `docs/auditoria.md` que afetam o ao
vivo (4: rate limit dos endpoints pagos; 5: race condition na fila; 6: timeout do Redis; 9: TTL do
cache de categoria). Itens abertos entram como tarefas da frente correspondente.

## Avaliação (pesquisa §14)

| Dimensão | Como medir aqui |
|---|---|
| Tempo | `duracao_fala_s` x orçamento; atraso em hard time (F1, F2) |
| Continuidade | música anunciada = música tocada (F3) |
| Participação | pedidos e promessas cumpridos (F4) |
| Precisão | dados com fonte e válidos (F5) |
| Coerência | juiz: fala x formato e horário (F6) |
| Clareza / naturalidade | verificador de oralidade + juiz (F7) |
| Repetição | estruturas repetidas por hora (F8) |
| Operação | silêncio involuntário, cortes, contingências acionadas (F11) |

Métricas de audiência do streaming não entram como critério de aceite: a pesquisa alerta que
desconexão não prova rejeição.

## Portão de qualidade de cada frente

1. `ruff check app tests` sem erros novos.
2. `pytest` completo sem falhas novas em relação à linha de base; cobertura não cai.
3. `vitest run` no painel, se a frente tocou o frontend.
4. `simular_hora.py --modo fake` para os três perfis cumpre os critérios da frente.
5. Juiz de locução (frentes F2–F4, F6–F8, F13): nenhuma dimensão abaixo da linha de base.
6. Documentação: atualizar `docs/plano.md` (seção "O que já está pronto") e o relatório da frente.

## Regras de execução

- Nenhuma chamada a Anthropic, ElevenLabs, Stripe ou WuzAPI reais sem aprovação explícita no chat.
- Migrações seguem o padrão de `app/db/migrations/` e são aditivas (sem apagar colunas).
- Uma branch por frente (`melhoria/f1-relogio` …), commits pequenos, sem push automático.
- Nenhuma fala de exemplo pode transcrever radialista real nem imitar apresentador real.
