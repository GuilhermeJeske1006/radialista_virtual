# Auditoria H0: linha de base e conjunto de testes (humanização da fala)

Branch auditada: `melhoria/f12-14-expansao`, HEAD `371b786`, com a árvore de trabalho limpa. O plano foi escrito sobre
`a9cc8f1`; depois dele entraram quatro commits: `2ee8b28` (bloqueio da API da Anthropic na suíte), `4fbd0fa`
(capacidades de TTS por modelo), `301717d` (direção de energia por programa) e `371b786` (plano e skill). A auditoria só
leu o código. `pytest --collect-only` coleta **2472 testes**. O portão final da F12–14 em `a9cc8f1` teve 2435 passed e
3 skipped. Contagem nos módulos envolvidos: `test_simular_hora` 29, `test_oralidade` 16, `test_oralidade_reescrita` 7,
`test_memoria` 19, `test_live_validacao_fala` 23 e `test_simulacao_f6` 36.

Fontes:
- `docs/plano-humanizacao-fala.md`: §1, §2, §3 (D1–D9), §5 (H0, mais H1, H4 e H5 por dependência), §7, §8 e §9.
- `docs/Locufy — Plano de humanização da fala.md`: padrões, "O que não corrigir", léxico e "Como medir".
- `docs/pesquisa-radio-locufy.md`: §5 (oralidade, `:139-148`) e §8 (banco de falas com colchetes, `:221-275`).
- Skills `referencia-radio`, `avaliar-locucao`, `conversa-teste`, `llm-evaluation` e `humanizar-fala`. Agentes
  `testador-locufy` e `juiz-locucao`.
- `docs/auditoria.md` e `docs/refatoracao.md`.

**Conclusão: a frente não está atendida, mas pode começar.** Nenhuma entrega da H0 existe hoje: não há corpus, não há
conjunto de 60 entradas, não há métricas novas, não há `docs/humanizacao/baseline.md` e as skills não têm a seção nova.
Os detectores que as métricas usam também não existem: `app/live/sinais_ia.py` cabe à H1 e à H4, e o detector de
bordão cabe à H5. Por isso a H0 entrega só o corpus, o conjunto e métricas com import tardio. Essas métricas devolvem
`None` enquanto o detector não existir, como `aviso_oralidade` fez até a F7. Os textos (as-run) ficam gravados para
serem recalculados com o mesmo detector depois. A pré-condição da §8 do plano, árvore limpa, já está resolvida.

---

## 1. Estado atual: o plano confere com o código?

