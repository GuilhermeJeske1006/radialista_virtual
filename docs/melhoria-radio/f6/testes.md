# F6 - Testes e portão local (branch melhoria/f6-formatos)

## Passo 0: linha de base na ponta da branch

Confirmada (não refeita) em 13/11/2026 no worktree `locufy-radio`, HEAD `5987eda` (só acrescenta a auditoria da F6 a
`3f9ab88`, que só acrescenta documentação ao portão da F5 em `d6bc878`). É contra esta linha de base, e não contra
`linha_de_base/`, que a F6 compara (auditoria §3 e C6).

| Item | Resultado |
|---|---|
| `ruff check app tests scripts/simular_hora.py scripts/simulacao` | All checks passed |
| `pytest --collect-only -q` | **1904 testes coletados** (o portão da F5 registrou 1901 passed, 3 skipped) |
| Python | 3.12.13 (`backend/.venv`) |

### Simulação fake: 12 rodadas contra `docs/melhoria-radio/f5/simulacao/`

Arranjo de `tests/test_simulacao_f5.py` (3 perfis × {relógio da fixture, `sem_relogio`, `voz_120`,
`sem_inicio_previsto`}), pelo CLI, dublê de TTS a 145 palavras/min, `PYTHONHASHSEED=0`, zero rede:

```
cd backend && PYTHONPATH=. PYTHONHASHSEED=0 .venv/bin/python scripts/simular_hora.py --modo fake \
    --programa <perfil> [--relogio-backend nenhum | --wpm-real 120 | --sem-inicio-previsto] --saida <scratchpad>
```

| Perfil | Relógio | Sem relógio | Voz 120 | Painel antigo |
|---|---|---|---|---|
| `musical_adulto` | igual | igual | igual | igual |
| `popular_sertanejo` | igual | igual | igual | igual |
| `variedades_leves` | igual | igual | igual | igual |

- **`as_run.json`: 12 de 12 idênticos byte a byte** aos gravados em `f5/simulacao/<perfil>/[<variante>/]`
  (`cmp`), com o registro de dados da F5 (sem tirar `dados`/`dado_legitimo`). Código de saída 0 em todas.
- `resumo.json`: iguais campo a campo, exceto `config.commit` (`6bcc0b3` → `5987eda`) e `tempo_execucao_s` (ruído).

A linha de base da F5 vale na ponta da branch: nada a refazer.

## Leva 1 (commits 0 a 4 do §7)

| Commit | O que mudou | Goldens / simulação |
|---|---|---|
| `f0ec447` | passo 0 (acima) | — |
| `2157e2b` | caracterização C2–C5, gravada no código anterior ao catálogo | 0 regravados |
| `c84afc4` | `app/live/formatos.py` (padrao, musical_adulto + alias, sete futuros); flags no lugar do booleano | 34 goldens e C2–C5 idênticos; 12 simulações byte a byte iguais |
| `8222790` | item 9: TTL e teto do cache de categoria | goldens idênticos |
| `2308549` | contrato (`perfil_programacao: str`, 422 em português, resposta tolerante), `GET /config/formatos`, gerador | goldens idênticos |

Testes primeiro em cada commit; os novos falharam pelo motivo certo antes do código (módulo inexistente, alias
tratado como padrão, settings ausentes, `Literal` antigo).

### Testes novos
| Arquivo | Testes | O que cobre (auditoria §8) |
|---|---|---|
| `tests/test_live_formatos_caracterizacao.py` | 6 | C2 (roteiro do router e puro, posições 0–20, cinco estruturas, `ultima_categoria`, sorteio fixado; `roteiro_base`), C3 (A/B/C × padrão/musical × duas peças × duas execuções, a cada 7 s), C4 (`orcamento_para`, 17 tipos × primeira × seis tetos), C5 |
| `tests/test_live_formatos.py` | 93 | U1, U2, U3 (tabela do fato 2, item a item), U4 (musical/padrão/alias/quadro/tabelas derivadas), U5, U7 (grade C3 com `formato=`, preenchimento pela flag, D8), U8 (padrão/musical, alias, D17 e D23 pela flag), D12, U9 e risco 1 (`"musical_companhia"` só em `formatos.py`/`formato.py`) |
| `tests/test_live_formatos_integracao.py` | 6 | I3 (os 3 goldens musicais com `musical_adulto` dão o mesmo retrato) e I9 |
| `tests/test_live_cache_categoria.py` | 4 | U10 |
| `tests/test_config_formatos.py` | 20 | I8, I10 e U12 |
| `tests/test_live_prompt_emissao.py` | +1 | U9 (`formatos` na lista de pureza) |

