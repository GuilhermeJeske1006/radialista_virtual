# Auditoria F3: estado confiável da emissão (contexto da geração)

Branch auditada: `melhoria/f2-duracao-fala` (último commit `d68c39f`, F0, F1 e F2 implementadas), em 09/11/2026.
Só leitura no código. `pytest --collect-only`: 1280 testes. Fontes: `docs/plano-melhoria-radio.md` (F3, F4,
F5, Transversal, Portão); `docs/pesquisa-radio-locufy.md` §8, §12.4 e §13; skill `referencia-radio`;
`docs/refatoracao.md`; `docs/auditoria.md`; `docs/melhoria-radio/RELATORIO.md`; auditorias e pendências de
`docs/melhoria-radio/f0`, `f1` e `f2`; auditoria da F5 (scratchpad, ainda não no repositório).

Itens que entram na F3 além do plano, pedidos pelo coordenador: item 6 de `docs/auditoria.md` (§5.7);
painel antigo sem `inicio_previsto` (§5.6); validador de música único para backend e simulador (§5.4 e §5.5);
pontos de extensão para a F5 (dados e `checar_fala`) e para a F4 (promessas) (§5.8).

## 1. Estado atual: o plano confere com o código?

| Afirmação do plano | Situação | Evidência |
|---|---|---|
| O pedido traz `historico` (últimas 8), `total_falas` e `ultima_fala` | confirmado, com campos a mais | `backend/app/live/router.py:141-161`. Desde a F1 também `inicio_previsto` (`:161`), além de `incluir_audio` e `perfil_pos_producao`. O painel manda as 8 últimas linhas no formato `"{tipo}: {fala} [Música(s) tocada(s) nesse bloco: …]"` (`frontend-painel/hooks/useLiveEngine.ts:1325-1328`, `linhaMusicasHistorico` em `:1246-1250`). |
| O roteador monta contexto de músicas (`_contexto_musica`, `_musicas_citadas_na_fala`) | confirmado | `router.py:1529-1545` e `:1587-1655`. As citadas são resolvidas e tocam no bloco de música do formato padrão sem relógio (`:3278-3282`) e em **qualquer** bloco que não seja música, inclusive no formato musical e com relógio (`:3283-3291`). |
| Tom anterior em Redis (`_ultimo_tom`) | confirmado, com docstring **diferente** do código | `router.py:893-902`. A docstring diz que o tom é gravado no TTS, mas também é gravado na geração (`:3308`, `:3395`), além de `/tts` (`:3701-3705`). |
| Fio condutor e temas recentes | confirmado | Fio: `:947-955`, lido em `:2949`, gravado em `:3457-3460`. Temas: sessão no Redis `:932-944`, rádio no banco `:1479-1493`, mescla em `:2545-2569`. |
| `gerar_proxima_fala` tem cerca de 1000 linhas | **diferente** | Tem **1245 linhas** (`router.py:2292-3536`) num arquivo de 3869. São quatro `return`: vinheta `:2358`, patrocinador `:2382`, música sem fala `:2500` e final `:3486`. |
| Lacuna: o contexto está espalhado e não há objeto único | confirmado | São cerca de 45 variáveis locais. O prompt é montado inline entre `:2592` e `:3141` (~550 linhas, mais de 70 `append`). No meio da montagem há efeitos colaterais: seleção de pedido com `commit` (`:2443`, `:2516`); registro de música (`:2464`, `:1689`, `:1653`); `registrar_callback_musica` dentro do prompt (`:3040`); rotações no Redis por `_proxima_variacao` (`:741`, `:2570`, `:2580`, `:2590`, `:2714`, `:2873`, `:3084`); sorteios do `random` global (`:2566`, `:2744`, `:2752`, `:2987`, `:2996`); pesquisa web (`:2906`). |
| Entrega 2: "`prompt_builder` recebe só `ContextoEmissao`" | **diferente** do que o nome sugere | `app/llm/prompt_builder.py:211` (`montar_system_prompt`) é compartilhado com o WhatsApp (`app/whatsapp/atendimento.py:261`, `app/whatsapp/webhook.py:112`) e tem efeitos no Redis: rotação `:24-33`, fato do dia `:36-46` e clima mencionado `:184-185`. O prompt do ao vivo é a parte inline da rota. Ver decisão D1. |
| Entrega 3: validador pós-geração de música | **ausente** | Hoje só existe a instrução do prompt (`router.py:3003-3057`). Uma citada que não se resolve gera só o log `live_musica_citada_sem_faixa` (`:1646`), e a fala vai ao ar com a menção. Na simulação, `anuncio_sem_confirmacao` é 1 no `musical_adulto` em F0, F1 e F2 (`docs/melhoria-radio/f{0,1,2}/simulacao/musical_adulto/resumo.json`). |

## 2. Fatos do código que mudam o desenho

1. **Os testes trocam funções pelo nome no módulo do router.** `git grep` em `tests/` e `scripts/` acha
   `app.live.router.gerar_resposta` 108 vezes, `buscar_musica` 24, `tts_habilitado` 22, `sintetizar_audio` 17,
   `classificar_tom_fala` 12, `classificar_tema_fala` 11, `processar_audio` 9, `classificar_fio_condutor` 9,
   `_buscar_musica_para_bloco` 8, `resumir_contexto_musica` 7, `_registrar_tema_em_background` 7,
   `extrair_musicas_citadas` 5, `sugerir_musica_do_genero` 5, `pesquisar_noticias` 3, `gerar_dialogo_multivoz` 3,
   `itens_fora_do_genero` 3, `resolver_musica_catalogada` 2, `_selecionar_musica_para_bloco` 2,
   `proxima_noticia` 1, `SessionLocal` 1, entre outros.
   - Código movido para outro módulo que faça `from app.llm.client import gerar_resposta` deixa de ser
     alcançado por esses patches, e dezenas de testes quebram.
   - As 16 trocas de `app.live.router.random.random` e as 3 de `settings` alteram o objeto global e
     continuam valendo em qualquer módulo.
   - O simulador troca por identidade em todo `sys.modules` (`backend/scripts/simulacao/dubles.py:498-522`,
     `:640-650`), então módulos novos também são alcançados.
2. **A ordem dos sorteios e das rotações faz parte do comportamento.** O simulador e os testes fixam a
   semente.
   - A seleção de música sorteia antes do prompt (`_escolher_query_musica`, `router.py:1311-1414`).
   - Os sorteios do prompt saem nesta ordem e com curto-circuito condicional: callback `:2566` (só com
     temas de outras transmissões), mudança de ideia `:2744`, imperfeição `:2752`, hora certa `:2987`, marco
     `:2996`.
   - Mover sem preservar a ordem e as condições muda a sequência dos três perfis da simulação.