| Afirmação | Situação | Evidência |
|---|---|---|
| `casos.json` tem 35 casos de regra editorial | **diferente: 48 casos e 96 falas rotuladas** | 35 casos vieram da F0 (`3356c13`) e 13 da F6 (`913fc19`). Formatos: 14 `musical_adulto`, 19 `popular_sertanejo` e 15 `variedades_leves`. As 9 chaves de `esperado` aparecem em todas as falas; 5 chaves da F6 aparecem em 26 falas. |
| Formato do `casos.json` | confirmado | `{versao, fonte, regras{wpm_referencia, esperado, observacao, formato_coerencia}, casos[{id, formato, bloco, frentes, dimensoes, contexto, criterio, falas_rotuladas[{texto, esperado}]}]}`. Regra "sem algarismo" em `tests/test_simular_hora.py:608`. Sete testes leem o arquivo por caminho fixo (`test_simular_hora.py:583`, `test_oralidade.py:8`, `test_live_validacao_fala.py:40`, `test_dados_checagem.py:22`, `test_live_formatos_coerencia.py:294`, `test_live_participacao.py:17`, `test_live_promessas.py:22`). Nenhum teste varre `docs/benchmarks/*/casos.json`, então uma pasta nova não interfere neles. |
| O conjunto não tem nenhum caso de sinais de IA | confirmado | A varredura das 96 falas não achou nenhum termo do léxico do documento de origem, nem colchete, chave, markdown, emoji, link ou travessão. Só 2 casos têm a dimensão `naturalidade` (`casos.json:1634`, `:1871`). Só 4 falas têm `avisos_oralidade_min > 0` (`test_oralidade.py:88-97`). |
| O simulador já calcula `aviso_oralidade` (`metricas.py:323`) | confirmado | `_aviso_oralidade` em `scripts/simulacao/metricas.py:323-332`: import tardio, aceita `avisos` ou `verificar` e devolve `None` se faltarem. A chave é gravada em `:505`. `_repeticao_estrutura` segue o mesmo padrão (`:314-320`, chave em `:506`). Nas rodadas gravadas da F6 as duas chaves valem `None`, porque são anteriores à F7 e à F8. É neste ponto que entram as quatro métricas novas. |
| As falas do modo fake são texto fixo (`banco_falas.py`) | confirmado | `scripts/simulacao/banco_falas.py:13-528` tem 372 frases distintas, com regras conferidas em `test_simular_hora.py:241-262`. Nenhum termo do léxico aparece. Três gerúndios legítimos de rádio aparecem (`:99`, `:235`, `:490`, como "Aqui é {locutor}, fechando {programa} de hoje."); eles servem de armadilha para o padrão "gerúndio final" da H4. `"Fica com a gente."` é fechamento em 8 modelos (`:113`, `:146`, `:184`, `:223`, `:288`, `:363`, `:388`, `:413`), o que importa para a D4 (bordão). Só há duas frases de injeção fixas (`:531-532`). |
| Como o dublê gera a fala | confirmado | `DubleLLM._gerar` (`dubles.py:184-287`) lê o tipo do bloco no prompt (`:49`), escolhe o modelo do banco (`:341-363`) e monta abertura, gancho, meios e fechamento com o RNG próprio (`:378-417`). As injeções entram por número de fala (`:244-268`): promessa, música, ouvinte, dado e as da F6 (`INJECOES_FRASE_F6`, `:62`, `:266`). O tipo de injeção é um `Literal` fechado (`fixtures.py:143-144`, modelo `_Estrito`). |
| O modo fake não mede prompt (achado 6) | confirmado | No `--modo llm`, só `gerar_resposta` e `gerar_dialogo_multivoz` são reais (grupo "texto" em `ALVOS`, `dubles.py:673-675`, `:816-817`); as funções de apoio continuam dublês. A estimativa da CLI (falas × 1,2, `simular_hora.py:64`, `:351-360`) conta exatamente essas chamadas. |
| `oralidade.py` (F7) | confirmado | `avisos()` em `app/live/oralidade.py:153-163`, com 5 regras e limite de 25 palavras (`:17`). `settings.oralidade_modo` vale `desligado` por padrão (`app/config/settings.py:153`). A integração com a reescrita única está em `app/live/geracao.py:162-175` e `:195-197`. |
| `BUROCRATICO` já tem "ademais", "outrossim" e "bem como" (achado 7) | confirmado | `oralidade.py:29-32`. |
| `validacao_fala.py`: pontos de registro | confirmado | `CHECAGENS_POS_GERACAO` em `:375-376` (5 checagens). `MODO_POR_REGRA` em `:379-388`. `Violacao` em `:87-95`. `fala_reserva_neutra` em `:487-499`. A remediação `fala_inteira` existe no `Literal` (`:42`), mas `corrigir()` (`:526-560`) só a usa para o fragmento abaixo do mínimo (`:553-558`). Isso confirma o item 2 da H1. |
| `memoria.py`: o que já existe de repetição | confirmado | `aberturas_e_fechamentos` em `:44`, Jaccard em `:78` (limiar 0,6 em `:66`), `abertura_da_fala` em `:132`, `fechamento_da_fala` em `:147` e `repeticao_estrutura` em `:162-171`. Nada disso tem janela por tempo nem trata bordão. "Você está…" cai na classe `identificacao` (`:110-113`) e conta como estrutura repetida: o passo 3 da F8 (reorientação permitida) continua pendente. |
| `app/live/sinais_ia.py` | não existe | confirmado por `ls`. `tests/fixtures/humanizacao/` e `docs/humanizacao/` também não existiam antes desta auditoria. |
| Skills: seção "Sinais de IA na fala" e dimensão "Soa como pessoa" | não existem | `referencia-radio/SKILL.md` não tem a seção. A rubrica de `avaliar-locucao/SKILL.md:42-49` tem 6 dimensões. A tabela automática (`:22-32`) não tem vazamento, sinais nem bordão. |
| `conversa-teste` | confirmado, mas não lê o conjunto | `scripts/conversa_teste.py:37-46` lê só `marketing/reels/<id>/roteiro.json` (`cenas[].mensagens_ouvinte`). O script precisa de Postgres, Redis e `seed_demo` e chama o LLM real. |
| §8: a branch tem alterações não commitadas | **já resolvido** | A árvore está limpa: o painel foi commitado em `4464fbc`, as tarifas e a TTS em `4fbd0fa` e a direção de voz em `301717d`. |
| Linhas citadas na §1 do plano | **diferente: deslocadas** por `301717d` e `4fbd0fa` | `prompt_emissao.py`: 193→200 (`naturalidade_encenada`), 253→262 ("NUNCA encadeie"), 303→310 (aberturas). `tts/client.py`: 93→94 (`_AJUSTE_TOM`), 125→127 (`_sanitizar_tags_v3`), 151→153 e 309 (regex e uso de `......`→`[pause]`), 301→307 (`normalizar_texto_fala`). As demais referências conferem: `geracao.py:45,66,178`, `validacao_fala.py:375,487,526`, `memoria.py:44,78,132`, `numeros.py:101`, `prompt_builder.py:166,227,282,341`, `contexto.py:563`, `patrocinador.py:29`, `webhook.py:103`, `atendimento.py:192-270,289`. |

## 2. Fatos do código que mudam o desenho

