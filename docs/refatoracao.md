# Refatoração e saúde do código — Locufy

Nenhuma sugestão aqui muda comportamento observável. Cada uma diz que teste cobre o trecho
hoje; onde não há teste, está marcado **"sem cobertura"**.

---

## 1. Arquivos e funções grandes demais

### Top 10 backend (linhas)
```
2959  app/live/router.py
1442  app/config/router.py
 749  app/main.py
 746  app/llm/config_generator.py
 626  app/live/music.py
 517  app/whatsapp/webhook.py
 507  app/tts/client.py
 415  app/whatsapp/gestao.py
 412  app/llm/prompt_builder.py
 384  app/llm/client.py
```

### Top 10 frontend (linhas)
```
1553  frontend-painel/hooks/useLiveEngine.ts
 876  frontend-painel/components/EditarProgramaForm.tsx
 786  frontend-painel/app/vinhetagem/page.tsx
 617  frontend-painel/app/radialista/page.tsx
 537  frontend-painel/app/billing/page.tsx
 526  frontend-painel/app/conversas/page.tsx
 497  frontend-painel/lib/types.ts
 450  frontend-painel/components/RoteiroBlocosEditor.tsx
 441  frontend-painel/components/EditarRadialistaForm.tsx
 416  frontend-painel/app/ajuda/page.tsx
```

### Funções Python com mais de 60 linhas (via AST, 27 no total)
As mais relevantes:
```
1002  app/live/router.py:1732   gerar_proxima_fala      <- rota POST /proxima inteira
 243  app/llm/prompt_builder.py:170  montar_system_prompt
 242  app/whatsapp/webhook.py:276    receber_webhook
 239  app/live/music.py:362     buscar_musica
 144  app/billing/router.py:186 webhook_stripe
 124  app/whatsapp/atendimento.py:172  _atender
 120  app/live/music.py:421     escolher
 115  app/whatsapp/gestao.py:67 alterar_pedido
 104  app/live/router.py:1198   _escolher_query_musica
  98  app/llm/intent.py:23      classificar_intencao
```

### `app/live/router.py::gerar_proxima_fala` (1002 linhas) — separação HTTP vs. regra de negócio

**Cobertura hoje:** `tests/test_live_router.py` tem 111 testes, boa parte via `client`/HTTP
contra este endpoint (404 de radialista/programa inexistente, atalho de patrocinador, atalho
de vinheta, encerramento por horário, diálogo multi-voz, música de fundo). São testes de
integração (entram pelo HTTP e conferem o `LiveProgramResponse`), não testes unitários da
lógica pura isolada do framework — é sinal bom para extrair com segurança, mas ao extrair vale
adicionar testes unitários das funções puras que saírem da rota.

O que é HTTP (deveria ficar em `app/live/router.py`):
- Assinatura da rota (`radialista_id`, `programa_id`, `dados: LiveProgramRequest`);
- `_buscar_radialista`/`_buscar_programa` (404);
- Serialização final em `LiveProgramResponse`.

O que é regra de negócio (candidato a sair para módulos novos):
- **`app/live/roteiro.py`** — escolha do tipo/categoria do próximo bloco: `_tipo_proximo_bloco`,
  `_categoria_bloco`, `_ultima_categoria_bloco`, lógica de `perto_do_fim`/encerramento,
  montagem do `system_prompt_linhas` (hoje inline, linhas ~1744-2462).
- **`app/live/service.py`** — orquestração que hoje vive dentro da própria
  `gerar_proxima_fala`: decidir patrocinador vs. vinheta vs. música vs. fala, chamar o roster
  (`_buscar_roster`), decidir multi-voz, gerar e revisar a fala (`_gerar_falas_bloco`, retry por
  repetição/orçamento/atribuição).
- **`app/live/repeticao.py`** — todo o acesso a Redis para não repetir conteúdo:
  `_historico_musicas`/`_registrar_musica_tocada`, `_historico_temas`/`_registrar_tema`,
  `_proxima_variacao` (rotação), `_historico_falas`/`_registrar_fala`, `_ultimo_tom`.
- Seleção de música (`_buscar_musica_para_bloco`, `_escolher_query_musica`) já está mais
  isolada — poderia ir para `app/live/service.py` ou ficar como está, é menos urgente.

## 2. Texto de prompt misturado com código

**Cobertura hoje:** `tests/test_llm_prompt_builder.py` testa `montar_system_prompt` via texto
final gerado (snapshot-like, comparando substrings esperadas) — cobre razoavelmente o
conteúdo, mas nada testa os fragmentos de `live/router.py` isoladamente (eles só são exercitados
indiretamente pelos testes de integração do item 1).