Testes existentes editados de propósito: `test_config_router.py::test_perfil_musical_persiste_e_rejeita_valor_desconhecido`
(aceita `musical_adulto`; `inexistente` continua 422).

### Fim da leva (HEAD `2308549`)
| Item | Linha de base | Leva 1 |
|---|---|---|
| `ruff check app tests scripts/simular_hora.py scripts/simulacao` | All checks passed | All checks passed |
| `pytest -q` | 1901 passed, 3 skipped (1904) | **2031 passed, 3 skipped** (2034, +130), 546 s |
| 12 simulações fake contra `f5/simulacao/` | — | `as_run.json` 12/12 idênticos byte a byte; `resumo.json` só com `config.commit` e `tempo_execucao_s` diferentes |

## Leva 2 (commits 5 a 8 do §7)

| Commit | O que mudou | Goldens / simulação |
|---|---|---|
| `8ebecc0` | seção `_formato(ctx)` no prompt (promessa, público, participação, temas, reorientação); papel `quadro` só pelo quadro fixo | 3 goldens musicais regravados (só as linhas da seção); 31 do `padrao` idênticos; 12 simulações idênticas |
| `67e4c46` | `popular_sertanejo` e `variedades_leves` no catálogo; quadro fixo no orçamento e na direção; gerador (uso, dica, exemplo) | 0 goldens existentes alterados; 6 novos; 22 snapshots das instruções; 12 simulações idênticas |
| `7cb526e` | `--formato`, referência do catálogo, canal lateral e injeções do dublê, `formatos.coerencia`, `resumo.json["formato"]`, log `live_formato_aviso` | goldens idênticos; 12 simulações `programa` byte a byte |
| `913fc19` | 13 casos F6 no benchmark e as chaves novas em `regras.esperado` | — |

Testes primeiro em cada commit; os novos falharam pelo motivo certo antes do código (`_formato` inexistente, formatos
fora do catálogo e `KeyError`, snapshots e goldens ausentes, `FalaNoAr` inexistente, `formato` desconhecido em
`simular`, log ausente, chaves da F6 ausentes em `regras.esperado`).

