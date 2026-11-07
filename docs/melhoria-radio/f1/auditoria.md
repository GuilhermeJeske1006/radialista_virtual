# Auditoria F1: relógio, espelho e hard time

Branch auditada: `melhoria/f0-bancada` (commit `db47401`). O código de `backend/app/` e
`frontend-painel/` é igual ao da `master` (`git diff master HEAD -- backend/app frontend-painel`
vazio). Auditoria feita em 07/11/2026, só leitura no código. Fontes: `docs/plano-melhoria-radio.md`
(F1, Transversal, Portão), `docs/pesquisa-radio-locufy.md` (§2, §4.3, §7, §9, §10, §12.3, §13),
`docs/melhoria-radio/f0/auditoria.md`, skill `referencia-radio`, `docs/auditoria.md`,
`docs/refatoracao.md`.

**Pré-requisito:** o portão da F0. Em 07/11 ainda não existem `backend/scripts/simular_hora.py`,
`backend/scripts/simulacao/` nem `backend/tests/fixtures/programas/` na árvore de trabalho. Os
passos 1 a 7 da §5.12 não dependem do simulador. O passo 8 (simulação) e o teste de paridade dos
presets dependem dele.

## 1. Estado atual: o plano confere com o código?

| Afirmação do plano | Situação | Evidência |
|---|---|---|
| O programa tem `horario_inicio`, `horario_fim`, `estrutura_blocos` e `perfil_programacao` | confirmado | `backend/app/models/programa.py:33-34`, `:52-53` |
| O próximo bloco sai da posição no roteiro (`_tipo_proximo_bloco`, `ROTEIRO_PADRAO`, `ROTEIRO_MUSICAL` em `app/live/formato.py`) | confirmado, com localização **diferente** | Os roteiros estão em `app/live/formato.py:8,10`. `_tipo_proximo_bloco` está em `app/live/router.py:718-760`, não em `formato.py`. |
| E pela contagem de falas (`total_falas`) | confirmado | `router.py:1925`. A vinheta pulada soma `passos_roteiro` (`:1939-1961`; o painel soma em `useLiveEngine.ts:1253,1493`). |
| Há marcos de tempo (`_marco_tempo_programa`, `_ajuste_energia_meio_programa`) | confirmado | `router.py:376-391` e `:394-411`. São só texto de prompt, com precisão de minuto, calculado a partir de `now()` por `minutos_restantes`. |
| Não há horário fixo dentro da hora, janela, obrigatório/ajustável/reserva nem cálculo de tempo restante | **diferente em parte** | Existe tempo restante até o **fim do programa**, em minutos inteiros (`app/guardrails/schedule.py:66-104`). Ele só decide o encerramento (`router.py:1929-1937`, limiar de 3 min em `:329`) e os marcos. Dentro da hora não há nada: `git grep -i "relogio\|hard_time\|backtiming"` em `app/` e no painel só acha comentários sobre "relógio de parede". |
| A análise de 09/09 registra que o ciclo é por quantidade de faixas | confirmado | `docs/analises/2026-09-09-implementacao-musical.md:55` |
| Lacuna: a fala é gerada sem saber se há espaço | confirmado | O único orçamento é fixo por tipo e só existe no formato musical (`formato.py:13-19`; usado em `router.py:2706` e `:2948`). Nada consulta o tempo antes do LLM. |
| Entrega 1: evento com `minuto_inicio` | **diferente (decisão da F0)** | O minuto inteiro não representa 00:40, 12:35 nem 59:30 (§9.A). A F1 adota **`inicio_s`**, como as fixtures da F0 (`f0/auditoria.md:328`). |
| Entrega 7: editor em `frontend-painel/app/programas` | **diferente** | `app/programas/page.tsx` só lista os programas e abre `components/EditarProgramaForm.tsx` num modal (`page.tsx:204`). O roteiro é editado na seção "Roteiro do programa" (`EditarProgramaForm.tsx:541-694`) e na rota `/radialista/[id]/programas/[programaId]/grade` (`components/GradeProgramacaoForm.tsx`, `RoteiroBlocosEditor.tsx`). O editor do relógio entra em `components/` e aparece no formulário. |

## 2. Fatos do código que a F1 precisa respeitar

**A hora da geração não é a hora em que o bloco vai ao ar.** Os fatos abaixo vêm da F0 e foram
reconfirmados.
- O painel prepara 2 blocos à frente (`frontend-painel/lib/filaPreparo.ts:16`; `retirar` em `:63-69`). O contexto avança na geração (`useLiveEngine.ts:1490-1495`).
- O pedido de `/proxima` não traz nenhum campo de horário (`router.py:96-110`). Tudo usa `now()`:
  - o encerramento (`:1931`);
  - o `agora_local` da hora certa (`:2011`, `:2541`);
  - os marcos (`:381`, `:399`);
  - o contexto de data e hora do prompt (`app/llm/prompt_builder.py:154`).
- A preparação começa 90 s antes do início (`useLiveEngine.ts:37`). O prewarm do servidor gera a primeira fala de 0 a 90 s antes, também com `now()` (`app/live/prewarm.py:64-66`, `:96`).
- **O início agendado é verificado a cada 15 s** (`useLiveEngine.ts:1927`). A abertura pode atrasar até 15 s. Isso fura o critério de 5 s no hard time de 00:00 e o simulador da F0 não reproduz.
- No programa agendado, o painel corta seco em `horario_fim` + 1 s (`useLiveEngine.ts:1947-1961`).
- O painel já mede a duração real de cada bloco no relógio de parede (`useLiveEngine.ts:1586-1588`, `atualizarDuracaoFala` em `:1259-1267`).

**Decisões dentro de `gerar_proxima_fala` (`router.py:1899-2957`, 1059 linhas).**
- A função tem quatro `return LiveProgramResponse(...)`:
  - vinheta (`:1947`);
  - patrocinador (`:1967`);
  - música sem fala do formato musical (`:2063`);
  - final (`:2918`).
- Bloco de notícia sem fonte vira música (`:1980-1991`). Comentário sem assunto num pipeline ativo também vira música (`:1999-2005`).
- "Primeira fala" é sempre `total_falas == 0` (`:2495`, `:2662`, `:2706`, `:2813`, `:2948`). Com relógio, uma vinheta de abertura antes da fala faz a abertura chegar com `total_falas == 1`. Ela perderia o orçamento de abertura, a "pergunta do dia" e o registro do fio condutor.
- O prompt descreve o roteiro "em loop" (`:2199`) e pede "4 a 6 frases" no formato padrão (`:2187`). Ambos são falsos para um programa com relógio.
- Há uma única revisão por orçamento (`:2706-2760`), hoje só no formato musical.
- `_categoria_bloco` trata `retomada`/`identificacao` como `abertura` sem LLM (`:1137-1138`). Todos os tipos que a F1 vai gerar casam por prefixo, então não chamam `classificar_categoria_bloco`.

**Música.**
- `buscar_musica` aceita `duracao_max_segundos` só como **preferência**. No último recurso ela relaxa o limite (`app/live/music.py:429`, `:517-525`).
- `_buscar_musica_para_bloco` registra a faixa como tocada **antes de devolver** (`router.py:1672-1674`). Um teto de duração precisa ser conferido ali dentro, antes do registro.
- **Os testes trocam `_buscar_musica_para_bloco` por funções de assinatura fixa:** `lambda db, programa, tipo=None` em `tests/test_live_router.py:1145` e `lambda *_` em `:2945`. Um kwarg novo só pode ser passado quando o programa tem relógio, senão 2 testes quebram.
- `musica-substituta` (`router.py:3021`) troca a faixa na hora de tocar, sem saber o espaço que resta. A diferença de duração é corrigida pelo desvio medido no painel (§5.9).

