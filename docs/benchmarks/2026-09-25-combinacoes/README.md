# Validação das combinações texto + voz

Executado em 25/09/2026 com APIs reais, dados fictícios e a voz configurada no ambiente. Uma
geração por caso: resultado indicativo, não estatístico. Não usou banco nem alterou configurações.

**Resultado:** as 6 combinações (3 modelos de texto × 2 vozes) estão oferecidas no onboarding,
por decisão do responsável. As duas com Haiku (Voz Premium e Essencial) mostram ao cliente a
limitação de fidelidade medida aqui e em 24/09. Todas as vozes passaram nas checagens
automáticas; falta a escuta humana em [escuta.html](escuta.html). O anúncio de música de cada
combinação virou o exemplo do catálogo (`--exportar-exemplos`).

## Como foi medido

Script: `backend/scripts/validar_combinacoes.py` (reproduzível, consome créditos).

- **Texto** — mesmo prompt do ao vivo, inclusive a instrução de direção vocal quando a voz é v3.
  Seis casos: anúncio de música, evento sem autorização, data incerta, evento encerrado,
  números (temperatura, telefone, preço) e diálogo em JSON. Checagens automáticas (limite de
  palavras, tags permitidas, tag sem voz v3, JSON do diálogo) e juiz LLM pontual (Opus 5) com
  critério por caso, recebendo o prompt do sistema — padrão da skill `llm-evaluation`.
- **Voz** — cada fala passa pelo pipeline real (normalização de números, sanitização de tags,
  parâmetros da voz) e é transcrita pelo Scribe v2 (skill `speech-to-text`). WER calculado com
  números por extenso nos dois lados; também verifica tag lida em voz alta, duração e saturação.

## Resultado por combinação

| Combinação | Texto aprovado (juiz) | Fidelidade | Instruções | Naturalidade | WER médio / máx. | Tag falada | Voz (s/fala) | Custo da rodada |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Premium · Opus 5 + v3 | 5/6 | 5,00 | 4,67 | 4,83 | 3,5% / 22,2% | 0 | 6,4 | US$ 0,31 |
| Equilibrada · Sonnet 5 + v3 | 6/6 | 4,83 | 4,50 | 4,67 | 0,7% / 3,9% | 0 | 6,2 | US$ 0,24 |
| Voz Premium · Haiku 4.5 + v3 | 4/6 | 4,83 | 4,00 | 4,17 | 1,6% / 6,1% | 0 | 6,8 | US$ 0,22 |
| Texto Premium · Opus 5 + Flash 2.5 | 6/6 | 4,83 | 4,67 | 4,83 | 1,0% / 4,2% | 0 | 1,3 | US$ 0,21 |
| Ágil · Sonnet 5 + Flash 2.5 | 4/6 | 5,00 | 4,17 | 4,67 | 0,1% / 1,2% | 0 | 1,3 | US$ 0,14 |
| Essencial · Haiku 4.5 + Flash 2.5 | 3/6 | 4,50 | 3,50 | 4,33 | 2,8% / 7,1% | 0 | 1,3 | US$ 0,12 |

Custo com as tarifas hipotéticas de `settings` (texto + voz), sem o juiz e a transcrição.
Nenhum áudio falhou (52/52) e nenhum teve amostra saturada. Voz Premium e Texto Premium foram
medidas numa segunda rodada no mesmo dia (`--acrescentar`), com o mesmo prompt e casos.

## O que as reprovações mostram

- **Regra interna explicada ao ouvinte** (Premium, Ágil e Essencial): no evento sem autorização,
  o locutor diz "a rádio não autorizou". Não divulga o evento, mas expõe a regra. É do prompt,
  não da combinação — mesmo achado de 24/09. Ajustar a instrução antes de culpar o modelo.
- **Temperatura omitida** (Ágil e Essencial): o pedido deu "23 graus", mas o prompt proíbe
  afirmar clima sem dado confirmado, e o modelo seguiu o prompt. Conflito de instrução; nenhum
  número foi alterado em nenhuma combinação.
- **Essencial (Haiku)**: acrescentou "evento tradicional por aqui" e "procure a prefeitura",
  generalidades ("marcou época"), passou do limite de palavras, usou emoji e cercou o JSON com
  ```` ``` ````. Oferecida com essa limitação escrita no card.
- **Voz Premium (Haiku + v3)**: nesta rodada não inventou fato, mas ficou abaixo do mínimo de
  palavras no anúncio e explicou a regra interna no evento sem autorização.
- **Texto Premium (Opus + Flash)**: 6/6 no texto; a voz Flash não usa direção vocal.
- **Maior WER da voz** (Premium, diálogo): "Tarde Musical" transcrito como "Tide Musical".
  Pode ser pronúncia do v3 ou erro do transcritor — confirmar ouvindo `premium-dialogo-4.mp3`.

## Limitações

Uma rodada por caso; o juiz (Opus) avalia também respostas do próprio Opus; WER não mede
expressividade, identidade vocal nem preferência humana. Para aprovar Essencial no futuro,
repetir com mais rodadas depois de ajustar o prompt.

## Arquivos

- `casos.json`: prompt do sistema e casos; `resultados.json`: textos, notas do juiz, envios,
  transcrições e métricas por fala; `resumo.json`: tabela acima.
- `<combinacao>-<caso>-<n>.mp3`: áudios gerados; `escuta.html`: página para escuta lado a lado.
- Exemplos do catálogo: `backend/app/billing/exemplos_combinacoes.json` (texto e unidades medidas)
  e `frontend-painel/public/exemplos/combinacoes/<id>.mp3` (caso "musica" de cada combinação).