### Testes novos
| Arquivo | Testes | O que cobre (auditoria §8) |
|---|---|---|
| `tests/test_live_formatos_prompt.py` (novo) | 30 | Seção do formato (D10): linhas do musical, reorientação só nos papéis do catálogo (retomada, identificação, retorno, quadro fixo; o nome "Quadro…" não faz quadro), público só quando preenchido, nada no `padrao`, alias = canônico, posição antes da direção, retorno pelo patrocinador ou pela etapa; `_duracao` dos novos com e sem relógio e a linha de agenda da F4; `contexto(...)` montado à mão |
| `tests/test_live_formatos_snapshot.py` (novo) | 38 | **U6 (aceite do plano):** 22 snapshots `tests/fixtures/formatos/<formato>__<papel>.txt` (3 formatos × 7 papéis e o quadro do variedades); para o mesmo papel, os três textos distintos dois a dois e só com o próprio cabeçalho; nada no `padrao` |
| `tests/test_live_formatos.py` | +66 (159) | U1 (tabela do §6.4 dos novos, roteiros, blocos do relógio, temas e participação), U3 (flags dos novos), U4 (aplicados com fonte `formato`, quadro só com `quadro=True`, tabelas derivadas com os quatro), U5 (meta que o dublê lê, condução, regra de promessa, sem "4 a 6 frases" nem nome próprio; meta sem palavras; o mesmo papel dirigido diferente), U7 (popular no link de A → comentário 20–35 e recado 20–60 no retorno; variedades no quadro de C; relógio efetivo distinto dois a dois), U8 (roteiro vazio de cada formato, abertura depois do intervalo nos novos e igual no padrão, blocos extras pela flag do programa) |
| `tests/test_live_formatos_integracao.py` | +14 (20) | I1 (popular sem relógio: direção no system, `orcamento_fala_s` 20–60 aplicado, `duracao_alvo_segundos`, uma reescrita), I2 (quadro do variedades 60–180 e sem convite; convite na chamada; popular convida fora da chamada), I5 (popular com A no link, variedades com C no quadro), I6 (multivoz nos novos, não no musical), I7 (painel antigo), golden do canônico = do alias, D21 (log sem trecho e fala intacta; nada no `padrao`) |
| `tests/test_live_formatos_coerencia.py` (novo) | 33 | U11: tolerância = a do orçamento, palavras para todo tema do catálogo, limites do musical; positivo e negativo de `fora_da_unidade` (com fala reduzida pelo relógio e o `padrao` fora), `bloco_fora_do_formato`, `convite_fora_da_politica` (detecção e política), `tema_revisao`, `reorientacao` (com memória); avisos sem trecho; `coerencia()` dentro e fora de cada item; banco do dublê e fixtures sem tema de revisão; registro do convite do banco do quadro; benchmark (100% dos positivos, nenhum falso positivo nos 48 casos) |
| `tests/test_simulacao_f6.py` (novo) | 36 | S1 (= C6, 12 rodadas `programa` byte a byte com `f5/simulacao`; `formato=None` = `programa`; id inválido recusado), S2 (12 rodadas `fixture` com os herdados e a coerência, valores medidos fora do limite registrados; o que fecha nas 12; CLI), S3 (alias = canônico, com e sem relógio), S4 (instrução 100% nos três e 0 no `padrao`; relógio efetivo e orçamentos distintos no as-run), S5 (espião: `metricas` delega a `formatos.coerencia`), S6 (`debate_longo` e `convite` no musical, `tema_revisao` no popular: detectados e no ar) |
| `tests/test_config_formatos.py` | +6 (26) | U12 (uso de cada formato, exemplo sertanejo em `popular_sertanejo`, dica `sertaneja`/`popular_mix`), I8 com os quatro ids, rota com os novos |
| `tests/test_live_relogio.py` | +6 (41) | Nenhum plano abaixo do mínimo nos presets A, B e C com `popular_sertanejo` e `variedades_leves` |
| `tests/test_live_proxima_caracterizacao.py` | +6 (41) | Goldens novos (abaixo) |

### Testes existentes editados de propósito
- `test_live_formatos.py::test_u1_implementados_e_futuros` e `::test_u4_tabelas_de_orcamento_derivadas_do_catalogo`:
  os quatro implementados e `FORMATOS_APLICADOS` = {musical_adulto, musical_companhia, popular_sertanejo,
  variedades_leves}.
- `test_config_formatos.py::test_i8_aceitos_sao_os_implementados_e_os_aliases` e
  `::test_u12_prompt_do_gerador_lista_os_formatos_implementados` (a linha do JSON com os quatro valores).
- `test_live_relogio.py::test_u11_nenhum_plano_com_orcamento_abaixo_do_minimo`: o parametrize ganhou os dois formatos
  (os seis casos de antes com os mesmos ids) e `_planejar` aceita o id do formato.
- `test_simular_hora.py::test_casos_de_avaliacao_cobrem_as_regras`: `regras.esperado` com as chaves da F6, que só os
  casos da F6 rotulam; positivo e negativo para cada chave.
- `test_live_participacao.py::test_u7_benchmark_participacao`, `test_live_validacao_fala.py::test_casos_benchmark_musica`,
  `test_dados_checagem.py::test_benchmark_casos_json` e `test_live_promessas.py::test_u6_benchmark_promessas`: o total
  de falas passa de 70 para 96 (os acertos e os falsos de cada detector não mudaram).

### Goldens
- **Regravados (commit 5):** `musical_retomada_com_excesso` (+5 linhas em cada uma das duas chamadas ao LLM),
  `musical_identificacao` (+5) e `musical_musica_pedido` (+4: sem a reorientação). Só linhas novas antes da direção do
  formato: programa/formato/promessa, "A promessa do formato prevalece sobre o perfil do horário.", participação,
  temas que exigem revisão e, na retomada e na identificação, "Reoriente quem acabou de chegar: nome do programa e da
  rádio em uma frase.". Resposta, Redis, banco, sorteios, buscas e temas iguais.
