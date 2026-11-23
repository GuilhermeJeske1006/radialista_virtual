# Linha de base da humanizacao (H0)

Branch `melhoria/h0-humanizacao`, HEAD `3cabff7`. Data: 2026-11-23.

## Ambiente
- Python 3.12.13 (`backend/.venv`), ffmpeg 8.0.1.

## Ruff (`ruff check app tests`)
- Sem avisos (All checks passed). `scripts/validar_melhorias_voz.py` tem erros pre-existentes fora do escopo do CI (nao reexecutado).

## Pytest (`--cov=app`)
- 2511 passaram, 1 falhou, 3 puladas (923,86 s).
- Falha: `tests/test_live_router_duracao.py::test_tts_com_perfil_mede_devolve_cabecalho_e_grava_ritmo`
  (`assert (1, 24.0, 'abertura') == (1, 24, 'padrao')`). Ja existia no `371b786` (mesma falha reproduzida em worktree temporario).
- Cobertura total: 89% (18226 linhas, 2041 nao cobertas).

| Pacote | Modulos (cobertura) |
|---|---|
| app/live | router 96%, relogio 96%, contexto 99%, formatos 99%, validacao_fala 97%, oralidade 99%, orcamento 97%, promessas 97%, music 77%, prewarm 79%, spotify 80%, demais 91-100% |
| app/llm | client 77%, config_generator 64%, economia 89%, noticias 95%, prompt_builder 97%, demais 100% |
| app/topics | pipeline 31%, matcher 85%, reserva 84%, derivador 95%, espelho 96%, pauta_conversa 99%, router 97%, fontes 92-96% |
| app/tts | cache 90%, client 91%, router 93%, profiles 95%, quality 94%, voices 97%, glossario 100% |
| app/whatsapp | gestao 68%, locks 67%, central 74%, worker 77%, inbox 82%, atendimento 86%, transmissao 87%, webhook 87%, demais 89-100% |

## Simulacao fake (`simular_hora.py --modo fake`, sem rede)

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
| llm (chamadas) | 7 | 11 | 23 |
| fim_antecipado_s | 37.44 | 4.44 | 2.08 |

Avisos nos logs: musical_adulto (musica citada sem faixa, pedido sem resultado na busca); popular_sertanejo (`live_orcamento_excedido` identificacao 11/8 palavras, pedido sem resultado na busca).

## Metricas novas da H0 (detector ausente)
| Metrica | Valor |
|---|---|
| vazamento_grave | None |
| sinais_ia_media | None |
| sinais_ia_p90 | None (nao impressa no resumo) |
| bordao_repetido | None (nao impressa no resumo) |

## Linha de base LLM
Pendente, aguardando confirmacao de custo.