Os blocos de instrução hoje ficam como f-strings soltas em dois lugares:
- `app/llm/prompt_builder.py::montar_system_prompt` (243 linhas, já é praticamente só prompt —
  esse já está relativamente centralizado, o problema maior é o próximo);
- `app/live/router.py`, espalhado entre as linhas ~1744 e ~2462 (dentro de
  `gerar_proxima_fala`): avisos de repetição, instruções de reação a ouvinte, instrução de
  formato musical, instrução de dialogo multi-voz.

Proposta de módulo `app/live/prompts.py` (ou pasta `app/live/prompts/`), separando por
dependência:
- **Fixo** (não muda entre chamadas): `_INSTRUCAO_REACAO_POR_NATUREZA`,
  `_VARIACOES_FORMATO_COMENTARIO`, `_VARIACOES_VERBO_IDENTIFICACAO`,
  `_VARIACOES_CONVITE_OUVINTE` — já são constantes no topo do arquivo, só precisam mudar de
  arquivo.
- **Depende de config** (`programa`/`account`): trechos que hoje ficam dentro de
  `montar_system_prompt` (tópicos, gêneros, fontes de notícia/pesquisa) — já isolados lá.
- **Depende de estado de sessão** (Redis: `temas_usados`, `historico_falas_categoria`,
  `ultima_categoria`, `assunto_escolhido`): esses são os que hoje moram dentro de
  `gerar_proxima_fala` porque precisam do resultado das consultas a Redis feitas ali — ao
  extrair para `app/live/repeticao.py` (item 1), essas funções de prompt podem virar funções
  puras que recebem o estado já carregado como parâmetro.

## 3. Duplicação real

**Cobertura hoje:** todas as duplicatas abaixo são funções puras já exercitadas
indiretamente pelos testes dos módulos que as usam (`test_llm_client.py`,
`test_llm_config_generator.py`, `test_news_worker.py`, `test_news_pauta.py`,
`test_tts_client.py`, `test_live_music.py`, `test_live_router.py`, `test_topics_matcher.py`) —
nenhuma tem teste unitário dedicado à função em si.

- **`_sem_acento` — idêntica, copiada em 8 arquivos:**
  `app/llm/client.py:272`, `app/llm/config_generator.py:359`, `app/news/worker.py:41`,
  `app/news/pauta.py:63`, `app/tts/client.py:207`, `app/live/music.py:63`,
  `app/live/router.py:1061`, `app/topics/matcher.py:41`. Todas byte-a-byte iguais:
  ```python
  def _sem_acento(texto: str) -> str:
      return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")
  ```
  Helper único: `app/util/texto.py::sem_acento`.

- **`", ".join(x) if x else "<padrão>"` — repetido 8 vezes:**
  `app/llm/prompt_builder.py:176-182,369` (7 ocorrências) e
  `app/guardrails/content_filter.py:30`. Helper único proposto:
  `lista_ou(lista: list[str] | None, padrao: str) -> str`.

- **Validação de voz duplicada:** `app/patrocinadores/router.py:53-57` (`_validar_voz`, devolve
  o valor) e `app/config/router.py:333-335` (`_validar_voz`, devolve `None`) são dois wrappers
  quase idênticos em cima de `app/tts/voices.py::voz_valida_para_conta`, cada um levantando o
  mesmo `HTTPException(400, "Voz invalida")`. `app/live/router.py:2808` faz a mesma checagem
  inline, sem usar wrapper nenhum. Proposta: mover um único `validar_voz_ou_400(db, account,
  voz_id)` para `app/tts/voices.py` e usar nos três lugares.

- **Categorização de bloco não é duplicação de verdade:** `app/live/router.py::_categoria_bloco`
  (prefixo/match direto) e `app/llm/client.py::classificar_categoria_bloco` (fallback via LLM,
  chamado de `live/router.py:1072-1081` só quando o prefixo não bate) formam um pipeline de
  duas camadas complementares, não código copiado — não precisa mexer.

## 4. Padrões repetidos em rotas e modelos

**Cobertura hoje:** cada `_buscar_*` é exercitado pelos testes do próprio router
(`test_patrocinadores_router.py`, `test_biblioteca_audio_router.py`,
`test_categorias_vinheta_router.py`, `test_config_router.py`, `test_metrics_router.py`,
`test_live_router.py`, `test_atendimento_ouvintes.py`) via caso de 404 — não há teste de um
helper genérico porque ele não existe ainda.

