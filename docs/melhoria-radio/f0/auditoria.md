# Auditoria F0: linha de base e bancada de testes

Branch auditada: `melhoria/plano-radio` (código igual à `master`, último commit `3ff9eeb`), em 06/11/2026.
Só leitura no código. Fontes: `docs/plano-melhoria-radio.md` (F0 e Transversal),
`docs/pesquisa-radio-locufy.md` (§9, §10, §14 e "Próxima pesquisa de campo"), skills
`referencia-radio` e `avaliar-locucao`, `docs/auditoria.md`, `docs/refatoracao.md`.

## 1. Estado atual: o plano confere com o código?

| Afirmação do plano | Situação | Evidência |
|---|---|---|
| "77 arquivos em `backend/tests`" | **diferente** | São 75 `test_*.py`, mais `conftest.py` e `fixtures/`. `pytest --collect-only`: 1120 testes. |
| CI com `ruff check app tests` e `pytest --cov=app` | confirmado | `.github/workflows/backend-ci.yml:37,40`. O CI instala ffmpeg (`:25`). `scripts/` **não** passa pelo ruff do CI. |
| Painel com `vitest run` | confirmado | `.github/workflows/frontend-ci.yml:35` (`npm run test:coverage`) |
| `benchmark_falas.py` e `conversa_teste.py` consomem créditos reais | confirmado | `backend/scripts/benchmark_falas.py:1` ("consome créditos"). `conversa_teste.py:1-9` usa o webhook real com LLM e exige Postgres e Redis locais. |
| Não há simulação de uma hora de programa | confirmado | Não existe `simular_hora.py`. O único `as_run` citado está nos documentos do plano e das skills. |
| Entrega 1: linha de base (`baseline.md`) | **já resolvido** | `docs/melhoria-radio/baseline.md`: ruff limpo, 1120/1120 testes, 85% de cobertura, vitest 300/300. O `npm run lint` do painel já falhava antes. Falta preencher a seção "Simulação" depois que o simulador existir. |
| Entregas 2, 3 e 4 (simulador, fixtures, `casos.json`) | ausentes | Não existem `backend/tests/fixtures/programas/` nem `docs/benchmarks/2026-11-06-formatos/` |

## 2. Fatos do código que o simulador precisa reproduzir

Sem estes pontos, a simulação mede outro sistema, não o que vai ao ar.

**Rota real (`POST /live/{rid}/programas/{pid}/proxima`, `backend/app/live/router.py:1899-2957`).**
- O pedido traz `historico`, `total_falas`, `ultima_fala`, `incluir_audio` e `perfil_pos_producao` (`router.py:96-110`).
- Limite de 60 chamadas por minuto por conta, com balde de tempo do Redis (`:1915`, `app/guardrails/http_rate_limit.py:11-29`).
- O encerramento acontece quando `minutos_restantes ≤ 3` no momento da **geração** (`:329`, `:1931`, `app/guardrails/schedule.py:66-94`).
- Vinhetas (`:1943-1961`) e patrocinadores (`:1963-1978`) saem sem LLM. Bloco de notícia sem fonte vira música (`:1980-1991`).
- No formato musical, o bloco de música **sem pedido** volta com `fala=""`, sem LLM e sem TTS (`:2060-2076`).
- Só o formato musical tem orçamento: `duracao_alvo_segundos` (`:2948`, vindo de `app/live/formato.py:13-19`). O texto passa por uma única revisão se ultrapassar o limite de palavras (`:2706-2760`).
- Fala que cita música faz essa música tocar no formato padrão. No formato musical, isso não acontece (`:2762-2781`).
- Pedidos de ouvinte seguem dois fluxos, escolhidos por `Account.atendimento_ouvinte_ativo` (padrão `False`):
  - Legado: o pedido é marcado como atendido **na seleção, antes de tocar** (`_proximo_pedido_fila_dentre`, `:1782-1804`).
  - Novo: `selecionar` passa o pedido para `selecionado` com um token (`app/whatsapp/atendimento.py:85-127`). Ele só vira `executado` depois que o player chama `POST /ouvintes/pedidos/{id}/reproducao` (`app/whatsapp/gestao.py:190-216`).
- Pontos que dependem do tempo:
  - `agora_local` (`router.py:2011`)
  - as janelas `:1220`, `:1385`, `:1409` e `:1816`
  - `ocorrencia`, `expirar` e `programa_no_ar` (`atendimento.py:33-82`, `schedule.py:18-35`)
  - o contexto de data, hora e clima do prompt (`app/llm/prompt_builder.py:156-178`)
- Pontos aleatórios, todos no `random` global:
  - `router.py:688-691`, `:753`, `:1313`, `:1318`, `:1330`, `:1704`
  - `router.py:2129`, `:2298`, `:2306`, `:2541`, `:2550`
- O tema de comentário e de notícia é registrado numa **thread solta** (`:1426-1445`, chamada em `:2787`).
- O prompt consulta o clima em `obter_clima_atual`, o que vai à rede quando `Account.cidade` está preenchida (`prompt_builder.py:178`, `app/weather/client.py:83-110`).

