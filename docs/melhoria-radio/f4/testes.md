# F4 - Testes e portão local (branch melhoria/f4-promessas)

## Ordem seguida
1. **Módulos puros com testes** (commits `b1a35de`, `cb1d7e5`, `9ed9152`, `0639ef0`): detector de promessas, agenda
   e casamento; detector de participação; tabela `promessas_no_ar` com migração e exclusões; relógio com
   `Plano.seguintes` e obrigações. Comportamento igual: os 28 goldens de `/proxima` intactos. A grade de planos do
   relógio sem obrigação foi gravada no código anterior à mudança (`tests/fixtures/relogio_planos_sem_obrigacao.json`).
2. **Mudanças de comportamento em commits próprios**, cada um com o teste novo vermelho antes do código e a suíte
   inteira verde antes de entrar: checagens e registro (`5f591b6`), cumprimento e contingência (`30ddc8f`), D2
   (`b70144b`), espiada do legado D7 (`81943cf`), caracterização do legado C2 (`122d2a3`) seguida da D1 isolada
   (`835d8e4`, asserções do C2 invertidas), textos de prompt (`4281825`), simulador (`b216d65`) e a correção de um
   falso positivo achado na simulação (`4153bf3`).
3. **Painel:** só tipos opcionais (`93a438c`).

## Testes novos
| Arquivo | O que cobre (auditoria §8) |
|---|---|
| `tests/test_live_promessas.py` | U1 detector (classes, tipo, acento, uma por frase, "toca agora" não conta, continuidade, "até amanhã"); U2 agenda do relógio (retorno de 27:00 no A, intervalo sem patrocínio, entrevista fora, noticioso só com fonte, quadro); U3 agenda do roteiro (popular, musical, zero sorteio com espião, `ia_pode_adicionar_blocos`, igual ao roteiro do router); U4 casamento (segundos, posições, rótulo, conteúdo, tipo, cancelado, intervalo, música, volta pela grade, teto); textos de contingência sem nova promessa; **U6 casos.json: 7/7, 0 falso positivo em 63** |
| `tests/test_live_participacao.py` | U7 regras (selecionado, em fila, não atendido, desconhecido, simulada, exclusões, partes de música, D8, D7, contenção, primeira palavra da frase); U8 corte de oração "e (também) para" só na participação; D10; **casos.json: pedido indevido 5/5, ouvinte inexistente 1/1, 0 falso positivo** |
| `tests/test_promessas_repo.py` | U10 registro idempotente, abertas, obrigações, resolução com `with_for_update`, vencimento, log sem nome nem trecho, chave sem relógio; U11 migração aditiva e idempotente; I14 exclusão de programa e de radialista apagam `promessas_no_ar` |
| `tests/test_live_relogio_obrigacoes.py` | U9 grade dos presets A, B e C igual sem obrigação; seguintes sem as concluídas; obrigação reserva a unidade e encolhe a música; etapa prometida pulada gera log |
| `tests/test_live_promessas_proxima.py` | I1 registro com relógio; I2 reescrita com a agenda e remoção, no máximo 2 LLM; continuidade e "até amanhã" livres; modo avisar; I7 sem relógio por posição; I8 "toca agora" só com o selecionado; I9 só a oração do ouvinte inexistente sai; I10 mensagem simulada vira reserva neutra; D10 nos dois fluxos; I15 contrato; I17 Redis fora; I18 multivoz |
| `tests/test_live_promessas_cumprimento.py` | I3 cumpre com pedido; I4 contingência garantida pelo código e sem duplicar; I5 obrigação no backtiming pela rota; I6 vencida antes do alvo e encerramento resolve todas; outra ocorrência vence; I16 transmissão recomeçada; U12 inserção e encurtamento |
| `tests/test_live_pedido_indisponivel.py` | I11 (D2) legado e fluxo novo: "nao_atendido" antes da geração, nome fora do prompt e da fala, padrão anuncia a automática, musical vira só música, sem `pedido_id` |
| `tests/test_live_espiada_legado.py` | I13 (D7) a espiada ignora o fluxo novo em revisão e os fechados; continua vendo o legado aberto |
| `tests/test_live_pedido_legado.py` | C2 e depois I12 (D1): seleção com token sem `atendido`, confirmação executado/falhou/interrompido, token e rádio do programa, selecionado não volta a ser escolhido nem espiado nem conta como fila, reenfileirar volta a `em_fila` |
| `tests/test_live_prompt_promessas.py` | U13 regra geral, linha de agenda com e sem relógio, encerramento sem agenda, música sem faixa, pedido recente, reserva do multivoz |
| `tests/test_simulacao_f4.py` | S1 três perfis × quatro variantes; S2 cenário dedicado; S3 métricas com os detectores do backend |
| Goldens novos em `tests/test_live_proxima_caracterizacao.py` | `relogio_a_retorno_cumpre`, `relogio_a_retorno_contingencia`, `promessa_vencida_sem_relogio` |

