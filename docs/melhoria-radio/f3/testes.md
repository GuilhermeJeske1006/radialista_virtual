# F3 - Testes e portão local (branch melhoria/f3-contexto-emissao)

## Ordem seguida
1. **Caracterização antes de mover código** (commit `3edddaf`): 28 cenários de `POST /proxima` em
   `backend/tests/test_live_proxima_caracterizacao.py`, com o system e a mensagem inteiros de cada chamada ao
   LLM, a resposta, o Redis, as linhas do banco e a sequência de sorteios
   (`backend/tests/fixtures/caracterizacao_proxima/`). Mais o digest da simulação (três perfis, com e sem
   relógio, dublê de TTS). Os goldens passaram a usar um RNG próprio por cenário (`bdda108`, regravados no
   código original `3edddaf`: a thread do Sentry consumia o `random` global na suíte inteira).
2. **Extração sem mudar comportamento** (`2ac1497`, `d3e268a`): goldens e digest idênticos, testes existentes
   sem edição.
3. **Mudanças de comportamento em commits próprios**, com teste novo vermelho antes do código:
   validador (`1d73585`), citadas (`c0eaa55`), Redis, cadeia do painel antigo.

## Testes novos
| Arquivo | O que cobre (auditoria §6) |
|---|---|
| `tests/test_live_proxima_caracterizacao.py` | C1: retrato de 28 cenários (permanente, D6) |
| `tests/test_live_portas.py` | ligação tardia das portas nos nomes do router |
| `tests/test_live_prompt_emissao.py` | U1/U2: módulos extraídos não importam o router; `montar_prompt` puro (Redis e `random` proibidos) e igual ao texto da rota; tocadas do histórico; pedido em fila não aprovado |
| `tests/test_live_validacao_fala.py` | U3/U4/U5: duas ordens, marcadores, nomes da rádio e ouvintes, "Evidencias" × "C&X - Evidencias", camadas a/b/c, fase "pre", `remover_frases`, fala vazia, multivoz, fragmento abaixo do mínimo, checagem extra registrada; **casos.json: 7/7 e 0 falsos positivos em 70 falas** |
| `tests/test_live_validacao_proxima.py` | I1, I2, I3, I4, I5, I9 pela rota; modo `avisar`; fragmento do momento C |
| `tests/test_simulacao_f3.py` | S1 (três perfis com relógio e dublê de TTS: `anuncio_sem_confirmacao == 0`, `validacao_fala` no as-run) e S3 (métricas sem detector próprio) |
| `tests/test_redis_client.py` | U7/I6: timeouts no `from_url`, `seguro`, disjuntor, rate limit fechado nas rotas públicas de autenticação e aberto no resto, `/proxima` e `/tts` com o Redis fora |
| `tests/test_live_cadeia_painel_antigo.py` | U6/I7/I8: cadeia vazia, um elo, reancoragem, vinheta fora da antecedência, limites, Redis fora, três pedidos sem o campo, primeiro elo do preparo antecipado |

## Testes existentes editados (mudança intencional, não extração)
- `tests/test_simular_hora.py::test_injecoes_aparecem_nas_metricas`: conferia `anuncio_sem_confirmacao >= 1` no
  musical (a injeção ia ao ar). Agora confere que a injeção aconteceu (`injecao_cita_musica >= 1`), que o
  validador a tirou (`validacao_fala.regras.musica_nao_confirmada >= 1`) e que o anúncio não foi ao ar (`== 0`).
- `tests/test_live_relogio_proxima.py::test_i1_i11_...`: o cliente sem `inicio_previsto` valia "agora"; desde a
  F3 o horário dele sai da cadeia de blocos (`origem_instante == "estimado"`).
- `tests/test_simulacao_caracterizacao_f3.py` (C2, criado nesta frente) saiu no commit do validador, como a
  auditoria previa: a F0 pede não travar o as-run de forma permanente.

## Portão local
- `ruff check app tests scripts/simular_hora.py scripts/simulacao`: All checks passed.
- `pytest -q`: **1379 passed** (1280 de antes + 99 novos), 327 s. Cada commit da frente rodou a suíte inteira
  verde antes de entrar.
- Painel (só `lib/liveTypes.ts`, tipos opcionais `validacao_fala` e `relogio.origem_instante`): `npm test`
  **318 passed**; `npx tsc --noEmit` sem erros.
- Simulação `--modo fake` com dublê de TTS a 145 palavras/min, nos três perfis: com relógio (padrão do CLI),
  `--relogio-backend nenhum` (`sem_relogio/`), `--wpm-real 120` (`voz_120/`) e `--sem-inicio-previsto`
  (`sem_inicio_previsto/`), em `docs/melhoria-radio/f3/simulacao/<perfil>/`. 1,5 a 5,5 s por rodada, zero rede.
  Modos `llm` e `completo` não rodados (custo).

## Critérios de aceite
| Critério | Resultado |
|---|---|
| Caracterização de `/proxima` verde | 28 goldens; idênticos na extração; 3 regravados de propósito no passo 9 |
| Validador pega 100% de "música anunciada sem confirmação" em `casos.json` sem falso positivo | 7/7, 0 FP em 63 |
| Simulador importa o mesmo detector de `app/live` | `metricas.mencoes`/`titulos_citados` delegam a `validacao_fala.mencoes_musica` (teste S3) |
| `anuncio_sem_confirmacao == 0` nos três perfis (fake) | 0 em relógio, sem relógio, voz 120 e painel antigo |
| Critérios da F1/F2 mantidos | hard time ≤ 5 s (máx. 0,36 s com relógio), encerramento no ar, 0% fora do orçamento com relógio, ≤ 2 LLM e ≤ 2 sínteses por fala |
| Painel antigo (S2) | atraso ≤ 5 s, encerramento no ar, 0 s cortados nos três perfis |
| `gerar_proxima_fala` < 250 linhas | 1245 → 115 |