**Player (o que define *quando* cada bloco é gerado e o que vai ao ar).**
- **Ele prepara dois blocos à frente.** `FilaPreparo` tem `antecedencia = 2` (`frontend-painel/lib/filaPreparo.ts:16`). Vinhetas não contam nessa reserva e o teto é de 12 blocos (`:25-29`, `:49-58`). Quando o bloco N começa a tocar, o bloco N+2 já está sendo gerado (`retirar`, `:63-69`).
- O contexto avança na geração, não na reprodução (`useLiveEngine.ts:1490-1495`). Por isso o `historico` enviado já inclui blocos que ainda não foram ao ar, e o `total_falas` cresce por `passos_roteiro` (`:1253`, `:1493`).
- A fila começa a encher 90 s antes de `horario_inicio` (`ANTECEDENCIA_PREPARO_SEGUNDOS`, `useLiveEngine.ts:37`). Não há espera entre blocos (`INTERVALO_PROGRAMA_MS = 0`, `:29`). A pausa é `pausa_antes_ms`, limitada a 0–5000 ms, com 350 ms quando vem nula (`frontend-painel/lib/continuidadeAudio.ts:17-21`).
- Formato da linha de histórico: `"{tipo}: {fala} [Música(s) tocada(s) nesse bloco: Título - Canal, ...]"`, com as últimas 8 em ordem cronológica (`useLiveEngine.ts:1241-1245`, `:1315-1322`).
- O player confirma a participação ao fim do bloco com `executado`, `falhou` ou `interrompido` (`:1572-1580`, `:1648-1655`). Depois do `encerramento`, ele para (`:1663-1680`).
- **Programa iniciado pelo agendamento tem corte seco em `horario_fim`.** O watchdog roda a cada 1 s e chama `pausarPrograma()` quando `programaNoAr` fica falso, ou seja, em `horario_fim` + 1 s (`useLiveEngine.ts:1947-1961`, `:87-90`).

**Consequência para a linha de base (hipótese a confirmar na primeira rodada).** A decisão de
encerrar acontece cerca de dois blocos antes de ir ao ar. No formato musical isso equivale a
cerca de 8 min. Com o corte seco, a fala de encerramento tende a ser cortada ou a nem ir ao ar.
Esse é o problema que a F1 precisa atacar. Também afeta o desenho da F1: o relógio precisa ser
consultado com o **horário previsto de reprodução**, e não com o horário da geração.

## 3. Testes existentes que tocam esta frente

- `backend/tests/conftest.py`:
  - Variáveis de ambiente falsas (`:13-31`), entre elas `ELEVENLABS_API_KEY=""`, que desliga o TTS.
  - `redis.from_url` passa a apontar para o fakeredis (`:38`).
  - Fixtures automáticas trocam por dublês `pesquisar_noticias` via `_client` (`:65`), `classificar_tema_fala` (`:73`), `extrair_musicas_citadas` (`:97`), `itens_fora_do_genero` (`:104`), o gerador de vinhetas (`:113`) e `obter_metadados_voz` (`:202`).
  - Banco SQLite em memória com `StaticPool` (`:124-138`). `TestClient` sem `with`, para não disparar o startup (`:141-157`). JWT real pelo `auth_headers` (`:193`).
- `backend/tests/test_live_router.py` tem mais de 111 testes de integração do `/proxima`, todos com `@freeze_time` (`:7`, `:30`) e `monkeypatch` por string em `app.live.router.*`.
  - A fixture `programa_musical` (`:2924-2932`) cobre música sem LLM (`:2936`), a sequência musical (`:2961`), a revisão por orçamento (`:2973`), o pedido no formato musical (`:2996`) e o encerramento perto do fim (`:3015`).
  - Nenhum teste encadeia blocos. Todos os testes atuais são de uma chamada só.
- `freezegun==1.5.1` e `fakeredis==2.26.2` já estão em `requirements-dev.txt`. Não é preciso nenhuma dependência nova.

## 4. Itens transversais de `docs/auditoria.md`

| Item | Situação hoje | Evidência | Onde entra |
|---|---|---|---|
| 4: rate limit nos endpoints pagos | **parcialmente resolvido** | Limites por conta: `/proxima` 60/min (`router.py:1915`), `/tts` 90/min (`:3105`), `musica-substituta` 20/min (`:3036`). Testes em `test_live_router.py:202,224`. Quem sai da equipe já perde o acesso, porque `get_current_usuario` exige `usuario.ativo` (`app/auth/dependencies.py:45-47`). **Continua aberto:** o JWT vale 7 dias (`app/config/settings.py:18`) e não é revogado na troca de senha (`app/auth/router.py:241,298`; o token não tem versão, `app/auth/security.py:32-37`). | Fora do plano de rádio: segurança e autenticação. Não afeta o comportamento ao vivo. Registrar como pendência no `RELATORIO.md`. |
| 5: race condition na fila | **resolvido** | `.with_for_update(skip_locked=True)` em `router.py:1796` e `atendimento.py:118`. Nenhum teste cobre isso, porque o SQLite ignora `FOR UPDATE`. | Nada a fazer. A F4 deve lembrar que `skip_locked` só funciona no Postgres. |
| 6: timeout do Redis | **aberto** | `app/config/redis_client.py:5` chama `redis.from_url(...)` sem `socket_connect_timeout` nem `socket_timeout`. Cada `/proxima` faz dezenas de chamadas ao Redis, a começar por `limite_excedido`. | **F3** (estado confiável da emissão). O `ContextoEmissao` lê histórico, temas, tom e rotação do Redis. Definir o timeout e a degradação quando o Redis cair (falhar aberto, sem histórico), com teste. A contingência "Redis fora" entra depois na F11. |
| 9: TTL do cache de categoria | **aberto** | `_CACHE_CATEGORIA_CUSTOMIZADA` recebe `hset` sem `expire` (`router.py:1107-1120`). | **F6** (catálogo de formatos). A F6 torna declarativa a categoria dos blocos de cada formato. Aproveitar para pôr TTL longo ou teto no hash. |

Da `docs/refatoracao.md`: o §1 (separar `gerar_proxima_fala`, 1059 linhas hoje) é da F3, e o
simulador da F0 vira o arnês de caracterização dela. O §5 trata do acoplamento externo, que hoje é
resolvido com monkeypatch por string. Por isso o simulador **não pode depender só do caminho
textual dos dublês** (ver §5.3).

## 5. Desenho da mudança

A F0 não muda nada em `app/`, não cria migração, não muda contrato de API e não mexe no painel.
É uma frente só de medição.

### 5.1 Arquivos novos

