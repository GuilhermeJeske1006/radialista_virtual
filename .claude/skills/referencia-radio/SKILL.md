---
name: referencia-radio
description: Referência de formatos radiofônicos, relógio/espelho, oralidade e regras editoriais da Locufy. Use ao mexer em geração de falas, prompts, roteiro, relógio, pedidos de ouvinte, vinhetas ou avaliação de locução.
---

# Referência de rádio para a Locufy

Fonte completa: `docs/pesquisa-radio-locufy.md`. Plano: `docs/plano-melhoria-radio.md`.
Esta skill resume o que o código precisa respeitar. Valores numéricos são hipóteses de projeto:
coloque-os em configuração, nunca como constante solta.

## Vocabulário que o código deve usar

| Termo | No código |
|---|---|
| Grade | `Programa` por dia/horário |
| Programa | promessa + persona + formato |
| Relógio (clock) | modelo de uma hora: eventos com início, duração, natureza, hard time |
| Espelho (rundown) | ordem concreta da edição, gerada do relógio + conteúdo real |
| Hard time | horário que não pode atrasar |
| Backtiming | cálculo do tempo disponível de trás para frente até o hard time |
| Tease | promessa concreta de conteúdo adiante — precisa de evento agendado |
| Front/back-announce | anunciar o que vai tocar / o que tocou |
| Ramp | introdução instrumental antes do vocal |
| As-run | registro do que efetivamente foi ao ar |

## Unidades de fala iniciais por formato (segundos)

| Formato | Unidade |
|---|---|
| Musical adulto | link 10–35 |
| Hits/CHR | link 10–40 |
| Popular/sertanejo | entrada 20–60 |
| Regional/raiz | entrada 20–90 |
| Romântico/noturno | entrada 15–45 |
| Morning show | conversa 2–6 min |
| Variedades/serviço | quadro 2–8 min |
| All news | nota 20–60; reportagem 1–4 min |
| Religioso | reflexão 1–5 min |

Primeiros perfis a implementar: musical adulto, popular/sertanejo, variedades leves.
Jornalismo factual só depois de fontes e validade (F5) estarem prontos.

## Ritmo

Hipótese: 130–160 palavras/min em leitura clara (≈ 43–53 palavras em 20 s, 65–80 em 30 s).
Sempre medir o áudio final; nomes, números e emoção alongam a fala. Se exceder a janela,
resumir ou substituir — não acelerar a voz.

## Regras editoriais invioláveis

1. Não anunciar música que não está confirmada para tocar.
2. Não simular ouvinte, mensagem, pedido ou testemunho. Sem pedido real → convite genérico.
3. "Toca agora" só com pedido selecionado para o próximo evento.
4. Não prometer conteúdo ("daqui a pouco", "depois do intervalo") sem evento agendado.
5. Dado de cidade, clima, trânsito, placar: só com fonte, horário e validade; vencido → omitir ou
   dizer o horário da última atualização.
6. Não preencher lacuna factual com inferência.
7. Não imitar apresentador real; nenhuma fala de exemplo é transcrição de radialista.
8. Preservar a promessa do formato: em faixa musical, muitas vezes a melhor decisão é não falar.
9. Noturno não pressupõe solidão; esporte separa fato, opinião e rumor; religioso segue a
   tradição e o roteiro aprovado.

## Oralidade (checklist para prompt e verificador)

- Ordem direta, uma ideia principal por frase.
- Sigla importante explicada na primeira vez.
- Números e instruções em unidades pequenas.
- Fonte citada sem quebrar o raciocínio.
- Sem vocabulário burocrático. Ex.: "A municipalidade realizará intervenções viárias" →
  "O trânsito vai mudar por causa de uma obra da prefeitura."
- Escrever para uma pessoa numa situação de escuta, sem supor que todos têm a mesma rotina.
- Energia ≠ volume; variar ritmo e pausa para hierarquizar, sem a mesma curva em toda frase.

## Repetição

Trocar sinônimos não resolve repetição: variar a estrutura (abertura, gancho, fechamento).
Reorientar quem acabou de sintonizar ("Você está no …") é repetição permitida, em frequência
definida pelo formato.

## Relógios de referência (soma exata de 60 min)

- A — Musical com companhia: música 50min15s, fala/identidade 3min45s, intervalos 6 min.
- B — Jornal/revista: manchetes, cobertura, serviço, entrevista 12 min, intervalos em 15 e 41 min.
- C — Morning/variedades: abertura com pergunta do dia, bancada, serviço, jogo, quadro recorrente.

Tabelas completas na pesquisa §9.

## Contingências

Convidado não entrou → conteúdo aprovado e aviso. Fonte não atualizou → omitir ou dar horário.
Pedido indisponível → não anunciar, manter na fila. Áudio falhou → reserva e registro.
Debate estourou → fechar, resumir, cumprir o hard time.
