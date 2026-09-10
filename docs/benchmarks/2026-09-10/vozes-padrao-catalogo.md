# Vozes padrão do catálogo (não clonadas) — 10/09/2026

Escopo diferente da análise de clonagem do mesmo dia
([analise-clonagem.md](analise-clonagem.md)): aqui o alvo são as 4 vozes fixas do
catálogo ([voices.py](/Users/guilhermejeske/projetos/locufy/backend/app/tts/voices.py))
— Paulo, Will, Yasmin Alves, Scheila —, comparando o ajuste de prosódia já em
produção contra a recomendação oficial da ElevenLabs e contra um TTS de sistema.
Não houve alteração de código; só geração e medição de áudio.

**Skill usada.** Busquei no marketplace (`npx skills find`) por tts/voice/radio/podcast
e instalei `elevenlabs/skills@text-to-speech` (fonte oficial ElevenLabs, 11,1 mil
instalações, risco "Safe"/"Low Risk"), em
`.agents/skills/text-to-speech`. O conteúdo é a documentação de uso da API (modelos,
`voice_settings`, normalização de texto, streaming) mais uma tabela de recomendação
de `stability`/`similarity_boost`/`style` por caso de uso
([voice-settings.md](/Users/guilhermejeske/projetos/locufy/.agents/skills/text-to-speech/references/voice-settings.md)).
Não achei no marketplace nenhuma skill especializada em "soar como locutor de rádio"
— o que existe é conteúdo genérico de produção de áudio/podcast, sem o mesmo nível de
detalhe que o projeto já implementou em
[client.py](/Users/guilhermejeske/projetos/locufy/backend/app/tts/client.py).

**Teste realizado.** Script em `/tmp` (não versionado — é diagnóstico avulso, mesmo
padrão de `scripts/comparar_clone_v3.py`), rodando de dentro de `backend`:

```sh
PYTHONPATH=. .venv/bin/python comparar_vozes_padrao.py --output /tmp/locufy-vozes-padrao-2026-09-10 --executar-api
```

24 chamadas reais à ElevenLabs, em duas rodadas (4 vozes do catálogo × 3 tipos de
bloco × 2 variantes) mais 3 sínteses locais via `say -v Luciana` (TTS embutido do
macOS, pt_BR, sem custo de API) como baseline de "voz de software" fora da
ElevenLabs. Resultado bruto em
[vozes-padrao-resultados.json](vozes-padrao-resultados.json) (27 itens) e página com
os 27 áudios entregue ao usuário nesta conversa (`comparacao-completa.html`, cópia
local em `/tmp/locufy-vozes-padrao-2026-09-10/`, que é temporário).

As duas variantes por bloco:
- **atual** — exatamente o que a aplicação envia hoje (`_preparar_sintese`, perfil
  `atual`): tipo de bloco + tom + jitter, sem os deltas de clone.
- **oficial** — só a tabela de recomendação por caso de uso da skill instalada
  (notícia → stability 0.8/style 0.0; música/chamada → 0.4/0.3; comentário →
  0.7/0.0), sem nenhum dos ajustes de rádio do projeto.

## Resultados objetivos