**Contratos de configuração.**
- `PUT /config/programas/{id}` substitui todos os campos via `model_dump()` (`app/config/router.py:1308-1321`). O refinamento por IA faz o mesmo `setattr` em laço (`:730-745`).
- O painel devolve no PUT tudo o que veio no GET: `normalizarPrograma` usa `...p` (`lib/types.ts:296-297`) e `semCamposSistema` só tira `id`/`radio_config_id` (`EditarProgramaForm.tsx:39-42`, `GradeProgramacaoForm.tsx:59-62`).
- `ProgramaRequest` não define `model_config`. Em Pydantic 2.10, campo extra é ignorado.
- Consequência: se o relógio ficar fora de `ProgramaRequest`, nenhum caminho de escrita atual consegue apagá-lo.

**Dados que já existem e a F1 reaproveita.**
- Vinheta com `papel` (`abertura|passagem|encerramento`) e `programa_id` (`app/models/biblioteca_audio.py:47-50`). Já existe `vinheta_encerramento` (`app/vinhetas/servico.py:60-66`).
- Durações: `BibliotecaAudioItem.duracao_segundos` (`biblioteca_audio.py:34`) e `Patrocinador.duracao_segundos` (`app/models/patrocinador.py:38`).
- Feriado nacional calculado (`app/feriados.py:60`). O municipal está em `programa.feriados_municipais` (`programa.py:80`) e é lido por uma função privada do prompt (`prompt_builder.py:103-112`).
- `RadioConfig.timezone` é texto livre, sem validação (`app/models/radio_config.py:50`, `app/config/router.py:52`).
- O painel estima a fala a 2,5 palavras/s, ou 150 wpm (`frontend-painel/lib/duracaoBloco.ts:7`). A F0 usa 145 wpm. A F1 passa a mandar a estimativa do backend (`duracao_prevista_s`), para não haver dois wpm.

**Migrações.** Hoje existem dois padrões:
- versionado, com tabela de controle: `app/db/migrations/consumo_20260925.py`, roda antes do `create_all` em `app/main.py:154-156`;
- colunas por inspeção: `garantir_colunas_programa`, `app/main.py:344-367`, coberto por `tests/test_programa_migration.py`.

## 3. Testes existentes que tocam esta frente

`pytest --collect-only`:
- `tests/test_live_router.py`: 135 testes;
- `tests/test_guardrails_schedule.py`: 22;
- `tests/test_live_prewarm.py`: 4;
- `tests/test_config_router.py`: 48;
- `tests/test_feriados.py`: 8;
- `tests/test_programa_migration.py`: 1.

O que já está coberto:
- **Encerramento por horário:**
  - `test_gerar_proxima_fala_perto_do_fim_vira_encerramento` (`test_live_router.py:380`);
  - `test_musical_encerra_perto_do_fim_em_vez_de_iniciar_outra_musica` (`:3016`, confere `duracao_alvo_segundos == [10, 18]`);
  - `test_fio_condutor_da_abertura_e_retomado_no_encerramento` (`:2325`).
- **Roteiro por contagem:** `test_musical_repete_sequencia_sem_reabrir_ou_inserir_comentarios` (`:2961`). `components/live/__tests__/ProximosBlocosPanel.test.tsx` cobre a cópia em TS.
- **Orçamento musical e revisão:**
  - `test_musical_revisa_retomada_longa_uma_vez` (`:2973`, confere "no máximo 25 palavras" e a ausência de "4 a 6 frases");
  - `test_musical_pedido_real_continua_anunciado` (`:2996`);
  - `test_musical_toca_sequencia_sem_llm_de_locucao_ou_tts` (`:2936`).
- **Marcos:** `:2602`, `:2625`, `:2646`.
- **Agenda:** janela que cruza a meia-noite, dia de início na madrugada, programa avulso depois da meia-noite, `minutos_restantes` com graça (`test_guardrails_schedule.py:49-139`). Todos os testes usam `@freeze_time` e o fuso `America/Sao_Paulo` (`AGORA_UTC`, `test_live_router.py:30`).
- **Prewarm:** grava, uso único, janela de 0 a 90 s (`test_live_prewarm.py:48-98`).
- **Migração de `programas`:** idempotente e preserva a linha (`test_programa_migration.py:4`). **Migração versionada:** `test_consumo_flex.py:224`.
- **Feriado municipal no prompt:** `tests/test_llm_prompt_builder.py:335-349`.
- **CRUD de programa:** `test_config_router.py:126-243`. **Refinamento por IA mantendo a persona:** `:725`.
- **Painel:**
  - `lib/__tests__/filaPreparo.test.ts` (7 casos);
  - `hooks/__tests__/useLiveEngine.preparo.test.ts` (7), que confere campos do corpo de `/proxima` um a um, sem comparar o objeto inteiro, então campo novo não quebra nada;
  - `useLiveEngine.prewarm.test.ts`;
  - `useLiveEngine.test.ts` (`programaNoAr`, `segundosParaInicio`);
  - `EditarProgramaForm.test.tsx`, `GradeProgramacaoForm.test.tsx` (incluindo "salva a programação chamando PUT");
  - `RoteiroBlocosEditor.test.tsx`.

Lacunas:
- Nenhum teste encadeia blocos.
- Nenhum teste passa um horário previsto.
- Nenhum teste cobre o fuso fora de São Paulo ou o feriado na decisão de bloco.
- Nenhum teste cobre a precisão do início agendado (o polling de 15 s).

## 4. Itens de `docs/auditoria.md` e `docs/refatoracao.md` que tocam a F1

| Item | Situação | Relação com a F1 |
|---|---|---|
| auditoria 4: rate limit de `/proxima` | parcialmente resolvido: 60/min por conta (`router.py:1915`) | A F1 não mexe. O campo novo não muda o custo por chamada. |
| auditoria 6: Redis sem timeout | aberto (`app/config/redis_client.py:5`) | A F1 acrescenta 1 ou 2 operações por `/proxima` (estado das etapas). Elas devem **falhar aberto**: sem estado, decide só pelo tempo, com log. O timeout em si é da F3. |
| auditoria 7: N+1 no prewarm | aberto (`prewarm.py:88-89`) | A F1 mexe no prewarm, mas só para passar `inicio_previsto`. Não corrigir aqui; registrar em `pendencias.md`. |
| auditoria 9: TTL do cache de categoria | aberto (`router.py:1107-1120`) | A F1 não aumenta o hash, porque todos os tipos que gera casam por prefixo. Continua com a F6. |
| refatoração §1: separar `gerar_proxima_fala` | aberto (F3) | A F1 **não move** código da rota. Faz inserções pontuais e põe a lógica nova num módulo puro (`app/live/relogio.py`). Esse módulo vira a peça de tempo do futuro `roteiro.py`/`ContextoEmissao` da F3. |
| refatoração §5: acoplamento externo | aberto | O relógio é caminho real e não pode virar dublê no simulador. A F1 não cria chamada externa nova. |
| refatoração §7, faixa 3: `useLiveEngine.ts` grande demais (2016 linhas hoje) | aberto | O cálculo do horário previsto vai para um módulo puro (`lib/relogioAoVivo.ts`). O hook só chama. |