3. **A música é confirmada de duas formas.**
   - (a) A faixa do bloco é escolhida antes da fala (`:2442-2493`, `_resolver_musica_do_relogio` `:2136-2157`).
   - (b) As citadas são resolvidas depois da fala (`:3273-3291`).
   - Bug (pendência da F1): `_musicas_citadas_na_fala` grava cada citada como tocada no Redis e em
     `MusicaHistorico` com `origem="citada_locutor"` **antes** de `_citadas_que_cabem` (`:3288-3289`)
     descartar as que não cabem no relógio (`:1653-1654`). A faixa descartada fica registrada sem tocar, e
     a menção continua na fala.
4. **Com relógio, o prompt proíbe citar música nos blocos de fala** (`:3047-3051`), mas o código ainda
   resolve as citadas que cabem (`:3288`). No formato musical, um bloco de retomada ou de identificação
   também faz a citada tocar (pendência da F0).
5. **O que "tocou" é o que foi gerado, não o que foi ao ar.**
   - O histórico do painel inclui os 2 blocos que já foram preparados e ainda não tocaram
     (`frontend-painel/lib/filaPreparo.ts:16`, `:27-28`).
   - `musicas_tocadas:*` no Redis é gravado na seleção (`router.py:916-925`).
   - Para o validador isso basta, porque a ordem é sequencial e o que foi gerado antes toca antes. Pular ou
     pausar fica para o as-run da F11.
6. **Painel antigo e `inicio_previsto`.**
   - `_planejar_relogio` usa `now()` quando o campo falta (`router.py:2091-2092`; `instante_previsto`,
     `app/live/relogio.py:434-447`).
   - Na simulação `f1/simulacao/popular_sertanejo/sem_inicio_previsto`: abertura atrasada 272,6 s,
     intervalo de 24:00 atrasado 412,2 s, os dois hard times seguintes perdidos e o encerramento cortado
     (73,7 s).
   - Causa: a primeira geração acontece 90 s antes do início, o instante cai fora da ocorrência e o plano
     vira `None`. Depois disso, cada decisão é tomada dois blocos antes de ir ao ar.
   - O painel não manda versão (`frontend-painel/lib/api.ts:42-50`) e o service worker não guarda nada em
     cache (`public/sw.js:12-20`). "Painel antigo" é, então, uma aba aberta antes do deploy, como a máquina
     que fica no ar dias seguidos.
   - `ultima_fala` também não indica reprodução: na fila, ela é a última fala **gerada**
     (`useLiveEngine.ts:1508`, `avancar` logo abaixo).
   - Invariante útil: o painel antigo gera o bloco *k* quando o bloco *k−2* (sem contar vinhetas) começa a
     tocar (antecedência 2, `filaPreparo.ts:16`; confirmado pelo teste
     `test_fila_de_preparo_gera_dois_blocos_a_frente`).
7. **Redis (item 6, aberto).**
   - `backend/app/config/redis_client.py:5` não define `socket_timeout` nem `socket_connect_timeout`.
     22 módulos importam o cliente.
   - O router faz 16 chamadas diretas. A elas somam-se `prompt_builder`, `pauta_conversa`
     (`app/topics/pauta_conversa.py:69-89`), `limite_excedido` e o cache de música, ou seja, dezenas por
     `/proxima`.
   - Já falham abertos: `relogio.py:1034-1057`, `ritmo_voz.py:110,159,166`, `tts/cache.py`, `llm/economia.py`.
   - `http_rate_limit.limite_excedido` (`app/guardrails/http_rate_limit.py:26-29`) não tem `try`. Ele protege
     login, cadastro, esqueci-senha (`app/auth/router.py:100,153,192,213`), equipe, webhook do WhatsApp e as
     rotas pagas do ao vivo (`router.py:2307,3615,3684`).
   - Só um timeout não resolve: com o Redis "buraco negro", dezenas de chamadas × timeout ainda travam a
     rota. É preciso um disjuntor.
   - Os testes trocam `redis.from_url` por `lambda *a, **k: fakeredis…` (`tests/conftest.py:38`;
     simulador em `scripts/simulacao/ambiente.py:48`). Passar novos kwargs não quebra nada.
8. **O simulador já tem dois detectores de música.**
   - `metricas.titulos_citados` e `anotar_eventos` (`scripts/simulacao/metricas.py:62-100`, contagem em
     `:263-267`).
   - O dublê de `extrair_musicas_citadas` (`dubles.py:479-489`).
   - Ambos casam títulos do catálogo da fixture. A auditoria da F0 manda trocar o detector das métricas
     por código de `app/live` (`f0/auditoria.md:424`; cabeçalho de `metricas.py:1-6`). O dublê não é
     validador: ele imita uma chamada de LLM e fica como está.
9. **O banco de falas do dublê anuncia artista antes do título.** Exemplo: "Quem chega agora é Irmãos
   Taquara, com Estrada de Chão Batido." Um detector que suponha "título, com artista" dá falso positivo
   (medido no protótipo, §5.5).
10. **Contrato da F5** (auditoria em scratchpad, §5.7 e §5.8).
    - `checar_fala(fala, dados, agora, tz, cobertura_extra=()) -> list[Violacao]`, com
      `Violacao(regra, trecho, dado_id, instrucao_retry)`.
    - A remediação usa a **mesma** reescrita única (`router.py:3201-3243`) e depois `remover_frases`, com uma
      reorientação neutra se a fala ficar vazia ("Você está no {programa}, na {rádio}."). Não usar a reserva
      que promete conteúdo (`router.py:3172`).
    - `ContextoEmissao.dados: tuple[DadoVerificavel, ...] = ()`. A F5 não importa `app.live.contexto`.
11. **Invariantes da F2 que a F3 move sem reescrever:** no máximo 2 chamadas de LLM por `/proxima`; no
    máximo 2 sínteses na voz única; os registros com o texto final ficam depois do TTS (`router.py:3426-3466`);
    a frase "Reescreva com no máximo N palavras" não muda (dublê e teste).
12. **`musica-substituta`** (`router.py:3600-3664`) troca a faixa na hora de tocar.
    - Ela tenta outra versão da mesma música primeiro, mas no último recurso chama
      `_buscar_musica_para_bloco(db, programa)`, que traz outra música e não tem teto de relógio.
    - Nesse caso, a fala já anunciou outra faixa. É uma contingência de reprodução (F11), não de geração.

## 3. Testes existentes que tocam a F3