O padrão "buscar por id, filtrar por `account_id`, 404 se não achar" aparece, com o mesmo
formato, em pelo menos 8 lugares: `patrocinadores/router.py:69-73`,
`biblioteca_audio/router.py:46-50`, `categorias_vinheta/router.py:35-39`,
`config/router.py:314-330` (dois: radialista e programa), `live/router.py:241-252` (idem,
duplicado do de `config/router.py`), `metrics/router.py:69-73`, `admin_sistema/router.py:173-177`,
`whatsapp/gestao.py:53-63`. Proposta: uma dependência FastAPI parametrizada por modelo
(`def buscar_ou_404(Model, campo_id="id")`) ou uma função de repositório genérica
`buscar_escopado(db, Model, id_, account_id, mensagem_erro)` — reduziria ~8 implementações a
uma, mantendo a mensagem de erro customizável por chamada.

Nota: `app/config/router.py::_buscar_radialista`/`_buscar_programa` e
`app/live/router.py::_buscar_radialista`/`_buscar_programa` são **duplicatas exatas entre si**
(mesmo nome, mesmo corpo) — candidatos óbvios a virar um só em `app/config/repositorio.py` (ou
onde o helper genérico acima for parar), importado pelos dois routers.

**Defaults de lista/dict vazios, declarados em três lugares independentes** para os mesmos
campos de `Programa` (`topicos_permitidos`, `generos_musicais`, `musicas_bloqueadas`,
`feriados_municipais`, `fontes_pesquisa` etc.):
1. DDL de migração inline: `backend/app/main.py` (dict `_COLUNAS_CONTEUDO_PROGRAMA`, ex.
   `"topicos_permitidos": "JSON DEFAULT '[]' NOT NULL"`, linha ~345-363);
2. Schema Pydantic: `backend/app/config/router.py:126,136,138,144,149`
   (`Field(default_factory=list)`);
3. Frontend: `frontend-painel/lib/types.ts:288-309` (`normalizarPrograma`, `p.campo ?? []`).

Os três precisam ser mantidos sincronizados manualmente hoje — adicionar um campo novo exige
lembrar de editar os três. Não há um jeito barato de unificar entre backend (Python/SQL) e
frontend (TypeScript) sem gerar código; o ganho realista de curto prazo é documentar essa
tríade num comentário em cada um dos três apontando para os outros dois, para reduzir o risco
de esquecer um ao adicionar campo novo — mudar a arquitetura em si (ex. gerar `types.ts` a
partir do schema Pydantic) é uma refatoração grande, não recomendo agora.

## 5. Acoplamento com serviços externos

**Cobertura hoje:** cada cliente externo tem teste próprio com mock/monkeypatch
(`test_llm_client.py`, `test_noticias.py`, `test_tts_client.py`, `test_live_spotify.py`,
`test_whatsapp_sender.py`, `test_whatsapp_session_manager.py`, `test_weather_client.py`) — a
falta de uma fronteira única não significa falta de teste, significa que o monkeypatch é feito
módulo a módulo (`monkeypatch.setattr("app.tts.client.httpx.Client", ...)` etc.), exatamente o
padrão frágil que o pedido original queria evitar.

Pontos de acoplamento direto encontrados:
- **Anthropic**: instanciado **duas vezes**, com configurações diferentes —
  `app/llm/client.py:10` (`Anthropic(api_key=...)`, sem timeout/retry explícitos, usa defaults
  do SDK) e `app/llm/noticias.py:19` (`Anthropic(api_key=..., timeout=25.0, max_retries=0)`).
  Isso é inconsistência de configuração, não só duplicação de import.
- **ElevenLabs**: `app/tts/client.py` (507 linhas, 6 `httpx.Client(...)` diferentes com
  timeouts distintos: 3s a 60s).
- **YouTube**: `app/live/music.py` (3 chamadas `httpx.get` diretas).
- **Spotify**: `app/live/spotify.py`.
- **WuzAPI**: `app/whatsapp/session_manager.py` (7 chamadas) + `app/whatsapp/sender.py`.
- **Redis**: importado diretamente (`from app.config.redis_client import redis_client`) em
  pelo menos 10 módulos (`live/router.py`, `live/prewarm.py`, `whatsapp/webhook.py`,
  `billing/router.py`, `llm/noticias.py`, `live/spotify.py`, `weather/client.py`, entre
  outros), sem wrapper.