## 5. Desenho da mudança

### 5.1 Princípios

1. **Programa sem relógio segue o caminho atual, byte a byte.** Com `programa.relogio_hora` nulo, `plano = None` e nada muda:
   - o `inicio_previsto` é ignorado;
   - o encerramento continua por `minutos_restantes`;
   - `_buscar_musica_para_bloco` é chamado com a mesma assinatura;
   - o prompt não muda.

   A resposta só ganha campos opcionais.
2. **O relógio é consultado no horário previsto de ir ao ar.** O painel informa esse horário (`inicio_previsto`). Sem ele, cai em `now()`, que é a qualidade de hoje.
3. **O relógio manda no tempo e a estrutura fornece as peças.** Com relógio, o tipo do bloco vem da etapa. A `estrutura_blocos` deixa de rodar em loop e passa a fornecer patrocinadores e quadros. As vinhetas de papel abertura/passagem vêm do programa.
4. **Sem tipo de resposta novo.** O intervalo sai como `patrocinador`, `vinheta` ou `musica`, que o painel atual já sabe tocar.
5. **Números são configuração** (`ConfigRelogio`), com origem na skill `referencia-radio` e na pesquisa. São hipóteses: a F2 calibra e a F6 substitui pelo catálogo de formatos.

### 5.2 Modelo `RelogioHora` (Pydantic, em `app/live/relogio.py`)

```python
TipoEvento = Literal["abertura", "musica", "link", "curadoria", "retorno", "participacao", "conversa",
                     "quadro", "servico", "noticia", "manchetes", "atualizacao", "entrevista",
                     "reportagem", "intervalo", "passagem", "fechamento"]

class EventoRelogio(BaseModel):
    model_config = ConfigDict(extra="ignore")      # aceita corresponde_a/fonte das fixtures da F0
    inicio_s: int = Field(ge=0, lt=3600)
    duracao_s: int = Field(gt=0, le=3600)
    tipo: TipoEvento
    rotulo: str = Field(default="", max_length=80)
    natureza: Literal["obrigatorio", "ajustavel", "reserva"]
    hard_time: bool = False

class RelogioHora(BaseModel):
    versao: Literal[1] = 1
    preset: Literal["A", "B", "C"] | None = None    # origem; None = personalizado
    eventos: list[EventoRelogio] = Field(min_length=1, max_length=40)
    em_feriado: Literal["mesmo", "sem_intervalos", "sem_relogio"] = "mesmo"
    # model_validator: eventos[0].inicio_s == 0; inicio_s[i+1] == inicio_s[i] + duracao_s[i];
    # soma == 3600. Mensagens em português, para o painel exibir.
```

O que cada `natureza` significa no serviço:
- `obrigatorio`: acontece mesmo atrasado, desde que antes do próximo hard time, e consome o espaço do backtiming.
- `ajustavel`: encolhe, desloca ou é pulado.
- `reserva`: só entra para preencher sobra.

`hard_time` marca o **início** do evento como compromisso.

### 5.3 Presets A, B e C: a fonte de verdade fica em `app/live`

Os arquivos ficam em `backend/app/live/relogios/{A_musical_companhia,B_jornal_revista,C_morning_variedades}.json`.
Segue o precedente de `app/postprod/perfis/*.json`, que o `COPY app ./app` do Dockerfile já leva
para a imagem. Eles são carregados e validados na importação (`PRESETS: dict[str, RelogioHora]`).

As durações e os hard times são os da F0 (`f0/auditoria.md:329-338`):
- **A:** 40, 680, 35, 685, 180, 60, 720, 60, 720, 180, 210, 30.
  - Hard times: 0, 1440, 3180 e 3570.
  - Música 3015 s, fala 225 s, intervalos 360 s.
- **B:** 180, 480, 240, 180, 720, 180, 480, 180, 540, 300, 120.
  - Hard times: 0, 900, 1080, 2460 e 3480.
- **C:** 120, 480, 360, 180, 360, 540, 420, 180, 360, 480, 120.
  - Hard times: 0, 960, 2460 e 3480.
- Natureza: abertura, intervalos e passagem/fechamento são `obrigatorio`; música, links e o resto são `ajustavel`.

Tipos por evento:
- **A:** abertura, musica, link, musica, intervalo, retorno, musica, curadoria, musica, intervalo, musica, passagem.
- **B:** manchetes, noticia, servico, intervalo, entrevista, atualizacao, noticia, intervalo, reportagem, participacao, passagem.
- **C:** abertura, musica, conversa, intervalo, servico, musica, participacao, intervalo, quadro, musica, fechamento.

Os rótulos são os da §9.

**Paridade com a F0.** O teste U2 carrega `tests/fixtures/programas/relogios/*.json` e exige
`inicio_s`, `duracao_s`, `tipo`, `natureza` e `hard_time` iguais aos dos presets. Se os textos de
`tipo` da fixture forem outros, a F1 ajusta a fixture, que é de teste. A partir da F1, o simulador
aplica o relógio ao backend com `app.live.relogio.PRESETS[fixture.relogio]` (§5.10). Assim os
presets ficam como fonte única e a fixture só mede.

**Como cada tipo vira bloco.** É uma tabela declarativa `BLOCOS_POR_TIPO`, sem `if` espalhado:

| Tipo do evento | Bloco no formato padrão | No formato musical | Repete enquanto houver tempo |
|---|---|---|---|
| abertura | hora 0: [vinheta de papel abertura, se houver] → `abertura` (primeira); hora > 0: `retomada` (reorientação) | igual | não |
| manchetes (B) | hora 0: `abertura` → `escalada`; hora > 0: `escalada` | igual | não |
| musica | `musica` **sem fala**; pedido real mantém anúncio curto (`orcamento_fala("musica")`) | igual (já é assim) | sim |
| link, curadoria | `comentario` | `retomada` | não |
| retorno, participacao | `chamada_ouvinte` | `chamada_ouvinte` | não |
| conversa | `comentario` (multivoz se houver elenco) | `retomada` | sim |
| quadro | primeiro rótulo de `quadros_fixos` que esteja na estrutura; senão `comentario` | `retomada` | sim |
| servico | `servico` | igual | sim |
| noticia, reportagem | `noticia` | igual | sim |
| atualizacao | `escalada` | igual | não |
| entrevista | `comentario` com assunto aprovado. Sem convidado real (F12/F13), vale a contingência "convidado não entrou → conteúdo aprovado" | `retomada` | sim |
| intervalo | patrocinadores ativos citados na `estrutura_blocos`, na ordem, **no máximo uma vez cada por etapa** | igual | por peça |
| passagem, fechamento | horas que não são a última: [vinheta de papel passagem] ou `identificacao`; última hora: `encerramento` | igual | não |

Os blocos de notícia, serviço e escalada continuam passando pela regra atual "sem fonte vira
música" (`router.py:1980-1991`). Por isso o B só é editorialmente útil depois da F5.

### 5.4 Migração aditiva