- **Novos (commit 6):** `formato_popular_comentario` (20–60 s aplicado, roteiro do popular na posição 4),
  `formato_popular_chamada_recado` (recado real, 20–60 s), `formato_popular_relogio_a_link` (comentário 20–35 no link
  de A), `formato_variedades_quadro` (quadro fixo 60–180 s, reorientação, sem convite),
  `formato_variedades_relogio_c_quadro` (quadro de 44:00 do relógio C, 60–180 s) e `formato_musical_adulto_identificacao`
  (igual a `musical_identificacao`, exceto o nome do cenário).
- **Sem mudança:** os outros 31.

### Fim da leva (HEAD `913fc19`)
| Item | Leva 1 | Leva 2 |
|---|---|---|
| `ruff check app tests scripts/simular_hora.py scripts/simulacao` | All checks passed | All checks passed |
| `pytest -q` | 2031 passed, 3 skipped | **2266 passed, 3 skipped** (2269, +235), 769 s |
| 12 simulações `--formato programa` contra `f5/simulacao/` | `as_run.json` 12/12 byte a byte | `as_run.json` 12/12 byte a byte; `resumo.json` com `config.commit`, `tempo_execucao_s` diferentes e as chaves novas `config.formato`, `config.perfil_programacao` e `formato` |
| 12 simulações `--formato fixture` | — | gravadas em `f6/simulacao/<perfil>/[<variante>/]`, código de saída 0, 0 tentativas de rede |

### Coerência medida (fake, `--formato fixture`) ao lado da linha de base do §3 da auditoria
`f6/simulacao/<perfil>/[<variante>/]resumo.json`, bloco `formato`. "Itens fora" e as hipóteses estão em
`pendencias.md` ("Limites do §9 medidos na primeira rodada"). Linha de base (§3, F5 com `programa`, só relógio e sem
relógio): fala no ar em % da hora, maior trecho só de música e maior intervalo sem reorientação.

| Perfil / variante | Falas | `fala_pct` (faixa) | §3 % | Fora da unidade | Maior seq. musical (§3) | Interrupções/h | Reorientações | Maior intervalo sem reorientação (limite) (§3) | Convites (fora) | Temas | Instrução | `coerencia_automatica` | Itens fora | `fora_orcamento_pct` | Atraso hard time |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| musical / relógio A | 6 | 1,9% (1–8) | 1,9% | 1 (16,7%) | 1166 s (1166) | 6 | 6 | 1175 s (1350) (1175) | 1 (0) | 0 | 100% | não | unidade | 0 | 0 s |
| musical / sem relógio | 8 | 2,0% (1–8) | 2,0% | 1 (12,5%) | 552 s (552) | 8 | 7 | 586 s (1350) (586) | 0 (0) | 0 | 100% | não | unidade | 0 | — |
| musical / voz 120 | 6 | 2,2% (1–8) | — | 0 | 1194 s | 6 | 6 | 1205 s (1350) | 1 (0) | 0 | 100% | sim | — | 0 | 0 s |
| musical / painel antigo | 6 | 1,9% (1–8) | — | 1 (16,7%) | 1166 s | 6 | 6 | 1175 s (1350) | 1 (0) | 0 | 100% | não | unidade | 0 | 0 s |
| popular / relógio A | 10 | 8,0% (4–20) | 6,8% | 0 | 842 s (775) | 10 | 5 | 1742 s (1800) (1612) | 0 (0) | 0 | 100% | sim | — | 10 | 2,09 s |
| popular / sem relógio | 23 | 17,9% (4–20) | 18,1% | 0 | 282 s (282) | 23 | 4 | 1197 s (1800) (3600) | 1 (0) | 0 | 100% | sim | — | 0 | — |
| popular / voz 120 | 9 | 8,3% (4–20) | — | 0 | 775 s | 9 | 4 | 3052 s (1800) | 0 (0) | 0 | 100% | não | reorientação | 11,1 | 11,1 s |
| popular / painel antigo | 10 | 8,0% (4–20) | — | 0 | 842 s | 10 | 5 | 1740 s (1800) | 0 (0) | 0 | 100% | sim | — | 10 | 0,02 s |
| variedades / relógio C | 20 | 24,5% (15–45) | 31,9% | 0 | 944 s (778) | 20 | 4 | 3467 s (1350) (3459) | 2 (2) | 0 | 100% | não | convite, reorientação | 0 | 0 s |
| variedades / sem relógio | 26 | 30,6% (15–45) | 35,7% | 0 | 274 s (274) | 26 | 5 | 1088 s (1350) (1159) | 4 (3) | 0 | 100% | não | convite | 0 | — |
| variedades / voz 120 | 19 | 30,8% (15–45) | — | 0 | 737 s | 19 | 4 | 3472 s (1350) | 3 (3) | 0 | 100% | não | convite, reorientação | 0 | 0 s |
| variedades / painel antigo | 20 | 24,5% (15–45) | — | 0 | 944 s | 20 | 4 | 3467 s (1350) | 2 (2) | 0 | 100% | não | convite, reorientação | 0 | 0 s |

