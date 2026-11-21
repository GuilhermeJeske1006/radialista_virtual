# Pendências registradas na F5

Achados e ideias fora do escopo da F5 (fontes, validade e dados verificáveis). Nada aqui foi implementado.

## Decisões (auditoria §11), todas adotadas pelo padrão, a confirmar
- **D1** bloco de dados na mensagem (papel user). **D2** JSON com cabeçalho fixo, `ensure_ascii=False`.
- **D3** entram no bloco: pauta, escalada, correção, apuração web, pauta de assunto, clima, mensagem do ouvinte (legado e
  fluxo novo) e contexto da faixa; nome do ouvinte e título/artista da faixa seguem inline, saneados.
- **D4** vencido no prompt só o clima, com o horário, até 3 h de idade; o resto é omitido.
- **D5** última leitura do clima retida 3 h no Redis de sessão; validade da leitura 60 min a partir da observação.
- **D6** detector: temperatura, tempo lá fora, previsão, trânsito (sujeito e predicado), placar (com contexto esportivo)
  e comercial. Agenda fora.
- **D7** `settings.validacao_dados_modo` para as duas regras, `corrigir`.
- **D8** fonte citada no ar: o prompt pede (clima: "o serviço de meteorologia"); o validador não exige.
- **D9** apuração web atribui a quem informou o fato, nunca ao veículo.
- **D10** textos que convidavam dado sem integração editados e a linha de regra geral em todo programa. Os textos do
  perfil das 9h às 11h e de segunda e sexta ficam em `_contexto_atual`, que o WhatsApp também usa: o WhatsApp recebe o
  mesmo texto mais seguro (o clima do WhatsApp não mudou).
- **D11** curadoria com isolamento, descarte determinístico e retificação limpa (a retificação que era só ordem não
  marca a notícia como retificada).
- **D12** agenda pela data do evento, em commit isolado (`f7dc1b2`); a seleção da pauta usa a mesma regra, então evento
  que já acabou deixa de virar pauta (consulta a mais por chamada: o fuso da rádio do programa).
- **D13** sem migração. **D14** fixtures de linha de base intocadas. **D15** `nome_seguro` em `PedidoRef` e nos nomes
  da fila e da transmissão. **D16** reserva do painel neutra. **D17** cobertura extra pelos textos da rádio, mais o
  contexto da faixa (decisão minha: é texto que já vai ao prompt como citável; a mensagem do ouvinte não cobre).
- **D18** contagem dobrada corrigida no simulador: os números de `validacao_fala.regras` relatados na F3 e na F4 eram
  o dobro em toda remoção (fase pre e final). Ex.: no popular sem relógio, `promessa_sem_evento` 2 → 1.

## Detector e validador: limites conhecidos
- **Falsos positivos com texto real de LLM não medidos** (S4 exige `--modo llm`, aprovação de custo). Benchmark
  `casos.json`: `dado_sem_fonte` 6/6 e `dado_vencido` 1/1, nenhum falso positivo nas outras 63 falas; nenhum achado nas
  falas gravadas da linha de base. O texto do dublê é restrito. Até a rodada real, o modo `avisar` existe.
- **Conversa de tempo sem número** ("Faz frio de manhã cedo, né?") vira `dado_sem_fonte`: a regra pede dado para
  "tempo lá fora". Se o LLM real falar assim com frequência, avaliar uma lista de expressões de conversa isentas.
- **Cobertura por tipo é larga:** qualquer dado de trânsito, aviso ou serviço válido cobre qualquer afirmação de
  trânsito do bloco, e qualquer clima válido cobre "o céu está limpo" mesmo se o dado diz "nublado". Conferir a
  condição contra o texto do dado é a próxima melhoria.
- **Radical da cobertura** (achado da simulação, corrigido em `3fcb872`): o radical curto casava palavra comum. O
  vocabulário de cobertura e o radical continuam heurísticos.
- **Encurtamento separa horário e valor** (risco da auditoria): se o horário ficar numa frase e o valor na seguinte, a
  segunda vira `dado_vencido` e sai. Aceito pela §10 (omitir é permitido).
- **Idade máxima só na afirmação "de momento"**: temperatura e tempo sempre; trânsito só na condição (parado, lento,
  congestionado), não na obra ou interdição; placar só no jogo em andamento. Achado do benchmark (f7): uma obra
  anunciada de manhã não pode virar "dado vencido" à tarde.
- **A apuração web é texto de LLM**: uma ordem pode sobreviver ao resumo; a limpeza e o validador são a rede.
- **Agenda não é detectada na fala** (D6): datas de evento dependem da validade do dado no bloco e das regras de evento
  do prompt.

## Prompt e contexto
- **Pauta escolhida que não pode ir ao bloco** (sem fonte, ou nada sobrou da limpeza) vira "sem notícia" no prompt, mas
  continua registrada em `noticia_historico` como lida (o registro é da F3/F4). Um título que é só injeção, portanto,
  some da fila sem ir ao ar: comportamento desejado, mas sem aviso ao operador.
- **Correção com retificação vazia depois da limpeza**: o worker já não marca; uma correção antiga gravada antes da
  F5 com texto cru continua passando pela limpeza no bloco.
- **`gerarFalaLocal` do painel** (`hooks/useLiveEngine.ts:159-196`) ainda tem frases com promessa e lacuna ("Ja volto
  com mais", "assim que a fonte confirmar eu trago certinho"). Só vai ao ar sem a reserva gravada e com voz
  disponível; trocar por texto neutro numa frente que mexa no painel (F11).
- **Histórico do painel** no prompt continua cru (D3): é texto que o próprio sistema gerou, mas inclui linhas de
  música com título vindo do YouTube.

## Fora da F5 (não mexido de propósito)
- **WhatsApp reaproveita a fala confirmada por 30 min** (`app/whatsapp/transmissao.py:54-73`) sem a validade dos dados
  que ela citou: um clima dito às 14h pode ser repetido às 14h25 como atual. Levar a validade junto da fala ou cortar
  dados do contexto público.
- **Webhook sem HMAC** (auditoria 1): uma mensagem forjada no legado vai ao ar como recado limpo, não como instrução.
- **Piloto esportivo** (`Fato` em `app/esportes`) não foi convertido em `DadoVerificavel` (fora do ao vivo).
- **Integração de trânsito, placar e previsão**: não existe; esses tipos só vêm de notícia, apuração ou aviso.
- **As-run persistente** dos dados ditos no ar e relatório no painel: F11.

## Simulação
- As 12 rodadas sem dado ficam iguais byte a byte à linha de base **fora o registro novo**: nas variantes
  `sem_relogio` do popular (2 eventos) e do variedades (1 evento) o as-run ganha `dados` com o assunto que a música
  anterior puxou (callback de música, tipo `assunto`). Nada do que foi ao ar mudou.
- O cenário `f5_popular_b` leva 15 s (relógio B com muitas falas noticiosas curtas); o limite de 30 s do S1 da F4 não
  se aplica a ele.
- No relógio B, as etapas noticiosas geram várias falas curtas seguidas e a pauta acaba antes da etapa: as falas sem
  pauta viram transição "sem notícia". É comportamento do relógio da F1, só ficou visível com notícia semeada.
- `--modo llm` e `completo` não rodados (custo).