- Coluna: `programas.relogio_hora JSON NULL`. Nulo significa sem relógio. No modelo: `relogio_hora: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=None)`.
- O valor é sempre substituído inteiro na gravação. Não precisa de `MutableDict`.
- Módulo novo `backend/app/db/migrations/relogio_20261107.py`, com `VERSAO = "20261107_01"` e `aplicar(engine)`:
  - inspeciona `programas` e sai se a tabela não existir ou se a coluna já existir;
  - senão roda `ALTER TABLE programas ADD COLUMN relogio_hora JSON NULL`.

  A existência da coluna é o próprio estado, então não precisa de tabela de controle. O nome `migracoes_consumo` é específico do consumo e não deve ser reaproveitado.
- Chamada em `criar_tabelas` **depois** de `create_all` e de `garantir_colunas_programa` (`app/main.py:156-159`).
- Postgres e SQLite aceitam `JSON NULL`.

### 5.5 Serviço `app/live/relogio.py`

O núcleo é **puro**: recebe o `instante` explícito, sem `now()`, e não acessa DB nem Redis. Só um
adaptador fino de estado usa Redis. O módulo não importa `app.live.router`, para não criar ciclo:
importa `formato`, `feriados`, `pydantic`, `zoneinfo` e `redis_client`.

```python
@dataclass(frozen=True)
class ConfigRelogio:              # hipóteses de projeto (skill referencia-radio, pesquisa §5/§9)
    wpm: int = 145                                # mesmo padrão da F0; a F2 calibra por voz
    tolerancia_hard_time_s: int = 5               # critério de aceite
    adiantamento_max_s: int = 90                  # quanto um compromisso pode começar mais cedo
    graca_pos_fim_s: int = 1200                   # igual a _GRACA_APOS_FIM_MIN
    inicio_previsto_max_s: int = 1800             # acima disso o campo é ignorado
    musica_duracao_padrao_s: int = 210            # quando a duração da faixa é desconhecida
    unidades: dict[str, tuple[int, int]] = ...    # por tipo de evento: link (10,35), curadoria (15,60),
        # retorno (15,60), participacao (20,90), conversa/quadro/entrevista/reportagem (60,180),
        # servico/noticia/manchetes/atualizacao (20,60), abertura (20,40), passagem (3,15),
        # encerramento (15,45), fechamento_curto (6,15). No formato musical vale o menor entre
        # isto e formato.ORCAMENTOS.

@dataclass(frozen=True)
class Ocorrencia: inicio: datetime; fim: datetime; data: date      # data = dia em que começou
@dataclass(frozen=True)
class Etapa: evento: EventoRelogio; hora: int; inicio: datetime; fim: datetime; tipo_efetivo: str
@dataclass(frozen=True)
class Plano:
    instante: datetime; ocorrencia: Ocorrencia; etapa: Etapa
    proximo_compromisso: Etapa | None; segundos_ate_hard_time: float | None; espaco_s: float | None
    acao: Literal["fala", "fala_reduzida", "fechamento_curto", "musica", "reserva",
                  "adiantamento", "intervalo", "encerramento"]
    tipo_bloco: str            # o que gerar_proxima_fala usa como `tipo`
    primeira: bool             # abertura do programa (hora 0)
    orcamento_s: tuple[int, int] | None; palavras_max: int | None
    duracao_max_musica_s: int | None; musica_sem_fala: bool
    alternativa: "Plano | None"          # usada se nenhuma música couber
    chave_estado: str | None             # peça a marcar como executada

def relogio_do_programa(programa, data: date | None = None) -> RelogioHora | None
    # JSON inválido no banco → None + log; feriado com em_feriado="sem_relogio" → None
def instante_previsto(valor: datetime | None, agora: datetime, cfg) -> tuple[datetime, bool]
    # None → agora; passado → agora; naive → UTC; > agora + inicio_previsto_max_s → agora (aceito=False)
def ocorrencia_em(programa, timezone, instante, cfg) -> Ocorrencia | None
def etapas_da_hora(relogio, ocorrencia, hora, cfg, *, eh_feriado) -> list[Etapa]
def etapa_em(relogio, ocorrencia, instante, cfg) -> Etapa
def proximo_compromisso(relogio, ocorrencia, instante, cfg) -> Etapa | None
def segundos_ate_hard_time(relogio, ocorrencia, instante, cfg) -> float | None
def espaco_livre(relogio, ocorrencia, instante, executadas, cfg) -> float
def planejar(programa, relogio, timezone, instante, *, formato_musical, ultima_categoria,
             ja_encerrou, executadas: set[str], pecas: PecasDisponiveis, cfg) -> Plano | None
def duracao_prevista_fala_s(texto, wpm) -> float      # usa formato.contar_palavras, ignora [tags]
def duracao_prevista_bloco(resposta, cfg, *, duracao_peca_s=None) -> float
# Adaptador de estado (Redis, TTL _TTL_SESSAO_AO_VIVO, falha aberta):
def etapas_executadas(programa_id, ocorrencia) -> set[str]
def marcar_executada(programa_id, ocorrencia, chave) -> None
```

`PecasDisponiveis` é montado pela rota com uma consulta por tipo, e só quando há relógio:
- vinheta ativa de papel `abertura` e de papel `passagem` do programa, com a duração;
- patrocinadores ativos citados na estrutura, com a duração (ou palavras ÷ wpm);
- rótulos de `quadros_fixos` presentes na estrutura;
- se há elenco para multivoz.

**Regras de tempo:**
- **Ocorrência.** Espelha `programa_no_ar`: na madrugada, a data é o dia em que o programa começou (`schedule.py:24-35`). Diferenças:
  - recebe o `instante`;
  - aceita de `inicio` até `fim + graca_pos_fim_s`;
  - fim = `inicio` + a duração de `_duracao_total_minutos`, que soma 24 h quando o fim é menor ou igual ao início.

  Fora disso, devolve `None` e o caminho atual vale. Isso cobre a transmissão manual fora da grade, que o painel permite (`useLiveEngine.ts:1938-1946`).
- **Âncora e virada de hora.** A posição na hora conta a partir do **início da ocorrência**: `hora, pos = divmod(instante - inicio, 3600)`, em tempo decorrido real entre instantes com fuso. Nas horas maiores que 0:
  - a abertura vira `retomada`;
  - a passagem das horas que não são a última vira `identificacao`;
  - o próximo compromisso pode ser a abertura da hora seguinte.
- **Fuso.** Tudo usa `ZoneInfo(radialista.timezone)`. Com horário de verão, a posição continua sendo tempo decorrido real e a ocorrência pode ter 23 h ou 25 h. Fuso inválido já quebra a rota hoje em `minutos_restantes`, e a F1 não acrescenta outro ponto de falha.
- **Fim que não cai em hora cheia** (por exemplo, 14:00–15:30, ou um programa de 45 min):
  - eventos que começam depois do fim são descartados;
  - eventos que cruzam o fim são truncados;
  - surge um evento `encerramento` sintético em `[fim − unidade_max(encerramento), fim]`, obrigatório e com hard time.

  Se o último evento da última hora for passagem ou fechamento e terminar exatamente no fim, ele mesmo vira o encerramento.
- **Feriado.** Vale a data da **ocorrência**, não a do instante. Ele conta se `feriado_nacional_do_dia(data)` encontrar o dia, ou se algum `feriados_municipais` tiver o mesmo `MM-DD`. Para não mover código da F7, a F1 cria `feriado_do_dia(data, feriados_municipais)` em `app/feriados.py`; `prompt_builder` continua com a função dele. Comportamento por `em_feriado`:
  - `mesmo`: nada muda;
  - `sem_intervalos`: os eventos de intervalo viram música ajustável, sem hard time;
  - `sem_relogio`: o programa usa a `estrutura_blocos`.