| Arquivo | Testes | O que cobre |
|---|---|---|
| `tests/test_live_router.py` | 135 | Integração de `/proxima`. Citadas: `test_musica_citada_em_comentario_toca_depois_da_fala` (`:3084`), `…_sem_faixa_nao_trava_comentario` (`:3121`, só confere `video_id`/`musicas`, **não** a fala), `test_bloco_musica_toca_tambem_as_musicas_citadas` (`:3143`), `…nao_repete_mesma_musica_citada_em_outra_versao` (`:3176`). Também: pedidos (`:1078`, `:1117`, `:2368-2849`), repetição (`:955`), temas (`:916`), formato musical (`:2936-3016`), tom (`:630-727`). |
| `tests/test_live_router_duracao.py` | 23 | Momentos A, B e C da F2, registros com o texto final (`:87`, `:127`, `:272`, `:334`), no máximo 2 LLM. |
| `tests/test_live_relogio_proxima.py` | 17 | Plano do relógio na rota, música com teto, histórico de música (`:278`), fio condutor (`:325`). |
| `tests/test_live_relogio.py` | 35 | Serviço puro, incluindo `instante_previsto` e o estado no Redis que falha aberto. |
| `tests/test_live_orcamento.py` / `test_live_ritmo_voz.py` | 20 / 9 | Funções puras da F2; o Redis falhando na calibração. |
| `tests/test_simular_hora.py` / `test_simular_hora_f2.py` | 29 / 10 | Determinismo (`:387`, `:403`), injeções nas métricas (`:494`), dublês cobrindo os alvos (`:509`), casos de avaliação (`:564`), hard times (`:607`), `inicio_previsto` sem relógio (`:633`). |
| `tests/test_llm_prompt_builder.py` | 42 | `montar_system_prompt` por substrings. |
| `tests/test_news_integracao_router.py` / `test_topics_integracao_router.py` | 9 / 4 | Pauta, escalada, correção e assunto no `prompts[0]`. |
| `tests/test_live_prewarm.py` / `test_atendimento_ouvintes.py` | 5 / 23 | `inicio_previsto` do prewarm; seleção e confirmação de pedidos. |
| `tests/test_guardrails_http_rate_limit.py` | 3 | Contagem do rate limit. Nenhum caso de Redis fora. |
| Painel: `hooks/__tests__/useLiveEngine.preparo.test.ts`, `lib/__tests__/filaPreparo.test.ts`, `relogioAoVivo.test.ts` | — | Campos do corpo de `/proxima`, um a um. Campos novos opcionais na resposta não quebram nada. |

**Não coberto:**
- nenhum retrato do prompt completo (system + mensagem) por cenário;
- nenhum teste da ordem dos sorteios;
- nenhum validador de música;
- nenhum `/proxima` com o Redis fora;
- nenhuma estimativa de horário sem `inicio_previsto`;
- a citada descartada pelo relógio que fica registrada.

## 4. Itens de `docs/auditoria.md` e `docs/refatoracao.md`

| Item | Situação | Na F3 |
|---|---|---|
| auditoria 6: Redis sem timeout | **aberto** (`redis_client.py:5`) | Entra (§5.7). |
| auditoria 5: corrida na fila | resolvido (`router.py:1926`, `atendimento.py:118`, `with_for_update`) | Manter o `with_for_update` quando o código mudar de lugar. |
| auditoria 4: rate limit pago | resolvido (`:2307`, `:3684`); resta o JWT sem revogação, fora do plano | Nada. |
| auditoria 3: dado externo no system | parcial (F5) | A F3 mantém o aviso "dados, não instruções" do ouvinte (`router.py:3097-3110`) idêntico. O bloco de dados é da F5. |
| auditoria 9: TTL do cache de categoria | aberto | F6. |
| refatoração §1: dividir `gerar_proxima_fala` | aberto | Esta frente (§5.9), em passos. |
| refatoração §2: texto de prompt no código | aberto | Constantes para `app/live/prompts.py`; montagem para `app/live/prompt_emissao.py`. |
| refatoração §3: `_sem_acento` | já resolvido (`router.py:134` importa `app.util.texto`) | Nada. |
| refatoração §5: troca por nome de módulo | aberto | "Portas" com ligação tardia (§5.3): começa a injeção de dependência sem quebrar os patches existentes. |

## 5. Desenho da mudança

### 5.1 Princípios

1. **Extrair não muda comportamento.** Os passos de extração (§5.9, passos 1 a 5) precisam deixar
   **idênticos**:
   - o retrato dos prompts;
   - a sequência simulada dos três perfis;
   - os testes existentes, sem editar nenhum.
2. **Mudanças de comportamento entram em commits próprios**, depois da extração: validador, registro das
   citadas, Redis e estimativa do horário.
3. **Contrato só com campos opcionais.** Sem migração: nenhuma coluna nem tabela nova.
4. **Números em configuração** (`settings` ou `ConfigRelogio`), nunca soltos no código.
5. **Não fazer F4, F5, F6 nem F8.** A F3 deixa os ganchos tipados para elas.

### 5.2 `ContextoEmissao` (`backend/app/live/contexto.py`, novo)

Dataclasses congeladas. Os objetos ORM entram só para leitura. O que muda depois da geração (músicas do bloco)
é trocado com `dataclasses.replace`.