## Goldens regravados (diff revisado no próprio commit)
- `b70144b` (D2): `pedido_sem_resultado` (fila `nao_atendido`, sem a linha do pedido no prompt, o nome sai e o bloco
  vira só música).
- `835d8e4` (D1): `pedido_legado`, `chamada_abraco`, `chamada_sorteio`, `chamada_recorrente`,
  `chamada_recorrente_dias`, `musical_musica_pedido`, `relogio_a_retorno_cumpre` (fila `selecionado`, atendido falso,
  campos `pedido_*` na resposta) e `pedido_sem_resultado` (só o atendido).
- `4281825` (textos): os 31 (linha da regra de promessa; a linha de música sem faixa em todo bloco sem faixa; a linha
  de agenda onde há o que chamar; `comentario_pedido_recente` no texto da espiada).

## Testes existentes editados de propósito
- `test_simular_hora::test_injecoes_aparecem_nas_metricas` (`5f591b6`): `promessa_vencida >= 1` passou a `== 0` com
  `injecao_promessa >= 1`; `ouvinte_inexistente >= 1` passou a `== 0` com `injecao_cita_ouvinte >= 1`.
- `test_live_router::test_pedido_musica_sem_resultado_cai_para_escolha_automatica` (`b70144b`, `835d8e4`): estado
  `nao_atendido` e motivo; com a D1, `atendido` falso.
- `test_live_router::test_pedido_de_sorteio_nao_confirma_inscricao_sem_registro` (`835d8e4`): selecionado com token.
- `test_simular_hora::test_pedido_fluxo_legado_atendido_antes_de_tocar` virou
  `test_pedido_fluxo_legado_confirma_depois_de_tocar` (`835d8e4`).
- `test_live_pedido_legado.py` (`835d8e4`): as asserções do C2 invertidas.
- `test_live_prompt_emissao::test_modulos_extraidos_nao_importam_o_router`: `promessas` e `participacao` na lista.

## Portão local
- `ruff check app tests scripts/simular_hora.py scripts/simulacao`: All checks passed.
- `pytest -q`: **1515 passed** (1379 da F3 + 136 novos), 387 s. Cada commit de comportamento rodou a suíte inteira
  verde antes de entrar.
- Painel (só `lib/liveTypes.ts`): `npm test` **318 passed**; `npx tsc --noEmit` sem erros.
- Simulação `--modo fake` com dublê de TTS a 145 palavras/min nos três perfis, nas variantes da F3: com relógio
  (padrão do CLI), `--relogio-backend nenhum` (`sem_relogio/`), `--wpm-real 120` (`voz_120/`) e
  `--sem-inicio-previsto` (`sem_inicio_previsto/`), em `docs/melhoria-radio/f4/simulacao/<perfil>/`; mais o cenário
  dedicado (S2) em `simulacao/cenario_f4/` (popular e musical com relógio e injeções extras). 1,4 a 5,7 s por rodada,
  zero rede. Modos `llm` e `completo` não rodados (custo).

## Simulação: F3 → F4
F3 medido de novo com o detector de participação da F4 sobre os as-runs gravados da F3 (o total bate com o detector
da F0). "Legado" é a parcela que só existia porque o pedido legado era consumido na seleção (`historico_legado`).