- **Backtiming.**
  - `H` é o próximo compromisso: o início do próximo evento com hard time, incluindo o da hora seguinte e o encerramento final.
  - `espaco_s = H − instante − Σ duracao_s` dos eventos obrigatórios (sem hard time) que começam entre `instante` e `H` e ainda não foram executados.
- **Etapa vigente.**
  - Por padrão, é o evento que contém o instante.
  - Exceção: uma etapa de fala ou de peça não repetível, com início entre o último hard time passado e o instante, que ainda não foi executada, é **deslocada**. Ela vira a vigente (o link que o atraso da música engoliu ainda acontece).
  - Etapa pulada é marcada com o motivo e registrada em log.

**Decisão (`planejar`), nesta ordem:**
1. `ja_encerrou`, ou instante fora da ocorrência: devolve `None` (caminho atual).
2. Instante dentro da janela de encerramento, ou espaço até o fim menor que (menor peça possível + mínimo de encerramento): `encerramento` com orçamento `[enc_min, clamp(fim − instante, enc_min, enc_max)]`.
3. Etapa de fala: `max = min(unidade_max(tipo), duracao da etapa [restante, se repetível], espaco_s)`.
   - Se `max ≥ unidade_min`: `fala`, ou `fala_reduzida` quando `max < unidade_max`.
   - Senão, se a etapa é repetível, a conversa está em andamento (`ultima_categoria` igual à categoria do bloco) e `espaco_s ≥ min(fechamento_curto)`: **`fechamento_curto`** ("debate estourou") com `[6, min(15, espaco_s)]`.
   - Senão, a etapa é pulada e a decisão volta ao passo 2 com a etapa seguinte, no máximo 4 vezes.
4. Etapa de música: `musica` sem fala, com `duracao_max_musica_s = espaco_s + tolerancia`. A `alternativa` é a primeira opção que couber, nesta ordem:
   1. peça de reserva (vinheta de passagem ou identificação);
   2. link de preenchimento, só no formato padrão, quando `espaco_s ≥ min(link)`;
   3. `adiantamento` do compromisso `H`, quando `espaco_s ≤ adiantamento_max_s`.
5. Intervalo: o próximo patrocinador ainda não tocado nesta etapa (`chave_estado = "patrocinador:N"`). Sem nenhum, a etapa termina e o serviço passa à próxima.
6. Abertura e passagem: a próxima peça da lista que ainda não foi executada.

`palavras_max = floor(max × wpm / 60)`. No formato musical, vale o menor entre esse valor e o de `formato.ORCAMENTOS`.

**Garantia do aceite.** Pelas regras 3 e 4, nada que termine depois de `H + tolerância` é
escolhido. Se nada couber, o compromisso começa mais cedo, nunca atrasado. Começar cedo não é
"atrasar" o hard time, mas no fim do programa vira buraco. Por isso o resumo ganha
`fim_antecipado_s` (meta ≤ 60 s, §6).

### 5.6 Integração em `gerar_proxima_fala` (inserções, sem mover código)

| Ponto | Mudança |
|---|---|
| depois de `ultima_categoria` (`router.py:1928`) | `instante, aceito = instante_previsto(dados.inicio_previsto, agora)`; `relogio = relogio_do_programa(programa, data)`; `plano = planejar(...)` só se `relogio` existir. Montar `PecasDisponiveis` e ler `etapas_executadas` só nesse caso. |
| `:1929-1937` | `if plano: tipo = plano.tipo_bloco`, que pode ser `encerramento`, `vinheta:N`, `patrocinador:N` ou um tipo de fala. Senão, o código atual. |
| laço de vinheta (`:1942-1961`) | Com plano, a vinheta já vem ativa. O fallback `_tipo_proximo_bloco` (`:1959`) não é usado. Se a vinheta falhar, usa `plano.alternativa`. |
| música (`:2049-2058`) | Com plano: `_buscar_musica_para_bloco(db, programa, tipo, duracao_max_s=plano.duracao_max_musica_s)`. O kwarg só é passado quando há plano (por causa dos testes com assinatura fixa). Dentro da função, a duração efetiva é `(fim or duracao or padrão) − inicio`; se passar do teto, devolve `None` **antes** de `_registrar_musica_tocada` (`:1672`). Sem faixa: `plano.alternativa`. |
| `:2060` | Condição `(formato_musical or (plano and plano.musica_sem_fala)) and categoria == "musica" and pedido_musica is None`. |
| `:2174-2190`, `:2199` | Com plano, troca o texto de "4 a 6 frases" e de "em loop" por "A duração deve seguir a meta deste bloco. Meta: {min} a {max} segundos, no máximo {palavras} palavras. Não anuncie o que vem a seguir nem prometa conteúdo." Ideia dos teases fica para a F4. |
| `fechamento_curto` | Instrução extra: "Feche o assunto em andamento: conclua a ideia, resuma em uma frase e não abra assunto novo. Não prometa retorno." |
| `primeira` (`:2495`, `:2662`, `:2706`, `:2813`, `:2948`) | `primeira = plano.primeira if plano else total_falas == 0`. |
| `:2011`, `:2541` | Com plano, `agora_local = instante`. Para o prompt ficar coerente, `montar_system_prompt(..., agora=None)` ganha um parâmetro opcional repassado a `_contexto_atual` (`prompt_builder.py:150-154`). O padrão continua `now()`. |
| `:2706` | `limite_palavras = plano.palavras_max if plano else (atual)`. A revisão única já existente passa a valer também no formato padrão com relógio. |
| `:2948` | `duracao_alvo_segundos = plano.orcamento_s if plano else (atual)`. |
| os quatro `return` | Passam por `_com_relogio(resposta, plano, duracao_peca_s)`. Esse helper preenche `relogio` e `duracao_prevista_s` e chama `marcar_executada(plano.chave_estado)` só aqui, depois que o bloco foi decidido. |

Se a fala revisada ainda passar do espaço pela estimativa de palavras, a F1 só registra
`relogio_fala_acima_do_espaco`. Medir e substituir pelo áudio real é tarefa da F2.

### 5.7 Contrato de `/proxima` e prewarm (compatível)

- Pedido: `inicio_previsto: datetime | None = None`, em ISO 8601 com fuso. Cliente antigo não manda e continua funcionando.
- Resposta (campos opcionais, com padrão `None`):
  - `duracao_prevista_s: float | None`: soma da fala estimada (palavras ÷ wpm), das músicas (`fim/duracao − inicio`), da vinheta ou patrocinador (duração conhecida ou palavras ÷ wpm) e da vinheta de encerramento. Calculado **para todos os programas**, porque é inofensivo e alimenta o painel e o as-run.
  - `relogio: RelogioAoVivo | None`: `{preset, inicio_previsto, inicio_previsto_aceito, hora, etapa: {inicio_s, tipo, rotulo, natureza, hard_time, inicio, fim}, proximo_compromisso, segundos_ate_hard_time, espaco_s, acao, orcamento_s}`. Só existe com relógio.
- Prewarm (`prewarm.py:64`): `LiveProgramRequest(..., inicio_previsto=combine(hoje, horario_inicio, tz))`. O payload do cache leva os campos novos, e o painel já espalha a resposta (`useLiveEngine.ts:1300-1303`).

### 5.8 API de configuração

