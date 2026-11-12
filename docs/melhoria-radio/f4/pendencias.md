# Pendências registradas na F4

Achados e ideias fora do escopo da F4 (promessas, chamadas e participação). Nada aqui foi implementado.

## Decisões (auditoria §10)
- **D1, confirmada pelo usuário em 12/11/2026 (opção A)**, repassada pelo coordenador: o fluxo legado de pedidos
  passa a usar seleção com token e confirmação de reprodução, sem moderação. Implementada no commit `835d8e4`,
  isolado, depois da caracterização do legado de antes (`122d2a3`, C2).
- **Adotadas por padrão, a confirmar** (padrão sugerido pela auditoria):
  - **D2** pedido de música indisponível: "nao_atendido" (Música indisponível) antes da geração, sem o nome no ar;
    o bloco segue como música comum.
  - **D3** promessas só no banco (`promessas_no_ar`), sem Redis.
  - **D4** sem relógio, agenda pelas próximas posições do roteiro (sem sorteio), prazo em posições.
  - **D5** contingência com frase da configuração, pedida no prompt e inserida pelo código se faltar.
  - **D6** regra de promessa em todos os programas (os goldens mudaram uma linha) e linha de agenda quando houver.
  - **D7** espiada de pedido recente mantida, só do legado aberto e só como "chegou uma mensagem".
  - **D8** citar ouvinte já atendido nesta transmissão é permitido sem construção de execução.
  - **D9** promessa para outra edição: só a volta do programa conferida pela grade ("até amanhã"); conteúdo
    prometido para outro dia é violação.
  - **D10** pedido selecionado que some da fala: reescrita pedindo o nome; persistindo, volta para a fila.
  - **D11** prazos em `ConfigPromessas` (`app/live/promessas.py`): imediato 300 s ou 2 posições, curto 900 s ou
    4 posições, "mais tarde" até o fim da ocorrência, tolerância 60 s, reserva da obrigação = máximo da unidade de
    fala (limitado à duração da etapa), teto de 3 promessas abertas; contingência fora do encerramento só se as
    frases somarem até 60% do máximo do orçamento aplicado.
  - **D12** modo por regra: `settings.validacao_promessa_modo` e `validacao_participacao_modo` (`corrigir` padrão).

## Detectores: limites conhecidos
- **Falsos positivos com texto real de LLM não medidos.** Benchmark `casos.json`: promessa 7/7, pedido indevido
  5/5, ouvinte inexistente 1/1, nenhum falso positivo nas outras falas; nas 155 falas das simulações da F3 só os
  casos esperados (injeções, "Rosa Bezerra" indisponível). O texto do dublê é restrito; a rodada `--modo llm` (S4)
  exige aprovação de custo. Até lá, o modo `avisar` existe por regra.
- **Marcadores ambíguos:** "a seguir", "na sequência" e "em seguida" também aparecem fora de promessa ("três
  músicas na sequência"). "amanhã" só conta como promessa quando há construção de volta ou de conteúdo.
- **Nomes com inicial maiúscula em frase de participação:** a primeira palavra da frase nunca é tomada como nome
  (achado da simulação: "Contato de Valdo Cunha"); com isso, "Dona Firmina mandou..." no começo da frase é
  reportado como "Firmina" (a frase sai do mesmo jeito). Título de música com conectivo é coberto pela menção.
- **Promessa de música** fica com a F3 (anúncio sem confirmação); a F4 só não a registra.

## Registro e estado
- **Promessa e contingência marcadas na geração**, não na reprodução (como as etapas do relógio, F1/F3): um bloco
  gerado que não vai ao ar (prewarm descartado, corte, pausa) pode registrar uma promessa que ninguém ouviu ou
  resolvê-la sem a frase no ar. O simulador mede isso (`registradas_sem_ar`, `cumpridas_sem_ar`, contingência fora
  do ar contam como vencidas); a correção é o as-run persistente da F11.
- **Legado selecionado sem confirmação** (painel fechado no meio do bloco) fica "selecionado" até a equipe
  reenfileirar: a expiração por ocorrência (`app.whatsapp.atendimento.expirar`) só cobre o fluxo novo. Sugestão:
  expirar o legado selecionado ao abrir outra ocorrência (F11/F12).
- **Nomes da transmissão** (`_nomes_da_transmissao`): janela de 6 h pela criação do pedido, igual à da sessão; um
  programa mais longo esquece os primeiros pedidos para a regra D8.
- **Agenda sem relógio** não sabe a posição do encerramento (sai pelo horário): o evento existe sem posição e só
  casa por rótulo.
- **Quadro:** o rótulo na agenda e na contingência é a chave de `quadros_fixos`. Nas fixtures do simulador a chave é
  `comentario_quadro` (o nome falado está só em `rotulos_quadros`); programas reais usam o nome do quadro. O
  conteúdo da próxima rotação do quadro não é antecipado.

## Painel e textos
- **Reserva do painel:** `frontend-painel/hooks/useLiveEngine.ts:1358` ainda fala "Seguimos no ar, ja volto com
  mais uma novidade." quando o bloco falha no navegador. É uma promessa sem evento; a F4 só mexeu em tipos no
  painel (regra da frente). Trocar pela reorientação neutra numa frente que mexa no painel.
- **Contingência dentro de um anúncio de música** (contingência vencida que cai num bloco de música do formato
  padrão) soa deslocada; com relógio a música não tem fala e a contingência espera a próxima fala.
- **Pedido recente do legado:** o prompt deixou de citar a música pedida (ela não está confirmada para tocar).

## Segurança e moderação (fora da F4)
- O legado continua sem moderação (F12) e o webhook sem HMAC (auditoria 1): uma mensagem forjada vira pedido "real"
  e vai ao ar. A F4 garante "ouvinte que está na fila", não "ouvinte autêntico".
- A mensagem crua do ouvinte do legado continua entrando no prompt (`_instrucao_reacao_*`): isolamento como dado é
  da F5 (auditoria 3).

## Simulação
- No cenário dedicado (`simulacao/cenario_f4/popular_sertanejo`, três injeções a mais), a identificação de 3-4 s
  com a promessa válida "Daqui a pouco tem mais recado..." fica em 4,55 s (dentro da tolerância de 15%, então o
  encurtamento não age) e o hard time atrasa 2,02 s: estresse do cenário, dentro do critério de 5 s.
- Nas fixtures de linha de base nenhuma promessa chega a ser registrada (a injeção do popular é cortada pelo
  encurtamento ou não tem evento dentro do prazo); cumprimento e contingência são exercitados no cenário dedicado e
  nos testes de rota.
- `--modo llm` e `completo` não rodados (custo).

## Para as próximas frentes
- **F5:** os mesmos arquivos (`validacao_fala.py`, `contexto.py`, `prompt_emissao.py`, `metricas.py`); reaproveitar
  `Violacao`, `MODO_POR_REGRA`/`com_modo` (modo por regra) e o registro em `CHECAGENS_POS_GERACAO`. A contingência de
  "fonte não atualizou" pode usar `Contingencia` e `garantir_contingencia`.
- **F8:** a memória consolidada pode ler `promessas_no_ar` (promessas e contingências da transmissão).
- **F11:** as-run persistente e estado pela reprodução (promessas inclusive); relatório pós-programa no painel.
- **F12:** moderação do legado; convidado real e entrevista (hoje "entrevista" nunca casa como evento).