| Arquivo | Conteúdo |
|---|---|
| `backend/scripts/simular_hora.py` | CLI e função `simular(...)`. Não importa `app.*` no topo do arquivo. |
| `backend/scripts/simulacao/ambiente.py` | Preparação do ambiente (variáveis, fakeredis, SQLite, bloqueio de rede) |
| `backend/scripts/simulacao/dubles.py` | Dublês de LLM, TTS, música, notícia e clima |
| `backend/scripts/simulacao/emissao.py` | Fila de preparo, reprodução, watchdog e pedidos (o laço da hora) |
| `backend/scripts/simulacao/metricas.py` | Detectores provisórios e `resumo.json` |
| `backend/scripts/simulacao/fixtures.py` | Modelos Pydantic das fixtures (relógio, programa, catálogo, pedidos, injeções) |
| `backend/tests/fixtures/programas/{musical_adulto,popular_sertanejo,variedades_leves}.json` | Os três perfis, únicos `*.json` no topo da pasta, porque o testador percorre o topo |
| `backend/tests/fixtures/programas/relogios/{A_musical_companhia,B_jornal_revista,C_morning_variedades}.json` | Relógios da §9 |
| `backend/tests/fixtures/programas/catalogos/{musical_adulto,popular_sertanejo,variedades_leves}.json` | Músicas fictícias com duração |
| `backend/tests/test_simular_hora.py` | Testes (§6) |
| `docs/benchmarks/2026-11-06-formatos/casos.json` | Conjunto de casos de avaliação |
| `docs/melhoria-radio/f0/simulacao/<perfil>/{as_run,resumo}.json` | Saídas da linha de base |
| `docs/melhoria-radio/baseline.md` | Preencher a seção "Simulação" |

`backend/scripts` não tem `__init__.py`. Com `pythonpath = .` (`backend/pytest.ini`), o
`import scripts.simular_hora` funciona como pacote de namespace. `scripts/simulacao/` ganha
`__init__.py`. Rodar `ruff check scripts/simular_hora.py scripts/simulacao` à mão, porque o CI
não cobre `scripts/`.

### 5.2 Execução: CLI e API

```
PYTHONPATH=. .venv/bin/python scripts/simular_hora.py --programa tests/fixtures/programas/musical_adulto.json \
    --saida /tmp/sim/musical_adulto [--modo fake|llm|completo] [--semente 7] [--wpm 145] \
    [--relogio A|B|C|<caminho>] [--antecedencia 2] [--preparo-antecipado-s 90] \
    [--corte agendado|manual] [--confirmo-custo]
```

- `--programa` aceita o caminho ou o id (`musical_adulto`). A saída é `<saida>/as_run.json` e `<saida>/resumo.json`, mais uma linha-resumo no stdout.
- `--modo fake` é o padrão.
- `--modo llm` e `--modo completo` sem `--confirmo-custo` primeiro rodam o modo fake, imprimem a estimativa (falas que chamariam LLM ≈ falas do fake × 1,2 por causa das revisões; caracteres de TTS no modo completo) e saem com código 3. Os agentes só passam `--confirmo-custo` com aprovação explícita do usuário. O auditor não estima preço em dinheiro: quem aprova consulta a tabela vigente.
- Códigos de saída: 0 quando a simulação terminou (as métricas não mudam o código), 2 em erro ou em tentativa de rede no modo fake, 3 quando falta confirmação.
- API para os testes: `simular(programa, modo="fake", semente=7, wpm=145, saida=None, relogio=None, antecedencia=2, preparo_antecipado_s=90, corte="agendado") -> Resultado(as_run: dict, resumo: dict)`.

**Preparação do ambiente.** Só acontece em `main()`, antes de importar `app.*`. Nos testes, quem
faz isso é o `conftest`.
- Em todos os modos:
  - `redis.from_url` aponta para o fakeredis.
  - `SENTRY_DSN=""`, `IA_MEDICAO_HABILITADA=false`, `IA_ORCAMENTO_BLOQUEAR=false` (`encerrar_contexto` não toca no banco, `app/billing/contexto_ia.py:233-240`).
  - `STORAGE_BACKEND=local`, `YOUTUBE_API_KEY=""`, `SPOTIFY_*=""`.
  - Valores falsos para `WUZAPI_*`, `JWT_SECRET` e `STRIPE_*` quando faltarem.
- No modo fake: `ANTHROPIC_API_KEY` falsa e `ELEVENLABS_API_KEY=""`.
- No modo llm: mantém a chave da Anthropic do `.env` e zera a da ElevenLabs.
- No modo completo: mantém as duas.
- As variáveis de ambiente se sobrepõem ao `.env` (`app/config/settings.py:123`).

**Banco e autenticação.**
- Banco próprio em SQLite `sqlite://` com `StaticPool`, `check_same_thread=False` e `Base.metadata.create_all`. A simulação não precisa de Postgres.
- `TestClient(app)` sem `with`, como em `conftest.py:141-157`. Sobrescrever só `get_db`. A autenticação é real: `Usuario` admin e `criar_token`.
- Guardar e restaurar `app.dependency_overrides`.
- Guardar e restaurar `random.getstate()`, para não contaminar outros testes.
- Rodar `redis_client.flushall()` no início de cada simulação.

### 5.3 Dublês: o que substituir

Dois mecanismos, aplicados juntos com `contextlib.ExitStack` e `unittest.mock.patch`:

- **Por nome**, em `app.live.router.<nome>`, que é o padrão atual dos testes.
- **Por identidade.** Percorrer `sys.modules` e trocar todo atributo que *seja* a função original. Isso continua valendo quando a F3 mover chamadas para `app/live/contexto.py` ou `service.py`.