Para não ser apagado pelos PUTs atuais (§2), o relógio fica **fora** de `ProgramaRequest`.
- `ProgramaResponse.relogio_hora: RelogioHora | None = None`, com leitura tolerante: JSON inválido no banco aparece como `null`, com log, em vez de devolver 500.
- `GET /config/relogios/presets`: devolve `[{id, nome, descricao, fonte, relogio, totais: {musica_s, fala_s, intervalo_s}}]`.
- `PUT /config/programas/{id}/relogio`: recebe um `RelogioHora` e devolve `ProgramaResponse`. Responde 422 com mensagem em português quando o relógio é inválido.
- `DELETE /config/programas/{id}/relogio`: volta a `null` e devolve `ProgramaResponse`.
- Isolamento por conta: as rotas usam `_buscar_programa(db, account, id)` do router de configuração.

### 5.9 Painel

**Motor ao vivo.**
- **`lib/relogioAoVivo.ts`** (novo, puro):
  - `estimarDuracaoSegmento(segmento)`: usa `duracao_prevista_s` ou, na falta dele (fala local ou backend antigo), palavras ÷ 2,5 mais as músicas;
  - `proximoInicioBruto(ctx, segmento)`;
  - `inicioAEnviar(bruto, desvio, agora)`.
- **`useLiveEngine.ts`:**
  - `ContextoPreparo` (`:62-68`) ganha `inicioPrevistoBrutoMs`.
    - No primeiro bloco, ele vale `max(agora, inicioAgendadoMs)` quando a fila nasce do agendamento ou do pré-aquecimento, e `Date.now()` nos outros casos.
    - O `avancar` (`:1490`) soma `pausa_antes_ms` (limitada como em `continuidadeAudio`) mais a duração estimada.
  - `prepararTexto` (`:1315`) envia `inicio_previsto = max(agora, bruto + desvioRef)` e guarda os dois valores no segmento.
  - Quando o bloco começa a tocar (depois de `esperarTransicao`, `:1566`): `desvioRef = agoraReal − bruto`. A cadeia continua bruta e só o valor enviado é corrigido, o que limita o erro a cerca de 2 blocos.
  - **Início pontual:** quando há um programa a até 90 s de começar (`:1908-1922`), um `setTimeout` dispara `verificarHorarioAgendado` exatamente em `horario_inicio`, em vez de esperar o polling de 15 s (`:1927`).
- **`lib/liveTypes.ts`:** acrescentar `duracao_prevista_s?` e `relogio?` à resposta.

**Editor (`components/RelogioHoraEditor.tsx`, novo).** Fica na seção "Roteiro do programa" de
`EditarProgramaForm.tsx`, logo depois de "Formato do programa" (`:586-620`).
- Seletor "Relógio da hora", com as opções:
  - "Sem relógio (segue a sequência de blocos)";
  - "A: Musical com companhia";
  - "B: Jornal/revista";
  - "C: Morning/variedades".
- Ao escolher um preset, mostra uma tabela com: início (mm:ss, calculado), rótulo, duração editável (mm:ss, passo de 5 s), selo de natureza e selo "horário fixo".
- **Ajuste de duração:** a diferença vai para o próximo evento `musica` ajustável, ou para o anterior se não houver próximo, com mínimo de 30 s. O total fica sempre em 60:00. Se não der para compensar, mostra o erro e mantém o valor anterior.
- Seletor "Em feriados": "mesmo relógio", "sem intervalos" ou "sem relógio".
- Avisos:
  - "Com relógio, a sequência deixa de rodar em loop; vinhetas de abertura/passagem e patrocinadores da sequência entram nas etapas";
  - quando a janela não é múltipla de 60 min;
  - no B sem fontes de notícia: "as etapas de notícia viram música até haver fontes";
  - "os tempos são hipóteses; ajuste à sua operação".
- **Gravação:** no mesmo "Salvar", depois do POST/PUT do programa, se o relógio mudou, chama `PUT .../relogio` ou `DELETE`. Se só essa chamada falhar, mostra "Programa salvo, mas o relógio não foi salvo". Os presets vêm de `GET /config/relogios/presets`.
- **`lib/relogio.ts`** (novo, puro): `recalcularInicios`, `ajustarDuracao`, `totais`, `formatarMinSeg`.
- **`lib/types.ts`:** tipos `RelogioHora` e `EventoRelogio`; `Programa.relogio_hora?: RelogioHora | null`; em `normalizarPrograma`, `relogio_hora: p.relogio_hora ?? null`.
- **`components/live/ProximosBlocosPanel.tsx`:** com relógio, troca a prévia por sequência por "Segue o relógio {preset}: a ordem vem do horário", mais a etapa atual e o próximo compromisso da última resposta. A prévia por contagem seria falsa (`:9-50`).
- `GradeProgramacaoForm.tsx` não muda. O PUT dele ecoa `relogio_hora`, mas o backend ignora o campo.

### 5.10 Ajustes no simulador da F0 (`backend/scripts/simulacao/`)

- `emissao.py`: envia `inicio_previsto` como o painel (cadeia bruta mais desvio). A opção `--sem-inicio-previsto` imita o painel antigo.
- Opção `--relogio-backend fixture|nenhum`, com `fixture` como padrão depois da F1: grava `programa.relogio_hora = PRESETS[fixture.relogio]`. Com `nenhum`, reproduz a linha de base.
- `as_run`:
  - cada evento ganha `relogio` (da resposta) e `duracao_prevista_backend_s`;
  - um patrocinador dentro de uma etapa de intervalo é registrado com `tipo: "intervalo"`;
  - os hard times são casados pela `relogio.etapa` (hora e `inicio_s`), o que é mais exato que `corresponde_a`.
- `resumo` ganha `fim_antecipado_s`, `etapas_puladas`, `adiantamentos` e `fechamentos_curtos`.
- Rodar `ruff check scripts/simular_hora.py scripts/simulacao` à mão, porque o CI não cobre `scripts/`.

### 5.11 Arquivos

| Arquivo | Novo ou alterado |
|---|---|
| `backend/app/live/relogio.py` | novo: modelos, presets, serviço puro e adaptador de estado |
| `backend/app/live/relogios/{A_musical_companhia,B_jornal_revista,C_morning_variedades}.json` | novos |
| `backend/app/db/migrations/relogio_20261107.py` | novo |
| `backend/app/models/programa.py` | coluna `relogio_hora` |
| `backend/app/main.py` | chamar `aplicar` da migração em `criar_tabelas` |
| `backend/app/feriados.py` | `feriado_do_dia(data, feriados_municipais)` |
| `backend/app/live/router.py` | pedido e resposta (§5.7), inserções (§5.6), kwarg opcional em `_buscar_musica_para_bloco` |
| `backend/app/live/prewarm.py` | `inicio_previsto` |
| `backend/app/llm/prompt_builder.py` | parâmetro opcional `agora` em `montar_system_prompt`/`_contexto_atual` |
| `backend/app/config/router.py` | `ProgramaResponse.relogio_hora` e as 3 rotas |
| `backend/scripts/simulacao/{emissao,fixtures,metricas}.py`, `backend/scripts/simular_hora.py` | §5.10 |
| `frontend-painel/lib/{relogio,relogioAoVivo}.ts` | novos |
| `frontend-painel/components/RelogioHoraEditor.tsx` | novo |
| `frontend-painel/lib/{types,liveTypes}.ts`, `hooks/useLiveEngine.ts`, `components/EditarProgramaForm.tsx`, `components/live/ProximosBlocosPanel.tsx` | alterados |
| `docs/melhoria-radio/f1/{RELATORIO,pendencias}.md`, `docs/plano.md` (§7 "O que já está pronto") | portão |