1. **O detector não existe, então a linha de base são os textos, não os números.** A H4 só cumpre o aceite ("50% menor
   que a linha de base da H0") se o antes e o depois forem medidos pelo **mesmo** detector. Como o léxico vai ser
   calibrado, um número gravado hoje não seria comparável depois. A H0 grava os `as_run.json` e um comando de recálculo.
   A H1, a H4 e a H5 recalculam as duas pontas com o detector da vez.
2. **O as-run é comparado byte a byte.** `test_simulacao_f5.py:47-56` e `test_simulacao_f6.py:43-52` comparam o as-run
   dos três perfis com os arquivos gravados, incluindo `observacoes`, que vem de `OBSERVACOES`
   (`simular_hora.py:65-76`, gravado no as-run em `:203`). Por isso a H0 não pode mexer em `banco_falas.py`, nas três
   fixtures, em `OBSERVACOES`, em `VERSAO_FORMATO` nem nas chaves dos eventos. As métricas novas vão só para o
   `resumo.json`, que nenhum teste compara byte a byte (conferido por grep).
3. **O banco do dublê não tem nenhum sinal.** Sem injeção, a linha de base fake fica em zero por construção, e o aceite
   da H1 ("`vazamento_grave = 0` nos três perfis") seria trivial. A F5 resolveu o mesmo problema com um cenário dedicado
   (`tests/fixtures/programas/cenarios/f5_*.json`, `test_simulacao_f5.py:91`). A H0 segue esse caminho com três tipos de
   injeção novos.
4. **`_limpar_fala` roda antes do as-run.** O caminho é `geracao.py:131`, `:143` e `:66-77`. Ele já tira `** * __ _` e
   crase, mas deixa passar `#`, listas, links, emoji, URL, colchetes e chaves. Um vazamento injetado chega ao as-run
   como o LLM real o deixaria, menos a ênfase. Alguns placeholders podem ser tirados **por acaso** pela F4: um "Um abraço
   para [NOME DO OUVINTE]" pode virar `ouvinte_nao_autorizado`. A frase injetada precisa ser escolhida e conferida.
5. **O dublê de TTS substitui a síntese inteira** (`dubles.py:692-693`, `:785-786`). `_preparar_sintese`
   (`tts/client.py:276`, com `normalizar_texto_fala` em `:307` e `_sanitizar_tags_v3` em `:127-138` e `:310`) nunca roda
   na simulação. Saber o que chega ao payload da TTS exige medir sobre o corpus, fora do simulador.
6. **Colchete minúsculo também é placeholder.** O próprio banco da pesquisa usa "[artista]" e "[nome autorizado]"
   (pesquisa `:222-275`, "Dados entre colchetes só podem ser usados depois de confirmados"). Um colchete minúsculo de uma
   palavra casa com `_TAG_V3_DISPLAY_RE` (`memoria.py:19`) e é apagado em silêncio por `_sanitizar_tags_v3`, o que deixa
   a frase quebrada. O corpus precisa cobrir colchete minúsculo, e as tags permitidas (`_TAGS_V3_PERMITIDAS`,
   `tts/client.py:117`, `:122`: excited, calm, laughs, sighs, whispers, sarcastic, pause) precisam estar em
   "não corrigir".
7. **O tom muda conforme o canal.** No ao vivo, quem controla o tom é `persona.formalidade` (`persona.py:29-33`;
   `_faixa` em `:52-53` trata 1–2 como informal e 4–5 como formal). As três fixtures de linha de base têm `persona` nula.
   O WhatsApp não lê persona (`webhook.py:103-121`), então lá o tom é o registro do ouvinte. O patrocínio não passa pelo
   LLM (`patrocinador.py:29`), então lá o tom é o do texto cadastrado.
8. **O conjunto de 60 entradas não tem executor.** O simulador roda uma hora inteira. Uma entrada por hora no `--modo
   llm` multiplicaria o custo: cada hora gera de 6 a 20 falas reais, mas só uma interessaria. Com `pedidos_extra`
   (`simular_hora.py:101`, `:134-136`) dá para colocar pedidos, mas só os escolhidos para os blocos de chamada vão ao ar.
   A H0 entrega o formato, a validação contra os modelos do simulador e um teste de fumaça. O executor fica pendente
   para a H3 (ao vivo, uma fala por entrada) e a H6 (adaptador de `conversa_teste.py`).
9. **Há poucas falas por perfil.** As rodadas da F6 têm 6, 10 e 20 falas no ar. No musical o p90 é praticamente o
   máximo. A nota por 100 palavras infla em falas curtas: uma identificação tem de 3 a 8 palavras, e uma palavra de peso
   4 já dá mais de 50 pontos. A H4 precisa pôr um piso no denominador. A H0 registra quantas falas foram medidas.
10. **`_sem_acento` está copiado em vários lugares** (`docs/refatoracao.md` §3, `:117-120`; `oralidade.py:51`; `_norm`
    em `validacao_fala.py:115`; `normalizar` em `metricas.py:42`). O código novo deve usar `app.util.texto.sem_acento`,
    como `memoria.py:11` já faz.

## 3. Testes existentes dos módulos envolvidos

| Arquivo | O que já cobre | Lacuna para a H0 |
|---|---|---|
| `tests/test_simular_hora.py` | Relógios e fixtures (`:61-129`); dublê de LLM e de música (`:146-238`); regras do banco (`:241-262`); métricas num as-run artificial, incluindo `aviso_oralidade` e `repeticao_estrutura` contra os detectores do backend (`:326-359`); três perfis fake sem rede, com as 14 chaves da skill (`:366-391`); determinismo (`:394-407`); random isolado (`:410-434`); injeções nas métricas (`:504-524`); dublês cobrindo os alvos (`:527-552`); CLI e modos pagos (`:555-579`); schema do `casos.json` de 06/11 (`:582-618`); relógio F1 (`:625-675`) | Nenhuma chave de vazamento, sinais ou bordão. Nenhum teste de detector ausente ou presente. Nenhuma injeção nova. |
| `tests/test_oralidade.py`, `test_oralidade_reescrita.py` | As 5 regras, o mínimo do benchmark, os modos desligado, avisar e reescrever, e o teto de 2 chamadas | Não há corpus de sinais. |
| `tests/test_memoria.py` | Classes de abertura e fechamento, janela como no simulador e a classe `outra`, que não conta | Bordão e reorientação permitida não são cobertos (F8 passo 3, H5). |
| `tests/test_live_validacao_fala.py` | Detecção de música, remoção, fala vazia, multivoz, fragmento, checagem extra registrada (`:240`), checagem que quebra (`:258`) e mesmo detector do simulador (`:265`) | Sem `fala_inteira` vinda de checagem (cabe à H1). |
| `tests/test_simulacao_f5.py`, `test_simulacao_f6.py` | As-run byte a byte, cenários dedicados e injeções por `injecoes_extra` | São a caracterização da H0 e precisam continuar verdes sem mudança. |
| `tests/test_tts_client.py` | Tags v3 permitidas e removidas (`:260-307`, `:451`) | `_limpar_fala` não tem teste direto (`git grep` não acha nada). Isso é anotado para a H1. |
| `tests/conftest.py:140-141` | `_sem_api_anthropic` (autouse): a suíte já não chega à rede da Anthropic | — |

## 4. Itens de `docs/auditoria.md` e `docs/refatoracao.md`

- `auditoria.md` item 3 (`:76-105`, prompt injection por notícia ou pesquisa no system): fica fora da H0. O corpus e o
  conjunto não podem trazer textos de injeção, porque a F5 já mede isso (`injecao.no_system`).
- `auditoria.md` itens 1 e 2 (`:12-69`, assinatura do webhook e STT antes do guardrail de custo): importam para o
  executor de WhatsApp da H6, que usa o HMAC da conta demo. Não tocam a H0.
- `refatoracao.md` §1 (`montar_system_prompt` com 243 linhas, `:42`) e §2 (texto de prompt no código, `:81-107`): são
  da H3.
- `refatoracao.md` §3 (`_sem_acento` duplicado, `:117-120`): o código novo usa `app.util.texto` (fato 10).
- Nenhum desses itens bloqueia a H0.

## 5. Desenho da mudança

Branch `melhoria/h0-linha-de-base`, criada de `melhoria/f12-14-expansao`. A H0 não tem migração, não muda contrato de
API, não toca o painel e não cria flag em `settings`.

### 5.1 Corpus determinístico: `backend/tests/fixtures/humanizacao/corpus.json`

Cerca de 150 textos curtos, todos originais, com nomes fictícios do mesmo universo dos benchmarks (Rádio Serra Clara,
Ipê Dourado, Vila Ventura e ouvintes inventados). Esquema:

```json
{
  "versao": 1,
  "fonte": "docs/plano-humanizacao-fala.md (H0); léxico e 'O que não corrigir' de docs/Locufy — Plano de humanização da fala.md",
  "regras": {
    "grupos": {"vazamento": "...", "sinal": "...", "nao_corrigir": "..."},
    "categorias": {"placeholder": {"grupo": "vazamento", "acao": "bloquear", "frente": "H1"},
                   "markdown": {"grupo": "vazamento", "acao": "limpar", "frente": "H1"},
                   "gerundio_final": {"grupo": "sinal", "acao": "pontuar", "frente": "H4"}},
    "observacao": "Textos originais; nenhum transcreve ou imita radialista real."
  },
  "textos": [
    {"id": "vaz-placeholder-01", "grupo": "vazamento", "categorias": ["placeholder"], "canal": "ao_vivo",
     "tom": "informal", "texto": "Um alô para [NOME DO OUVINTE], que ouve do trabalho.",
     "trechos": ["[NOME DO OUVINTE]"], "esperado": {"vazamento": true, "acima_do_limite": null}}
  ],
  "sequencias": [
    {"id": "seq-bordao-01", "categorias": ["bordao"], "bordoes": ["A viola que acompanha o seu dia"],
     "falas": [{"inicio_s": 0, "texto": "..."}, {"inicio_s": 600, "texto": "..."}],
     "esperado": {"bordao_repetido": 2, "repeticao_estrutura": 0, "repeticao_proibida": 0}}
  ]
}
```

Composição. Cada categoria de sinal tem **no mínimo 5 positivos**, para que a revocação de 0,8 da H4 aceite um erro
(4 de 5).

| Grupo | Categoria (frente) | Qtd. | Notas |
|---|---|---|---|
| vazamento (43) | placeholder (H1) | 10 | Colchete maiúsculo e minúsculo ("[artista]", fato 6), `{nome}`, `<bairro>`, "FULANO", "XXX", "NOME DO". |
| | recusa (H1) | 6 | "Desculpe, não posso ajudar com isso." e variações. |
| | identidade_ia (H1) | 5 | "como uma inteligência artificial", "sou um modelo de linguagem". |
| | data_corte (H1) | 5 | "até minha última atualização", "meus dados vão até 2025" (algarismo permitido aqui). |
| | markdown (H1, `acao: limpar`) | 8 | `#`, lista com `-` e `1.`, `[texto](url)`, `>`, ênfase. |
| | emoji (H1 e H2, `limpar`) | 5 | No ar. No WhatsApp a regra é outra (ver "não corrigir"). |
| | url (H1, `limpar`) | 4 | Com `https://`. |
| sinal (64) | atendimento/chatbot (H4 e H6) | 6 | "Espero ter ajudado", "Fico à disposição", "Posso ajudar em algo mais?", "Ótima pergunta". |
| | importancia_inflada, ressalva, conectivo_redacao, vocabulario_ia, evitar_e, folheto (canal patrocinio), paralelismo_negativo, triade, gerundio_final, fechamento_resumo, atribuicao_vaga (H4) | 5 cada (54) | `conectivo_redacao` **sem** "ademais", "outrossim" e "bem como" (achado 7). 5 textos "densos", com várias categorias, levam `acima_do_limite: true`. |
| | travessao (H2) | 4 | `—`, `–` e ` -- ` entre orações. |
| nao_corrigir (45) | noticia_formal | 10 | Formal e correto, com fonte e horário. Nenhum vício. |
| | conectivo_isolado | 5 | Um "além disso" sozinho em fala longa. |
| | mistura_registro | 6 | Casual e formal juntos. |
| | reorientacao | 5 | "Você está na…" e "Você está ouvindo…". |
| | armadilhas | 19 | Tags v3 permitidas (`[laughs]`, `[pause]`); "não posso deixar de agradecer"; IA como **assunto** da notícia; "na última atualização da Defesa Civil, às quinze horas"; "jornada de trabalho"; "cenário" de teatro; "o vereador que representa o bairro"; "vale a pena"; "é importante levar documento com foto"; gerúndio legítimo ("Aqui é a Lia, fechando o programa de hoje."); "fulano" coloquial em minúsculas; tríade factual da previsão ("chuva, vento e frio, segundo o instituto"); domínio falado ("ponto com ponto br"); um emoji no WhatsApp quando o ouvinte usou (`contexto.ouvinte_usou_emoji: true`). |
| sequências (cerca de 8) | bordão, abertura, naturalidade encenada, fechamento | — | Slogan 3 vezes em 20 min (`bordao_repetido` 2). Slogan 2 vezes com 40 min de intervalo (0). Reorientação 3 vezes na frequência do formato (`repeticao_proibida` 0, mas `repeticao_estrutura` hoje 1). Mesma saudação 3 vezes (1). "é... deixa eu ver aqui" em 3 de 4 falas (achado 3, H5). "Fica com a gente" 4 vezes (decisão D4 na H5). |

Regras do corpus, conferidas por teste:
- algarismo só no grupo vazamento e nos canais `patrocinio` e `whatsapp`;
- cada `trecho` é substring do `texto`;
- `acima_do_limite` fica `null` nos sinais isolados, porque os pesos são da H4 e da D5. É `true` nos densos e `false` em
  todo "não corrigir";
- as respostas fixas de `atendimento.py:192-270` **não** são copiadas para o corpus, porque mudam na H6. A linha de base
  as cita por referência.

### 5.2 Conjunto de geração: `docs/benchmarks/<data>-humanizacao/casos.json`

`<data>` é a data da implementação; hoje seria `2026-11-23`. O conjunto tem 60 entradas, 10 por tipo, e cada entrada
roda nos dois tons (DH0-1), o que dá 120 casos avaliados. O esquema é próximo ao do benchmark de 06/11, para o juiz
reaproveitar:

```json
{
  "versao": 1, "fonte": "...",
  "regras": {
    "tipos": ["recado", "pedido_musica", "aniversario", "clima_transito", "patrocinio_lido", "whatsapp"],
    "tons": {"formal": {"persona": {"formalidade": 4}}, "informal": {"persona": {"formalidade": 2}}},
    "esperado": {"sem_vazamento": "...", "sem_frase_atendimento": "...", "cita_especifico": "...",
                 "whatsapp_max_frases": 2, "whatsapp_max_emoji": "1 se o ouvinte usou, senão 0",
                 "nao_prometer_execucao": "..."},
    "observacao": "Entradas originais; nomes e telefones fictícios (55000000030xx)."
  },
  "casos": [
    {"id": "recado-01", "tipo": "recado", "canal": "ao_vivo", "formato": "popular_sertanejo",
     "bloco": "chamada_ouvinte", "tons": ["formal", "informal"],
     "entrada": {"pedidos": [{"chega_em_s": 300, "tipo": "abraco", "nome": "...", "telefone": "5500000003001",
                              "natureza": "recado_comum", "mensagem": "...", "texto_autorizado": "..."}]},
     "por_tom": {}, "criterio": "...", "dimensoes": ["soa_como_pessoa", "naturalidade", "precisao"]}
  ]
}
```

Como cada tipo vira objetos do simulador. As chaves de `entrada` são campos de `FixturePrograma`, e `por_tom` sobrepõe
o que muda com o tom.

| Tipo | `entrada` / `por_tom` | Tom |
|---|---|---|
| recado, aniversario | `pedidos: [Pedido]` com `tipo "abraco"` e `natureza "recado_comum"` (`fila_ao_vivo.py:33-37`) | `persona.formalidade` 4 ou 2 |
| pedido_musica | `pedidos: [Pedido]` com `tipo "musica"` e `musica_query` do catálogo do `formato` da entrada. Duas entradas pedem faixa indisponível, para exercitar a substituição. | persona |
| clima_transito | `clima: [LeituraClimaFixture]` e/ou `noticias: [NoticiaFixture(categoria="transito")]`, no padrão de `cenarios/f5_popular_b.json` | persona |
| patrocinio_lido | `por_tom.<tom>.patrocinadores: [PatrocinadorFixture]` com `tipo_conteudo "texto"`. Pode ter algarismo ("R$ 19,90", "18h"), que exercita a H2. Não passa pelo LLM. | o próprio texto |
| whatsapp | `por_tom.<tom>.mensagens_ouvinte: [str]`, mesma chave de `roteiro.json` usada por `conversa_teste.py:42` | o registro do ouvinte ("Boa tarde, gostaria…" ou "kkk vlw manda aquela") |

### 5.3 Métricas novas no simulador (`backend/scripts/simulacao/metricas.py`)

Uma função nova e pura, `metricas_humanizacao(as_run, *, bordoes=(), config=None) -> dict`, no padrão de
`metricas_formato`. Ela não muta o as-run (ao contrário de `anotar_eventos`) e lê só falas com texto não vazio
(`tipo in config["tipos_fala"]`). Saída plana:

| Chave | Detector (dono) | Valor |
|---|---|---|
| `vazamento_grave` | `app.live.sinais_ia.vazamentos(texto) -> list` (H1) | Falas no ar com a lista não vazia; `None` sem detector. |
| `sinais_ia_media` | `app.live.sinais_ia.pontuar(texto).nota` (H4) | Média com 1 casa decimal; `None` sem detector ou sem falas. |
| `sinais_ia_p90` | idem | Posto mais próximo: `ordenadas[ceil(0,9·n) − 1]`. |
| `bordao_repetido` | `app.live.memoria.bordoes_repetidos(falas: list[tuple[float, str]], bordoes, janela_s, maximo) -> int` (H5; contrato proposto) | Ocorrências acima de `maximo` na janela. Até a H8, os bordões são o slogan da conta (DH0-3). |
| (opcional) `sinais_ia_falas` | — | n medido, para ler o p90 (fato 9). |

- O import usa um ajudante `_detector(modulo, *nomes)` com `importlib.import_module`, que consulta `sys.modules` e
  deixa o teste trocar o módulo. Ele devolve `None` só em `ModuleNotFoundError` cujo `erro.name` seja o próprio módulo;
  um erro de import interno sobe. Se o módulo existir sem a função (por exemplo, a H1 pronta e a H4 ainda não), devolve
  `None` só para aquela métrica.
- Configuração nova: `CONFIG_METRICAS["humanizacao"] = {"bordao": {"janela_s": 1800, "maximo": 1}, "percentil": 90}`.
  Esses valores repetem o padrão da H5 e não ficam soltos no código.
- `simular_hora.py`: depois de `calcular_metricas` (`:206`), mesclar `metricas_humanizacao(as_run,
  bordoes=[fixture.conta.slogan])` no topo do `resumo` (`:248`) e acrescentar `vazamento_grave=` e
  `sinais_ia_media=` em `_linha_resumo` (`:332-348`). `OBSERVACOES` **não** muda (fato 2).
- Recálculo: `backend/scripts/recalcular_humanizacao.py --as-run <arquivo> [--slogan <texto>] [--saida <json>]`.
  O script prepara o ambiente (`ambiente.preparar_processo("fake")`), lê o as-run gravado e grava ou imprime as quatro
  métricas. A H1, a H4 e a H5 usam esse comando sobre as duas pontas (fato 1).

### 5.4 Injeções e cenário

- `fixtures.py:143-144`: `Injecao.tipo` ganha `"vazamento"`, `"sinal_ia"` e `"bordao"` (todos com `frase`), e a
  docstring é atualizada.
- `dubles.py`: uma tupla `INJECOES_FRASE_H0 = ("vazamento", "sinal_ia", "bordao")` tratada como a da F6 (`:266-268`),
  com os contadores `injecao_vazamento`, `injecao_sinal_ia` e `injecao_bordao`.
- Cenário `backend/tests/fixtures/programas/cenarios/h0_popular_sinais.json`: cópia de `popular_sertanejo.json` em que
  só mudam `id`, `descricao` e `injecoes`. Ele recebe três vazamentos (recusa, identidade de IA, cabeçalho `#`), um
  sinal denso e o slogan em três falas dentro de 30 minutos. Toda `frase` injetada é copiada de um texto do corpus.
  O implementador confere na rodada fake que nenhum validador da F3 à F6 tira a frase. Se algum tirar, troca a frase e
  registra o achado.
- As três fixtures de linha de base e o banco continuam intocados.

### 5.5 Skills (entrega 5)

- `.claude/skills/referencia-radio/SKILL.md`: seção "Sinais de IA na fala", com vazamentos (bloqueio), categorias do
  léxico (pontuação ou reescrita), o que não corrigir (formal, transição isolada, mistura de registro, reorientação),
  bordão (D4) e um ponteiro para o corpus.
- `.claude/skills/avaliar-locucao/SKILL.md`: dimensão "Soa como pessoa" (5 = não dá para dizer que é IA; 1 = tique de
  chatbot evidente) e as linhas `vazamento_grave`, `sinais_ia_media`, `sinais_ia_p90` e `bordao_repetido` na tabela
  automática. A partir da H1, `vazamento_grave > 0` reprova; `None` significa que a métrica não se aplica.

### 5.6 Linha de base: `docs/humanizacao/baseline.md` (gravada pelo `testador-locufy`)

1. **Ambiente:** commit, Python e Node, totais do `pytest -q --cov=app` e cobertura de `app/live`, `app/llm`,
   `app/tts` e `app/whatsapp`.
2. **Corpus:** contagens por grupo, categoria, canal e tom. Pipeline atual sobre os vazamentos: `_limpar_fala` seguido
   de `_preparar_sintese` em v3 e em v2/flash, num script temporário fora do repositório, como pede `avaliar-locucao`.
   Registrar quantos `trechos` chegam ao payload e quantos somem deixando a frase quebrada. Registrar também
   `oralidade.avisos` por grupo, só como informação.
3. **Conjunto:** contagens. Fica registrado que nenhuma entrada rodou ainda (executor pendente para H3 e H6).
4. **Simulação fake:** os três perfis com `--formato fixture` e os padrões da CLI (relógio da fixture, `--tts duble`,
   145 wpm, semente 7), mais o cenário H0. Gravar em `docs/humanizacao/h0/simulacao/<perfil>/` e
   `.../cenario_h0/`. Registrar todas as métricas, com as quatro novas em `None` até H1, H4 e H5, os contadores de
   injeção e se o texto injetado foi ao ar.
5. **`--modo llm` (só com a D9 aprovada):** a mesma rodada dos três perfis com `--confirmo-custo`, gravada em
   `docs/humanizacao/h0/simulacao_llm/<perfil>/`, com o comando de recálculo. Antes, o testador roda `--modo llm` sem
   `--confirmo-custo` (saída 3, sem rede, nada gravado; `simular_hora.py:29-31`, `:393`, `:416-418`) e passa a
   estimativa ao orquestrador. Referência das rodadas da F6: 7, 10 e 23 chamadas reais; a HEAD atual pode diferir. Sem
   aprovação, o item fica como "pendente D9".
6. **Decisões provisórias** usadas (§8 desta auditoria).

## 6. Testes a escrever antes do código

**Caracterização (antes de mexer em `metricas.py`, `dubles.py` e `fixtures.py`):**
1. Guardar em pasta temporária o `resumo.json` dos três perfis (fake, `--formato fixture`) na HEAD antes da H0. Depois
   da mudança, todas as chaves que já existiam precisam ficar iguais (portão §7.4).
2. Os testes byte a byte de `test_simulacao_f5.py` e `test_simulacao_f6.py` precisam ficar verdes sem nenhuma edição.

**Unitários:**
3. `tests/test_humanizacao_corpus.py`:
   - esquema;
   - ids únicos;
   - grupos e categorias declarados em `regras`;
   - mínimo de 5 por categoria de sinal;
   - presença das quatro subcategorias de "não corrigir" e das armadilhas listadas;
   - `trecho ⊂ texto`;
   - regra do algarismo;
   - tags v3 só em "não corrigir";
   - `conectivo_redacao` sem termos de `oralidade.BUROCRATICO` (achado 7);
   - tons e canais válidos;
   - `esperado.repeticao_estrutura` das sequências igual a `memoria.repeticao_estrutura` (detector que já existe);
   - nenhum teste chama `sinais_ia`, porque isso cabe ao `tests/test_sinais_ia.py` da H1.
4. `tests/test_humanizacao_conjunto.py`:
   - 60 entradas, 10 por tipo, ids e telefones únicos;
   - `tons` igual aos dois;
   - para cada entrada e cada tom, `FixturePrograma.model_validate` da fixture do `formato` com a persona do tom e a
     `entrada`/`por_tom` mesclada;
   - `musica_query` resolvida no catálogo, ou marcada como indisponível;
   - no WhatsApp, `mensagens_ouvinte` não vazio por tom.
5. `tests/test_simular_hora.py`:
   - `metricas_humanizacao` sem detector (`monkeypatch.setitem(sys.modules, "app.live.sinais_ia", None)`, sem
     `bordoes_repetidos`) devolve as quatro chaves como `None`;
   - com um detector dublê no `sys.modules` (`vazamentos` acusa "[", `pontuar` com nota conhecida) e um
     `bordoes_repetidos` dublê sobre `_as_run_artificial()`, devolve média, p90 e contagens esperadas;
   - p90 com n = 1, n = 10 e lista vazia;
   - fala vazia não entra na conta;
   - um `ModuleNotFoundError` de outro módulo sobe;
   - o dublê de LLM injeta as frases `vazamento`, `sinal_ia` e `bordao` e conta cada uma (no padrão de `:146-189`).

**Integração:**
6. Nos três perfis da fixture `simulacoes`: o `resumo.json` tem as quatro chaves, com valor `None` ou número.
7. Cenário H0 com o detector dublê:
   - `vazamento_grave` igual ao número de falas do as-run cujo texto contém uma frase injetada (consistência, não um
     número fixo, para sobreviver à H1);
   - contadores `injecao_*` ≥ 1;
   - `max_chamadas_llm_por_fala ≤ 2`;
   - `anuncio_sem_confirmacao`, `promessa_vencida` e `pedido_indevido` iguais a 0.
8. Cenário H0 igual a `popular_sertanejo.json`, exceto `id`, `descricao` e `injecoes`. Toda frase injetada existe no
   corpus.
9. Fumaça do conjunto: `simular("popular_sertanejo", pedidos_extra=[Pedido(**recado-01)])` recebe 5 pedidos, sem rede.
10. `recalcular_humanizacao.main` sobre o `_as_run_artificial` gravado em `tmp_path` devolve as quatro chaves.

**Simulação:**
11. CLI fake nos três perfis e no cenário H0, gravados em `docs/humanizacao/h0/simulacao/`: as métricas anteriores ficam
    iguais e a rede tem 0 tentativas.
12. Com a D9 aprovada, `--modo llm --confirmo-custo` nos três perfis, com o as-run gravado para recálculo.

## 7. Riscos e o que não fazer

**Riscos:**
- **Linha de base sem número.** Até a H1 e a H4, as métricas novas valem `None` e a meta de 50% só se mede com
  recálculo e `--modo llm`. Mitigação: gravar os textos e o comando de recálculo (fato 1). A meta exige uma rodada LLM
  aprovada.
- **Aceite fake trivial.** Os três perfis não têm vazamento. Mitigação: o cenário H0. Recomenda-se que o aceite da H1
  inclua esse cenário.
- **Remoção acidental por outro validador.** Um placeholder com nome pode sair pela F4 e esconder a lacuna.
  Mitigação: frases conferidas e o achado registrado (fato 4).
- **n pequeno e falas curtas.** O p90 fica próximo do máximo e a nota infla em falas curtas (fato 9). A H4 define o
  piso. A H0 registra o n.
- **Rótulo enviesado pelo léxico.** Escrever os textos já olhando a regex vira teste viciado. Mitigação: escrever os
  textos antes de qualquer regex (a H1 e a H4 vêm depois); não rotular `acima_do_limite` em sinal isolado; manter as
  armadilhas.
- **Formato sem executor.** O conjunto de 60 só ganha valor quando a H3 e a H6 tiverem executor (fato 8).
- **Custo de uma rodada por entrada no simulador de uma hora.** Rodar o conjunto entrada por entrada no simulador
  multiplica as chamadas reais. Não fazer.

**O que não fazer nesta frente:**
- Não criar `app/live/sinais_ia.py`, regex de vazamento ou léxico em `scripts/`, nem "provisório". A regra é um
  detector único (§8 do plano e precedente da F3).
- Não mexer em `banco_falas.py`, nas três fixtures, em `OBSERVACOES`, em `VERSAO_FORMATO` nem nas chaves dos eventos
  do as-run (fato 2).
- Não contar "ademais", "outrossim" nem "bem como" no grupo de sinais (achado 7).
- Não copiar as respostas fixas de `atendimento.py` para o corpus, nem textos de radialista real ou de outra emissora.
- Não rodar `--modo llm`, `conversa-teste`, `text-to-speech` nem `speech-to-text` sem aprovação, com estimativa (D9).
- Não ligar `oralidade_modo` nem criar flag em `settings`. Na H0 nada muda no ar.
- Não adaptar `conversa_teste.py` nem escrever o executor do conjunto. Isso fica como pendência para a H3 e a H6.

## 8. Decisões provisórias desta frente

| Id | Pergunta | Padrão provisório |
|---|---|---|
| DH0-1 | "Cada uma nos tons formal e informal": 60 entradas vezes 2 ou 30 + 30? | 60 entradas, cada uma nos dois tons, 120 casos. Patrocínio e WhatsApp trazem um texto por tom. |
| DH0-2 | Qual escala representa o tom no ao vivo? | `persona.formalidade` 4 (formal) e 2 (informal), nas fronteiras da D2. No WhatsApp, o registro do ouvinte. No patrocínio, o texto cadastrado. |
| DH0-3 | Quais bordões o simulador usa antes da H8? | O slogan da conta (subconjunto da D4). A recorrência de "Fica com a gente" fica para a H5 decidir (D4). |
| DH0-4 | Com que flags roda a linha de base? | `--formato fixture` e os padrões da CLI, semente 7, uma rodada por perfil. A variância do LLM não é medida e fica registrada. |
| DH0-5 | Onde gravar o conjunto? | `docs/benchmarks/<data da implementação>-humanizacao/casos.json`, sem mexer no de 06/11. |

Pendências a registrar em `docs/humanizacao/h0/pendencias.md`:
- executor do conjunto ao vivo, uma fala por entrada (H3);
- adaptador do conjunto para `conversa_teste.py` (H6);
- sinais medidos sobre os eventos `patrocinador` do as-run (H7);
- fonte de bordões cadastrados (H8);
- passo 3 da F8, reorientação permitida (H5);
- teste direto de `_limpar_fala` (H1).

Dependências: `vazamento_grave` depende da H1; `sinais_ia_media` e `sinais_ia_p90` dependem da H4; `bordao_repetido`
depende da H5 e, para bordões cadastrados, da H8; a nota real de partida depende da D9.

PRONTA PARA IMPLEMENTAR