Um **bloqueio de rede** no modo fake troca `socket.getaddrinfo`, `socket.create_connection`,
`socket.socket.connect` e `connect_ex` por funções que contam a tentativa e levantam exceção.
O contador vai para `resumo.tentativas_rede` e o teste exige 0. O `TestClient` não abre sockets.

| Alvo (onde é chamado) | fake | llm | completo |
|---|---|---|---|
| `app.llm.client.gerar_resposta` (`router.py:2676`) | **DubleLLM** (abaixo) | real | real |
| `app.llm.client.gerar_dialogo_multivoz` (`:2678`) | DubleLLM em JSON `{"linhas": [...]}` | real | real |
| `classificar_fio_condutor` (`:2814`) | `""` | dublê | dublê |
| `classificar_categoria_bloco` (`:1114`) | mapa determinístico, padrão `"comentario"`. As fixtures só usam rótulos conhecidos. | dublê | dublê |
| `classificar_tema_fala` e `_registrar_tema_em_background` (`:1426-1445`) | troca por versão **síncrona**: tema determinístico + `_registrar_tema` + `_registrar_tema_persistente` na sessão da simulação, sem thread | idem | idem |
| `extrair_musicas_citadas` (`:1529`) | títulos do catálogo e das injeções presentes no texto, menos os já tocados | dublê | dublê |
| `itens_fora_do_genero` (router e `app.live.spotify`) | `set()` | dublê | dublê |
| `sugerir_musica_do_genero` (`:1334`) | primeira faixa do gênero no catálogo | dublê | dublê |
| `resumir_contexto_musica` (`:1468`) | campo `contexto` da faixa ou `""` | dublê | dublê |
| `buscar_musica` (`:2028`, `:1629`, `:1652`, `:1559`) | catálogo (§5.5) | catálogo | catálogo |
| `resolver_musica_catalogada` (`:1269`, `:1548`, `:1707`) | correspondência exata no catálogo | catálogo | catálogo |
| `buscar_faixas_por_categoria` (`:1328`, `:1703`) | `[(artista, titulo)]` do gênero, sem os já tocados | catálogo | catálogo |
| `pesquisar_noticias` (`:2460`) e `app.llm.noticias._client.messages.create` | `PesquisaNoticias(status="desabilitada")` | dublê | dublê |
| `app.llm.prompt_builder.obter_clima_atual` | `None` (o clima só entra depois da F5) | dublê | dublê |
| `tts_habilitado`, `sintetizar_audio`, `processar_audio`, `obter_metadados_voz` | TTS desligado; duração estimada | desligado; estimada | **real**, via `POST /live/{rid}/tts` como o player faz (`useLiveEngine.ts:1383-1392`) |

Não trocar por dublê `limite_excedido`, `selecionar`, `_proximo_pedido_fila_dentre`,
`minutos_restantes`, `_tipo_proximo_bloco` nem nenhum Redis ou banco. Tudo isso faz parte do
caminho real que está sendo medido.

**DubleLLM (`gerar_resposta(system, mensagem)`).** Ler o mínimo do prompt, porque o texto do
prompt muda nas frentes seguintes.
- **Tipo do bloco:** vem da mensagem, `"Tipo do próximo bloco: (.+)\."` (`router.py:2667`).
- **Música confirmada:** canal lateral. O dublê de música grava em `estado_chamada.faixa` a faixa que devolveu nesta chamada. O simulador zera esse estado antes de cada `/proxima`. Não usar regex sobre o "anuncie exatamente a música…".
- **Pedido desta chamada:** o simulador tira um retrato dos estados de `FilaAoVivo` antes da chamada. O dublê consulta, na mesma sessão, a linha que mudou para `selecionado` ou `historico_legado`, e usa o `nome` dela. Se `pedido.musica_query` não bater com a faixa confirmada, gera a fala de "não achei a pedida, vai esta no lugar".
- **Orçamento:**
  - Formato musical: `app.live.formato.orcamento_fala(tipo, primeira)`, a mesma função do backend.
  - Formato padrão: `orcamento_ref_s[categoria]` da fixture.
  - Número de palavras alvo: `round(wpm × alvo_s / 60)`, limitado ao máximo de palavras quando ele existir.
- **Revisão:** se o prompt tiver "ficou muito parecida", troca de variante. Se tiver `Reescreva com no máximo (\d+) palavras`, obedece ao número.
- **Texto:** banco de modelos **originais** por categoria, com 8 ou mais variantes de estrutura diferente em abertura, gancho e fechamento, e espaços para preencher (rádio, programa, título, artista, nome autorizado). Sem promessa ("daqui a pouco"…), sem "toca agora" fora de pedido e sem número em algarismo. Nenhum modelo transcreve ou imita radialista real.
- **RNG próprio:** `random.Random(semente)`, nunca o `random` global. Assim, mexer no dublê não muda a sequência aleatória do backend.
- **Injeções da fixture**, indexadas pelo número da fala:
  - `promessa` (anexa uma frase de promessa)
  - `excesso` (primeira tentativa com o fator ×1,6, para exercitar a revisão de `:2706-2760`)
  - `cita_musica` (cita um título fora do catálogo ou marcado `indisponivel`)
  - `cita_ouvinte` (nome que não existe na fila)

  Assim, a linha de base mostra as violações que a F3 e a F4 precisam pegar.
- **Contadores:** chamadas por função, revisões e prompts reconhecidos. O resumo traz `dubles.faixa_reconhecida_pct`, que deve ficar perto de 100% nos blocos de música. Se cair, algum refactor contornou o dublê.

### 5.4 Relógio virtual (sem sleep)

- Uma única `freezegun.freeze_time(inicio - preparo_antecipado_s)` envolve toda a simulação. O tempo avança com `relogio.move_to(t)`.
- O freezegun troca `datetime` globalmente, inclusive na thread do `TestClient`. Os testes atuais já combinam os dois.
- Datas e horários das fixtures: terça-feira, 10/11/2026, das 14h às 15h em `America/Sao_Paulo`. Não é feriado; o dia 15/11 é. `dias_semana: []`.
- **Atenção:** dentro do freeze, `time.perf_counter` também fica congelado. O tempo de parede (`tempo_execucao_s` e o aceite de menos de 30 s) é medido **fora** do contexto ou com `freezegun.api.real_perf_counter`.

