# Simulação: R$ 69,90/mês + consumo com acréscimo de 100%

Simulação em 24/09/2026. Não altera planos, cobrança ou seleção de modelos no produto. Tarifas são as premissas locais, não uma nova validação de preços dos provedores. Não mede lucro líquido contábil.

## Premissas

- Um plano de acesso, sem créditos de IA incluídos. Texto e voz escolhidos separadamente; combinações sujeitas à validação de qualidade e compatibilidade com a voz.
- Mensalidade R$ 69,90; cobrança de consumo = 2 × custo direto faturável em reais. Acréscimo de 100% não significa margem de 100%.
- Cenários de 30, 60 e 120 horas de programa por mês, com 10% de locução nova: 180, 360 e 720 minutos. Música e reprodução de áudio pronto não geram nova cobrança de síntese.
- Todos os cenários usam 1.000 mensagens/mês e 60 buscas/mês. As mensagens são consumo pago, não franquia incluída.
- Câmbio hipotético R$ 5,50/USD; 1.500 tokens de entrada e 150 de saída por geração; uma geração por mensagem; duas por minuto de locução; três classificações Haiku por geração, de 500/32 tokens; 1.000 caracteres/minuto.
- Transcrição: 20% das mensagens com áudio de 30 segundos; US$ 0,40/h como hipótese. Sem desconto de cache.
- Os 10% de regeneração do simulador são interpretados aqui como novas versões solicitadas e faturáveis. Falhas internas não são repassadas: devem caber na reserva ou reduzirão a sobra.
- Taxas/tributos hipotéticos: 10% da receita. Reserva: 15% do custo de IA. Base operacional: R$ 52 = infraestrutura 25 + suporte 15 + cobrança 0,50 + outras despesas 10 × 1,15.
- A base considera uma cobrança mensal; recargas adicionais e custos específicos de armazenamento, clonagem ou serviços não medidos exigem revisão. Custos de equipe, aquisição de clientes e demais despesas não contempladas não estão deduzidos.

## Fórmulas

Tarifas hipotéticas usadas: Opus US$ 5/25, Sonnet US$ 2/10 e Haiku US$ 1/5 por milhão de tokens de entrada/saída, respectivamente; voz v3 US$ 0,10 e Flash US$ 0,05 por mil caracteres; buscas US$ 10 por mil. A seleção simulada corresponde a `claude-opus-5`, `claude-sonnet-5`, `claude-haiku-4-5`, `eleven_v3` e `eleven_flash_v2_5`.

Para C = custo direto faturável de IA em reais:

```text
Cliente paga = 69,90 + 2C
Sobra estimada = receita × 0,90 − 1,15C − 52
Sobra estimada = 10,91 + 0,65C
Margem estimada = sobra / receita
```

Os componentes de IA foram calculados com o simulador offline dos planos antigos (removido após a migração para o Locufy Flex), com metade da franquia Starter de 2.000 mensagens, `horas × 6` minutos de voz e 60 buscas, apenas para reutilizar a aritmética. O preço do plano antigo não é usado. As premissas estão acima e em [simulacao-plano-consumo.json](simulacao-plano-consumo.json).

## Resultados

| Texto | Voz | Programa h/mês | Custo IA R$ | Cliente paga R$ | Sobra R$ | Margem |
|---|---|---:|---:|---:|---:|---:|
| Opus | v3 | 30 | 224,72 | 519,35 | 156,98 | 30,23% |
| Opus | v3 | 60 | 362,44 | 794,78 | 246,49 | 31,01% |
| Opus | v3 | 120 | 637,87 | 1.345,64 | 425,52 | 31,62% |
| Opus | Flash | 30 | 170,27 | 410,45 | 121,59 | 29,62% |
| Opus | Flash | 60 | 253,54 | 576,98 | 175,71 | 30,45% |
| Opus | Flash | 120 | 420,07 | 910,04 | 283,95 | 31,20% |
| Sonnet | v3 | 30 | 169,18 | 408,27 | 120,88 | 29,61% |
| Sonnet | v3 | 60 | 292,20 | 654,30 | 200,84 | 30,70% |
| Sonnet | v3 | 120 | 538,22 | 1.146,35 | 360,76 | 31,47% |
| Sonnet | Flash | 30 | 114,73 | 299,37 | 85,49 | 28,56% |
| Sonnet | Flash | 60 | 183,30 | 436,50 | 130,05 | 29,79% |
| Sonnet | Flash | 120 | 320,42 | 710,75 | 219,19 | 30,84% |
| Haiku | v3 | 30 | 150,67 | 371,24 | 108,85 | 29,32% |
| Haiku | v3 | 60 | 268,78 | 607,47 | 185,62 | 30,56% |
| Haiku | v3 | 120 | 505,01 | 1.079,92 | 339,17 | 31,41% |
| Haiku | Flash | 30 | 96,22 | 262,34 | 73,45 | 28,00% |
| Haiku | Flash | 60 | 159,88 | 389,67 | 114,83 | 29,47% |
| Haiku | Flash | 120 | 287,21 | 644,32 | 197,60 | 30,67% |

## Leitura e proposta

Sem consumo e sem buscas automáticas, o cliente paga R$ 69,90 e a sobra simulada é R$ 10,91 (15,61%). Nos cenários com uso, a margem cresce em direção a 32,5%, conforme o peso do consumo supera a mensalidade.

O usuário pode escolher texto e voz por programa, ver estimativa antes de gerar, definir teto mensal e consultar extrato por modelo. Alterações de modelo valem para gerações futuras. Um programa pode misturar modelos: soma-se o custo efetivo de cada geração antes de aplicar o multiplicador.

A medição implementada é controle interno de custo; ainda não representa uma carteira financeira pronta para cobrar o cliente. A implementação comercial exige separar custo interno, custo faturável, reserva, cobrança e estornos, mantendo bloqueio atômico por saldo.

Amostras anteriores não aprovaram troca universal de modelos: Haiku apresentou informação não sustentada; Flash não teve equivalência de expressividade comprovada. Estes resultados financeiros não são aprovação de qualidade.