Em todas: nenhum bloco fora do formato, nenhum tema de revisão no ar, instrução de outro formato 0, no máximo 2 LLM e 1
síntese por fala, anúncio sem confirmação, promessa vencida, pedido indevido, ouvinte inexistente e dado sem fonte ou
vencido em 0. O encerramento foi ao ar em todas as variantes com relógio.

## Leva 3 (commit 9 do §7: painel)

Só `frontend-painel/`; o backend não mudou desde `913fc19`.

| Commit | O que mudou | Testes |
|---|---|---|
| `3ba3ed0` | `lib/types.ts` (`perfil_programacao: string`, `FormatoPrograma`); `lib/formatoPrograma.ts` com `formatoDe`, `definicaoDoFormato`, `ehMusical`, `roteiroDoFormato`, `blocosExtrasDoFormato`, `formatosImplementados`, `catalogoFormatos`; espelho estrutural dos quatro implementados; `tipoMusical` com o roteiro do formato | `lib/__tests__/formatoPrograma.test.ts` (novo, 16) e `lib/__tests__/formatosFixtures.ts` (cópia de `GET /config/formatos`) |
| `3fb469d` | `ProximosBlocosPanel`: ciclo por `ehMusical`, roteiro do formato com a estrutura vazia, aviso de blocos extras pela flag do formato (D23); lê a rota e cai no espelho | `ProximosBlocosPanel.test.tsx` +5 (14): musical pelo alias e pelo canônico, popular e variedades vazios e personalizados, lista da rota prevalece |
| `f1a05d4` | `gerarFalaLocal` exportada: `ehMusical`, tipo pela regra do motor (estrutura em loop ou abertura + roteiro do formato por n-1), reorientação neutra em toda fala (D22) | `hooks/__tests__/gerarFalaLocal.test.ts` (novo, 6) |
| `bbe3d9f` | `EditarProgramaForm`: select pelo catálogo, textos do formato, "Usar relógio sugerido", "Usar sequência sugerida", checkbox pela flag do formato, aviso de valor fora do catálogo, cartão "Identidade da rádio" e seção "Identidade do programa" (D16) | `EditarProgramaForm.test.tsx` +8 (17): opções só implementadas com "Livre" primeiro, musical pelo canônico, popular com relógio A aplicado uma vez, "Livre" sem sugestões, alias preservado ao salvar (D2), troca grava o canônico, valor desconhecido avisado e preservado, identidade separada, sem rádio configurada |

Testes primeiro em cada commit; os novos falharam pelo motivo certo antes do código (exports ausentes em
`formatoPrograma.ts`, `musical_adulto` tratado como não musical na prévia, `gerarFalaLocal` não exportada, select
com duas opções fixas e sem as seções de identidade).

### Fim da leva (HEAD `bbe3d9f`, 16/11/2026)
| Item | Leva 2 | Leva 3 |
|---|---|---|
| `npx vitest run` | 354 | **389** (+35) |
| `npx tsc --noEmit` | ok | ok |
| `npm run lint` | falha preexistente (F0) | falha preexistente (F0) |
| `grep musical_companhia` fora de `lib/formatoPrograma.ts` (código de produção) | 3 arquivos | só o comentário de `lib/types.ts` |
| Backend (`ruff`, `pytest -q`, simulações) | ruff limpo; 2266 passed, 3 skipped; 12 + 12 rodadas | iguais: nenhum arquivo do backend mudou |

Não conferido: o formulário no navegador (a validação visual do painel precisa do backend e do banco de pé).
