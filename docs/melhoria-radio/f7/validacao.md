# Validação automática da F7 (avaliar-locucao, seção 1)

Data: 20/11/2026. HEAD `73bad8b`. Sem `--modo llm` (sem custo). Script fora do repositório.

## Linha de base

- Comparação com `f6/simulacao/` (`--formato fixture`) e `f5/simulacao/` (`--formato programa`, pré-F6).
- A primeira rodada comparou com a baseline errada (F6 é `fixture`, eu rodei `programa`). Refeita com a baseline certa.

## 1. Métricas automáticas

| Perfil | as_run igual à baseline | Falas | Fora do orçamento | Estouro máx. | Atraso hard time | Anúncio sem confirmação | Promessa vencida | Pedido indevido | Aviso oralidade | Fim antecipado (s) |
|---|---|---|---|---|---|---|---|---|---|---|
| musical_adulto | sim (F5 e F6) | 8 → 8 | 0 → 0 | 0 → 0 | 0 → 0 | 0 → 0 | 0 → 0 | 0 → 0 | null → 0 | 37,44 → 37,44 |
| popular_sertanejo | sim (F5 e F6) | 13 → 13 | 10 → 10 % | 6,4 → 6,4 % | 2,09 → 2,09 s | 0 → 0 | 0 → 0 | 0 → 0 | null → 0 | 33 → 33 |
| variedades_leves | sim (F5 e F6) | 18 → 18 (F5) / 20 → 20 (F6) | 0 → 0 | 0 → 0 | 0 → 0 | 0 → 0 | 0 → 0 | 0 → 0 | null → 0 | 10,44 → 10,44 |

Leitura:
- Nenhuma reprovação automática (`anuncio_sem_confirmacao`, `promessa_vencida`, `pedido_indevido` todos 0).
- Mesmo comportamento que a F6. O popular já fura o orçamento em 10 % e o hard time em 2,09 s, mas isso vem da F6, não da F7.
- `aviso_oralidade` passou de null para 0. Motivo: o verificador agora existe. Nas falas do dublê não há nenhum aviso, então o número não mede nada sobre oralidade.
- A redução de 50 % de avisos não se mede aqui. O dublê devolve falas fixas sem avisos, e a reescrita não dispara.

## 2. Rubrica (notas 1 a 5)

Não aplicada. As falas são o banco fixo do dublê, não saída de LLM. Notar o texto do dublê mediria o dublê, não a F7. O mesmo motivo que deixou a rubrica de fora da F4 (ver `f4/avaliacao.md`).

## 3. Piores falas

Não aplicável: sem rubrica, não há nota para ordenar.

## 4. Veredito

**INCONCLUSIVO.** Sem reprovação automática. A rubrica e a comparação com fala real de LLM não foram feitas. O aceite do plano (juiz ≥ 4/5 e redução ≥ 50 %) continua pendente de `--modo llm` com aprovação de custo.
