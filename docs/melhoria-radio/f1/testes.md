# F1 - Portão de qualidade (testes)

Branch melhoria/f1-relogio. Verificação sem alterar código.

## Comandos e resultados
- ruff check app tests scripts/simular_hora.py scripts/simulacao: All checks passed.
- pytest -q --cov=app: 1209 passed, 1 failed (8m34s). Cobertura total 86% (F0: 85%). F0 tinha 1142 testes.
  - FALHA: tests/test_simular_hora.py::test_sem_relogio_inicio_previsto_nao_muda_as_run (teste novo da F1, não existia na baseline).
    Mensagem de erro não foi capturada (saída do pytest truncada por tail). Reexecutado isolado: tests/test_simular_hora.py 28 passed (3m47s).
    Indício de teste instável na suíte completa (ordem/estado compartilhado/tempo); arquivo provável: backend/tests/test_simular_hora.py ou backend/scripts/simulacao.
  - Cobertura por pasta: app/live/relogio.py 96%, router.py 93%, music.py 77%, prewarm.py 85%; app/llm 58% (config_generator) a 100%; app/topics pipeline.py 31%, demais 84-100%; app/tts 90-100%; app/whatsapp gestao.py 63%, demais 82-100%.
- Simulação fake (relógio padrão / --relogio-backend nenhum), saída em scratchpad sim/f1/<perfil>[/nenhum]:
  - musical_adulto (A): fixture hard_times_perdidos=0, atraso_hard_time_s=0.0, estouro_fim_s=0.0, falas_abaixo_minimo=0, encerramento_no_ar=True | nenhum: hard_times_perdidos=3, estouro 1.0
  - popular_sertanejo (A): fixture 0 perdidos, atraso 0.0, falas_abaixo_minimo=0 | nenhum: 3 perdidos
  - variedades_leves (C): fixture 0 perdidos, atraso 0.0, falas_abaixo_minimo=0 | nenhum: 3 perdidos, fora_orcamento_pct 4.0
- as_run sem relógio vs F0 (docs/melhoria-radio/f0/simulacao): igual ignorando commit/tempo e campos novos aditivos (duracao_prevista_backend_s, inicio_previsto_s, relogio); único campo extra no topo: relogio_backend=null.
- Testes preexistentes: git diff melhoria/f0-bancada...HEAD --stat: só adições em tests (test_live_prewarm.py +14, sem remoção de asserts); novos test_config_relogio, test_live_relogio, test_live_relogio_proxima, test_relogio_migracao, test_simular_hora. Fixtures de relógios (A/B/C) foram alteradas (dados, não testes).
- Painel: npm test 56 arquivos, 318 passed (F0: 300); npx tsc --noEmit sem erros; npm run lint falha ("Invalid project directory .../lint"), já falhava na baseline, não conta.

## Critérios F1
- Hard time atrasado > 5 s: nenhum (OK). Fala abaixo do mínimo: 0 (OK). Sem relógio igual à F0: OK. Testes preexistentes intactos: OK.
- Pendência: falha do teste novo na suíte completa, não reproduzida isolado.

VERMELHO

## Rodada 2 (HEAD 87859df, após a correção do RNG)

- `ruff check app tests scripts/simular_hora.py scripts/simulacao`: limpo.
- `pytest -q --cov=app`: 1211 passed, 0 failed, cobertura 86% (298,8 s). A falha da rodada 1
  (`test_sem_relogio_inicio_previsto_nao_muda_as_run`) não reapareceu.
- Simulação fake com relógio, 3 perfis: hard_times_perdidos 0, atraso 0,0 s, falas_abaixo_minimo 0.
  Fim antecipado: musical_adulto 7,23 s; popular_sertanejo 5,78 s; variedades_leves 13,78 s.
- `--relogio-backend nenhum`: 3 hard times perdidos por perfil, como na F0. `as_run` idêntico a
  `f1/simulacao/<perfil>/sem_relogio/` (referência corrigida), ignorando commit/tempo.
- Contra a F0: popular_sertanejo e variedades_leves idênticos. O `musical_adulto` da F0 foi gravado
  com o `random` global contaminado pela thread do Sentry (segundos cortados 146,1 na F0 x 100,1
  corrigido; eventos divergem a partir do 7). Referência válida: `f1/simulacao/musical_adulto/sem_relogio/`.
- Painel sem mudança desde a rodada 1: vitest 318 passed, `tsc --noEmit` ok; `npm run lint` quebrado
  desde a linha de base.

VERDE