| Voz | Bloco | Variante | Síntese (s) | Duração (s) | Palavras/min | LUFS bruto | True peak bruto |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| Paulo | notícia | atual | 8,74 | 15,52 | 201,0 | -13,74 | -0,50 |
| Paulo | notícia | oficial | 6,63 | 14,56 | 214,3 | -13,63 | -0,91 |
| Paulo | música | atual | 6,60 | 10,88 | **275,7** | -13,46 | -0,41 |
| Paulo | música | oficial | 5,23 | 10,64 | **282,0** | -13,70 | -0,45 |
| Paulo | comentário | atual | 6,37 | 12,24 | 245,1 | -14,44 | -0,48 |
| Paulo | comentário | oficial | 4,72 | 11,84 | 253,4 | -13,84 | -0,60 |
| Yasmin | notícia | atual | 7,84 | 18,72 | 166,7 | -17,79 | -0,65 |
| Yasmin | notícia | oficial | 7,29 | 17,44 | 178,9 | -17,37 | -0,39 |
| Yasmin | música | atual | 5,44 | 12,64 | 237,3 | -17,91 | -0,94 |
| Yasmin | música | oficial | 5,66 | 12,80 | 234,4 | -18,23 | -1,27 |
| Yasmin | comentário | atual | 6,51 | 14,08 | 213,1 | -18,18 | -2,16 |
| Yasmin | comentário | oficial | 5,90 | 14,16 | 211,9 | -17,36 | -0,88 |
| say Luciana | notícia | — | — | 17,94 | 173,9 | -15,94 | -3,78 |
| say Luciana | música | — | — | 13,78 | 217,7 | -16,02 | -4,37 |
| say Luciana | comentário | — | — | 14,54 | 206,4 | -16,10 | -3,86 |
| Will | notícia | atual | — | 17,52 | 178,1 | -18,62 | -1,77 |
| Will | notícia | oficial | — | 16,48 | 189,3 | -17,51 | -1,08 |
| Will | música | atual | — | 13,20 | 227,3 | -17,52 | -0,73 |
| Will | música | oficial | — | 12,32 | 243,5 | -16,78 | -0,90 |
| Will | comentário | atual | — | 13,44 | 223,2 | -18,42 | -1,63 |
| Will | comentário | oficial | — | 13,36 | 224,6 | -18,05 | -2,04 |
| Scheila | notícia | atual | — | 16,56 | 188,4 | -16,13 | -0,58 |
| Scheila | notícia | oficial | — | 16,56 | 188,4 | -16,25 | -1,03 |
| Scheila | música | atual | — | 13,68 | 219,3 | -16,25 | -0,69 |
| Scheila | música | oficial | — | 13,52 | 221,9 | -16,51 | -0,91 |
| Scheila | comentário | atual | — | 15,52 | 193,3 | -17,78 | -0,64 |
| Scheila | comentário | oficial | — | 14,24 | 210,7 | -17,60 | -0,49 |

LUFS/true peak são do áudio bruto, antes do mastering (`finalizar_audio`/`radio_fm`),
que já normaliza pra -16 LUFS/-2 dBTP em produção — a diferença entre vozes/variantes
aqui não é o volume final ouvido no app.

## Achados

**1. Paulo é o único das 4 vozes do catálogo fora da faixa natural — a mesma
configuração produz ritmo bem diferente por voz.** Com as 4 vozes testadas
(Paulo, Yasmin, Will, Scheila), o ritmo em música/comentário fica assim:

| Voz | música (wpm) | comentário (wpm) |
| --- | ---: | ---: |
| Paulo | 276–282 | 245–253 |
| Will | 227–244 | 223–225 |
| Yasmin | 234–237 | 211–213 |
| Scheila | 219–222 | 193–211 |

