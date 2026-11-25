# Avaliação da locução no fim do programa (skill `avaliar-locucao`)

Texto real da Anthropic (`--modo llm --confirmo-custo`, aprovado pelo usuário em 25/11/2026), TTS por dublê
(145 palavras/min), sem relógio (o caminho padrão dos programas), semente 7. Recorte: falas dos últimos 15 minutos.

- Depois: `simulacao/llm/popular_sertanejo/sem_relogio`, `simulacao/llm/musical_adulto/sem_relogio`.
- Antes: linha de base com texto real da H0 (`docs/humanizacao/h0/simulacao/llm/<perfil>`, 23/11/2026). Ela rodou
  **com** o relógio A; sem relógio, antes desta frente, a despedida nem ia ao ar (simulação fake). A comparação de
  texto é de conteúdo, não de mecânica.

## 1. Checagens automáticas

| Métrica | popular antes | popular depois | musical antes | musical depois |
|---|---|---|---|---|
| `fora_orcamento_pct` | 22,2 | **0,0** | 0,0 | 0,0 |
| `estouro_max_pct` | 4,5 | **0,0** | 0,0 | 0,0 |
| `anuncio_sem_confirmacao` | 0 | 0 | 0 | 0 |
| `promessa_vencida` | 0 | 0 | 0 | 0 |
| `pedido_indevido` | 0 | 0 | 0 | 0 |
| `vazamento_grave`, `sinais_ia_*`, `bordao_repetido` | n/a (detector H1/H4 ainda não existe) | n/a | n/a | n/a |
| Despedida no ar | sim | sim | sim | sim |
| Algo cortado no fim | não | não | não | não |
| Termina antes do fim (s) | 15,6 | 31,1 | 42,6 | 38,4 |
| Avisos de reta final | 0 | **1** | 0 | **1** |
| Despedida fora do encerramento | 0 | 0 | 0 | 0 |
| Convite a mandar mensagem nos últimos 10 min | 0 | **1** | 0 | 0 |
| Encerramento diz quando volta | sim ("amanhã, mesma hora", sem dado) | sim ("amanhã, às catorze horas", da grade) | não | sim ("amanhã, às catorze horas") |

Nenhuma reprovação automática.

## 2. Rubrica (1 a 5), falas não musicais dos últimos 15 min

| Dimensão | popular antes (n=4) | popular depois (n=7) | musical antes (n=2) | musical depois (n=4) |
|---|---|---|---|---|
| Clareza | 4,5 | 4,6 | 4,5 | 4,8 |
| Utilidade | 3,5 | 4,0 | 3,5 | 4,3 |
| Coerência (com o fim do programa) | 3,0 | 3,9 | 3,5 | 4,8 |
| Continuidade | 3,3 | 4,0 | 4,0 | 4,8 |
| Naturalidade | 4,0 | 4,1 | 4,0 | 4,5 |
| Precisão | 4,0 | 3,9 | 4,0 | 5,0 |
| Soa como pessoa | 3,8 | 4,1 | 4,0 | 4,5 |

Notas 1–2 e o trecho que as justifica:

- **popular depois, link a 2 min do fim (Coerência 2, Continuidade 2):** depois de "Pra encerrar o Prosa e Viola de
  hoje, … Ipê na Beira da Estrada", o link abre pergunta nova e convida: "quem é a pessoa que sempre aparece quando
  essas toadas tocam. Manda no WhatsApp da rádio, eu gosto de ler esse tipo de história." Causa: a variação sorteada
  do comentário ("convide o ouvinte a responder pelo WhatsApp") entrou também na zona de fechamento.
- **popular antes, comentário a 2 min do fim (Coerência 2):** assunto novo de 58 s ("Tem gente que acha que moda de
  viola é música de ouvir calado…") colado na despedida.

## 3. Piores falas e correção

1. *popular depois, link antes da despedida* — pergunta ao ouvinte e convite ao WhatsApp sem tempo de ler.
   **Corrigido** depois da rodada: na zona de fechamento a variação de comentário não entra, o prompt proíbe pergunta
   e convite, e o link que antecede a despedida recebe "não abra assunto novo; retome algo que já foi ao ar neste
   programa e prepare o fechamento" (`prompt_emissao._reta_final`; teste
   `test_zona_sem_pergunta_nem_formato_de_comentario_e_link_que_retoma_o_programa`). Exemplo de estrutura: "Essa toada
   da beira da estrada fecha uma tarde de viola mansa e recado bonito aqui no Prosa e Viola."
2. *popular depois, chamada a 12 min do fim* — "pode escrever que eu leio com todo carinho por aqui": promessa de
   leitura sem evento agendado. **Corrigido no prompt:** fora da zona, o convite só diz que a rádio recebe as
   mensagens, sem prometer ler, responder ou tocar.
3. *despedidas curtas* — 47,6 s (popular) e 35,2 s (musical) para uma meta de 50 a 60 s; sobra de 31 e 38 s antes do
   horário. **Corrigido no prompt:** o encerramento passa a pedir a faixa de palavras pelo ritmo da voz ("escreva entre
   N e M palavras de fala corrida"), não só segundos.

O que já saiu certo com o texto real: o aviso de reta final uma vez só ("Reta final do Tarde Serena, Rádio Serra
Clara."; "Estamos na reta final do Prosa e Viola"), a última música apresentada como tal só quando era a última
("Pra encerrar o Prosa e Viola de hoje, …"), a despedida retomando o que tocou ("O Sobrado Amarelo deixou a casa
arrumada pra essa despedida. Foi uma tarde de música sem pressa, com a Helena Marés, o Tomás Ribeira…") e a volta com
dia e hora da grade.

## 4. Veredito

**REPROVADO** pela regra da skill (nenhuma dimensão abaixo do antes), só por uma dimensão: popular, Precisão 4,0 → 3,9
(a promessa "eu leio"). Nenhuma reprovação automática; no musical todas as dimensões subiram; no popular as demais
subiram.

As três correções do item 3 foram feitas depois da rodada paga e estão cobertas por teste de prompt, não por nova
rodada com LLM. Para virar APROVADO: repetir `--modo llm` no popular_sertanejo sem relógio (cerca de 29 chamadas,
pedir aprovação de custo) e conferir que o link antes da despedida não pergunta nem convida, que o convite da reta
final não promete leitura e que a despedida chega perto da meta.