**Laço de emissão (`emissao.py`), espelho da `FilaPreparo` e do player:**

```
fila = deque(); ctx = Ctx(historico=[], total_falas=0, ultima_fala=None); gerando = True
t = inicio
def preencher(t_ger):
    while gerando and nao_vinhetas(fila) < antecedencia and len(fila) < 12:
        relogio.move_to(t_ger); inserir_pedidos_com_chegada_ate(t_ger)
        seg = POST /proxima {incluir_audio: False, historico: ctx.ultimas8_cronologicas(), total_falas: ctx.total,
                             perfil_pos_producao: "radio_fm", ultima_fala: ctx.ultima}
        seg.gerado_em = t_ger; fila.append(seg)
        ctx = avancar(ctx, seg)           # None após "encerramento" -> gerando = False
preencher(inicio - preparo_antecipado_s)
while fila:
    preencher(t); seg = fila.popleft(); preencher(t)
    t += clamp(seg.pausa_antes_ms ?? 350, 0, 5000) / 1000
    eventos = reproduzir(seg, t)           # fala -> músicas -> vinheta de encerramento
    se corte == "agendado" e algum evento passa de horario_fim + 1 s: truncar (cortado=True), parar
    confirmar pedido do bloco (POST /ouvintes/pedidos/{id}/reproducao: executado|interrompido|falhou), em t do fim
    t = fim do último evento
    se seg.tipo == "encerramento": parar
travas: 400 chamadas; t > horario_fim + 30 min
```

- Bloco vazio (sem fala, sem música e sem vinheta): gera um evento `bloco_vazio` e avança 5 s, que é o `INTERVALO_RETENTATIVA_FALHA_MS` do player (`useLiveEngine.ts:33`). Isso conta em `silencio_s`.
- Resposta HTTP diferente de 200: gera um evento `erro` e avança 5 s.
- O GET `/preparo` (preparo prévio no servidor) fica de fora. A primeira fala sai do `/proxima` normal. Documentar isso no resumo.

### 5.5 Músicas com duração de fixture

- O catálogo é fictício, com 30 ou mais faixas por perfil (mais de 100 min, para cobrir 1 h sem repetir).
- Cada faixa: `{video_id, titulo, artista, generos, duracao_s, fim_s?, contexto?, indisponivel?}`.
- Os nomes são inventados, para não sugerir dado real e manter o determinismo.
- Comportamento dos dublês:
  - `buscar_musica(query, genero, bloqueados, evitar_video_ids, titulos_tocados, ...)` procura faixas cujo texto normalizado contenha os tokens da query. Se a query for genérica (`QUERY_MUSICA_GENERICA` ou "{gênero} musica"), considera todas as faixas do gênero.
  - Os dublês respeitam `evitar_video_ids`, `titulo_ja_tocado` e `bloqueados`, e escolhem sempre a primeira faixa na ordem do catálogo. Não iteram sobre `set`.
  - Devolvem `MusicaEncontrada(video_id, titulo, canal=artista, inicio_segundos=0, fim_segundos=fim_s, duracao_segundos=duracao_s)`.
- Duração tocada: `(fim_segundos or duracao_segundos) - inicio_segundos`, como no player.
- As `musicas_permitidas` das fixtures seguem o formato `"Artista - Título"`, o mesmo do caminho `_via_catalogo` (`router.py:1256-1278`).

### 5.6 Pedidos, vinhetas e patrocinadores

- Pedidos da fixture: `{chega_em_s, tipo: musica|abraco|sorteio, nome, telefone, natureza, musica_query?, texto_autorizado}`.
- Eles são inseridos direto em `FilaAoVivo` no instante virtual de chegada, sem passar pelo webhook:
  - Fluxo novo: `programa_id`, `transmissao=ocorrencia(programa, tz)`, `estado="em_fila"`.
  - Fluxo legado: `programa_id=None`.
- Distribuição dos fluxos: `popular_sertanejo` usa o fluxo novo (`atendimento_ouvinte_ativo: true`). `variedades_leves` usa o legado, que é o padrão da conta. Assim, os dois são medidos.
- Vinhetas: `vinhetas: [{papel, texto, duracao_s, com_audio}]` vira um `BibliotecaAudioItem` com `audio_path="sim/<papel>.mp3"` quando `com_audio`. A `estrutura_blocos` usa marcadores `"vinheta:@abertura"`, que o simulador resolve para o id. Duração: `duracao_s`, ou `palavras/wpm` sem áudio.
- Patrocinadores: `"patrocinador:@spot"` funciona do mesmo jeito. A duração é `duracao_s` (áudio) ou estimada a partir do texto.

### 5.7 `as_run.json`

O arquivo é um objeto com metadados e `eventos` (a skill deve ler `["eventos"]`):

```json
{
  "versao": 1, "programa": "musical_adulto", "formato": "musical_adulto", "modo": "fake",
  "semente": 7, "wpm": 145, "inicio": "2026-11-10T14:00:00-03:00", "fim_programa": "2026-11-10T15:00:00-03:00",
  "eventos": [
    {
      "n": 12, "bloco_n": 7,
      "inicio": "2026-11-10T14:31:04-03:00", "fim": "2026-11-10T14:31:13-03:00",
      "inicio_s": 1864.0, "fim_s": 1873.4, "gerado_em_s": 1381.0, "pausa_antes_s": 0.15,
      "tipo": "fala", "bloco": "retomada", "categoria": "abertura", "formato": "musical_adulto",
      "texto": "…", "palavras": 22,
      "duracao_prevista_s": 9.1, "duracao_medida_s": null,
      "orcamento_s": {"min": 6, "max": 12, "fonte": "backend"},
      "orcamento_ref_s": {"min": 10, "max": 35, "fonte": "formato"},
      "musicas_citadas": [], "musica_anunciada": [], "musica_tocada": "Rua das Acácias - Duo Estrada Velha",
      "musicas_bloco": [],
      "promessas_abertas": [], "promessas_fechadas": [],
      "pedido_id": null, "pedido_estado": null, "pedido_estado_final": null,
      "audio_status": "pendente", "tom": "neutro", "passos_roteiro": 1,
      "chamadas_llm": 1, "revisada": false, "cortado": false
    }
  ]
}
```