```python
@dataclass(frozen=True)
class MusicaRef:
    titulo: str
    artista: str = ""
    video_id: str | None = None
    origem: Literal["bloco", "citada", "pedido", "historico", "sessao"] = "bloco"

@dataclass(frozen=True)
class PedidoRef:                       # só pedido aprovado: estado "selecionado" (fluxo novo) ou o legado consumido
    id: int; tipo: str; nome: str; natureza: str | None
    texto: str                         # texto_autorizado (novo) ou mensagem_usuario (legado)
    musica: MusicaRef | None
    estado: str; token: str | None

@dataclass(frozen=True)
class EstadoMusical:
    tocou: tuple[MusicaRef, ...]       # "[Música(s) tocada(s) nesse bloco: …]" das 8 linhas + títulos da sessão (Redis)
    confirmada: MusicaRef | None       # faixa deste bloco, que toca em seguida
    bloco: tuple[MusicaRef, ...] = ()  # preenchido depois da geração: confirmada + citadas resolvidas que cabem
    pedido_sem_resultado: bool = False
    resolve_citadas: bool = True       # False no bloco de música do formato musical ou com relógio (citadas = [])
    citaveis: tuple[MusicaRef, ...] = ()  # títulos conhecidos: camada (a) do validador
    contexto_faixa: str = ""

@dataclass(frozen=True)
class Participacao:
    novo_atendimento: bool
    pedido_musica: PedidoRef | None; pedido_ouvinte: PedidoRef | None
    ouvinte_recorrente: str | None; ouvinte_recorrente_dias: str | None   # tipo legível do pedido anterior
    pedido_recente: PedidoRef | None   # espiado, não consumido (legado)
    nomes_autorizados: tuple[str, ...]

@dataclass(frozen=True)
class Chamadas:                         # "chamadas pendentes" (§12.4)
    fio_condutor: str | None
    pedidos_em_fila: int = 0
    promessas: tuple = ()              # F4: registro de promessas ligado ao relógio

@dataclass(frozen=True)
class Tempo:
    agora_local: datetime; instante: datetime
    origem_instante: Literal["painel", "estimado", "agora"]
    plano: Plano | None; preset_relogio: str | None; inicio_previsto_aceito: bool
    ajuste_energia: str | None; marco_tempo: str | None; hora_certa: str | None

@dataclass(frozen=True)
class Memoria:
    historico_prompt: str               # as 6 últimas linhas, ou "Programa acabou de entrar no ar."
    ultima_categoria: str | None
    falas_categoria: tuple[str, ...]; aberturas: tuple[str, ...]; fechamentos: tuple[str, ...]
    tom_anterior: str | None; temas_usados: tuple[str, ...]; tema_callback: str | None

@dataclass(frozen=True)
class Variacoes:                         # já sorteadas/rotacionadas, na ordem atual
    verbo_identificacao: str; transicao: str | None; formato_comentario: str | None
    convite_ouvinte: str | None; expressao_regional: str | None
    quadro_fixo: str | None; assunto_sugerido: str | None; assunto: AssuntoConversa | None
    mudanca_de_ideia: bool; imperfeicao: bool

@dataclass(frozen=True)
class Jornalismo:
    pautas: tuple[NoticiaPauta, ...]; pauta: NoticiaPauta | None; correcao: NoticiaPauta | None
    pesquisa: PesquisaNoticias | None

@dataclass(frozen=True)
class ContextoEmissao:
    request_id: str
    account: Account; radialista: RadioConfig; programa: Programa
    tipo: str; categoria: str; primeira_fala: bool; total_falas: int; passos_roteiro: int
    formato_musical: bool; multi_voz: bool; roster: tuple[ParticipantePrograma, ...]
    tempo: Tempo; musica: EstadoMusical; participacao: Participacao; chamadas: Chamadas
    memoria: Memoria; variacoes: Variacoes; jornalismo: Jornalismo
    orcamento: OrcamentoFala; wpm_fala: float; categoria_voz: str; limite_palavras: int | None
    prompt_base: str                    # montar_system_prompt(...) chamado no montador (tem efeitos no Redis)
    modelo_com_tags: bool
    dados: tuple = ()                   # F5: DadoVerificavel (a F3 não importa app.dados)
    extensoes: Mapping[str, Any] = field(default_factory=dict)  # F4/F7/F8 sem mudar a assinatura
```

O montador é dividido em fases, na mesma ordem de hoje, para preservar sorteios, rotações e `commit`:

1. `roteiro.decidir_bloco(...) -> DecisaoBloco`:
   - tipo, plano e instante;
   - laço de vinheta e patrocinador, notícia sem fonte que vira música, assunto esgotado.
   - Pode devolver uma resposta imediata (vinheta ou patrocinador), que o router serializa.
2. `contexto.resolver_musica_e_pedidos(...) -> (EstadoMusical, Participacao)`:
   - pedido, busca e relógio.
   - Pode devolver "música sem fala", que o router serializa.
3. `contexto.montar_contexto(...) -> ContextoEmissao`:
   - memória, variações (inclusive `registrar_callback_musica`), jornalismo, orçamento da F2;
   - `prompt_base`, sorteios.

O módulo não importa `app.live.router`. As funções que os testes trocam por nome entram pelas portas (§5.3).

### 5.3 Portas (`backend/app/live/portas.py`, novo)

`PortasEmissao` é uma dataclass de chamáveis: `gerar_resposta`, `gerar_dialogo_multivoz`, `buscar_musica`,
`resolver_musica_catalogada`, `extrair_musicas_citadas`, `resumir_contexto_musica`, `pesquisar_noticias`,
`proxima_noticia`, `classificar_fio_condutor`, `classificar_categoria_bloco`, `_buscar_musica_para_bloco`,
`_selecionar_musica_para_bloco`, `_registrar_tema_em_background`, `tts_habilitado`, `sintetizar_audio`,
`processar_audio` etc.

O router a monta com **ligação tardia**, buscando o nome em `globals()` do router no momento da chamada:

```python
def _portas() -> PortasEmissao:
    g = globals()
    return PortasEmissao(**{n: (lambda n=n: lambda *a, **k: g[n](*a, **k))() for n in PortasEmissao.nomes()})
```

Assim, os 108 patches em `app.live.router.gerar_resposta` e os demais continuam valendo sem editar teste. O
simulador continua alcançando tudo (troca por identidade mais `por_nome`). É também o primeiro passo da
fronteira pedida em refatoração §5.

### 5.4 Validador pós-geração (`backend/app/live/validacao_fala.py`, novo)

```python
@dataclass(frozen=True)
class Violacao:                     # mesmo formato que a F5 usa
    regra: str                      # "musica_nao_confirmada" | (F5) "tema_sem_dado" … | (F4) "promessa_sem_evento"
    trecho: str                     # frase onde está
    ref_id: str = ""                # título citado / dado_id / promessa_id
    instrucao_retry: str = ""       # texto para a reescrita única
    remediacao: Literal["remover_frase", "avisar"] = "remover_frase"

Checagem = Callable[[str, "ContextoEmissao"], list[Violacao]]
CHECAGENS_POS_GERACAO: list[Checagem] = [checar_musicas]   # F5 acrescenta checar_fala; F4, promessas

def mencoes_musica(texto, citaveis, nao_musica) -> list[MencaoMusica]       # puro, usado pelo simulador
def checar_musicas(fala, ctx) -> list[Violacao]
def validar(fala, ctx, fase: Literal["pre", "final"], checagens=CHECAGENS_POS_GERACAO) -> list[Violacao]
def remover_frases(fala, violacoes, preservar) -> str            # extrativo; reaproveita a divisão de app.live.orcamento
def fala_reserva_neutra(ctx) -> str                              # "Você está no {programa}, na {rádio}."
```

**Detecção (determinística, sem LLM, padrões em configuração no módulo).**
- **Camada (a), títulos conhecidos:** `ctx.musica.citaveis` aparecem no texto como palavras inteiras.
  - Em produção, os títulos conhecidos são:
    - `musicas_permitidas`;
    - `MusicaHistorico` recente da rádio (a consulta de `_musicas_recentes_da_radio` já existe);
    - `musica_query` dos pedidos em fila;
    - títulos da sessão.
  - No simulador, são o catálogo da fixture mais as injeções.