Todos os pontos **já têm timeout explícito por chamada** (confirmado por grep — nenhum
`httpx.get`/`httpx.Client(...)` sem `timeout=`) e a maioria já tem fallback/try-except
degradando graciosamente (ex. `weather/client.py`, `live/spotify.py`, `llm/noticias.py`). O
ganho de uma fronteira fina não é "adicionar resiliência que falta" (ela já existe, espalhada),
é **consolidar** timeout/retry num só lugar por serviço e permitir mock por injeção de
dependência em vez de `monkeypatch` por string de módulo. Proposta: um cliente por serviço
(`app/tts/client.py` já é quase isso; replicar o padrão para Anthropic — um único
`app/llm/anthropic_client.py` usado por `llm/client.py` e `llm/noticias.py`).

## 6. Código morto e inconsistências

**Ruff (`F401` imports não usados, `F841` variáveis não usadas) rodado sobre `backend/app`:
zero ocorrências reais** — os 3 únicos avisos são em `app/models/__init__.py`
(`ConversaOuvinte`, `MensagemOuvinte`, `FunnelEvent`), que são re-exports intencionais para
registrar os modelos no metadata do SQLAlchemy (mesmo padrão documentado no comentário do
próprio arquivo para os outros imports da lista), não código morto de verdade. **Não encontrei
função, endpoint ou campo de modelo obviamente sem uso** dentro do tempo desta auditoria — não
rodei uma ferramenta de dead-code cross-module (tipo `vulture`) nem um equivalente de
`ts-prune` no frontend, então isso é **"não verificado exaustivamente"**, não "confirmado limpo".

**Nomenclatura `radialista` / `radio_config` / `locutor`:** os três termos coexistem, mas de
forma consistente por camada — `RadioConfig` é o nome do model/tabela (`radio_configs`),
`radialista`/`radialista_id` é o termo usado em rotas, variáveis e parâmetros de URL,
`nome_locutor`/`locutor_nome` é especificamente o campo de nome exibido. Não é uma mistura
aleatória, é um vocabulário de três camadas já usado de forma previsível em todo o código que
li. Renomear para unificar (ex. tudo virar `radialista`) exigiria migração de coluna/tabela
(`radio_configs` → `radialistas`) e tocaria dezenas de arquivos (todo import de `RadioConfig`)
para um ganho cosmético — **não recomendo**, custo não compensa.

## 7. Ordem de execução (impacto ÷ risco)

### Faixa 1 — hoje, sem risco (máximo 3 itens)
1. **Extrair `_sem_acento` para `app/util/texto.py`** e trocar os 8 imports. Função pura,
   byte-idêntica nas 8 cópias, comportamento não muda. Menor ponto de partida possível.
2. **Extrair o padrão `", ".join(x) if x else padrao` para um helper `lista_ou(...)`** em
   `app/llm/prompt_builder.py` + `app/guardrails/content_filter.py`. Também puro, saída
   idêntica, já coberto pelos testes de `prompt_builder`/`content_filter` existentes.
3. **Unificar `_validar_voz`** (`patrocinadores/router.py` + `config/router.py`) num único
   `validar_voz_ou_400` em `app/tts/voices.py`. Coberto pelos testes de patrocinadores e config
   já existentes (ambos testam voz inválida → 400).

### Faixa 2 — vale, mas escreva teste antes
- **Helper genérico de "buscar por id + account_id + 404"** (item 4): toca 8 arquivos; antes
  de generalizar, escrever um teste de contrato (mensagem de erro, status code) que hoje só
  existe implicitamente espalhado pelos testes de cada router.
- **Consolidar os dois clientes Anthropic** (`llm/client.py` + `llm/noticias.py`) num só,
  decidindo timeout/retry únicos: hoje divergem de propósito (chat costuma ser rápido, busca
  usa `max_retries=0` de propósito por causa do `pause_turn` handling) — escrever teste que
  trave esse comportamento (timeout efetivo, contagem de retries) antes de unificar, para não
  perder a diferença intencional sem perceber.

### Faixa 3 — grande demais por agora
- **Separar `gerar_proxima_fala` (1002 linhas) em router + `service.py` + `roteiro.py` +
  `repeticao.py`** (item 1): valioso, mas é a função central do produto (fala ao vivo); fazer
  isso com segurança pede não só os 111 testes de integração que já existem, mas testes
  unitários novos para cada peça extraída — melhor fazer depois que a Faixa 2 (helpers menores)
  já tiver reduzido o tamanho do arquivo.
- **Quebrar `frontend-painel/hooks/useLiveEngine.ts` (1553 linhas)**: não investiguei a
  cobertura de teste do lado frontend (`frontend-painel/hooks/__tests__`) a fundo o bastante
  para propor um plano de extração seguro agora — precisa de uma auditoria específica do
  frontend antes.