- `tipo` só pode ser `fala`, `musica`, `vinheta`, `patrocinador`, `intervalo` (reservado para a F1), `bloco_vazio` ou `erro`. O tipo do backend vai em `bloco`, porque `"musica"` também é o anúncio. Assim, "avaliar fala de tipo ≠ musica" funciona na skill.
- `orcamento_s`: no formato musical, vem de `duracao_alvo_segundos` do backend. No padrão, vem de `orcamento_ref_s` da fixture, com `fonte: "formato"`.
- `duracao_prevista_s`: `contar_palavras(texto) / wpm × 60`, com a função de `app/live/formato.py:33`, que ignora `[tags]`.
- `duracao_medida_s`: só no modo completo, com `mp3_bytes_para_array` de `app/postprod/audio_io.py:11` (amostras ÷ taxa).
- `musica_anunciada` é **lista**: títulos citados que ainda não tocaram, o que exclui o comentário sobre a faixa anterior. `musica_tocada` é a próxima faixa que de fato foi ao ar.
- Promessas: detector provisório em `metricas.py`, com padrões configuráveis ("daqui a pouco", "depois do intervalo", "já já", "ainda hoje", "logo mais", "mais tarde", "em instantes", "a seguir", "na sequência", "volto já"). Cada uma ganha `{id, padrao, trecho, prazo_s}`.
  - Prazo padrão: 900 s, ou o fim do programa para "ainda hoje", "mais tarde" e "logo mais".
  - Uma promessa só fecha quando a promessa de música é cumprida pela próxima faixa. Na F0, todo o resto vence: é o retrato honesto de hoje. A F4 troca esse detector pelo de `app/live`.
- `pedido_estado` é o estado logo depois da geração. `pedido_estado_final` é o estado depois da confirmação ou no fim da simulação.

### 5.8 `resumo.json`

Usa os nomes da skill, mais alguns extras:

- **Identificação:** `config` com `modo`, `semente`, `wpm`, `antecedencia`, `preparo_antecipado_s`, `corte`, fixture, relógio, `commit` e `versao_formato`.
- **Uso de recursos:** `tempo_execucao_s`, `chamadas_proxima`, `chamadas_llm` (por função e revisões), `chamadas_tts`, `caracteres_tts`, `tentativas_rede`, `erros_http`, `dubles.faixa_reconhecida_pct`.
- **Métricas da skill:** `fora_orcamento_pct`, `estouro_max_pct`, `atraso_hard_time_s`, `anuncio_sem_confirmacao`, `promessa_vencida`, `pedido_indevido`, `abertura_repetida` (provisório: as três primeiras palavras normalizadas iguais em três falas seguidas; a F8 refina), `silencio_s` (só lacunas involuntárias; as pausas editoriais vão em `silencio_editorial_s`), `aviso_oralidade` (`null` até existir `app/live/oralidade.py`, que a F7 cria e o simulador passa a importar se existir), `repeticao_estrutura` (`null`, F8).
- **Composição e horário:**
  - `tempo_fala_s`, `tempo_musica_s` e `tempo_outros_s`, comparados com o relógio (o A prevê 3015, 225 e 360 s).
  - `hard_times: [{inicio_s, tipo, executado_em_s, atraso_s, status: ok|atrasado|perdido}]`, com tolerância de 5 s (critério da F1). Correspondência via `corresponde_a` do relógio: abertura com `abertura`, intervalo com `intervalo`, passagem e fechamento com `encerramento`, entrevista com `entrevista`.
  - `hard_times_perdidos`, `encerramento_no_ar`, `estouro_fim_programa_s`, `segundos_cortados`.
- **Pedidos e participação:** `pedidos` com recebidos, selecionados, executados, não atendidos, pendentes ao fim, selecionados e não tocados, e atendidos antes de tocar. Mais `ouvinte_inexistente`.
- **Volume:** `eventos_por_tipo` e `falas_por_bloco`.
- **No modo completo:** `wpm_observado` por voz, que alimenta a calibração da F2.

Regra de `pedido_indevido` (a da skill): fala com "toca agora", "pediu" ou nome de ouvinte da
fixture quando não há pedido ligado, quando o `pedido_estado` é diferente de `selecionado`, ou
quando a faixa do pedido ≠ `musica_tocada`. No fluxo legado, o estado `historico_legado` conta como
indevido de propósito: ele marca o pedido como atendido antes de tocar. Esse é o problema da F4.

### 5.9 Fixtures em `backend/tests/fixtures/programas/`

**Relógios** (`relogios/*.json`):

```json
{"id": "A", "nome": "Musical com companhia", "fonte": "docs/pesquisa-radio-locufy.md §9.A", "hipotese": true,
 "eventos": [{"inicio_s": 0, "duracao_s": 40, "tipo": "abertura", "rotulo": "Identidade e abertura",
              "natureza": "obrigatorio", "hard_time": true, "corresponde_a": ["abertura"]}, ...]}
```