### 5.12 Ordem de commits (`melhoria/f1-relogio`)

1. Modelo, presets, validação e migração.
2. Serviço puro `relogio.py`.
3. Contrato de `/proxima`, inserções na rota e prewarm.
4. Teto de duração da música.
5. API de configuração.
6. Motor do painel (horário previsto, desvio e início pontual).
7. Editor e prévia.
8. Ajustes no simulador, rodadas e relatório.

## 6. Testes, nesta ordem

**Caracterização (antes de alterar `router.py`):**
1. `test_proxima_sem_relogio_ignora_inicio_previsto`, parametrizado em cinco caminhos:
   - comentário no formato padrão;
   - música sem fala no musical;
   - encerramento perto do fim;
   - vinheta;
   - patrocinador.

   Com `@freeze_time`, `random` fixo e dublês, a resposta com e sem `inicio_previsto` tem de ser igual, ignorando só `duracao_prevista_s`. Ele passa já antes da mudança, porque o Pydantic ignora o campo extra, e trava o comportamento.
2. Rodar o simulador da F0 nos 3 perfis **antes** de qualquer mudança e gravar em `docs/melhoria-radio/f1/simulacao/antes/`. Depois da F1, `--relogio-backend nenhum` tem de reproduzir a mesma sequência de `bloco` e as mesmas `chamadas_llm` (conferência no relatório, não teste permanente, como pede a F0).
3. Os testes de feriado municipal já existentes (`test_llm_prompt_builder.py:335-349`) continuam verdes. O helper novo não substitui o do prompt.

**Unitários (`tests/test_live_relogio.py`, puros, com instante explícito):**
- U1 presets:
  - soma 3600 e eventos contínuos a partir de 0;
  - A com 3015/225/360;
  - hard times da §5.3;
  - naturezas.
- U2 paridade com `tests/fixtures/programas/relogios/*.json` (§5.3).
- U3 validação. Cada caso tem de dar erro com mensagem em português:
  - soma 3599 ou 3601;
  - buraco ou sobreposição;
  - `duracao_s <= 0`;
  - `inicio_s` fora de 0–3599;
  - mais de 40 eventos;
  - tipo desconhecido.

  Além disso, um JSON inválido no programa faz `relogio_do_programa` devolver `None`.
- U4 programa 14:00–15:00 com o A:
  - 14:00:10 cai na abertura e 14:12:10 no link;
  - às 14:20:00, `segundos_ate_hard_time` é 240 (intervalo às 14:24).
- U5 virada de hora (14:00–16:00 com o A):
  - às 14:59:50, a passagem vira identificação, não encerramento;
  - o próximo compromisso é a abertura de 15:00 como `retomada`, a 10 s;
  - às 15:59:40, é encerramento.
- U6 fim no meio do relógio (14:00–15:30) e programa curto (14:00–14:45): truncamento, encerramento sintético e descarte do que passa do fim.
- U7 meia-noite (23:00–01:00, de terça para quarta):
  - às 00:00:05 de quarta: hora 1, retomada, data da ocorrência na terça;
  - às 00:59:45: encerramento;
  - às 22:59 de terça: `None`.
- U8 fuso:
  - o mesmo instante UTC em `America/Sao_Paulo` e em `America/Manaus` dá etapas diferentes;
  - `America/New_York` em 01/11/2026 (fim do horário de verão), programa 00:30–02:30: 3 horas decorridas e nenhuma exceção.
- U9 feriados:
  - em 15/11/2026, `mesmo` dá o mesmo plano, `sem_intervalos` transforma o intervalo em música e `sem_relogio` dá `None`;
  - num programa de 23:00 a 01:00 entre 14 e 15/11, às 00:30 o dia não conta como feriado;
  - um feriado municipal `11-10` vale.
- U10 backtiming: `espaco_s` desconta os obrigatórios entre o instante e `H` (relógio personalizado com obrigatório sem hard time).
- U11 orçamento:
  - link no horário: [10, 35];
  - com 18 s de espaço: [10, 18] e `fala_reduzida`;
  - com 7 s: sem fala.

  Nenhum plano sai com `orcamento_s[1] < unidade_min`. `palavras_max = floor(max × 145 / 60)`. No musical, vale o menor com `ORCAMENTOS`.
- U12 debate estourou: conversa do C a 10 s do intervalo de 16:00, com `ultima_categoria = comentario`, dá `fechamento_curto` [6, 10]. Sem conversa em andamento, a etapa é pulada.
- U13 música:
  - teto = espaço + 5;
  - a alternativa segue a ordem reserva → link (só no padrão) → adiantamento;
  - com espaço acima de `adiantamento_max_s` e sem nada que caiba, o resultado é documentado e registrado em log.
- U14 intervalo: patrocinadores na ordem, uma vez cada (estado), etapa encerrada quando acabam, programa sem patrocinadores.
- U15 etapa deslocada: um link engolido pelo atraso da música acontece antes do próximo hard time.
- U16 encerramento:
  - orçamento `clamp(fim − instante)`;
  - depois do fim, dentro da graça, ainda é encerramento;
  - com `ja_encerrou`, o resultado é `None`.
- U17 instante fora da ocorrência (manual fora da grade): `None`.
- U18 `instante_previsto`: `None`, passado, naive, mais de 30 min (`aceito=False`).
- U19 `duracao_prevista_bloco`: tags ignoradas, `fim − inicio` das músicas, duração desconhecida assume 210 s, vinheta e patrocinador.
- U20 configuração: trocar um valor de `ConfigRelogio` muda o resultado, ou seja, nenhum número fixo na decisão.
- U21 estado no Redis falhando: o plano sai só pelo tempo, sem exceção.
- Migração (`tests/test_relogio_migracao.py`): preserva a linha, pode rodar duas vezes e a coluna fica `NULL`.

**Integração:**
- **`tests/test_config_relogio.py`:**
  - A1: os presets vêm com 3600 s;
  - A2: o PUT válido grava e o GET do programa traz `relogio_hora`;
  - A3: soma 3599 dá 422 e nada é gravado;
  - **A4: o PUT do programa completo (sem o campo, ou ecoando o campo) preserva o relógio;**
  - A5: o refinamento por IA (`:725`) preserva o relógio;
  - A6: o DELETE volta a `null`;
  - A7: programa de outra conta dá 404;
  - A8: programa criado nasce com `null`.
- **`tests/test_live_relogio_proxima.py`** (freeze_time, fakeredis e monkeypatch por nome, como em `test_live_router.py`):
  - I1: `inicio_previsto` aceito e ecoado em `relogio`.
  - I2: sem espaço, não chama o LLM (`Mock.assert_not_called`) e devolve música ou adiantamento.
  - I3: pouco espaço reduz `duracao_alvo_segundos` e o prompt traz "no máximo N palavras".
  - **I4: o encerramento é decidido pelo horário previsto.** Com `now` em 14:52 e `inicio_previsto` em 14:59:35, o resultado é `encerramento`; o código de hoje não encerraria.
  - I5: debate estourou leva a instrução de fechamento com orçamento [6, 12].
  - I6: revisão por orçamento no formato padrão com relógio.
  - I7: o teto de música só é passado com relógio (spy). Faixa longa demais não entra em `_historico_musicas`.
  - I8: intervalo com dois patrocinadores em sequência, e na terceira chamada a etapa seguinte.
  - I9: vinheta de papel abertura e depois a abertura `primeira` (orçamento de abertura e fio condutor registrado); na hora 1, retomada.
  - I10: o prewarm passa `horario_inicio` (`test_live_prewarm.py`).
  - I11: cliente antigo sem o campo usa `now()`.
  - I12: horário a mais de 30 min é ignorado.
  - I13: `duracao_prevista_s` aparece em todos os programas.
  - I14: relógio inválido no banco cai no caminho atual.
  - I15: o prompt com relógio não traz "4 a 6 frases" nem "em loop".
  - I16: com `agora` informado, `montar_system_prompt` mostra a hora prevista.

