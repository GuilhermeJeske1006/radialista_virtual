# Pendências registradas na F1

Achados e ideias fora do escopo da F1 (relógio, espelho e hard time). Nada aqui foi implementado.

## Decisões a confirmar com o usuário
- **D4 — `inicio_previsto` só vale com relógio.** Programas sem relógio continuam decidindo o encerramento por
  `now()`, e o encerramento deles segue sendo gerado dois blocos antes e cortado (simulação `sem_relogio`).
  Estender o horário previsto a eles resolveria isso, mas muda o comportamento atual.
- **D7 (nova) — intervalo sem patrocinador vira música.** Sem patrocinador citado na sequência, a etapa de intervalo
  do relógio vira janela de música ajustável e deixa de ser hard time (`dispensado` na simulação). Alternativa: tocar
  uma reserva comercial ou vinheta institucional no horário.
- **D8 (nova) — fechamento longo.** Em B e C o fechamento tem 2 min; a unidade de encerramento é de 15 a 45 s. O espelho
  divide a etapa: um resumo (20 a 90 s, mantém o hard time) e o encerramento nos últimos 45 s.

## Para as próximas frentes
- **F2:** medir o áudio final contra a estimativa (`relogio_fala_acima_do_espaco` hoje só registra log) e calibrar o
  wpm por voz; a origem do wpm é `ConfigRelogio.wpm`, usada por `app.live.orcamento.estimar_duracao_s`.
- **F3:** o estado das etapas é marcado na geração, não na reprodução (mesma fragilidade do registro de músicas): pular
  ou pausar deixa a etapa marcada. Confirmar pelo as-run.
- **F3:** painel antigo em cache (sem `inicio_previsto`) com programa de relógio decide com `now()`, dois blocos antes:
  na simulação `popular_sertanejo/sem_inicio_previsto` os hard times atrasam até 412 s e o encerramento é cortado.
  Avaliar aviso de versão do painel ou recarga forçada.
- **F3:** música citada numa fala fora do bloco de música e descartada por falta de espaço já foi registrada como tocada
  em `_musicas_citadas_na_fala` (`relogio_musica_citada_sem_espaco`). Com relógio o prompt pede para não citar música.
- **F3:** `musica-substituta` troca a faixa na hora de tocar sem saber o espaço restante; hoje só o desvio medido corrige.
- **F3/F6:** seleção de faixa por duração-alvo (catálogo com duração conhecida) para fechar a janela antes do hard time.
  Hoje são até 3 buscas por bloco (custo de cota do YouTube) e, quando nada cabe com espaço acima de 90 s, o compromisso
  começa mais cedo com log `relogio_adiantamento_acima_do_maximo`.
- **F4:** pedido de música numa etapa de música só é aceito com espaço ≥ 330 s; a faixa pedida não passa pelo teto
  (log `relogio_pedido_acima_do_espaco`). Teases a partir dos eventos agendados do relógio também ficam para a F4.
- **F5:** o relógio B só é útil com fontes de notícia: sem fonte, as etapas de notícia, serviço e atualização viram música.
- **F6:** unidades de fala por tipo de evento e o relógio personalizado completo (editar tipo, natureza e hard time, não
  só a duração) no catálogo de formatos. Relógio de rede ancorado na hora cheia (D1).
- **F12/F13:** entrevista do B sem convidado real usa a contingência "conteúdo aprovado"; multivoz na conversa do C só
  recebe a meta de duração no prompt.
- `_marco_tempo_programa` e `_ajuste_energia_meio_programa` ainda usam `now()` (precisão de minuto) mesmo com relógio.
- Com relógio, `ia_pode_adicionar_blocos` e vinhetas da sequência sem papel deixam de valer (o editor avisa).

## Fora do escopo (auditoria transversal)
- N+1 no prewarm (`docs/auditoria.md`, item 7): `prewarm.executar_tick` consulta conta e programas por radialista.
  A F1 só passou `inicio_previsto`.
- Timeout do Redis (item 6): o estado das etapas falha aberto, mas sem `socket_timeout` uma queda ainda trava a chamada.

## Bancada
- Os catálogos fictícios têm faixas de 187 a 285 s; fim antecipado e adiantamentos da simulação dependem disso. O dublê
  da busca passou a respeitar `duracao_max_segundos` como preferência, como `buscar_musica`.
- O dublê do LLM decide "primeira fala" por `total_falas == 0`; com vinheta de abertura antes, a abertura usa o modelo de
  reabertura (cosmético, não muda tempo).
- `simular()` mantém `relogio_backend="nenhum"` como padrão para os testes da F0; o CLI usa `fixture`.