- O campo é **`inicio_s`**. O `minuto_inicio` inteiro previsto na F1 não representa 00:40, 12:35 nem 59:30, e a F1 deve adotar `inicio_s`.
- Durações em segundos:
  - **A:** 40, 680, 35, 685, 180, 60, 720, 60, 720, 180, 210, 30. Música 3015, fala 225, intervalos 360.
  - **B:** 180, 480, 240, 180, 720, 180, 480, 180, 540, 300, 120.
  - **C:** 120, 480, 360, 180, 360, 540, 420, 180, 360, 480, 120.
- Os três fecham 3600 s e são contínuos.
- `hard_time` (hipótese de projeto, documentada no arquivo):
  - A: abertura 0, intervalos 1440 e 3180, passagem 3570.
  - B: abertura 0, intervalos 900 e 2460, entrevista 1080, passagem 3480.
  - C: abertura 0, intervalos 960 e 2460, fechamento 3480.
- `natureza`: música e links são `ajustavel`; intervalos, abertura e passagem são `obrigatorio`.
- Na F0, os relógios só **medem**: o backend ainda não os conhece. Os intervalos vão aparecer como `perdido`, e isso é a linha de base.
- O B fica sem programa até a F5. A F1 o simula com `--relogio B` sobre qualquer perfil.

**Programas** (topo da pasta): `{id, formato, descricao, relogio, timezone, inicio, unidade_fala, orcamento_ref_s, conta, radialista, programa, catalogo, vinhetas, patrocinadores, pedidos, injecoes}`.
- O campo `programa` replica as colunas de `Programa` (`app/models/programa.py`).
- `conta.cidade` fica `""`, sem clima.
- `dose_noticia` fica `"nenhuma"` e `pode_pesquisar` fica `false`: jornalismo factual só depois da F5.

| Perfil | Backend | Relógio | Configuração |
|---|---|---|---|
| `musical_adulto` | `perfil_programacao="musical_companhia"` | A | `estrutura_blocos` vazia, que segue o `ROTEIRO_MUSICAL`, com `"vinheta:@abertura"`. Unidade de fala 10–35 s. Um pedido de música. Injeção `cita_musica` (no formato musical, música citada não toca). |
| `popular_sertanejo` | `padrao` | A | Blocos `["abertura","musica","musica","chamada_ouvinte","musica","comentario","musica","patrocinador:@spot"]`. `generos_musicais: ["sertanejo"]`. Fluxo de atendimento novo. Quatro pedidos (música, abraço e um de música `indisponivel`). Unidade 20–60 s. Injeção `promessa`. |
| `variedades_leves` | `padrao` | C | Blocos `["abertura","comentario","musica","chamada_ouvinte","musica","comentario_quadro","musica"]`. `quadros_fixos.comentario_quadro` e `assuntos_ao_vivo`. Fluxo legado. `orcamento_ref_s` por categoria, com quadro de 120–480 s e demais de 20–60 s. Injeção `excesso`. |

- `ia_pode_adicionar_blocos: false` nos três, para facilitar a leitura. A semente garante o determinismo de qualquer forma.
- Os valores de orçamento ficam na fixture como configuração, com origem na tabela da skill `referencia-radio`.
- Divergência anotada para a F2 e a F6: o backend musical limita `retomada` a 6–12 s e `identificacao` a 3–7 s (`formato.py:13-19`). A pesquisa propõe link de 10–35 s.

### 5.10 `docs/benchmarks/2026-11-06-formatos/casos.json`

Estrutura: `{versao, fonte, regras, casos: [...]}`. Cada caso:
`{id, formato, bloco, frentes, dimensoes, contexto, criterio, falas_rotuladas}`, em que:
- `contexto` traz `tocou`, `proxima_confirmada`, `pedidos` (com estado), `promessas_pendentes`, `eventos_agendados`, `dados` (com fonte, `atualizado_em` e `valido_ate`), `segundos_ate_hard_time` e `orcamento_s`.
- `criterio` é a frase de rubrica para o juiz.
- `falas_rotuladas` é uma lista de `{texto, esperado: {...}}`, para os validadores determinísticos das frentes seguintes. As chaves de `esperado` são `anuncio_sem_confirmacao`, `promessa_sem_evento`, `pedido_indevido`, `ouvinte_inexistente`, `dado_sem_fonte`, `dado_vencido`, `avisos_oralidade_min` e `excede_orcamento`.

São 30 ou mais casos, com controles positivos e negativos para cada regra, cobrindo os três
perfis e as dimensões da §14:

| Bloco de casos | Quantos | Consumido por |
|---|---|---|
| Faixa anunciada confirmada × não confirmada; comentário sobre o que tocou × faixa nova | 6 ou mais | F3 (aceite: 100% detectado) |
| Tease com evento agendado × sem evento; antes do intervalo; retorno e reorientação; contingência (convidado não entrou) | 6 ou mais | F1, F4 |
| Pedido `selecionado` com "toca agora" × pedido em fila ou indisponível; sem pedido (convite genérico, sem simular mensagem); ouvinte inexistente | 6 ou mais | F4 |
| Dado com fonte e válido × vencido (dizer o horário) × sem integração (temperatura, placar) × injeção em título de notícia | 5 ou mais | F5 |
| Oralidade: frase de mais de 25 palavras, sigla sem explicação, número longo, "municipalidade realizará intervenções viárias" | 4 ou mais | F7 (redução de 50% ou mais) |
| Estrutura de abertura repetida × reorientação permitida | 2 ou mais | F8 |
| Fala prevista que ultrapassa o hard time, com fechamento curto esperado | 2 ou mais | F1, F2 |

Todas as falas são **originais**. Nenhuma transcreve ou imita apresentador real (regra 7).

## 6. Testes a escrever, nesta ordem

Não há caracterização a fazer: nenhum código de `app/` será movido. O simulador é que vira o
arnês de caracterização da F3.