| Rodada (musical / popular / variedades) | F3 | F4 |
|---|---|---|
| Promessa vencida: relógio / sem relógio / voz 120 / painel antigo | 0/0/0, 0/1/0, 0/1/0, 0/1/0 | **0 em todas** |
| Promessa sem registro | — | 0 em todas |
| Pedido indevido, total (relógio / sem relógio / voz 120 / painel antigo) | 1/1/3, 1/1/4, 1/1/3, 1/1/3 | **0 em todas** |
| ... dos quais só pelo legado | 1/0/2, 1/0/3, 1/0/2, 1/0/2 | 0 em todas |
| Ouvinte inexistente no ar | 0/0/1 nas quatro | **0 em todas** |
| Atendido antes de tocar | 1/0/2, 1/0/3, 1/0/2, 1/0/2 | 0 em todas |
| Anúncio sem confirmação | 0 em todas | 0 em todas |
| Atraso máximo em hard time (s): relógio / sem relógio / voz 120 / painel antigo | 0/0,36/0,18; 0/0/0; 0/12,1/0; 0/0/0,18 | 0/0,36/0; 0/0/0; 0/12,1/0; 0/0/0 |
| Fora do orçamento (%): relógio / voz 120 | 0/0/0; 0/0/14,3 | 0/0/0; 0/0/6,7 |
| LLM máximo por fala | 2 (1 no popular, painel antigo) | 2 em todas |
| Sínteses máximas por fala | 1 | 1 |

O que aconteceu com cada injeção e pedido nas rodadas F4:
- **Popular, "Daqui a pouco tem mais recado de ouvinte por aqui."** Sem relógio, voz 120 e painel antigo: sem
  chamada de ouvinte no prazo, reescrita com a agenda e removida (`promessa_sem_evento`). Com relógio: o encurtamento
  da identificação cortou a frase e entrou a reorientação neutra (como na F3).
- **Variedades, "Um abraço também para Dona Firmina."** Removida nas quatro (`ouvinte_nao_autorizado`).
- **Pedidos:** "Rosa Bezerra" (popular, indisponível) e "Joana Lis" (musical com relógio, indisponível) viram
  `nao_atendido` antes da geração e o nome não vai ao ar (D2). "Paulo Brandão" e "Cida Morais" (variedades,
  legado; também "Seu Afonso" sem relógio) são selecionados com token e confirmados pelo player depois de tocar (D1).
- **Cenário dedicado (S2):** popular, a promessa "Mais tarde a gente lê os recados de ouvinte." (fala 2) e a da
  fixture são cumpridas no retorno de 27:00 com o recado do Seu Ditinho; "Daqui a pouco tem receita de bolo." e a
  mensagem inventada saem. Musical, "Mais tarde a gente lê os recados por aqui." vira a contingência "Ainda não chegou
  recado para ler agora; o WhatsApp da Rádio Serra Clara segue aberto." no retorno sem abraço na fila, e ela vai ao
  ar. 0 vencida nos dois. No popular dedicado, a identificação com a promessa válida passa 13% do máximo (dentro da
  tolerância) e o hard time atrasa 2,02 s (critério: 5 s).

## Critérios de aceite
| Critério | Resultado |
|---|---|
| 0 promessas vencidas sem fala de contingência (três perfis, fake) | 0 nas 12 rodadas e no cenário dedicado; contingência no ar quando o conteúdo cai (S2) |
| 0 pedidos anunciados como "toca agora" fora do estado correto | 0 nas 12 rodadas, inclusive a parcela do legado (D1) |
| Nenhuma fala cita ouvinte inexistente | 0 nas 12 rodadas |
| Simulador usa os detectores do backend | `metricas` delega a `app.live.promessas` e `app.live.participacao` (S3) |
| F1-F3 não pioram | hard time ≤ 5 s com relógio e painel antigo, encerramento no ar, 0% fora do orçamento com relógio, ≤ 2 LLM e 1 síntese por fala; voz 120 e sem relógio iguais ou melhores que na F3 |
| Goldens de `/proxima` | 28 iguais nos commits de extração; 3 novos; regravados só nos commits previstos |
