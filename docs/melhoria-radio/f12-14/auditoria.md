# F12–F14 — Expansão (status parcial)

Branch `melhoria/f12-14-expansao`, base `melhoria/f11-producao`.

## F12 — Autonomia graduada e revisão humana

| Item | Estado | Motivo |
|---|---|---|
| Roteamento por categoria (`automatico` / `revisao` / `proibido`) | **feito (função pura)** | `app/live/roteamento_revisao.py`: rota por categoria (plantão, repórter, entrevista), tema delicado no texto e tópico proibido de `Programa.topicos_proibidos`. Estado inicial: `no_ar`, `aguardando_revisao` ou `bloqueado`. |
| Estado `aguardando_revisao` gravado e aprovado no painel | **não feito** | Precisa de coluna de estado no bloco, endpoint de aprovação e tela. Não fiz sem decisão: quem aprova (operador ou responsável por programa), e o que acontece com a fala aprovada depois do horário. |
| Integração ao router ao vivo | **não feito** | Depende da decisão acima. Hoje a rota é calculada só pela função. |

Decisões pedidas: 1) a lista de temas delicados é fixa no código ou por rádio? 2) quem aprova e em quanto tempo (se o bloco
passa do horário, o que vai ao ar)?

## F13 — Bancada com múltiplas personas

**Estado:** multivoz existe (`_sintetizar_falas_multivoz` em `app/live/router.py`, `ParticipantePrograma` em
`app/llm/prompt_builder.py`). **Não feito:** papéis (mediador, comentarista, contraponto), turnos que respondem ao anterior
e tempo total dentro do relógio. O aceite (juiz "resposta ao que acabou de ser dito" ≥ 4/5) exige `--modo llm` com
aprovação de custo.

Decisões pedidas: 1) os papéis são fixos ou configuráveis por programa? 2) a resposta ao turno anterior vem do prompt
(LLM) ou de regra de código?

## F14 — Narrativos, especiais e cortes

**Estado:** nada implementado. Quadro narrativo (personagem → situação → mudança → consequência) é conteúdo editorial, e a
marcação de cortes depende do as-run log (F11, item 1), que ainda não existe.

Decisões pedidas: 1) o narrativo entra como categoria nova ou como quadro fixo de `Programa.quadros_fixos`? 2) cortes são
marcados só depois do as-run persistente (F11 item 1) ou dá para marcar antes?
