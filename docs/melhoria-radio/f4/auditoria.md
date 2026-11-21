# Auditoria F4: promessas, chamadas e participação de verdade

Branch auditada: `melhoria/f4-promessas`, criada da ponta da F3 (`c382859`), em 12/11/2026. Só leitura no código.
`pytest --collect-only`: 1379 testes. Portão da F3: VERDE (`docs/melhoria-radio/f3/testes.md`, seção "Portão
independente").

Fontes:
- `docs/plano-melhoria-radio.md`: F4, Transversal, Avaliação, Portão e Regras.
- `docs/pesquisa-radio-locufy.md`: §8, §10, §12.7 e §13.
- Skill `referencia-radio`.
- `docs/auditoria.md` e `docs/refatoracao.md`.
- `docs/melhoria-radio/RELATORIO.md`, as pendências de F0 a F3 e a auditoria da F3 (modelo de formato).
- `docs/benchmarks/2026-11-06-formatos/casos.json`.
- Simulações gravadas em `docs/melhoria-radio/f3/simulacao/`.

**Conclusão: a frente NÃO está atendida.**
- Não existe registro de promessas: `Chamadas.promessas` é um marcador vazio.
- Nenhuma checagem de promessa ou de participação roda na fala.
- O fluxo legado marca o pedido como atendido antes de tocar.
- Um pedido de música indisponível vai ao ar com o nome do ouvinte.
- Um ouvinte inexistente injetado vai ao ar nos quatro cenários de `variedades_leves`.

## 1. Estado atual: o plano confere com o código?

| Afirmação do plano | Situação | Evidência |
|---|---|---|
| `FilaAoVivo` tem `estado` (`em_fila`, `aguardando_revisao`, `selecionado`, `executado`, `expirado`, `cancelado`) | **diferente**: há mais estados | `backend/app/models/fila_ao_vivo.py:24`. Também existem `recebido` (`app/whatsapp/atendimento.py:16`), `nao_atendido` (`app/whatsapp/gestao.py:177,205`, `app/live/router.py:2213`) e `historico_legado` (`router.py:1583`). Linhas pendentes de antes da coluna `estado` foram migradas para `aguardando_revisao` com `programa_id` nulo (`app/main.py:458-459`). Por isso o legado pendente pode estar em `em_fila` ou em `aguardando_revisao`. |
| `eventos` | confirmado | `fila_ao_vivo.py:25`; `registrar_evento` em `atendimento.py:19-30`. |
| `texto_autorizado` | confirmado | `fila_ao_vivo.py:26`; aprovação em `gestao.py:113-157`; o prompt usa esse campo só no fluxo novo (`app/live/contexto.py:90`). |
| "Só marca atendido após confirmação de reprodução (`app/whatsapp/atendimento.py`)" | **diferente** | Vale só no fluxo novo (`Account.atendimento_ouvinte_ativo`, padrão `False` em `app/models/account.py:16`). A confirmação fica em `gestao.py:190-216`, não em `atendimento.py`. O legado marca `atendido=True` e `historico_legado` na seleção, antes de tocar (`router.py:1564-1586`). No fluxo novo, música indisponível vira `nao_atendido` na geração, antes de qualquer reprodução (`router.py:2209-2217`). |
| "`direcao_musical` proíbe prometer retorno sem programação confirmada" | confirmado, mas só no formato musical | `app/live/formato.py:54` e `:64`. Com relógio, `_instrucao_relogio` proíbe qualquer tease ("Não anuncie o que vem a seguir nem prometa conteúdo", `app/live/prompts.py:327-328`). O fechamento curto também proíbe (`prompts.py:332-335`). Sem relógio, no formato padrão, só existe a regra genérica de "promessa vaga" (`app/live/prompt_emissao.py:235-237`). |
| "Não há registro de promessas feitas no ar" | confirmado | `Chamadas.promessas: tuple = ()` (`contexto.py:119-125`) nunca é preenchido (`contexto.py:606`). `CHECAGENS_POS_GERACAO = [checar_musicas]` (`app/live/validacao_fala.py:321`). Só existe o detector provisório do simulador (`backend/scripts/simulacao/metricas.py:13-22`, `:51-60`, `:110-121`). |
| Lacuna: "daqui a pouco…" dito sem garantia | confirmado, e há mais | Ver §2, fatos 6 a 9. |

## 2. Fatos do código que mudam o desenho

1. **A F3 deixou os ganchos, mas sem uso.**
   - `ContextoEmissao.chamadas` (`contexto.py:119-125`); `Chamadas.pedidos_em_fila` também nunca é preenchido.
   - `CHECAGENS_POS_GERACAO` e `validar` (`validacao_fala.py:321-334`).
   - `Violacao`, `remover_frases` e `fala_reserva_neutra` (`validacao_fala.py:86-94`, `:363-399`).
   - `ContextoEmissao.extensoes` (`contexto.py:209`).
   - `ctx.tempo.plano` com `ocorrencia`, `etapa` e `proximo_compromisso` (`app/live/relogio.py:372-396`).
   - O `Plano` **não** carrega as etapas seguintes. A agenda precisa delas: `montar_espelho` é puro (`relogio.py:511-550`), mas só `_Decisao` o conhece (`relogio.py:608-926`).
2. **O modo do validador é global.**
   - `corrigir(..., modo=settings.validacao_musica_modo)` decide a remoção de todas as regras (`validacao_fala.py:435`).
   - `_checagem_pre` desliga a fase "pre" inteira fora do modo `corrigir` (`router.py:2022-2026`).
   - A F4 precisa de modo por regra (decisão D12).
3. **A geração vai dois blocos à frente, e o estado é marcado na geração.**
   - As etapas do relógio são marcadas na geração (`relogio.py:1055-1067`, chamada em `router.py:1861`), não na reprodução (pendência da F1, para a F11).
   - Promessa registrada e cumprida seguem a mesma regra. Pular ou pausar fica para o as-run da F11.
4. **O texto que vai ao ar só existe depois do TTS.**
   - O encurtamento da F2 (momentos B e C) pode remover a frase da promessa. Foi o que aconteceu na simulação da F3: no `popular_sertanejo` com relógio, a injeção "Daqui a pouco tem mais recado de ouvinte por aqui." caiu junto com o fragmento "Rádio." (`f3/simulacao/popular_sertanejo/as_run.json`, evento 10, `fala_neutra`).
   - O registro tem de usar o texto final, no mesmo ponto de `_registrar_fala_no_ar` (`router.py:2180-2206`).
   - Na F3, `promessa_vencida == 0` com relógio foi sorte: nenhuma regra removeu a promessa.
5. **Sem relógio, o roteiro é a agenda, mas `_tipo_proximo_bloco` sorteia.**
   - Com `ia_pode_adicionar_blocos`, há um comentário extra em 15% das posições (`router.py:694-696`).
   - Olhar posições futuras com essa função consome o `random` e muda a ordem dos sorteios (golden C1). A agenda pelo roteiro tem de usar uma versão pura, sem sorteio.
   - Outras trocas de posição: vinheta morta pula (`app/live/roteiro.py:100-113`), notícia sem fonte vira música (`roteiro.py:124-133`), assunto esgotado vira música (`roteiro.py:139-146`), encerramento por tempo (`roteiro.py:86-90`).
6. **Textos de prompt e reservas que convidam a prometer sem evento:**
   - música sem faixa: "chamada pro próximo momento do programa" (`prompt_emissao.py:417-421`);
   - pedido recente do legado: "o pedido em si ainda vai ser atendido de verdade no bloco próprio dele depois" (`prompt_emissao.py:371-377`);
   - reserva do multivoz com promessa fixa: "Seguimos no ar, ja volto com mais uma novidade." (`app/live/geracao.py:149`, `:194`);
   - abertura: "lance … uma pequena pergunta … Isso pode ser retomado no encerramento" (`prompt_emissao.py:337-342`). É o fio condutor (`router.py:765-773`, retomado em `prompt_emissao.py:343-347`), um mecanismo de promessa que já existe e é cumprido pelo encerramento.
   - O gancho manda retomar "o nome ou o clima" do ouvinte da fala anterior (`prompt_emissao.py:118-119`). Isso conflita com uma proibição cega de nome de ouvinte fora do pedido selecionado (decisão D8).
7. **Pedido de música indisponível.**
   - No fluxo novo, o prompt manda dizer o nome e "não achei" (`prompt_emissao.py:396-403`), e o pedido vira `nao_atendido` só depois da geração (`router.py:2209-2217`).
   - No legado, o pedido já foi consumido.
   - A pesquisa §10 diz "não anunciar execução imediata; manter status na fila". O benchmark rotula essa fala como `pedido_indevido` (`casos.json`, caso `f4-pedido-indisponivel`).
8. **O fluxo legado é o padrão das contas.**
   - Quem decide é `atendimento_ouvinte_ativo=False`; `docs/atendimento-ouvintes.md:3` trata o fluxo novo como piloto.
   - O legado:
     - insere sem moderação, com o nome do WhatsApp e a mensagem crua (`app/whatsapp/webhook.py:507-517`);
     - consome na seleção (`router.py:1581-1585`);
     - não devolve `pedido_id`/token, então o painel não confirma (`_pedido_confirmavel`, `router.py:2209-2217`; `frontend-painel/lib/participacoes.ts:4-5`).
   - A F0 contou o legado como `pedido_indevido` "de propósito… Esse é o problema da F4" (`f0/auditoria.md:313-316`; teste `tests/test_simular_hora.py:485-491`). O benchmark tem o rótulo correspondente (`f4-legado-atendido-antes-de-tocar`).
9. **Defeito: a espiada de pedido recente no legado não filtra o fluxo.**
   - `_pedido_recente_nao_atendido` filtra só por rádio, tipo, `atendido=False` e janela (`router.py:1589-1609`).
   - Uma conta que desligou o atendimento novo pode levar ao ar o nome e a música de um pedido `aguardando_revisao` ainda não aprovado. O documento diz o contrário (`docs/atendimento-ouvintes.md:3`).
10. **Exclusões com FK.**
    - `excluir_programa` (`app/config/router.py:1396-1427`) e a exclusão de radialista (`config/router.py:1050-1072`) apagam à mão cada tabela com FK para `programas`, porque o Postgres não tem `ON DELETE CASCADE` aqui (comentário em `:1418-1421`).
    - Uma tabela nova de promessas precisa entrar nos dois caminhos. Os testes usam SQLite sem `PRAGMA foreign_keys` (`tests/conftest.py`), então só uma asserção explícita pega o esquecimento.
11. **Retrato dos goldens (`tests/test_live_proxima_caracterizacao.py:387-435`).**
    - O Redis entra inteiro: qualquer chave nova muda os 28 goldens.
    - O banco é um conjunto fixo de tabelas (`musica_historico`, `fila`, `noticia_historico`, `temas`): uma tabela nova não entra.
    - Campo de resposta nulo some do retrato; lista vazia não.
12. **O dublê do LLM ignora instruções do prompt.**
    - Ele escolhe o pedido pela linha que mudou para `selecionado`/`historico_legado` (`scripts/simulacao/dubles.py:332-347`) e reinjeta a injeção na reescrita (`dubles.py:216-229`).
    - Uma contingência só pedida no prompt nunca aparece no modo fake. Para medir o aceite, ela precisa ser garantida pelo código (decisão D5).
13. **O benchmark já codifica as regras da F4.** São 70 falas rotuladas:
    - 7 com `promessa_sem_evento`;
    - 5 com `pedido_indevido`;
    - 1 com `ouvinte_inexistente`.
    - Entram no `pedido_indevido`: legado consumido, pedido em fila, pedido indisponível com nome e participação simulada sem pedido.
    - Entra como permitido: "até amanhã" de encerramento.
14. **Protótipo de viabilidade** (descartável, fora do repositório):
    `/private/tmp/claude-501/-Users-guilhermejeske-projetos-locufy/90d4eff0-6fe1-4f02-8ce6-b92d53a2561e/scratchpad/f4proto/proto.py`.
    - Detector de promessa com marcadores por prazo (imediato, curto, intervalo, fim, fora da transmissão), tipo por palavra-chave e casamento com `eventos_agendados`.
    - Detector de participação com três camadas: nomes conhecidos não selecionados; nome com inicial maiúscula em frase de participação; mensagem simulada sem pedido.
    - Ambos reaproveitam `mencoes_musica` da F3 para não tomar título ou artista por ouvinte.
    - **Resultado em `casos.json`: promessa 7/7 com 0 falsos positivos; pedido indevido 5/5 com 0; ouvinte inexistente 1/1 com 0.**
    - Nas 155 falas das 12 simulações da F3:
      - promessas: só a injeção do popular e dois "até amanhã" de encerramento (permitidos como volta do programa, D9);
      - participação: só os três "Rosa Bezerra… não está no acervo" (pedido indisponível, D2) e "Dona Firmina" (injeção).

## 3. Linha de base da simulação (F3, modo fake, dublê de TTS)

| Métrica (musical / popular / variedades) | Com relógio | Sem relógio | Voz 120 | Painel antigo |
|---|---|---|---|---|
| `promessa_vencida` | 0 / 0 / 0 | 0 / **1** / 0 | 0 / **1** / 0 | 0 / **1** / 0 |
| `pedido_indevido` | **1 / 1 / 3** | **1 / 1 / 4** | 1 / 1 / 3 | 1 / 1 / 3 |
| `ouvinte_inexistente` | 0 / 0 / **1** | 0 / 0 / 1 | 0 / 0 / 1 | 0 / 0 / 1 |
| `pedidos.atendidos_antes_de_tocar` | 1 / 0 / 2 | 1 / 0 / 3 | 1 / 0 / 2 | 1 / 0 / 2 |

O que gera cada caso:

- **Promessa (popular):** injeção na fala 4, um convite de `chamada_ouvinte` sem pedido. Com relógio, ela caiu por acaso no encurtamento (fato 4).
- **Pedido indevido no musical:** "Joana Lis, procurei a sua pedida e ela não está disponível por aqui." É legado e indisponível.
- **Pedido indevido no popular:** "Recebi o seu pedido, Rosa Bezerra, mas essa música não está no acervo." O pedido é novo, indisponível e `nao_atendido`.
- **Pedido indevido em variedades:**
  - "Um abraço também para Dona Firmina." (injeção);
  - dois ou três pedidos legados lidos com estado `historico_legado` ("toca agora Patins Amarelos", "Cida Morais…").

## 4. Testes existentes que tocam a F4

| Arquivo | Testes | O que cobre |
|---|---|---|
| `tests/test_atendimento_ouvintes.py` | 22 | Fluxo novo: recepção privada, seleção ≠ execução, callback idempotente, player falho (`:136-180`), tenant e token (`:181`), expiração (`:201`), aprovação (`:228`, `:542`), migração aditiva da fila (`:478-508`), fala só com conteúdo aprovado (`:511-539`), exclusão de programa (`:567`). |
| `tests/test_live_router.py` | 122 | Legado: pedido de música (`:1078`); sem resultado com `atendido is True` (`:1117-1165`); sorteio com `atendido is True` (`:2443-2473`); ouvinte recorrente (`:2368`, `:2849`); naturezas (`:2477-2600`); pedido recente (`:2755`, `:2791`); convite varia (`:885`); musical com pedido (`:2996`). |
| `tests/test_live_validacao_fala.py` / `test_live_validacao_proxima.py` | 15 / 9 | Validador da F3; checagem extra registrada (`test_live_validacao_fala.py:240`), que é o padrão para registrar as da F4. |
| `tests/test_live_prompt_emissao.py` | 7 | Módulos extraídos não importam o router (`:19`, lista de módulos); `montar_prompt` puro; fila não aprova (`:156`). |
| `tests/test_live_proxima_caracterizacao.py` | 28 goldens + 1 | Cenários de pedido legado, pedido novo, sem resultado, abraço, sorteio, recorrente, pedido recente, encerramento com fio, música sem faixa ("já já tem mais rádio") e relógio A/C. |
| `tests/test_simular_hora.py` | 23 | Banco do dublê sem promessa (`:241-262`, usa `detectar_promessas`); métricas em as-run artificial (`:326-351`); pedido novo vira executado (`:472`); legado atendido antes de tocar (`:485-491`); injeções (`:494-509`: `promessa_vencida >= 1`, `ouvinte_inexistente >= 1`); casos de avaliação (`:564-580`). |
| `tests/test_simulacao_f3.py` | 2 | S1/S3 da F3 (padrão que a F4 repete). |
| `tests/test_live_relogio.py` / `test_live_relogio_proxima.py` | 35 / 13 | Serviço puro do relógio e plano na rota (onde entram obrigações e etapas seguintes). |
| Painel: `lib/__tests__/participacoes.test.ts`, `hooks/__tests__/useLiveEngine*.test.ts` | — | Callback `executado`/`falhou`/`interrompido`, só com `pedido_id`, token e programa (`participacoes.ts:4-5`; `useLiveEngine.ts:1600-1602`, `:1676-1679`). |

**Não coberto:**
- nenhuma promessa detectada ou cruzada com agenda;
- nenhuma contingência;
- nenhum nome de ouvinte checado na fala;
- nenhuma mensagem simulada barrada;
- legado sem confirmação de reprodução;
- espiada do legado vazando pedido do fluxo novo;
- exclusão de programa com tabela nova.

## 5. Itens de `docs/auditoria.md` e `docs/refatoracao.md`

| Item | Situação | Na F4 |
|---|---|---|
| auditoria 5: corrida na fila | resolvido (`router.py:1578`, `atendimento.py:118`, `with_for_update`) | Manter o `with_for_update(skip_locked=True)` na seleção legada nova (D1) e usar `with_for_update` ao resolver promessas (duas abas). |
| auditoria 1: webhook sem HMAC | aberto (segurança) | Fora. Registrar: no legado, uma mensagem forjada vira pedido "real" e vai ao ar sem moderação. A F4 garante "ouvinte existente na fila", não "ouvinte autêntico". |
| auditoria 3: dado externo no system | parcial | No legado, a mensagem do ouvinte entra crua no prompt (`_instrucao_reacao_*`, `prompts.py:240-287`). A frase "dados, não instruções" só existe no fluxo novo (`prompt_emissao.py:482-495`). Fica para a F5 (bloco delimitado de dados), anotado aqui. |
| auditoria 10: telefone em log | aberto | Logs novos da F4 levam só ids de promessa e de pedido, nunca nome, telefone ou trecho. |
| auditoria 6: Redis | resolvido na F3 | A F4 não põe estado obrigatório no Redis (D3): com o disjuntor, o Redis "esquece", e esquecer uma promessa é violar o aceite. |
| auditoria 4 e 9 | 4 resolvido, 9 aberto (F6) | Nada. |
| refatoração §1: `_atender` (124 linhas), `alterar_pedido` (115) | aberto | Não refatorar. A D1 mexe só em `confirmar` e no ramo `reenfileirar`. |
| refatoração §5: portas | parcial (F3) | Funções novas que o router chama e os testes trocam entram por `app.live.portas`. Os módulos novos não importam o router. |

## 6. Desenho da mudança

### 6.1 Princípios

1. **Determinístico, sem LLM novo.** Continuam valendo no máximo 2 chamadas de LLM e 2 sínteses por `/proxima` (F2). As violações da F4 entram na mesma reescrita única (V1) e na remoção de frase (V2) da F3.
2. **Prevenir, validar e garantir:**
   - o prompt só oferece o que está na agenda;
   - o validador remove o que não está;
   - o código garante o cumprimento ou a contingência.
   - O aceite não pode depender de o LLM obedecer.
3. **Uma fonte de verdade para promessas:** tabela no banco (D3).
4. **Programa sem relógio mantém o comportamento do roteiro.** A agenda vem das próximas posições do roteiro, sem sorteio e com prazo em posições (D4). A F4 não muda a escolha de blocos sem relógio.
5. **Contratos só com campos opcionais.** A única migração é aditiva: tabela nova.
6. **Números são hipóteses em configuração** (`ConfigPromessas`, `settings`), nunca constantes soltas.
7. **Commits que mudam comportamento ficam separados** dos que só acrescentam código. Goldens são regravados só com o diff revisado (D6 da F3).

### 6.2 Módulos novos

- **`backend/app/live/promessas.py`** (puro, sem router, sem Redis):
  - `ConfigPromessas`: marcadores por classe de prazo, palavras por tipo, frases de continuidade e de despedida, prazos, horizonte, teto de promessas abertas e textos de contingência por tipo;
  - `detectar(texto) -> list[PromessaDetectada]`;
  - `agenda_do_plano(plano, programa, pecas) -> tuple[EventoAgendado, ...]`;
  - `agenda_do_roteiro(programa, total_falas, formato_musical) -> tuple[EventoAgendado, ...]`;
  - `casar(promessa, agenda, instante, posicao, ctx) -> EventoAgendado | Livre | None`;
  - `checar_promessas(fala, ctx) -> list[Violacao]`;
  - `a_cumprir_e_contingencias(ctx) -> (tuple[PromessaRef], tuple[Contingencia])`;
  - `garantir_contingencia(fala, contingencias, ctx) -> str`.
- **`backend/app/live/participacao.py`** (puro):
  - `mencoes_participacao(texto, ctx) -> list[MencaoOuvinte]`;
  - `checar_participacao(fala, ctx) -> list[Violacao]`, com as regras `pedido_nao_selecionado`, `ouvinte_nao_autorizado`, `participacao_simulada` e `pedido_sem_mencao` (D10);
  - `nomes_permitidos(ctx)`.
- **`backend/app/models/promessa_no_ar.py`** e **`backend/app/live/promessas_repo.py`** (banco):
  - `registrar`, `abertas`, `obrigacoes`, `resolver` (com `with_for_update`) e `vencer`.
- **`backend/app/db/migrations/promessas_20261112.py`:** cria a tabela se não existir. Segue o padrão de `ritmo_voz_20261109.py`.

### 6.3 Estruturas (aditivas em `contexto.py`)

```python
@dataclass(frozen=True)
class EventoAgendado:
    chave: str                    # "etapa:<hora>:<inicio_s>" | "roteiro:<posicao>" | "encerramento"
    tipo: str                     # participacao | quadro | informacao | retorno | musica | encerramento
    rotulo: str                   # rótulo do relógio ou nome do quadro
    inicio: datetime | None = None  # com relógio
    posicao: int | None = None      # sem relógio (total_falas da posição)
    conteudo: str = ""            # ex.: assunto do quadro fixo
    cancelado: bool = False

@dataclass(frozen=True)
class PromessaRef:
    id: int; tipo: str; trecho: str; evento_alvo: str; rotulo: str
    prazo: datetime | None; prazo_posicao: int | None

@dataclass(frozen=True)
class Contingencia:
    promessa_id: int; texto: str; motivo: Literal["conteudo_caiu", "prazo_vencido", "fim_do_programa"]

@dataclass(frozen=True)
class Chamadas:                    # campos novos com padrão: não mudam nada sem promessa
    fio_condutor: str | None
    pedidos_em_fila: int = 0       # passa a ser preenchido
    promessas: tuple[PromessaRef, ...] = ()       # abertas nesta ocorrência
    agenda: tuple[EventoAgendado, ...] = ()       # o que pode ser chamado adiante
    a_cumprir: tuple[PromessaRef, ...] = ()       # alvo = este bloco, com conteúdo
    contingencias: tuple[Contingencia, ...] = ()  # alvo = este bloco sem conteúdo, ou vencidas

@dataclass(frozen=True)
class Participacao:                # campos novos com padrão
    ...  # atuais intactos (nomes_autorizados continua servindo ao detector de música)
    nomes_selecionados: tuple[str, ...] = ()   # pedido_musica/pedido_ouvinte deste bloco
    nomes_ja_atendidos: tuple[str, ...] = ()   # executados ou selecionados antes, nesta transmissão (D8)
    nomes_conhecidos: tuple[str, ...] = ()     # todos os pedidos da transmissão e o legado pendente
    nome_recente: str | None = None            # espiada do legado (D7)
```

- No relógio: o `Plano` ganha `seguintes: tuple[Etapa, ...] = ()`, as etapas depois da atual que ainda não foram concluídas, preenchidas em `_Decisao._plano`.
- `planejar(..., obrigacoes: frozenset[str] = frozenset())` (§6.6).
- Com `obrigacoes` vazio, o `Plano` fica idêntico ao de hoje. Um teste confere isso numa grade de instantes nos três presets.

### 6.4 Detecção e agenda

**Marcadores** (configuração; acento e caixa ignorados; uma promessa por frase):

| Classe | Exemplos | Prazo com relógio | Prazo sem relógio |
|---|---|---|---|
| imediato | "já já", "em instantes", "a seguir", "na sequência", "em seguida", "volto já" | `prazo_imediato_s` (300) | `posicoes_imediato` (2) |
| curto | "daqui a pouco", "daqui a pouquinho", "logo logo", "não sai daí" | `prazo_curto_s` (900, o mesmo da F0) | `posicoes_curto` (4) |
| intervalo | "depois do intervalo", "na volta do intervalo", "depois dos comerciais" | etapa logo depois do próximo intervalo **com patrocinador** | posição depois do próximo `patrocinador:` |
| fim | "mais tarde", "logo mais", "ainda hoje", "ainda neste programa", "no fim do programa" | fim da ocorrência | antes do encerramento |
| fora | "amanhã", "na próxima edição", "semana que vem" | só a volta do próprio programa pela grade (D9) | idem |

"Toca agora", "agora vem" e "agora," **não** são promessa: são front-announce, e quem cuida é a F3.

**Tipo** (palavras depois do marcador):
- `participacao`: recado, mensagem, resposta, pedido, ouvinte, alô, abraço, dedicatória;
- `musica`: música, sucesso, canção;
- `informacao`: notícia, boletim, trânsito, previsão, agenda, serviço, resultado;
- `entrevista`: entrevista, convidado, "entra na linha";
- `continuidade`: "continua", "segue", "seguimos", "mais rádio", com o nome do programa ou da rádio;
- senão, `conteudo`.

**Agenda com relógio** (`plano.seguintes` até o fim da ocorrência, excluindo música):

| Etapa | Entra na agenda como |
|---|---|
| `retorno`, `participacao` (`relogio.py:295-296`) | `participacao` |
| `quadro` | `quadro`, com o rótulo de `quadros_fixos` e o conteúdo da rotação, quando conhecido |
| `servico`, `noticia`, `reportagem`, `atualizacao` | `informacao`, só com fonte, porque sem fonte o `tipo_efetivo` vira música (`relogio.py:504-505`) |
| `intervalo` com patrocinador | `retorno` |
| encerramento | `encerramento` |
| `entrevista` | **nunca**: não há convidado real (`relogio.py:304-305`) |
| intervalo sem patrocinador | fora: virou música (`relogio.py:495-497`) |

**Agenda sem relógio:** as próximas `max(posicoes_curto, len(roteiro))` posições do roteiro, por uma função **pura**.
- Usa a mesma lista de `_tipo_proximo_bloco`, sem o sorteio de `ia_pode_adicionar_blocos` (fato 5).
- Entram `chamada_ouvinte` (participação), quadro fixo, bloco noticioso com fonte, `patrocinador:` (retorno) e o encerramento.
- Formato musical (`ROTEIRO_MUSICAL`): agenda vazia, o que coincide com `direcao_musical`.

**Casamento** (`casar`), nesta ordem:
1. Frase com menção a música (`mencoes_musica` da F3): a promessa é de música. Vale se cada menção estiver confirmada; senão, `promessa_sem_evento` (a F3 também acusa `musica_nao_confirmada`).
2. `continuidade`: sempre vale, não é registrada.
   - Com marcador de intervalo, exige um intervalo na agenda ("Depois do intervalo, a Tarde Serena continua").
   - "Mais música" num programa com etapas de música também vale e não é registrada.
3. `fora`:
   - vale só como volta do programa ("até amanhã", "amanhã tem mais <programa>"), se a grade tiver a próxima ocorrência no dia citado (`ocorrencia_em` com a data seguinte);
   - conteúdo prometido para outra edição é violação (D9).
4. Demais: precisa de um `EventoAgendado` não cancelado, dentro do prazo, que:
   - seja citado pelo rótulo;
   - ou tenha palavra de conteúdo em comum;
   - ou seja do mesmo tipo.
   - Senão, `promessa_sem_evento`. `entrevista` nunca casa.
5. Teto: com `max_promessas_abertas` (3) já abertas, uma promessa nova é violação.

**Checagem** `checar_promessas(fala, ctx)`, registrada em `CHECAGENS_POS_GERACAO`:
- roda nas fases "pre" e "final";
- `Violacao("promessa_sem_evento", frase, marcador, instrucao_retry)` com remediação `remover_frase`, ou `avisar` no modo avisar (D12);
- instrução da reescrita: "Você prometeu '{trecho}' sem programação confirmada." Com agenda: "O que está agendado: {rótulo} em cerca de {N} minutos; se quiser chamar algo adiante, use só isso." Sem agenda: "Não prometa conteúdo futuro."

### 6.5 Registro (`promessas_no_ar`, migração aditiva)

```python
class PromessaNoAr(Base):
    __tablename__ = "promessas_no_ar"
    id: int (PK)
    programa_id: FK programas.id, index      # apagada à mão nos dois caminhos de exclusão (fato 10)
    radio_config_id: FK radio_configs.id, index
    ocorrencia: str, index                   # Ocorrencia.chave (relogio.ocorrencia_em, vale sem relógio); fora da grade: "manual:<data local>"
    request_id: str                          # idempotência: um registro por (request_id, trecho)
    tipo: str; marcador: str; trecho: Text   # o trecho pode ter nome de ouvinte: nunca vai para log
    evento_alvo: str; evento_rotulo: str
    prazo: DateTime(tz) | None; prazo_posicao: int | None
    estado: str = "aberta", index            # aberta | cumprida | cancelada | vencida
    motivo: str = ""                         # "cumprida no bloco", "contingencia:conteudo_caiu", "nao_foi_ao_ar", "transmissao_encerrada"
    contingencia: Text = ""                  # frase de contingência dita
    eventos: JSON = []                       # trilha de transições, como FilaAoVivo.eventos
    criada_em; resolvida_em: DateTime(tz) | None
```

- Migração `promessas_20261112.py`:
  - `aplicar(engine)` cria a tabela só se ela não existir, e é idempotente;
  - é chamada em `app/main.py` ao lado de `aplicar_ritmo_voz`, antes do `create_all`;
  - o modelo entra em `app/models/__init__.py`.
- Exclusão: `excluir_programa` (`config/router.py:1396-1427`) e a exclusão de radialista (`:1050-1072`) apagam as promessas do programa ou do radialista.
- Sem Redis (D3): um `SELECT` indexado por `/proxima` (`programa_id, ocorrencia, estado`).

### 6.6 Cumprimento, contingência e obrigação

**Ordem na rota** (`gerar_proxima_fala`, `router.py:2220-2333`; acréscimos marcados com +):

1. `decidir_bloco`. + `_planejar_relogio` lê `promessas_repo.obrigacoes(db, programa, ocorrencia)`, as `evento_alvo` das abertas, e passa a `planejar(obrigacoes=...)`.
2. `resolver_musica_e_pedidos` (com D2).
3. `montar_contexto`:
   - \+ `chamadas.promessas`, `agenda`, `a_cumprir` e `contingencias`. São só leituras, depois de todos os sorteios, como as leituras do validador da F3, para não mudar a ordem do `random`;
   - \+ `participacao` com os nomes novos.
4. `montar_prompt`:
   - \+ linha de agenda (§6.9);
   - \+ "Você prometeu '{trecho}'. Cumpra agora: {o que este bloco traz}." para cada `a_cumprir`;
   - \+ "Comece a fala com esta frase, exatamente: '{texto}'" para cada contingência.
5. `gerar_fala`: o `checar_pre` inclui promessa e participação.
6. V2 (`_validar_fala_final`). + `garantir_contingencia`:
   - se a frase de contingência (normalizada) não está na fala final, o código a põe no início;
   - no multivoz, entra na primeira linha;
   - a frase entra em `preservar` e `manter` do encurtamento da F2, para o momento C não tirá-la.
7. TTS (momento C).
8. `_registrar_fala_no_ar`. + `promessas_repo.registrar_e_resolver(db, ctx, fala_final)`, numa transação com `with_for_update` nas linhas resolvidas:
   - promessas novas, detectadas **no texto final** e casadas: `aberta`;
   - `a_cumprir` com fala não vazia: `cumprida`;
   - contingências ditas: `cancelada`, `motivo=contingencia:<motivo>`.
9. Resposta com `promessas` (§6.10).

**Quando o conteúdo cai** (alvo é este bloco):
- `participacao` sem `pedido_ouvinte` nem `pedido_musica` selecionado;
- `quadro` sem conteúdo do quadro;
- `informacao` sem pauta nem pesquisa `ok`. O caso de dado vencido é da F5; a F4 só trata "não veio".

**Textos de contingência** (originais, configuração, sem nova promessa e sem "fica para depois"):

| Tipo | Texto |
|---|---|
| participação | "Ainda não chegou recado para ler agora; o WhatsApp da {rádio} segue aberto." |
| quadro | "O {rótulo} não entra hoje." |
| informação | "Não temos atualização confirmada sobre {rótulo} agora." |
| genérico | "{Rótulo} não vai entrar hoje." |

Os três primeiros seguem a §10.

**Promessa vencida antes do alvo** (`prazo < instante − tolerancia_vencimento_s`):
- A etapa foi pulada ou o roteiro trocou a posição.
- Vira contingência na **próxima fala** de qualquer tipo, salvo vinheta, patrocinador e música sem fala.
- Se a frase não cabe no orçamento desse bloco, espera a próxima. O encerramento sempre resolve todas as abertas: promessas de "fim do programa" pela instrução de cumprir (como o fio condutor), as demais por contingência.
- Depois do encerramento, ou ao abrir outra ocorrência, `vencer` marca `vencida` o que sobrou. É o único caminho para `vencida`, e o aceite exige zero.

**Obrigação do relógio:** em `planejar`, a etapa de `obrigacoes` sem hard time passa a `natureza="obrigatorio"`.
- O backtiming (`_Decisao.espaco`, `relogio.py:629-637`) passa a reservar o tempo dela.
  - Reserva o máximo da unidade (`UNIDADES_PADRAO`), não a duração da etapa: "Participação ou jogo" do C tem 7 min de etapa e 20–90 s de fala.
- As janelas de música antes dela encolhem.
- Se mesmo assim ela não couber (`relogio_etapa_pulada`, `relogio.py:889-891`):
  - log `relogio_promessa_pulada promessa_id`;
  - a promessa vence e cai na contingência da próxima fala.
- Sem relógio, nada muda na escolha do bloco: a posição prometida trocada vira contingência.

### 6.7 Participação ("toca agora" e ouvinte inexistente)

`checar_participacao(fala, ctx)` roda nas fases "pre" e "final". Nomes comparados com a regra de contenção de `validacao_fala._mesma` ("Seu Ditinho" × "Ditinho").

| Regra | Quando | Remediação |
|---|---|---|
| `pedido_nao_selecionado` | nome de `nomes_conhecidos` que não está em `nomes_selecionados`, com construção de execução ("pediu", "toca agora", "vai tocar", "já já", "recebi o seu pedido") ou citado sem estar em `nomes_ja_atendidos` | V1 ("Cite só {selecionado}; não cite outros ouvintes"), depois `remover_frase` |
| `ouvinte_nao_autorizado` | em frase de participação (abraço, beijo, alô, recado, mensagem, pediu, mandou, escreveu), um nome com inicial maiúscula fora dos nomes conhecidos | idem |
| `participacao_simulada` | sem nenhum pedido selecionado nem `nome_recente`: "chegou (agora) uma mensagem", "acabou de chegar", "recebi um pedido", "uma ouvinte pediu", "muita gente pediu" | idem; fala vazia vira `fala_reserva_neutra` |
| `pedido_sem_mencao` (D10) | bloco `chamada_ouvinte` com `pedido_ouvinte` selecionado e o nome ausente da fala final | V1 ("Cumprimente {nome} pelo nome"); se continuar ausente, o pedido volta para a fila e a resposta sai sem `pedido_id` |

- Ficam fora da camada de nomes desconhecidos:
  - os nomes de `nomes_nao_musica` da F3 (rádio, cidade, programa, locutor, elenco, quadros);
  - "WhatsApp";
  - as partes de cada menção de música (`mencoes_musica`);
  - a primeira palavra da frase quando sozinha ("Alô", "Quer").
- `remover_frases` ganha corte de oração em " e também para" / " e para", além da vírgula. "Um abraço para Cida Morais e também para a Dona Firmina" mantém Cida.
- Regra 3 da skill, "'toca agora' só com pedido selecionado para o próximo evento":
  - é verdade por construção quando a música do pedido é a faixa confirmada do bloco (`EstadoMusical.confirmada`, F3);
  - fora disso, `pedido_nao_selecionado` e `musica_nao_confirmada` (F3) cobrem.

### 6.8 Fluxo legado e pedido indisponível

**D2, pedido indisponível sem nome no ar (§10).** Em `resolver_musica_e_pedidos`, no ramo `pedido_sem_resultado` (`contexto.py:308-319`):
- uma porta nova `reprovar_pedido(db, pedido, "Música indisponível")` faz `nao_atendido`, registra o evento e dá `commit` **antes** da geração;
- `pedido_musica=None` no resto do bloco;
- com isso:
  - no formato musical e com relógio, o bloco vira só música (`contexto.py:333-335`);
  - no padrão, vira anúncio normal da faixa automática;
  - a linha "não foi encontrada" (`prompt_emissao.py:396-403`) sai;
  - `_pedido_confirmavel` não devolve o pedido;
- a equipe vê "Não atendido — Música indisponível" no painel. Nenhuma busca é repetida, então não há laço.

**D1, legado confirma a reprodução.**
- `_proximo_pedido_fila_dentre` (`router.py:1564-1586`):
  - seleciona `programa_id IS NULL`, `atendido=False` e estado fora de `selecionado`/`executado`/`nao_atendido`/`cancelado`/`expirado`, cobrindo `em_fila` e o `aguardando_revisao` migrado;
  - marca `estado="selecionado"`, `selecao_token`, `selecionado_em` e o evento `selecionar_legado`;
  - mantém o `with_for_update(skip_locked=True)`;
  - **não** marca `atendido`.
- `_pedido_confirmavel` devolve também o pedido legado, com `pedido_programa_id = programa.id`.
- `gestao.confirmar` (`gestao.py:190-216`) aceita `pedido.programa_id IS NULL` quando o rádio do pedido é o rádio do programa informado (o token continua obrigatório).
- `alterar_pedido("reenfileirar")` (`gestao.py:167-175`) leva o legado para `em_fila`, não para `aguardando_revisao`, porque o legado não tem revisão.
- Filtros que passam a ignorar o legado `selecionado`:
  - `_ha_pedido_musica_pendente` (`router.py:1800-1801`);
  - `_pedidos_em_fila` (`router.py:1293-1306`);
  - `_pedido_recente_nao_atendido` (`router.py:1589-1609`), que também ganha `programa_id IS NULL` e corrige o defeito do fato 9.
- `atendido` passa a significar "o player confirmou" também no legado. `_ouvinte_recorrente_*` continua lendo `atendido=True`, agora com o significado certo.
- O painel não muda: ele já confirma quando recebe `pedido_id`, token e programa (`participacoes.ts:4-5`).

**D7, espiada do legado.**
- O recurso fica, com os filtros acima.
- A frase "o pedido em si ainda vai ser atendido … depois" sai do prompt.
- O nome espiado só vale com "chegou uma mensagem"; nunca com "pediu … toca" ou com prazo.

### 6.9 Prompt (`prompt_emissao.py`, `prompts.py`, `geracao.py`)

- A regra geral de "promessa vaga" (`prompt_emissao.py:235-237`) ganha a regra 4 da skill: "Não prometa conteúdo futuro ('daqui a pouco', 'depois do intervalo', 'já já', 'ainda hoje') fora da agenda informada." É uma linha editada, não acrescentada: muda os 28 goldens numa linha só (D6).
- **Linha de agenda**, só quando `chamadas.agenda` não está vazia e o bloco não é encerramento nem fechamento curto: "Agenda confirmada adiante (só isto pode ser chamado como próximo): {rótulo} em cerca de {N} minutos{; conteúdo}…"
  - Com relógio, substitui a última frase de `_instrucao_relogio` (`prompts.py:327-328`) quando há agenda; sem agenda, a frase atual fica.
  - Sem relógio, a referência é "mais adiante neste programa".
- Música sem faixa (`prompt_emissao.py:420`): sai "chamada pro próximo momento do programa"; fica "transição curta e natural, sem prometer nada".
- Pedido recente (`prompt_emissao.py:376`), conforme D7.
- Reserva do multivoz (`geracao.py:149`): passa a `fala_reserva_neutra(ctx)`, sem "já volto com mais uma novidade".
- Encerramento e fechamento curto mantêm "Não prometa retorno" (`prompts.py:334`, `formato.py:54`). O encerramento ganha as linhas de cumprimento e contingência das abertas.

### 6.10 Contratos e painel

- `LiveProgramResponse.promessas: PromessasBloco | None = None`. Nulo quando não há nada, então os goldens não mudam.
  ```python
  class PromessaResponse(BaseModel): id: int; tipo: str; trecho: str; evento_alvo: str; prazo: datetime | None = None; prazo_posicao: int | None = None
  class PromessaResolvidaResponse(BaseModel): id: int; estado: Literal["cumprida", "cancelada", "vencida"]; contingencia: str | None = None
  class PromessasBloco(BaseModel): registradas: list[PromessaResponse] = []; resolvidas: list[PromessaResolvidaResponse] = []
  ```
- `ValidacaoFalaResponse` não muda de forma: `regra` é `str` e ganha os valores novos. `acao` fica com o mesmo `Literal`.
- `RelogioAoVivo.obrigacoes: list[str] | None = None`. Usa `None` e não `[]`, para não mexer no retrato dos goldens com relógio.
- Legado (D1): a resposta passa a trazer `pedido_id`, `pedido_token`, `pedido_programa_id` e `pedido_radialista_id`. Os campos já existem e são opcionais.
- **Painel:** só tipos opcionais em `frontend-painel/lib/liveTypes.ts` (`promessas?`, `relogio.obrigacoes?`). Sem tela nova; o relatório é da F11. `vitest` e `tsc` só por causa dos tipos.
- O prewarm serializa a resposta inteira (`app/live/prewarm.py:80`): nada a fazer.

### 6.11 Simulador

- `metricas.py`:
  - `detectar_promessas` vira invólucro de `app.live.promessas.detectar`, com importação preguiçosa, como `mencoes` da F3;
  - `_pedido_indevido` delega a `app.live.participacao` com o pedido do bloco;
  - sem detector próprio, como no teste S3 da F3.
- Compatibilidade: um as-run sem dados do backend (o artificial de `test_simular_hora.py:265-351`) continua sendo medido pelo detector, como hoje.
- `emissao.py`: guarda a resposta de cada bloco (`promessas`, `validacao_fala`) no evento.
- `simular_hora.py`:
  - ao fim, lê `PromessaNoAr` pela sessão (como `pedidos_finais`);
  - grava `as_run["promessas"]`;
  - no `resumo`:
    - `promessas` com registradas, cumpridas, canceladas com contingência, canceladas sem ar, vencidas e abertas no fim;
    - `promessa_vencida = vencidas + abertas_no_fim`;
    - `promessa_sem_registro`: promessa detectada no texto que foi ao ar, nem livre nem registrada.
- Cenário dedicado da F4, que **não** altera as três fixtures de linha de base:
  - uma promessa com evento e conteúdo (cumprida);
  - uma com evento e sem conteúdo (contingência, por exemplo "mais tarde a gente lê os recados" no musical A, que não tem abraço na fila no retorno das 27:00);
  - uma sem evento (removida);
  - uma participação simulada.
  - Pode ser uma fixture em `tests/fixtures/programas/cenarios/` ou um parâmetro só de teste, `simular(..., injecoes_extra=..., pedidos_extra=...)`.

### 6.12 O que não muda

- Programa sem relógio: a escolha do bloco e a ordem do `random` ficam iguais. A agenda pelo roteiro é pura.
- Sem promessa no texto: nenhuma escrita nova no banco e nenhuma chave no Redis.

## 7. Ordem de commits e impacto nos 28 goldens

| # | Commit | Comportamento | Goldens (`tests/fixtures/caracterizacao_proxima/`) |
|---|---|---|---|
| 1 | Detector de promessas, agenda e casamento (`app/live/promessas.py`, puro) + `casos.json` | igual | 0 |
| 2 | Detector de participação (`app/live/participacao.py`, puro) + `casos.json`; corte de oração em `remover_frases` | igual | 0 |
| 3 | Modelo `promessas_no_ar`, migração aditiva, exclusões em `config/router.py` | igual | 0 (o retrato não lê a tabela) |
| 4 | `relogio.planejar(obrigacoes)` e `Plano.seguintes` | igual sem obrigação | 0 |
| 5 | Checagens registradas (modo por regra, D12); contexto com agenda, promessas e nomes; registro depois do TTS; `promessas` na resposta | **muda** só com promessa ou nome indevido no texto | 0 esperados. Conferir `musica_sem_faixa` ("já já tem mais rádio" tem de sair como continuidade); se mudar, regravar com justificativa |
| 6 | Cumprimento, contingência garantida, vencimento, obrigação lida do banco; 3 cenários novos de golden (retorno que cumpre, retorno com contingência, vencida sem relógio) | **muda** com promessa aberta | 0 existentes + 3 novos |
| 7 | D2: pedido indisponível sem nome no ar | **muda** | `pedido_sem_resultado` |
| 8 | D1: legado com seleção e confirmação; D7: filtros da espiada | **muda** em todo pedido legado | `pedido_legado`, `pedido_sem_resultado`, `chamada_abraco`, `chamada_sorteio`, `chamada_recorrente`, `chamada_recorrente_dias`, `musical_musica_pedido` (linha da fila e campos `pedido_*`) |
| 9 | Textos de prompt (§6.9): regra geral, agenda, música sem faixa, pedido recente, reserva do multivoz | **muda** texto | **28** (uma linha de regra) + linha de agenda em `relogio_a_link` e onde houver agenda + `comentario_pedido_recente` e `musica_sem_faixa` (textos) |
| 10 | Simulador mede promessas e pedidos pelo backend; cenário dedicado; testes S | — | — |
| 11 | Painel: tipos opcionais | — | — |
| 12 | Rodadas da simulação, `RELATORIO.md`, `pendencias.md`, `testes.md`, `docs/plano.md` | — | — |

Notas sobre a ordem:
- A D1 fica isolada no commit 8. Se o usuário escolher a alternativa B, ele sai sem mexer nos outros.
- O commit 9 vem por último entre os que mudam texto, para que todas as regravações de prompt aconteçam numa só, com o diff revisado.

## 8. Testes, nesta ordem

**Caracterização**
- **C1.** Os 28 goldens ficam idênticos nos commits 1 a 6. Os commits 7, 8 e 9 regravam só os listados na §7, com o diff revisado no próprio commit.
- **C2.** Antes do commit 8, caracterizar o legado de hoje em teste próprio:
  - seleção marca `atendido`;
  - `confirmar` devolve 409 para `programa_id` nulo.
  - O commit 8 inverte as asserções de propósito, para a mudança ficar explícita no histórico.

**Unitários**
- **U1, `test_live_promessas.py::detectar`:**
  - cada classe de marcador;
  - tipo por palavra;
  - acento e caixa;
  - uma por frase;
  - "toca agora" e "agora vem" não contam;
  - continuidade;
  - "até amanhã".
- **U2, agenda do plano:**
  - A às 12:35 traz o retorno das 27:00;
  - intervalo sem patrocinador fica fora;
  - entrevista fica fora;
  - noticioso só com fonte;
  - etapas concluídas ficam fora;
  - quadro com rótulo e conteúdo.
- **U3, agenda do roteiro:**
  - estrutura do popular;
  - musical dá agenda vazia;
  - **zero chamadas ao `random`** (espião);
  - `ia_pode_adicionar_blocos` não altera a agenda.
- **U4, `casar`:**
  - prazo em segundos e em posições;
  - rótulo, conteúdo, tipo;
  - evento cancelado;
  - "depois do intervalo" exige intervalo;
  - música só confirmada;
  - "fora": volta pela grade (`dias_semana` de amanhã) × conteúdo de amanhã;
  - teto de 3 abertas.
- **U5, `checar_promessas`:** instrução com a agenda; modo avisar.
- **U6, benchmark de promessas:** 7/7 `promessa_sem_evento` e 0 falsos positivos nas outras 63.
- **U7, `test_live_participacao.py`:**
  - selecionado passa; em fila ou `nao_atendido` é acusado;
  - nome desconhecido em frase de participação;
  - mensagem simulada sem pedido;
  - exclusões: rádio, programa, locutor, cidade, elenco, quadro, WhatsApp, partes de menção de música;
  - D8 (volta a quem já foi atendido, sem construção de execução);
  - D7 (nome recente só com "chegou mensagem");
  - **benchmark: 5/5 `pedido_indevido`, 1/1 `ouvinte_inexistente`, 0 falsos positivos.**
- **U8:** `remover_frases` corta "e também para X" e mantém o selecionado; `pedido_sem_mencao`.
- **U9, `test_live_relogio.py`:**
  - com `obrigacoes` vazio, o `Plano` fica igual na grade dos presets A, B e C;
  - com obrigação, o backtiming reserva o máximo da unidade e o teto da música encolhe;
  - etapa prometida sem espaço gera log e vence;
  - `Plano.seguintes` exclui as concluídas.
- **U10, `test_promessas_repo.py`:**
  - registro idempotente por `request_id`;
  - `abertas` por ocorrência;
  - `resolver` com `with_for_update`;
  - `vencer`: outra ocorrência, e o que sobra depois do encerramento;
  - trilha em `eventos`;
  - log sem nome nem trecho (`caplog`).
- **U11, migração (padrão de `test_relogio_migracao.py`):** aditiva, idempotente (roda duas vezes), não toca outras tabelas.
- **U12, contingência:**
  - texto por tipo, sem nova promessa (o próprio `detectar` aplicado ao texto tem de dar zero);
  - `garantir_contingencia` insere quando falta e não duplica;
  - preservada pelo encurtamento B e C.
- **U13, `test_live_prompt_emissao.py`:**
  - `promessas` e `participacao` entram na lista de módulos que não importam o router;
  - `montar_prompt` continua puro;
  - linha de agenda só com agenda;
  - encerramento e fechamento curto mantêm "Não prometa retorno";
  - contingência com a frase exata.

**Integração** (HTTP, patches por nome em `app.live.router`)
- **I1.** Relógio A no link: "Mais tarde a gente lê os recados" gera uma linha `aberta` com `evento_alvo` da etapa 27:00 e `promessas.registradas` na resposta.
- **I2.** "Daqui a pouco tem receita de bolo": reescrita com a agenda na instrução; persistindo, a frase sai. Nenhuma linha gravada. No máximo 2 LLM.
- **I3.** Retorno com `pedido_ouvinte` selecionado e promessa aberta: linha de "cumpra" no prompt e a promessa vira `cumprida`.
- **I4.** Retorno sem pedido: linha de contingência no prompt. Se o dublê a ignora, o código a insere. A promessa vira `cancelada` com contingência.
- **I5.** Obrigação: com uma promessa aberta para o retorno, o `espaco_s` e o teto da música antes dele diminuem, e a etapa não é pulada.
- **I6.** Promessa vencida antes do alvo: contingência na próxima fala. O encerramento com abertas resolve todas; depois dele, nenhuma fica `aberta`.
- **I7.** Sem relógio (estrutura do popular):
  - "daqui a pouco… recado" com o próximo `chamada_ouvinte` a 8 posições é removido;
  - "mais tarde" é registrado como `roteiro:<posição>`;
  - o `chamada_ouvinte` seguinte com pedido cumpre.
- **I8.** "Toca agora":
  - pedido novo selecionado passa;
  - nome de pedido em fila é removido; a F3 remove a música;
  - no máximo 2 LLM e 2 sínteses.
- **I9.** Ouvinte inexistente junto do selecionado: sai só a oração; `validacao_fala` traz `ouvinte_nao_autorizado`.
- **I10.** Participação simulada sem pedido: a frase sai; fala vazia vira reserva neutra.
- **I11, D2.**
  - Nome fora do prompt e da fala.
  - Pedido `nao_atendido` ("Música indisponível") antes da geração.
  - Musical ou relógio: `fala == ""`. Padrão: anúncio normal.
  - Resposta sem `pedido_id`.
  - Edita `test_live_router.py:1117-1165` (`atendido is True` passa a `estado == "nao_atendido"`).
- **I12, D1.**
  - Legado: seleção vira `selecionado` com token e `atendido=False`.
  - `POST /ouvintes/pedidos/{id}/reproducao` com `executado` leva a `executado` e `atendido=True`; com `falhou`, a `nao_atendido`.
  - O selecionado não é escolhido de novo.
  - `_ha_pedido_musica_pendente`, a espiada e `_pedidos_em_fila` o ignoram.
  - `reenfileirar` devolve o legado a `em_fila`.
  - Edita `test_live_router.py:2443-2473`.
- **I13, D7.** A espiada ignora linhas do fluxo novo (`programa_id` preenchido) e as que não estão abertas; o prompt fica sem "vai ser atendido depois".
- **I14.** `DELETE /config/programas/{id}` e a exclusão de radialista apagam `promessas_no_ar` (asserção explícita, porque o SQLite não acusa FK).
- **I15.** Contrato: campos atuais iguais; `promessas` nulo sem promessa; `relogio.obrigacoes` nulo sem obrigação.
- **I16.** Prewarm registra com `request_id`; uma transmissão recomeçada não apaga promessas da mesma ocorrência.
- **I17.** Redis fora (disjuntor aberto): promessas e obrigações funcionam, porque vêm do banco.
- **I18.** Multivoz: remoção por linha e contingência na primeira linha.

**Simulação**
- **S1.** Três perfis × {com relógio, `sem_relogio`, `voz_120`, `sem_inicio_previsto`}. Tem de dar zero em:
  - `promessa_vencida`;
  - `promessa_sem_registro`;
  - `pedido_indevido`;
  - `ouvinte_inexistente`;
  - `anuncio_sem_confirmacao`;
  - `pedidos.atendidos_antes_de_tocar` (D1).
  - E também:
    - `injecao_promessa >= 1` no popular e `injecao_cita_ouvinte >= 1` em variedades, para provar que a injeção aconteceu e foi tratada;
    - critérios da F1, F2 e F3 não piores: hard time ≤ 5 s com relógio, encerramento no ar, 0% fora do orçamento com relógio, no máximo 2 LLM e 2 sínteses por fala;
    - menos de 30 s por rodada e zero rede.
- **S2.** Cenário dedicado: pelo menos uma `cumprida`, pelo menos uma `cancelada` com contingência dita no as-run, uma removida, zero `vencida`.
- **S3.** `metricas` não tem detector próprio de promessa nem de participação (espião, como S3 da F3); o as-run artificial continua medido.
- **S4.** `--modo llm`, só com aprovação explícita de custo: falsos positivos dos dois detectores com texto real.

**Testes existentes editados de propósito** (registrar em `f4/testes.md`):
- `test_simular_hora.py::test_injecoes_aparecem_nas_metricas`: `promessa_vencida >= 1` passa a `== 0` com `injecao_promessa >= 1`; `ouvinte_inexistente >= 1` passa a `== 0` com `injecao_cita_ouvinte >= 1`.
- `test_simular_hora.py::test_pedido_fluxo_legado_atendido_antes_de_tocar`: passa a conferir que o legado confirma depois de tocar (D1).
- `test_live_router.py:1164` e `:2473` (D1 e D2).
- Goldens da §7.

## 9. Riscos e o que não fazer

- **Falsos positivos com texto real de LLM.**
  - "A seguir" e "na sequência" aparecem em outros sentidos.
  - Palavras com inicial maiúscula em frase de participação.
  - Mitigação:
    - padrões em configuração;
    - modo `avisar` por regra (D12);
    - S4 só com aprovação;
    - o protótipo pode estar ajustado demais às 70 falas.
- **Remover frase pode deixar emenda solta ou apagar o cumprimento do selecionado.** O corte por oração (§6.7) e `pedido_sem_mencao` (D10) evitam marcar como executado um pedido que não foi dito.
- **D1 muda o fluxo padrão de todas as contas.**
  - Filtros esquecidos levam a pedido selecionado de novo ou espiado.
  - `confirmar` com `programa_id` nulo.
  - `reenfileirar` sem revisão.
  - Histórico no painel ("Selecionado" em vez de "Executado" até o callback).
  - Fica isolada no commit 8, com C2 antes.
- **Obrigações mexem no backtiming.** Conferir na simulação que o atraso de hard time continua ≤ 5 s e que a música não fica sem faixa que caiba (log `relogio_adiantamento_acima_do_maximo`).
- **FK sem cascata.** Esquecer um caminho de exclusão quebra a exclusão de programa ou radialista em produção (Postgres), sem falhar nos testes (SQLite). Por isso o I14.
- **Contingência inserida aumenta a fala.** Respeitar o orçamento: preferir a próxima fala que comporta a frase e nunca acelerar a voz. O encerramento é o limite.
- **Promessa de bloco que não foi ao ar** (prewarm descartado, corte, pausa). O registro é na geração (fato 3); a contingência pode citar algo nunca dito. Limite conhecido até o as-run da F11.
- **Ordem dos sorteios.** A agenda pelo roteiro não pode chamar `_tipo_proximo_bloco`. As leituras novas do contexto entram depois de todos os sorteios.
- **Redis nos goldens.** Não gravar chave nova quando não há promessa (fato 11).
- **PII.** Nenhum nome, telefone ou trecho em log.
- **Conflito com a F5:** os mesmos arquivos (`validacao_fala.py`, `contexto.py`, `prompt_emissao.py`, `metricas.py`). A F4 entra antes; a F5 reaproveita `Violacao`, o modo por regra e o padrão de checagem.
- **Não fazer nesta frente:**
  - F5: `DadoVerificavel`, validade de dado e o isolamento do texto do ouvinte legado (auditoria 3);
  - F8: consolidar a memória (a F4 só persiste promessas; a F8 consome);
  - F11: as-run persistente, relatório pós-programa no painel, peça de reserva, contingência de áudio e estado pela reprodução;
  - F12: convidado real e entrevista, moderação do legado, revisão por categoria;
  - chamada de LLM para validar, ou terceira chamada;
  - tela nova no painel;
  - refatorar `_atender` e `alterar_pedido`;
  - mudar a escolha de blocos sem relógio;
  - tease de música nova num bloco de fala (D3 da F3 continua).

## 10. Decisões para o usuário (não bloqueiam; padrão sugerido entre parênteses)

- **D1. Fluxo legado e o "estado correto".**
  - **(A)** O legado passa a `selecionado` com token e confirmação de reprodução, como o fluxo novo, sem moderação (§6.8). Atende o aceite como a F0 o definiu.
  - **(B)** O legado fica como está, e a F4 revisa a métrica `pedido_indevido`, o teste `:485-491` e o rótulo `f4-legado-atendido-antes-de-tocar`, que hoje dizem "indevido de propósito".
  - (A, isolada no commit 8.)
- **D2. Pedido de música indisponível.**
  - **(A)** Não vai ao ar com nome; o pedido fica `nao_atendido` ("Música indisponível") à vista da equipe, e o bloco segue como música comum.
  - **(B)** Manter "não achei sua música, vai X no lugar", que contradiz a §10 e o benchmark.
  - (A.)
- **D3. Onde guardar as promessas.**
  - Tabela `promessas_no_ar` como única fonte, sem Redis. O plano diz "Redis + persistência", mas o Redis da F3 falha aberto, e esquecer uma promessa é vencê-la.
  - Ou Redis mais banco.
  - (Só banco.)
- **D4. Programa sem relógio.**
  - Agenda pelas próximas posições do roteiro, com prazo em posições e contingência na posição.
  - Ou proibir qualquer tease sem relógio.
  - (Roteiro.)
- **D5. Contingência.**
  - Frase determinística da configuração, pedida no prompt e inserida pelo código se faltar.
  - Ou só instrução ao LLM.
  - (Determinística; é o único jeito de medir o aceite no modo fake.)
- **D6. Prompt.**
  - Editar a regra geral em todos os programas (os 28 goldens mudam uma linha) e acrescentar a agenda quando houver.
  - Ou mexer só com relógio e deixar o resto para o validador.
  - (Todos.)
- **D7. Espiada de pedido recente no legado.**
  - Manter, com os filtros corrigidos, sem "vai ser atendido depois" e só como "chegou uma mensagem".
  - Ou remover o recurso.
  - (Manter.)
- **D8. Citar ouvinte já atendido nesta transmissão** (o gancho de `prompt_emissao.py:118-119`).
  - Permitido sem construção de execução.
  - Ou proibido.
  - (Permitido.)
- **D9. Promessa para outra edição.**
  - Só a volta do programa conferida pela grade ("até amanhã" quando há programa amanhã); conteúdo prometido para outro dia é violação até a F11.
  - (Assim.)
- **D10. Pedido selecionado que some da fala.**
  - Reescrita pedindo o nome; persistindo, o pedido volta à fila e não é confirmado.
  - Ou só log.
  - (Devolver.)
- **D11. Prazos e horizontes** (hipóteses, em `ConfigPromessas`):
  - imediato: 300 s ou 2 posições;
  - curto: 900 s ou 4 posições;
  - "mais tarde": fim da ocorrência;
  - tolerância de vencimento: 60 s;
  - reserva da obrigação: máximo da unidade;
  - teto de 3 promessas abertas.
  - (Esses.)
- **D12. Modo do validador por regra.**
  - `validacao_promessa_modo` e `validacao_participacao_modo` (`corrigir` | `avisar`, padrão `corrigir`), ao lado de `validacao_musica_modo`.
  - Ou um modo único.
  - (Por regra, para poder ligar `avisar` só no detector que der falso positivo com LLM real.)

## 11. Pendências de frentes anteriores atribuídas à F4

| Origem | Pendência | Tratamento |
|---|---|---|
| F0 | Pedido indisponível vira fala com o nome do ouvinte | D2, commit 7 |
| F0 | Detector provisório de promessa no simulador | §6.11, commit 10 |
| F0 | Legado atendido antes de tocar conta como indevido "de propósito" | D1, commit 8 |
| F1 | Teases a partir dos eventos agendados do relógio | §6.4 e §6.9 |
| F1 | Pedido de música aceito só com espaço ≥ 330 s; a faixa pedida não passa pelo teto (`relogio_pedido_acima_do_espaco`) | Fica. Se a faixa do pedido não couber, é contingência de áudio (F11); a F4 só garante que "toca agora" seja da faixa confirmada |
| F3 | `Chamadas.promessas`, checagem em `CHECAGENS_POS_GERACAO`, eventos de `ctx.tempo.plano`, trocar o detector do simulador | §6.2 a §6.6 e §6.11 |
| F1/F3 | Estado marcado na geração, não na reprodução | Fora: F11 (§9) |

## 12. Dependências

- Nenhuma bloqueia. F0 a F3 estão na branch, e o portão da F3 deu VERDE.
- A F5 ainda não foi implementada; a auditoria dela supõe a F3 antes. A F4 entra antes da F5, que refaz a base sobre os mesmos arquivos (§9).
- Modos `llm` e `completo` do simulador só com aprovação explícita de custo.

**Tamanho:** grande, menor que a F3.
- Código novo: cerca de 900 a 1100 linhas, em quatro módulos novos (`promessas.py`, `participacao.py`, `promessas_repo.py` e o modelo) mais a migração.
- Arquivos alterados:
  - backend: `contexto.py`, `prompt_emissao.py`, `prompts.py`, `geracao.py`, `validacao_fala.py`, `router.py`, `relogio.py`, `roteiro.py`, `portas.py`, `whatsapp/gestao.py`, `config/router.py`, `main.py`, `models/__init__.py`, `config/settings.py`;
  - simulador: `scripts/simulacao/metricas.py`, `emissao.py` e `scripts/simular_hora.py`;
  - painel: `frontend-painel/lib/liveTypes.ts`.
- Testes: cerca de 90 a 120 novos.
- 12 commits.

PRONTA PARA IMPLEMENTAR