**Unitários** (`backend/tests/test_simular_hora.py`):
1. `test_relogios_somam_3600_e_sao_continuos`: A, B e C. Para o A, também confere música 3015, fala 225 e intervalos 360.
2. `test_fixtures_de_programa_validas`: carregam pelos modelos Pydantic, o relógio referenciado existe, as `musicas_permitidas` estão no catálogo, o catálogo tem 100 min ou mais e nenhum `*.json` do topo da pasta é um relógio.
3. `test_linha_historico_igual_ao_painel`: `"musica: Vem aí [Música(s) tocada(s) nesse bloco: T - C, U - D]"`, com referência a `useLiveEngine.ts:1241`.
4. `test_duble_llm_respeita_orcamento_tipo_e_faixa_confirmada`: o canal lateral funciona sem depender do texto do prompt, e a revisão obedece ao limite.
5. `test_duble_musica_respeita_evitar_e_titulos_tocados`.
6. `test_metricas_em_as_run_artificial`: um `as_run` montado à mão com uma violação de cada tipo dá contagens exatas (`anuncio_sem_confirmacao`, `promessa_vencida`, `pedido_indevido`, `silencio_s`, `fora_orcamento_pct`, `estouro_max_pct`, `atraso_hard_time_s`, `abertura_repetida`).

**Integração** (pelo `/proxima` real):

7. `test_simulacao_fake_rapida_e_sem_rede[musical_adulto|popular_sertanejo|variedades_leves]`:
   - menos de 30 s de parede, medidos fora do freeze;
   - `tentativas_rede == 0`;
   - `as_run.json` e `resumo.json` gravados em `tmp_path`;
   - cada evento tem as 14 chaves da skill;
   - `fim(n) <= inicio(n+1)`;
   - `bloco_n` crescente.
8. `test_determinismo_mesma_semente`: duas rodadas iguais, ignorando `tempo_execucao_s`.
9. `test_fila_de_preparo_gera_dois_blocos_a_frente`: `gerado_em_s` do bloco k ≈ `inicio_s` do bloco k-2.
10. `test_corte_agendado_trunca_no_horario_fim` e `test_corte_manual_mede_estouro`.
11. `test_pedido_fluxo_novo_selecionado_vira_executado` e `test_pedido_fluxo_legado_atendido_antes_de_tocar`.
12. `test_injecoes_aparecem_nas_metricas`: promessa vencida 1 ou mais, revisão por excesso (`chamadas_llm > falas`), anúncio não confirmado no formato musical.
13. `test_dubles_cobrem_alvos_existentes`: cada alvo existe, a troca por identidade alcança todos os módulos que importaram a original e `faixa_reconhecida_pct` fica em 95% ou mais.
14. `test_modos_pagos_exigem_confirmacao`: `--modo llm` sem `--confirmo-custo` sai com código 3, sem tocar a rede.

**Simulação** (a cargo do implementador, depois dos testes verdes):
- Rodar o CLI nos três perfis.
- Gravar as saídas em `docs/melhoria-radio/f0/simulacao/<perfil>/`.
- Preencher a seção "Simulação" do `baseline.md` com as métricas principais de cada perfil.

Os modos `llm` e `completo` **não** rodam na F0 sem aprovação explícita do usuário.

## 7. Riscos e o que não fazer

- **Não alterar `app/`** na F0, nem para "facilitar o teste". O tempo é controlado com o freezegun e o resto com dublês. Qualquer ajuste no backend vai para a F1 ou a F3.
- **Não ignorar a fila de preparo (antecedência 2) nem o watchdog de corte.** Sem eles, a linha de base subestima o estouro do fim e a perda do encerramento, e a F1 teria um critério de aceite falso.
- **Dublê acoplado ao texto do prompt.** As frentes F3, F6 e F7 reescrevem prompts. Por isso, só tipo, revisão e limite saem do texto, e o resto vem do canal lateral. O `faixa_reconhecida_pct` e o bloqueio de rede denunciam quando um dublê é contornado.
- **Os números de fala no modo fake são sintéticos.** O dublê fala dentro do orçamento por construção. No fake, só a mecânica é medida: relógio, fila, corte, pedidos, continuidade e detectores. Qualidade e comprimento real da fala só aparecem no modo llm.
- **Não comparar `as_run` byte a byte em teste.** As frentes seguintes mudam o comportamento de propósito. Comparar invariantes e métricas, e manter as saídas da linha de base só para comparação.
- **Detectores provisórios.** Promessa, abertura repetida e música anunciada são heurísticas da F0. A F3, a F4, a F7 e a F8 os substituem por código em `app/live`, que o simulador passa a importar. Não criar dois validadores divergentes.
- **SQLite não é Postgres.** `with_for_update` e a ordenação com `case` não reproduzem a concorrência real (item 5). A simulação é sequencial.
- **Determinismo:**
  - semente no `random` global, guardando e restaurando o estado;
  - RNG próprio para o dublê;
  - nenhuma iteração sobre `set` nos dublês;
  - `json.dumps(sort_keys=True)`;
  - `PYTHONHASHSEED=0` recomendado para comparar entre processos.
- **Duplicação de relógio com a F1.** A F1 deve tornar os presets de `app/live` a fonte de verdade e testar a igualdade com estas fixtures, ou fazer as fixtures referenciarem os presets.
- **Nomes e textos:** artistas, ouvintes, rádio e locutor fictícios. Os modelos de fala são originais (regra 7). Os relógios são hipóteses (a §9 diz que os intervalos são ilustrativos).
- **Fora do escopo da F0:** criar o tipo `intervalo` no backend (F1), o registro de promessas (F4), o verificador de oralidade (F7), a bancada com mais de um locutor (F13) e o `/preparo` do servidor.
- **Pendência opcional:** ajustar a skill `avaliar-locucao` para ler `as_run["eventos"]`, aceitar `musica_anunciada` como lista e reaproveitar o `resumo.json` em vez de recalcular.

PRONTA PARA IMPLEMENTAR
