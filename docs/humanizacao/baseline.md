# Linha de base da humanizacao (H0)

Branch `melhoria/h0-humanizacao`, HEAD `cbbafcb` + alteracoes nao commitadas desta rodada (ver "Alteracoes desde o HEAD").
Data: 2026-11-23.

## Ambiente
- Python 3.12.13 (`backend/.venv`), ffmpeg 8.0.1. anthropic 0.110.0 na venv (fora do `requirements.txt`, que pede `>=0.75.0`).
- pydantic 2.10.4 (pinado). A falha de schema que travou a rodada LLM anterior NAO era do pydantic: era o freezegun
  trocando `datetime.datetime` durante o `freeze_time`. Corrigido em `scripts/simular_hora.py::_aquecer_schemas_anthropic`.

## Alteracoes desde o HEAD
- `app/live/formatos.py`: funcao `abertura` do formato musical proibe promessa de retorno (opcao 1 da abertura fora da unidade).
- `scripts/simulacao/dubles.py`: `_EspiaoTexto` registra a direcao do formato no canal lateral (medicao 0% nos modos pagos).
- `scripts/simular_hora.py`: aquecimento dos schemas do SDK antes do `freeze_time`.
- Testes atualizados: `tests/test_live_formatos.py`, `tests/test_live_orcamento.py`,
  `tests/fixtures/formatos/musical_adulto__abertura_primeira.txt` (regravado com `ATUALIZAR_GOLDEN=1`),
  `tests/test_simular_hora.py` (regressoes do freezegun e do espiao).

## Ruff (`ruff check app tests`)
- Sem avisos (All checks passed). `scripts/validar_melhorias_voz.py` tem erros pre-existentes fora do escopo do CI.

## Pytest (`--cov=app`)
- Rodada completa desta versao: 2512 passaram, 1 falhou, 3 puladas (830 s). Depois dela, a unica correcao foi
  a expectativa de `tests/test_live_orcamento.py` (`abertura`), reexecutada e verde (179 passam em
  `test_live_orcamento.py` + `test_live_formatos.py`).
- Falha pre-existente: `tests/test_live_router_duracao.py::test_tts_com_perfil_mede_devolve_cabecalho_e_grava_ritmo`
  (`assert (1, 24.0, 'abertura') == (1, 24, 'padrao')`). Ja existia no `371b786`.
- Cobertura total: 89% (18226 linhas, 2041 nao cobertas), igual ao HEAD.

| Pacote | Modulos (cobertura) |
|---|---|
| app/live | router 96%, relogio 96%, contexto 99%, formatos 99%, validacao_fala 97%, oralidade 99%, orcamento 97%, promessas 97%, music 77%, prewarm 79%, spotify 80%, demais 91-100% |
| app/llm | client 77%, config_generator 64%, economia 89%, noticias 95%, prompt_builder 97%, demais 100% |
| app/topics | pipeline 31%, matcher 85%, reserva 84%, derivador 95%, espelho 96%, pauta_conversa 99%, router 97%, fontes 92-96% |
| app/tts | cache 90%, client 91%, router 93%, profiles 95%, quality 94%, voices 97%, glossario 100% |
| app/whatsapp | gestao 68%, locks 67%, central 74%, worker 77%, inbox 82%, atendimento 86%, transmissao 87%, webhook 87%, demais 89-100% |

## Simulacao fake (`simular_hora.py --modo fake`, sem rede, sem custo)

Rodada final desta versao. Os valores batem com a rodada do HEAD `cbbafcb`: nenhuma regressao nas metricas de
musica, promessa, pedido, dado ou orcamento.

| Metrica | musical_adulto | popular_sertanejo | variedades_leves |
|---|---|---|---|
| relogio | A | A | C |
| encerramento_no_ar | True | True | True |
| hard_times_perdidos | 0 | 0 | 0 |
| atraso_hard_time_s | 0.0 | 0.36 | 0.0 |
| anuncio_sem_confirmacao | 0 | 0 | 0 |
| promessa_vencida | 0 | 0 | 0 |
| pedido_indevido | 0 | 0 | 0 |
| fora_orcamento_pct | 0.0 | 0.0 | 0.0 |
| llm (chamadas, fake) | 7 | 11 | 23 |
| fim_antecipado_s | 37.44 | 4.44 | 2.08 |
| coerencia_automatica | False | True | True |