- **Camada (b), construções de anúncio:**
  - um marcador ("toca agora", "agora vem", "vem aí", "já já vem", "a seguir", "na sequência", "pode
    esperar", "vamos de", "vamos ouvir", "bora ouvir", "com vocês", "agora,") seguido de um trecho com
    iniciais maiúsculas (conectivos de/da/do/na/no/e/em permitidos);
  - ou a forma canônica da §8, "`<Trecho>`, com/de `<Trecho>`".
  - Valem as **duas ordens** (título e artista, ou artista e título), por causa do fato 9.
  - Trechos iguais aos nomes da rádio, do programa, do locutor, do elenco, do quadro, da cidade ou dos
    ouvintes autorizados são ignorados.
- **Camada (c), só em produção:** citadas devolvidas pelo `extrair_musicas_citadas` (a chamada já existe) que
  não se resolveram.
- **Comparação:** um trecho está permitido se qualquer de suas partes for "a mesma música" de algum item
  de `confirmada ∪ bloco ∪ tocou ∪ pedido selecionado`. A regra é a de `app.live.music.titulo_ja_tocado` e
  `_titulo_normalizado` (`music.py:223-258`), que já trata "Evidencias" × "Chitaozinho & Xororo - Evidencias".
  Um pedido `em_fila` **não** confirma nada.

**Onde roda (sem chamada de LLM nova; invariante da F2 de no máximo 2):**
- **V1, fase "pre":** antes da decisão de reescrita (`router.py:3201`), só quando `resolve_citadas=False`.
  Nesse caso nenhuma citada vai tocar, e a violação é definitiva. Ela entra como mais um motivo da **mesma**
  reescrita única. Texto: "Você citou '{X}', que não vai tocar. A única faixa confirmada é '{título}' de
  '{artista}'; não cite outra." Sem faixa confirmada: "não cite música pelo nome". Se a reescrita já tiver
  sido usada por outro motivo, segue para V2.
- **V2, fase "final":**
  - Roda depois do momento B e da resolução das citadas, **antes do TTS** e dos registros.
  - As violações saem por `remover_frases`, preservando o nome do ouvinte e o título confirmado.
  - Fala vazia:
    - no bloco de música com faixa e sem pedido, a fala vira `""` (só música, regra 8, mesma saída do
      `pode_cortar` da F2);
    - nos outros casos, `fala_reserva_neutra(ctx)`.
  - No multivoz, a remoção é por `FalaItem`.
- **Modo:** `settings.validacao_musica_modo: "corrigir" | "avisar"` (padrão `corrigir`, decisão D2). Em
  `avisar`, só log e resposta.
- **Registro das citadas (corrige o fato 3):**
  - `_musicas_citadas_na_fala` passa a só **resolver**.
  - `_registrar_musica_tocada` e `_registrar_historico_persistente` rodam só para as faixas que ficam em
    `musicas_bloco`, depois de `_citadas_que_cabem`.
  - Sem relógio o resultado é igual, porque todas ficam. Os testes `:3084` e `:3143` continuam valendo sem
    mudança.

### 5.5 Como medir "100 % dos casos"

1. **Casos (`tests/test_live_validacao_fala.py::test_casos_benchmark_musica`).**
   - Carrega `docs/benchmarks/2026-11-06-formatos/casos.json` (35 casos, 70 falas rotuladas, 7 com
     `anuncio_sem_confirmacao=true`).
   - Para cada fala, monta o `EstadoMusical` a partir de `contexto`: `tocou`, `proxima_confirmada` e pedidos
     com `estado == "selecionado"`.
   - Os nomes que não são música saem da fixture do formato (`tests/fixtures/programas/<formato>.json`:
     `conta.nome_radio`, `programa.nome`, `radialista.nome_locutor`) mais os nomes dos pedidos. Não é preciso
     mudar `casos.json`.
   - **Critério:** 7 de 7 detectados **e** 0 falsos positivos nas outras 63 falas.
2. **Protótipo de viabilidade (descartável, fora do repositório):**
   `/private/tmp/claude-501/-Users-guilhermejeske-projetos-locufy/4efade71-3851-4394-9e93-629b2f839d1f/scratchpad/melhoria-radio/f3/proto/prototipo_validador.py`.
   - As camadas (a) e (b), com as duas ordens, dão **7/7 e 0 falsos positivos**.
   - Rodado nos `as_run.json` da F1 e da F2 (`proto/sim_check.py`), coincide com o
     `anuncio_sem_confirmacao` do simulador: 1 no `musical_adulto`, a injeção "Canção do Sereno", e 0 nos
     demais.
   - A primeira versão, que só aceitava a ordem título-artista, deu 8 falsos positivos nas falas do dublê
     (fato 9).
3. **Simulador.**
   - `metricas.anotar_eventos` passa a calcular `musicas_citadas`/`musica_anunciada` com
     `app.live.validacao_fala.mencoes_musica`. A importação é preguiçosa, dentro da função, como já faz
     `_aviso_oralidade` (`metricas.py:218-227`); o módulo continua sem importar `app.*` no carregamento.
   - `titulos_citados` vira um invólucro dessa função. Não sobra um segundo detector.
   - Cada evento ganha `validacao_fala`, vindo da resposta.
   - **Critério:** `anuncio_sem_confirmacao == 0` nos três perfis, com relógio, `sem_relogio` e `voz_120`.
     O contador `injecao_cita_musica` continua ≥ 1, o que prova que a injeção aconteceu e foi removida.
4. **Fora desta medição:** a taxa de falsos positivos com texto real de LLM. Só no `--modo llm`, com
   aprovação de custo. Até lá, o modo `avisar` está disponível (D2).

### 5.6 Painel antigo sem `inicio_previsto`: estimativa no servidor

Só para programas **com relógio** e quando o campo falta. Programa sem relógio continua com `now()` (D4 da F1).

- **Cadeia no Redis:**
  - chave `relogio_cadeia:{programa_id}:{ocorrencia.chave}`, lista de elos
    `{tipo, vinheta: bool, duracao_s, gerado_em}`;
  - TTL `cfg.ttl_estado_s`;
  - gravada em `_com_relogio` para **toda** resposta de programa com relógio, inclusive o prewarm. A
    duração é `pausa_antes_ms` mais `duracao_prevista_s`, que já usa o ritmo calibrado da F2.
- **Função pura** `relogio.instante_sem_painel(elos, agora, inicio_ocorrencia, cfg) -> datetime`. Ela usa o
  invariante do fato 6:
  - sem elos (`total_falas == 0` e histórico vazio, o que também zera a cadeia): `max(agora, início)`.
    Para achar o início ainda antes da ocorrência, procura um `horario_inicio` de hoje até
    `cfg.preparo_sem_painel_max_s` (novo, padrão 120) à frente, a mesma conta do prewarm
    (`prewarm.py:64-66`);
  - menos de `cfg.antecedencia_painel_antigo` (novo, padrão 2) elos sem vinheta:
    `max(agora, início) + Σ duração dos elos`;
  - caso contrário: `agora + Σ duração dos elos a partir do penúltimo elo sem vinheta`. O bloco *k−2* acabou
    de começar, então cada pedido se reancora em `agora` e o erro não acumula.
  - Limite: `agora ≤ instante ≤ agora + inicio_previsto_max_s`.
- **Adaptador** que falha aberto: sem Redis, vale `agora`, como hoje.
- **Contrato:** `RelogioAoVivo.origem_instante: Literal["painel", "estimado", "agora"]`, opcional
  (`relogio.py:995`). Log `relogio_inicio_previsto_estimado programa_id instante elos`, que também mede
  quantos painéis antigos ainda estão no ar.
- **Critério na simulação `--sem-inicio-previsto`** (popular com A, variedades com C):
  - atraso em hard time ≤ 5 s;
  - `encerramento_no_ar` verdadeiro;
  - `segundos_cortados == 0`.
- **Limite conhecido:** o painel antigo verifica o início agendado a cada 15 s (F1, `useLiveEngine.ts`, timer
  pontual só no painel novo). No ar, o hard time 00:00 pode atrasar até 15 s, e o simulador não reproduz isso.

### 5.7 Redis (item 6)

- **`app/config/redis_client.py`:** `redis.from_url(url, decode_responses=True,
  socket_connect_timeout=settings.redis_connect_timeout_s, socket_timeout=settings.redis_socket_timeout_s,
  health_check_interval=settings.redis_health_check_s)`. Padrões: 0,5 s, 1,0 s e 30 s, em configuração.
- **Disjuntor no mesmo módulo:**
  - `redis_disponivel()`;
  - `seguro(operacao, padrao, nome)`: captura `RedisError` (inclusive `TimeoutError` e `ConnectionError`),
    grava um log por janela e abre o disjuntor por `settings.redis_pausa_apos_falha_s` (15 s);
  - com o disjuntor aberto, devolve `padrao` sem tocar o socket.
- **Aplicação nesta frente:**
  - leituras e escritas de sessão do ao vivo, todas via `seguro`:
    - as 16 do router;
    - `_proxima_variacao` e `_fato_do_dia` do `prompt_builder`;
    - `clima_mencionado`;
    - as leituras de `pauta_conversa`;
    - o adaptador da cadeia.
  - Padrões neutros: lista ou conjunto vazio, `None`. Na rotação, `opcoes[0]`, determinístico.
  - `limite_excedido`: falha **aberto** nas rotas do ao vivo e das contas. Nas rotas públicas de
    autenticação, conforme a decisão D5.
- **Fora:** dedupe e travas do WhatsApp (`whatsapp/locks.py`, `inbox.py`). Com o timeout eles falham em ≤ 1 s,
  em vez de travar. Registrar em `pendencias.md`.

### 5.8 Contratos, painel e ganchos para F4/F5

- `LiveProgramResponse.validacao_fala: ValidacaoFalaResponse | None = None`, com
  `{violacoes: [{regra, trecho, ref_id}], acao: "nenhuma" | "reescrita" | "mencao_removida" | "fala_neutra"}`.
  Aditivo. O prewarm serializa a resposta inteira (`prewarm.py:80`).
- `RelogioAoVivo.origem_instante` (§5.6). O pedido não muda.
- **Painel:** só tipos opcionais em `frontend-painel/lib/liveTypes.ts:55-110`. Sem interface nova. Vitest só se
  os tipos mudarem.
- **Sem migração.** Chave nova no Redis: `relogio_cadeia:*`.
- **F5:**
  - preenche `ContextoEmissao.dados` em `montar_contexto`;
  - registra `checar_fala` em `CHECAGENS_POS_GERACAO` com um adaptador
    `lambda fala, ctx: checar_fala(fala, ctx.dados, ctx.tempo.instante, ctx.radialista.timezone, …)`;
  - reaproveita `Violacao`, `remover_frases` e `fala_reserva_neutra`, que **não** devem ser recriados em
    `app/dados`;
  - leva o bloco de dados para `PromptEmissao.mensagem`. As linhas que a F5 apontava no router
    (`:2193-2760` na numeração antiga) passam a ficar em `contexto.py` e `prompt_emissao.py`.
  - Ordem de merge: F3 antes da F5.
- **F4:**
  - `Chamadas.promessas` mais uma checagem de promessa registrada no mesmo laço;
  - o relógio (`ctx.tempo.plano`) dá os eventos agendados;
  - o detector provisório de promessas do simulador é trocado pela F4, e o de abertura repetida pela F8.

### 5.9 Extração incremental de `gerar_proxima_fala`

Cada passo é um commit. O portão do passo:
- golden de prompts idêntico;
- digest da simulação idêntico;
- `pytest` dos arquivos da §3 verde, **sem editar teste**;
- `ruff`.

| Passo | O que faz | Comportamento |
|---|---|---|
| 0 | Caracterização: C1 e C2 (§6) gravam os goldens no código atual | igual |
| 1 | `portas.py` e `_portas()` no router (ainda sem uso) | igual |
| 2 | Constantes de texto (`_PROSODIA_BLOCO`, `_DESCRICAO_BLOCO`, `_REGRAS_REDACAO_NOTICIA`, `_INSTRUCAO_*`, `_VARIACOES_*`, `INSTRUCAO_TAGS_V3`, `_PROB_*`) vão para `app/live/prompts.py`, com reimportação explícita no router (`scripts/validar_combinacoes.py:116` e os testes importam do router) | igual |
| 3a | **Dentro do router**, os efeitos colaterais e os sorteios da faixa `:2541-3110` sobem para antes da montagem, em variáveis, na mesma ordem e com as mesmas condições: rotações, `registrar_callback_musica`, `_contexto_musica`, convite, transição, marco, energia, sorteios | igual (o golden confere a ordem das chaves no Redis e das chamadas a `random`) |
| 3b | Cria as dataclasses e preenche o `ContextoEmissao` no router com as variáveis do 3a. `prompt_emissao.montar_prompt(ctx) -> PromptEmissao(system, mensagem)` substitui `:2592-3141` e é **puro** (sem Redis, sem `random`). `prompt_revisao(ctx, prompt, fala, motivos)` substitui o texto da reescrita (`:3205-3235`) com as mesmas frases | igual |
| 4a | Memória, variações e jornalismo vão para `contexto.montar_contexto(entrada, portas)` | igual |
| 4b | Pedidos e música (`:2440-2539`, `_resolver_musica_do_relogio`) vão para `contexto.resolver_musica_e_pedidos`. A seleção com `with_for_update` fica igual | igual |
| 4c | Decisão de bloco (`:2317-2424`) vai para `app/live/roteiro.py::decidir_bloco` (inclui `_tipo_proximo_bloco`, `_categoria_bloco` e `_ultima_categoria_bloco`, reimportados no router) | igual |
| 5 | Geração e reescrita única, com os momentos A e B da F2 (`:3143-3271`), vão para `app/live/geracao.py::gerar_fala(ctx, portas)`. O router fica com HTTP, retornos imediatos, TTS (momento C), registros e resposta | igual; meta: `gerar_proxima_fala` com menos de 250 linhas |
| 6 | Validador V1 e V2, `validacao_fala` na resposta, simulador importando o detector | **muda** (goldens com violação são regravados no mesmo commit, com o diff revisado) |
| 7 | Citadas: resolver sem registrar, registrar só as que ficam no bloco | **muda** só com relógio |
| 8 | Redis: timeouts, disjuntor, `seguro`, falha aberta | **muda** só com o Redis fora |
| 9 | Cadeia de horário para o painel antigo | **muda** só com relógio e sem o campo |
| 10 | Rodadas da simulação, `RELATORIO.md`, `pendencias.md`, `docs/plano.md` | — |

Os passos 8 e 9 não dependem da extração. Se a extração travar, eles podem entrar antes, desde que usem as
funções onde elas estão hoje.

## 6. Testes, nesta ordem

**Caracterização (passo 0, antes de mover código)**

- **C1, `tests/test_live_proxima_caracterizacao.py`.**
  - Cerca de 20 cenários parametrizados, com `@freeze_time`, fakeredis limpo, `random.seed(n)` e dublês que
    capturam `(system, mensagem)`.
  - Golden em `tests/fixtures/caracterizacao_proxima/<cenario>.json`, com o texto completo do system e da
    mensagem, o JSON da resposta sem `criado_em`, as chaves e valores do Redis depois da chamada e a sequência
    de chamadas a `random.random`. Regravação só com `ATUALIZAR_GOLDEN=1`.
  - Cenários:
    - padrão: comentário com assunto, com quadro fixo, com assunto sugerido e com callback de tema;
    - padrão: música com faixa, sem faixa e com citada;
    - pedido legado, pedido novo com `texto_autorizado`, pedido sem resultado;
    - chamada de ouvinte com abraço, sorteio, recorrente e recorrente de outro dia; pedido recente
      inesperado;
    - notícia com pauta, escalada, correção, pesquisa `ok`;
    - abertura primeira, encerramento com fio condutor;
    - musical: retomada, identificação, música com pedido;
    - relógio A: link, fechamento curto, encerramento;
    - multivoz;
    - voz com tags (v3).
- **C2, `test_simulacao_caracterizacao_f3`.**
  - Digest de `(bloco, texto, musica_tocada, chamadas_llm, relogio.acao)` por evento, nos três perfis ×
    {`fixture`, `nenhum`}, comparado com `tests/fixtures/caracterizacao_proxima/simulacao.json`.
  - Vale nos passos 1 a 5. No passo 6 é regravado ou retirado, com registro no relatório. A F0 pede não
    travar `as_run` de forma permanente.
- **C3.** As suítes da §3 continuam verdes sem edição em todos os passos de extração.

**Unitários**

- **U1, `test_live_contexto.py`:**
  - `tocou` sai das 8 linhas e da sessão;
  - `confirmada`, `resolve_citadas` por formato e relógio;
  - pedido `em_fila` não entra como aprovado;
  - nomes autorizados;
  - ordem dos sorteios (espião) igual à do router antigo;
  - o montador não importa `app.live.router`.
- **U2, `test_live_prompt_emissao.py`:**
  - mesmo `ctx` dá o mesmo texto;
  - zero acesso ao Redis e ao `random` (espiões);
  - substrings por campo;
  - a frase "Reescreva com no máximo N palavras" continua intacta.
- **U3, `test_live_validacao_fala.py`:**
  - as duas ordens, título-artista e artista-título;
  - marcadores;
  - exclusão de rádio, programa, locutor e ouvintes;
  - "Evidencias" × "Chitaozinho & Xororo - Evidencias";
  - pedido `em_fila` não confirma;
  - camadas (a), (b) e (c);
  - `remover_frases` preserva o ouvinte e o título;
  - fala vazia: `""` na música sem pedido, reserva neutra nos outros blocos;
  - multivoz por linha.
- **U4:** `test_casos_benchmark_musica`, 7/7 e 0 falsos positivos em 70 falas (§5.5).
- **U5:** uma checagem extra falsa (imitando a F5) registrada em `CHECAGENS_POS_GERACAO` é chamada; as
  violações dela entram na reescrita única e na remoção.
- **U6, `test_live_relogio.py` (cadeia):**
  - vazio → início;
  - `[b1]` → início + d1;
  - `[b1, b2]` → agora + d1 + d2;
  - vinheta não conta na antecedência;
  - limite superior;
  - zera com `total_falas == 0`;
  - Redis falhando → agora.
- **U7, `test_redis_client.py`:**
  - kwargs de timeout passados ao `from_url` (espião);
  - `seguro` devolve o padrão;
  - o disjuntor não chama o Redis durante a pausa;
  - `limite_excedido` segue a política de D5.

**Integração (HTTP, patches pelo nome no router)**

- **I1.** Musical, bloco de música, dublê anunciando outra faixa:
  - uma reescrita com a instrução que nomeia a confirmada;
  - se ainda estiver errada, a frase é removida e `validacao_fala.acao == "mencao_removida"`;
  - no máximo 2 LLM.
- **I2.** Cenário de `:3121`: comentário que cita uma música inexistente.
  - A menção sai, e a fala vira reserva neutra se esvaziar.
  - `musicas == []`. Mudança intencional, documentada.
- **I3.** Relógio, citada descartada pela falta de espaço:
  - fora de `musicas_tocadas:*` e de `MusicaHistorico`;
  - menção removida.
- **I4.** Cenários de `:3084` e `:3143`: citada resolvida toca, sem violação e sem mudança.
- **I5.** Música, duração e repetição juntas: ainda no máximo 2 LLM e no máximo 2 sínteses.
- **I6.** Redis fora (métodos do fakeredis levantando `ConnectionError`):
  - `/proxima` e `/tts` dão 200;
  - o prompt sai sem memória;
  - log único;
  - com o disjuntor aberto, contagem de chamadas = 0.
- **I7.** Relógio sem `inicio_previsto`, 3 pedidos seguidos: `origem_instante == "estimado"` e instante
  conforme a cadeia. Com o campo: `"painel"`.
- **I8.** O prewarm grava o primeiro elo; o primeiro `/proxima` do painel antigo encadeia a partir dele.
- **I9.** Resposta: todos os campos atuais iguais; só `validacao_fala` e `relogio.origem_instante` novos.

**Simulação**

- **S1.** Três perfis × {relógio, `sem_relogio`, `voz_120`}:
  - `anuncio_sem_confirmacao == 0`;
  - `injecao_cita_musica ≥ 1`;
  - `validacao_fala` no as-run;
  - demais métricas não piores que as da F2;
  - menos de 30 s e 0 rede.
- **S2.** `--sem-inicio-previsto` (popular com A, variedades com C):
  - atraso ≤ 5 s, encerramento no ar, 0 s cortados.
  - Gravar em `docs/melhoria-radio/f3/simulacao/<perfil>/sem_inicio_previsto/`.
- **S3.** Teste de que `metricas` não tem detector de título próprio: `titulos_citados` delega a
  `app.live.validacao_fala`.
- **S4.** `--modo llm` só com aprovação explícita: mede os falsos positivos do validador com texto real.

## 7. Riscos e o que não fazer

- **Ordem e condições de sorteios e rotações.**
  - Não reordenar `random.random()` nem as chamadas de `_proxima_variacao` ao mover.
  - O golden C1 grava a sequência; os passos 3a e 3b são os de maior risco.
- **Patches por nome.**
  - Não importar de `app.llm.client` ou `app.live.music` em módulo novo nada que os testes troquem em
    `app.live.router`. Usar as portas.
  - Não editar testes nos passos 1 a 5.
- **Prompt.** Não mudar uma vírgula do texto durante a extração. Mudança de texto é de outra frente (F6/F7).
- **Validador e falsos positivos com LLM real.** Nomes próprios de ouvinte fora da fila, títulos que são
  expressões comuns, artista antes do título.
  - Padrões ficam em configuração.
  - Modo `avisar` disponível.
  - Medir no `--modo llm` antes de considerar o modo `corrigir` validado em produção.
  - Os 70 rótulos são pequenos; o protótipo pode estar ajustado demais a eles.
- **Remover frase pode deixar emenda solta** ("E essa…"). A reserva neutra cobre a fala vazia. Medir no
  as-run quantas falas foram removidas ou neutralizadas.
- **Não criar chamada de LLM para validar** nem uma terceira chamada (invariante da F2). Não acelerar a voz.
- **Cadeia do painel antigo.**
  - Ela supõe a antecedência 2 do painel atual de `master`.
  - Outro cliente sem o campo seria mal estimado, por isso o limite superior e o log.
  - Não estender a programas sem relógio (D4 da F1).
- **Falha aberta no rate limit é uma troca de segurança.** Durante a queda, o login fica sem limite. Ver D5.
- **Conflito de merge** com F4 e F5 na mesma região. A F3 entra antes; a F5 refaz a base sobre
  `contexto.py`/`prompt_emissao.py`.
- **Não fazer nesta frente:**
  - F4: registro de promessas, teases;
  - F5: `DadoVerificavel`, bloco de dados, `checar_fala`;
  - F6: catálogo, TTL do cache de categoria;
  - F8: consolidar a memória em `app/live/memoria.py`. A F3 só lê pelas funções atuais;
  - pré-reserva da próxima faixa (D3);
  - teto em `musica-substituta` (F11);
  - estado das etapas pela reprodução (F11).
- **`with_for_update`** (auditoria 5) precisa ir junto quando `_proximo_pedido_fila_dentre` e `selecionar`
  forem chamados de outro módulo.
- **`montar_system_prompt` tem efeitos no Redis.** Ele é chamado uma vez em `montar_contexto`, para que
  `montar_prompt` fique puro.

## 8. Decisões para o usuário (não bloqueiam; padrão sugerido entre parênteses)

- **D1.** "`prompt_builder` recebe só `ContextoEmissao`" vira `app/live/prompt_emissao.py::montar_prompt(ctx)`.
  `app/llm/prompt_builder.montar_system_prompt` fica como está, porque o WhatsApp o usa. (Sim.)
- **D2.** Remediação: reescrita única (V1) e depois remoção da frase (V2). Modo inicial: `corrigir`, com
  `avisar` em configuração. (Corrigir.)
- **D3.** Reservar a **próxima** faixa num bloco de fala, para permitir o front-announce de uma retomada
  ("Agora, [faixa]"), como no caso `f3-retomada-anuncia-confirmada`. Isso muda o momento da seleção e
  interage com o teto do relógio. (Não nesta frente; sem isso, bloco de fala não anuncia faixa nova.)
- **D4.** Citadas em bloco de fala com relógio: manter a resolução com teto, que é o comportamento atual, ou
  proibir de vez, como o prompt já pede. (Manter; o validador cobre as descartadas.)
- **D5.** Redis fora:
  - rate limit falha aberto no ao vivo e nas rotas autenticadas;
  - nas rotas públicas de autenticação (`auth_login`, `auth_register`, `auth_esqueci_senha`,
    `auth_redefinir_senha`): falhar fechado com 503 ou aberto.
  - (Fechado nas públicas de autenticação, aberto no resto.)
- **D6.** Goldens de prompt (C1) como caracterização permanente, regravados de propósito pelas frentes que
  mudam texto, ou retirados ao fim da F3. (Manter; as frentes F5 a F8 regravam com o diff revisado.)

## 9. Pendências de frentes anteriores atribuídas à F3

| Origem | Pendência | Tratamento |
|---|---|---|
| F0, F1, F2 | Redis sem timeout (auditoria 6) | §5.7, passo 8 |
| F0 | Detectores provisórios no simulador: música | §5.4 e §5.5, passo 6. Promessa fica com a F4, abertura repetida com a F8. |
| F0 | Citada toca em retomada ou identificação no formato musical | Mantido (D4). O validador remove as que não tocam. |
| F1 | Painel antigo sem `inicio_previsto` atrasa até 412 s | §5.6, passo 9 |
| F1 | Citada descartada por espaço já registrada como tocada | §5.4, passo 7 |
| F1 | Estado das etapas marcado na geração | Fora: as-run da F11 |
| F1 | `musica-substituta` sem o espaço restante | Fora: F11 (contingência "áudio falhou"). A F3 só registra em log quando a substituta é outra música, não outra versão. |
| F2 | Reescrita e encurtamento em funções puras; o router só chama | Passo 5 move as chamadas sem reescrever a regra |

## 10. Dependências

Nenhuma bloqueia. F0, F1 e F2 estão na branch. A F5 já auditada supõe que a F3 entra antes. A F4 vem depois e
usa `ctx.tempo.plano` e `ctx.chamadas`. Os modos `llm` e `completo` do simulador só rodam com aprovação
explícita de custo.

PRONTA PARA IMPLEMENTAR
