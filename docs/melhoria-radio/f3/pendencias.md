# Pendências registradas na F3

Achados e ideias fora do escopo da F3 (estado confiável da emissão). Nada aqui foi implementado.

## Decisões adotadas (padrão sugerido pela auditoria, §8)
- **D1** `app/live/prompt_emissao.py::montar_prompt(ctx)`; `app/llm/prompt_builder.montar_system_prompt` (WhatsApp)
  intacto, chamado uma vez em `montar_contexto` e entregue pronto em `ctx.prompt_base`.
- **D2** Remediação: reescrita única (V1) e remoção da frase (V2). Modo em `settings.validacao_musica_modo`
  (`corrigir` padrão, `avisar` só registra).
- **D3** Sem pré-reserva da próxima faixa: bloco de fala não anuncia faixa nova (o validador remove).
- **D4** Citadas em bloco de fala com relógio continuam resolvidas com teto; as descartadas saem da fala.
- **D5** Redis fora: rate limit falha **fechado** (503) nas rotas públicas de autenticação (`auth_login`,
  `auth_register`, `auth_esqueci_senha`, `auth_redefinir_senha`) e aberto no resto.
- **D6** Goldens de `/proxima` (`tests/fixtures/caracterizacao_proxima/`) ficam como caracterização permanente.

## Validador: limites conhecidos
- **Falsos positivos com texto real de LLM não medidos.** Os 70 rótulos do benchmark e os as-runs do modo fake
  dão 7/7 e 0 falsos positivos, mas o protótipo pode estar ajustado demais a eles. Medir no `--modo llm` (só com
  aprovação de custo) antes de considerar o modo `corrigir` validado em produção; até lá o modo `avisar` existe.
- **Títulos conhecidos (camada a) em produção** saem de `musicas_permitidas`, das músicas pedidas na fila e das
  linhas do histórico do painel. O histórico de 48 h da rádio (`MusicaHistorico`) ficou de fora: os títulos do
  YouTube vêm como "Artista - Título (Clipe)" e só são úteis normalizados, para confirmar, não para detectar.
- **Remoção de frase pode deixar emenda solta** ("E essa..."). A reserva neutra só cobre a fala vazia. O as-run
  registra `validacao_fala.acao`; medir quantas falas foram removidas ou neutralizadas no `--modo llm`.
- **Fragmento abaixo do mínimo:** a regra só vale para fala que o encurtamento ou o validador alteraram e com
  orçamento aplicado (relógio ou formato musical). Fala curta escrita assim pelo LLM continua indo ao ar.

## Redis
- **Fora desta frente:** deduplicação e travas do WhatsApp (`app/whatsapp/locks.py`, `inbox.py`, webhook) usam o
  cliente cru. Com o `socket_timeout` falham em até 1 s em vez de travar, mas sem o disjuntor cada mensagem ainda
  espera o timeout. Também ficam com o cliente cru `app/topics/matcher.py`, `topics/reserva.py`,
  `live/song_service.py`, `live/spotify.py`, `live/audio_analysis.py`, `llm/noticias.py` e `prewarm.py`.
- **Rate limit aberto no ao vivo durante a queda** (D5): `/proxima` e `/tts` ficam sem teto enquanto o Redis não
  volta. É a troca de segurança aceita; o login fecha.

## Painel antigo (cadeia de horário no servidor)
- A estimativa supõe a antecedência 2 do painel atual. Outro cliente sem `inicio_previsto` seria mal estimado; o
  limite superior (`inicio_previsto_max_s`) e o log `relogio_inicio_previsto_estimado` contêm o erro e medem
  quantos painéis antigos seguem no ar.
- O painel antigo verifica o início agendado a cada 15 s: no ar, o hard time 00:00 pode atrasar até 15 s; o
  simulador não reproduz isso.

## Para as próximas frentes
- **F4:** registrar promessas em `Chamadas.promessas` e a checagem em `CHECAGENS_POS_GERACAO`
  (`app/live/validacao_fala.py`); o relógio (`ctx.tempo.plano`) dá os eventos. Trocar o detector provisório de
  promessa de `scripts/simulacao/metricas.py`.
- **F5:** preencher `ContextoEmissao.dados` em `montar_contexto`, registrar `checar_fala` em
  `CHECAGENS_POS_GERACAO` com um adaptador e reaproveitar `Violacao`, `remover_frases` e `fala_reserva_neutra`.
  O bloco de dados vai para `prompt_emissao.montar_prompt`. A F5 regrava os goldens com o diff revisado.
- **F8:** a memória da sessão (`_historico_falas`, `_ultimo_tom`, temas, fio condutor) segue no router e chega ao
  contexto pelas portas; consolidar em `app/live/memoria.py`.
- **F11:** `musica-substituta` sem o teto do relógio; estado das etapas marcado na geração (não na reprodução).
- **Refatoração §5:** as portas (`app/live/portas.py`) usam ligação tardia nos nomes do router para não quebrar os
  patches dos testes. Quando os testes passarem a injetar portas falsas, a ligação tardia pode sair.