Avisos: musical_adulto reprova `falas_fora_da_unidade` no fake (abertura de 1 de 6 falas, 16,7% contra limite de 5%).
Esse achado ja existia antes das alteracoes desta rodada (rodada fake anterior ao prompt novo). Vem do duble fake, nao do
LLM: no modo LLM a abertura ficou dentro da unidade (ver abaixo).

## Metricas novas da H0 (detector ausente)
| Metrica | Valor |
|---|---|
| vazamento_grave | None |
| sinais_ia_media | None |
| sinais_ia_p90 | None (nao impressa no resumo) |
| bordao_repetido | None (nao impressa no resumo) |

O detector de sinais de IA ainda nao existe (H1 em diante). Essas quatro metricas ficam None ate la.

## Linha de base LLM (`--modo llm`, aprovada pelo usuario, com estimativa)

Rodada final por perfil. Musical: rodada apos a correcao do espiao e a mudanca do prompt da abertura.
Popular e variedades: rodada apos a correcao do espiao (o bug so afetava a medicao de direcao de formato, e esses
perfis sao `padrao`, sem direcao); antes da mudanca do prompt, que so tocou o musical.

| Metrica | musical_adulto | popular_sertanejo | variedades_leves |
|---|---|---|---|
| relogio | A | A | C |
| encerramento_no_ar | True | True | True |
| hard_times_perdidos | 0 | 0 | 0 |
| atraso_hard_time_s | 0.0 | 3.74 | 0.0 |
| anuncio_sem_confirmacao | 0 | 0 | 0 |
| promessa_vencida | 0 | 0 | 0 |
| promessa_sem_registro | 0 | 0 | 0 |
| pedido_indevido | 0 | 0 | 1 |
| ouvinte_inexistente | 0 | 0 | 0 |
| fora_orcamento_pct | 0.0 | 22.2 | 5.0 |
| estouro_max_pct | 0.0 | 4.5 | 7.6 |
| fim_antecipado_s | 42.61 | 15.63 | 7.02 |
| falas_fora_da_unidade_pct | 0.0 | 0.0 | 0.0 |
| instrucao_no_prompt_pct | 100.0 | n/a (padrao) | n/a (padrao) |
| coerencia_automatica | True | True | True |
| chamadas LLM (total) | 7 | 11 | 27 |
| revisoes | 1 | 2 | 7 |
| ajustes de fala (nenhum / reescrita) | 5 / 1 | 9 / 0 | 17 / 3 |
| truncamentos por max_tokens (aparados) | 0 | 0 | 13 |

Leitura:
- `fora_orcamento_pct` (popular 22,2%) e `falas_fora_da_unidade_pct` (0%) medem coisas diferentes: o primeiro conta
  blocos fora do orcamento do relogio; o segundo, falas fora da unidade do papel do formato. O popular e `padrao`, sem
  unidade de formato, entao o segundo nao se aplica. Ver pendencia.
- Variedades teve 13 truncamentos por `max_tokens`; cada um foi aparado na ultima frase completa. Sinal para revisar o teto
  de tokens do perfil antes de H4.
- Musical: a abertura da rodada com o bug (34 palavras, 14,1 s, fora da unidade) virou 53 palavras e 21,9 s na rodada
  final. Uma amostra com semente 7. Nao prova estabilidade.

Custo real desta rodada (chamadas LLM das rodadas que entram na linha de base e nas tentativas que a precederam):
- Rodada dos tres perfis: 46 chamadas (8 + 11 + 27).
- Rodada do musical apos a correcao do espiao: 8 chamadas.
- Rodada do musical apos a mudanca do prompt: 7 chamadas.
- Tentativas anteriores que falharam (erro de schema, antes do diagnostico): pelo menos 7 chamadas pagas sem resultado.
- Total aproximado: 68 chamadas pagas nesta frente. O painel da Anthropic e a referencia do valor em dolar.

## Pendencias que afetam a linha de base
- Abertura musical abaixo do minimo: aceita e registrada em `docs/humanizacao/h0/pendencias.md`. A mudanca de prompt
  (opcao 1) resolveu a ocorrencia na amostra; nao ha medicao de estabilidade.
- `falas_fora_da_unidade` no fake do musical: vem do duble, nao do LLM. Decidir se o duble deve gerar abertura dentro da unidade.
- `coerencia_automatica` do popular e do variedades: `padrao` sem unidade de formato; o item passa por vacuidade.
- Teste pre-existente `test_live_router_duracao`: nao e da H0.