Rádio real gira em torno de 150–190 palavras/minuto mesmo em blocos animados; Will,
Yasmin e Scheila ficam acima disso mas dentro de uma faixa "animado, mas ainda
inteligível". Paulo é o único que passa de 245 em todo bloco e chega a 282 em
música — isso é consistente com o comentário já registrado no próprio código
([client.py:60](/Users/guilhermejeske/projetos/locufy/backend/app/tts/client.py#L60):
"reclamação recorrente de locução rápida demais"): o ajuste feito reduziu o `speed`
globalmente, mas Paulo continua o mais rápido das 4 com o mesmo multiplicador.
Recomendação concreta: dar a Paulo um `speed` mais baixo que as outras 3 vozes
nos blocos música/comentário (hoje todas recebem o mesmo valor via
`_VOICE_SETTINGS_POR_TIPO`), em vez de só o ajuste global já feito.

**2. O preset de notícia diverge bastante da recomendação oficial.** O projeto usa
stability 0,5/style 0,25 pra notícia; a tabela da skill recomenda stability 0,8/style
0,0 pra "News/Professional". Não dá pra dizer qual soa melhor sem audição — pode ser
que o valor mais baixo tenha sido escolhido de propósito pra fugir do tom "robótico
demais" de leitura de teleprompter. Vale ouvir as duas variantes de notícia na página
entregue antes de decidir se aproxima do valor oficial.

**3. O baseline do `say` (voz de sistema, sem nenhum ajuste) é o mais "seguro"
objetivamente — ritmo dentro da faixa natural (174–218 wpm) e maior headroom
(-3,8 a -4,4 dBTP, longe de clipar) — mas é conhecido por soar monótono/mecânico por
timbre e entonação, não por essas duas métricas. Essas métricas não capturam
naturalidade; servem só de piso de comparação técnico, não de veredito de qualidade.**

## O que não foi possível fazer nesta sessão

- **Comparar com rádios reais.** Não há gravação de rádio de referência no projeto
  nem uma forma legítima de baixar e reusar áudio ao vivo de uma emissora real neste
  ambiente. A comparação com "rádio existente" que dá pra fazer aqui é por
  conhecimento geral de produção (ritmo de fala, respiração, imperfeição natural),
  não por A/B contra um áudio real — sinalizando isso em vez de fingir que ouvi uma
  rádio de verdade.
- **Comparar com outras vozes de software além do `say`.** Não há chave/acesso a
  outros provedores de TTS (Azure, Google, Play.ht etc.) configurados neste ambiente;
  o único "TTS de software" testável localmente sem custo extra foi o `say` do macOS.
- **Julgamento de naturalidade em si.** As métricas acima (LUFS, ritmo, duração) são
  proxies; naturalidade percebida exige audição humana — por isso a página com os 18
  áudios foi entregue em vez de eu declarar um vencedor.

## Ajuste aplicado

Adicionado `_AJUSTE_SPEED_MULTIPLICADOR_POR_VOZ` em
[client.py:162](/Users/guilhermejeske/projetos/locufy/backend/app/tts/client.py#L162):
multiplicador de 0,85 no `speed`, só pro `voice_id` do Paulo, aplicado em qualquer
tipo de bloco/tom antes do clamp final. Escolhido multiplicador (não delta fixo)
porque o excesso medido é proporcional (13–21% mais rápido conforme o bloco), não
constante — assim a diferença relativa entre tipo de bloco de Paulo é preservada,
só desloca a régua toda pra baixo. `voice_id` passou a ser propagado até
`_construir_voice_settings` (parâmetro novo, default `None`, não quebra as chamadas
existentes nos testes). As outras 3 vozes do catálogo e a voz clonada não são
afetadas — `_AJUSTE_SPEED_MULTIPLICADOR_POR_VOZ.get(voice_id, 1.0)` cai em 1,0 pra
qualquer `voice_id` fora do dicionário.

Confirmado por teste unitário rápido: em música/energico no v3, o `speed` de Paulo
sai ~0,89 contra ~1,05 das outras vozes (antes do jitter). 99 testes de TTS/live
relacionados a áudio/tom passaram depois da mudança
(`test_tts_client.py`, `test_tts_router.py`, `test_tts_voices.py`, `test_tts_profiles.py`,
`test_tts_quality.py`, `test_live_router.py -k 'tts or audio or tom'`).

**Confirmado com 2 chamadas reais** (`sintetizar_audio` completo, caminho de produção,
não só `_construir_voice_settings` isolado): Paulo em música caiu de 275,7 para
229,0 palavras/minuto; em comentário, de 245,1 para 219,4. Isso coloca Paulo dentro
da faixa das outras 3 vozes no mesmo bloco (música: Will 227,3 / Yasmin 237,3 /
Scheila 219,3; comentário: Will 223,2 / Yasmin 213,1 / Scheila 193,3) — deixou de
ser outlier. Ainda não é audição humana (continua sendo proxy objetivo de ritmo),
mas o sintoma medido original (Paulo destoando das outras vozes) está corrigido.

O preset de notícia (stability 0,5/style 0,25 vs recomendação oficial 0,8/0,0) segue
em aberto — decisão por audição, não implementada nesta sessão.
