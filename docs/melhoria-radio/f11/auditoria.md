# F11 — Produção antes, durante e depois (status parcial)

Branch `melhoria/f11-producao`, base `melhoria/f10-direcao-som`.

| Item | Estado | Motivo |
|---|---|---|
| 1. As-run log persistente do que foi ao ar | **não feito, precisa de decisão de desenho** | Gravar o que *foi ao ar* exige um ponto de confirmação de reprodução no player (hoje o backend entrega o áudio e o player toca). Falta decidir: gravar no envio da fala, na confirmação do player, ou nas duas? E tabela nova (aditiva) com quais campos: fala, música, vinheta, patrocinador, pedido, promessa. |
| 2. Relatório pós-programa | **feito (função pura)** | `app/live/relatorio_programa.py::montar_relatorio`: promessas (cumpridas, vencidas, canceladas), orçamento, avisos de oralidade, pedidos, repetição de estrutura e hard time; alertas para críticos; sugestões de continuidade por regra. Sem endpoint nem tela no painel ainda. |
| 3. Contingência automática com peça de reserva aprovada | **não feito, precisa de decisão de produto** | O plano pede convidado, fonte, pedido, áudio e estouro com peça de reserva *aprovada*. Falta decidir: quem aprova a peça (operador antes do programa, ou um catálogo pré-aprovado), e onde a peça fica (tabela nova ou `Programa.quadros_fixos`). Hoje só existe a reorientação neutra (F4) e a contingência de promessa. |

## Decisões pedidas

1. Item 1: o ponto de "foi ao ar" é a confirmação do player ou o envio da fala? Aceita uma tabela nova `as_run_eventos`?
2. Item 2: o relatório entra no painel como endpoint + tela? (hoje é só a função).
3. Item 3: peça de reserva é aprovada por operador (antes do programa) ou por um catálogo fixo aprovado uma vez?