**Painel (vitest):**
- P1 `lib/__tests__/relogio.test.ts`: início, compensação, erro de compensação, totais, mm:ss.
- P2 `lib/__tests__/relogioAoVivo.test.ts`: cadeia, correção pelo desvio, `max(agora)`, estimativa sem `duracao_prevista_s`.
- P3 `useLiveEngine.preparo.test.ts`: o `inicio_previsto` cresce conforme `duracao_prevista_s`; com 10 s de atraso real, o terceiro pedido também avança 10 s.
- P4 `useLiveEngine.prewarm.test.ts`: o primeiro pedido usa o `horario_inicio`; com timers falsos, a transmissão começa em `horario_inicio` ± 1 s, e não depois do próximo tick de 15 s.
- P5 `components/__tests__/RelogioHoraEditor.test.tsx`: preset A com 12 linhas e 60:00; link de 0:35 para 0:50 tira 15 s da música seguinte; "Sem relógio".
- P6 `EditarProgramaForm.test.tsx`: salvar com o relógio alterado chama PUT do programa e depois PUT do relógio; "Sem relógio" chama DELETE; programa sem relógio não chama a rota do relógio.
- P7 `ProximosBlocosPanel.test.tsx`: aviso de relógio. Os testes atuais sem relógio continuam iguais.
- P8 `GradeProgramacaoForm.test.tsx`: continua verde sem mudança.

**Simulação (`tests/test_simular_hora.py` e CLI):**
- S1 `test_relogio_hard_times_sem_atraso[musical_adulto-A, popular_sertanejo-A, variedades_leves-C, variedades_leves-B]`, no modo fake com relógio no backend:
  - todos os `hard_times` com `atraso_s ≤ 5`;
  - nenhuma fala com `orcamento_s.max` abaixo do mínimo do tipo;
  - `encerramento_no_ar` verdadeiro e `segundos_cortados == 0`;
  - `fim_antecipado_s ≤ 60`;
  - `tentativas_rede == 0`;
  - menos de 30 s de parede.
- S2 `test_sem_relogio_inicio_previsto_nao_muda_as_run`: com `--relogio-backend nenhum`, com e sem `--sem-inicio-previsto`, o `as_run` é idêntico com a mesma semente, ignorando os campos novos.
- S3 CLI:
  - 3 perfis × {nenhum, fixture}, mais o B em `variedades_leves`, mais uma rodada `--sem-inicio-previsto`;
  - saída em `docs/melhoria-radio/f1/simulacao/<perfil>/<variante>/`;
  - tabela no `RELATORIO.md` comparando com a F0: atraso, perdidos, fim antecipado, silêncio, composição × relógio (o A prevê 3015/225/360).

Os modos `llm` e `completo` não rodam sem aprovação explícita do usuário.

## 7. Riscos e o que não fazer nesta frente

- **Não mover código de `gerar_proxima_fala`** (é da F3). Só as inserções da §5.6. Não fazer refatoração oportunista.
- **Não mudar programa sem relógio.** Isso vale também para usar `inicio_previsto` no encerramento e na hora certa desses programas. Seria uma melhoria real (é o problema que a F0 mostrou), mas muda comportamento. Fica como decisão do usuário depois de comparar a simulação (D4).
- **Não criar tipo de resposta novo** (`intervalo`). O painel antigo não saberia tocar.
- **Não cortar música para caber** (§9: "não cortar canções automaticamente"). O ajuste é feito com teto na seleção, reserva e adiantamento. **Não acelerar a voz** (F2).
- **Não gerar tease a partir do relógio** ("depois do intervalo…"). Isso é da F4, que vai usar os eventos agendados como fonte. O prompt da F1 manda não anunciar o que vem.
- **Não passar o kwarg novo para `_buscar_musica_para_bloco` sem relógio.** Os testes trocam a função por versões de assinatura fixa (`test_live_router.py:1145`, `:2945`).
- **Estado das etapas é marcado na geração, não na reprodução.** É a mesma fragilidade do registro de músicas (`:1672`). Pausar ou pular deixa a etapa marcada. A confirmação pelo as-run é da F3/F11. Por isso a marcação só acontece no `return`.
- **A precisão real depende da estimativa** (145 wpm e duração conhecida das músicas). Com a correção pelo desvio, o erro fica em cerca de 2 blocos. Música de duração desconhecida assume 210 s. No modo fake, o critério de 5 s vale por construção. No ar, a fala que passar do espaço depois da revisão só gera log até a F2 medir o áudio.
- **Painel antigo em cache** não manda o campo, e o programa com relógio decide com `now()`, a qualidade de hoje. O início agendado com polling de 15 s fura o hard time de 00:00; o timer pontual (§5.9) é obrigatório nesta frente.
- **B depende da F5** (fontes) e da F12/F13 (convidado real). Na F1 ele é validado, simulado e mostrado com aviso.
- **Multivoz numa conversa do C**: a duração do diálogo é só uma instrução ao LLM. A F13 trata os turnos.
- Com relógio, `ia_pode_adicionar_blocos` deixa de valer, e vinhetas da estrutura sem papel não tocam. O editor precisa avisar disso.
- **Não validar `timezone`** nesta frente, porque a rota já falha antes com fuso inválido.
- **Não corrigir o N+1 do prewarm** (auditoria 7). Registrar em `pendencias.md`.
- Números (unidades, 145 wpm, 90 s, 210 s, 5 s) são hipóteses da pesquisa e da skill. Ficam em `ConfigRelogio` e nunca soltos no código.

## 8. Decisões de projeto registradas (revisáveis, não bloqueiam)

- D1. A âncora é o início da ocorrência, não a hora cheia. Programas que começam em hora cheia não notam diferença. O relógio de rede ancorado na hora cheia (§4.3) fica para depois.
- D2. Com relógio, a janela de música não tem fala também no formato padrão, exceto pedido real. O relógio decide onde a fala acontece (A: 3 min 45 s por hora).
- D3. Um compromisso pode começar até 90 s mais cedo. Atraso tem tolerância de 5 s.
- D4. `inicio_previsto` só vale para programas com relógio. Estender aos demais é decisão do usuário, com base na simulação S3.
- D5. As unidades de fala por tipo de evento ficam em `ConfigRelogio` e a F6 as substitui. Há uma divergência de orçamento entre o backend musical e a pesquisa (`f0/auditoria.md:355`); vale o menor dos dois.
- D6. O relógio fica fora de `ProgramaRequest` e tem rota própria. A alternativa (campo em `ProgramaRequest` com `exclude_unset`) exigiria auditar todo `setattr` em laço.

PRONTA PARA IMPLEMENTAR
