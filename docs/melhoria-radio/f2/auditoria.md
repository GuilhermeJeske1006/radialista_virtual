# Auditoria F2: duração real da fala

Branch auditada: `melhoria/f0-bancada` (o `backend/app/` é igual à `master`, cujo último commit é `6ccf3d7`, de 21/10/2026). Nenhum commit em `app/live`, `app/tts`, `app/postprod` ou `useLiveEngine.ts` depois de 15/10. Auditoria feita em 07/11/2026, só com leitura do código.

Fontes: `docs/plano-melhoria-radio.md` (F2, F1, F6 e "Avaliação"); `docs/pesquisa-radio-locufy.md` §5 ("Ritmo e duração"), §11 e §12.8; skill `referencia-radio`; `docs/melhoria-radio/f0/auditoria.md`; `docs/auditoria.md`; `docs/refatoracao.md`; benchmarks de voz em `docs/benchmarks/`.

Premissas do coordenador:
- A F1 (relógio e backtiming) entrega o orçamento disponível. A F2 recebe esse orçamento por parâmetro.
- Sem relógio, a F2 usa `ORCAMENTOS` de `app/live/formato.py`.

## 1. O estado atual descrito no plano confere com o código?

| Afirmação do plano | Situação | Evidência |
|---|---|---|
| `ORCAMENTOS` em `formato.py` dá segundos e limite de palavras por tipo no perfil musical | confirmado | `backend/app/live/formato.py:13-19`, tupla `(min_s, max_s, max_palavras)`. `orcamento_fala` (`:26-30`) troca `abertura` por `retomada` quando não é a primeira fala. Tipo desconhecido recebe `(10, 20, 45)`. Não existe "alvo". |
| `contar_palavras` existe | confirmado | `formato.py:33-34`. Ignora `[tags]`, não normaliza números e não conta pausas. |
| `_limpar_fala` limpa o texto | confirmado | `backend/app/live/router.py:786-799` (aspas, markdown, espaços). Só avisa sobre algarismos (`:771-783`). |
| A resposta de `/proxima` tem `duracao_segundos` para a música, não para a fala | **diferente** | `duracao_segundos` é da música (`router.py:168`, `:2931`). **Já existe** `duracao_alvo_segundos: tuple[int, int]`, a meta da fala (`router.py:201`, `:2948`), mas só no formato musical. O painel só a declara no tipo (`frontend-painel/lib/liveTypes.ts:66`, `:96`) e não a usa. |
| Não há medição da duração do áudio sintetizado | confirmado no ao vivo | Nada mede o áudio da fala em `/proxima` nem em `/tts`. Já existem três medidores fora do ao vivo: `app/patrocinadores/router.py:69-75` e `app/biblioteca_audio/router.py:70-73` (pydub, arredondado) e `app/vinhetas/audio.py:72-87` (ffprobe sobre arquivo temporário). O player mede a duração real ao tocar (`frontend-painel/hooks/useLiveEngine.ts:1262-1268`), mas **não a manda ao backend**. |
| Não há calibração por voz | **diferente (parcial)** | Existe um ajuste manual de `speed` por voz, medido em benchmark (`app/tts/client.py:183-195`: Paulo 0,85, Yasmin 1,12). Não há nenhuma calibração da **estimativa** de duração. |
| "O orçamento é só uma instrução ao LLM; nada confere o áudio final" | **diferente (parcial)** | No formato musical já existe uma conferência por **palavras**: se `contar_palavras(fala) > max_palavras`, entra uma única reescrita, somada aos outros motivos (`router.py:2706-2760`). Se a fala ainda passar do limite, o código só registra `live_orcamento_excedido` (`:2754-2756`) e ela vai ao ar assim mesmo. No formato padrão não há orçamento nenhum: o prompt pede "umas 4 a 6 frases de rádio" (`:2186-2189`). Nada confere o áudio. |

### Fatos do código que mudam o desenho

1. **O painel não recebe áudio do `/proxima`.**
   - O painel envia sempre `incluir_audio: false` (`useLiveEngine.ts:1316`) e só depois chama `POST /live/{id}/tts` com `perfil_pos_producao: "radio_fm"` (`:1444-1454`). O motivo está em `:1270`: "Entrega o texto antes do TTS para liberar a escrita do próximo bloco".
   - Com `incluir_audio=False`, o `/proxima` devolve `audio_status="pendente"` sem sintetizar (`router.py:2831-2832`).
   - Só três caminhos sintetizam dentro do `/proxima`: o **prewarm** (`app/live/prewarm.py:64`, `incluir_audio=True`), o **multivoz** (`router.py:2884-2898`, sempre que o TTS está habilitado) e clientes antigos.
   - Consequência: no caminho principal, quando o áudio existe, o texto já saiu e já está na fila de preparo do player. Ali só dá para medir e calibrar. Corrigir exige que a decisão aconteça **antes do TTS**, com uma estimativa calibrada.
2. **O `/tts` com pós-produção devolve o mp3 inteiro.** O caminho é `Response`, em `router.py:3166-3195`, e pode ser medido. Sem perfil, o caminho é streaming (`:3129-3164`) e não dá para medir sem acumular os bytes. O painel sempre manda perfil.
3. **Velocidade da voz.**
   - `sintetizar_audio` não tem parâmetro de velocidade (`app/tts/client.py:352-366`). O `speed` vem do tipo do bloco, do tom (`energico` +0,04, `calmo` −0,04, `:95-96`), de ser voz clonada e do multiplicador por voz.
   - O v4 ignora `speed` (`:158-160`).
   - Logo, "não acelerar a voz além do perfil" significa: **não trocar tom, modelo nem perfil para caber**, e não aplicar `atempo` na pós-produção.
4. **O ritmo real das vozes fica bem acima da hipótese da pesquisa (130–160).**
   - `docs/benchmarks/2026-10-08-eleven-v4/README.md:23-36`: v3 162, v4 158, Flash 171 palavras/min. O v4 varia de 139 a 195.
   - `docs/benchmarks/2026-09-10/vozes-padrao-catalogo.md:86-93,154`: de 193 a 237 no v3 com os presets de bloco.
   - Com 145 palavras/min (o padrão do dublê da F0), a estimativa **superestima** a duração em 10% a 40%. Sem calibração, isso gera reescritas desnecessárias e falas mais curtas do que o orçamento permite.
5. **Pausas e normalização.**
   - `......` vira `[pause]`, de cerca de 1,2 a 1,5 s (`client.py:146-152`, `app/tts/modelos.py:7-9`).
   - Números e pronúncias são expandidos em `normalizar_texto_fala` (`app/numeros.py:101`) antes do TTS (`client.py:296`).
   - `contar_palavras` não vê nenhuma das duas coisas.
6. **Cache de TTS.** O mesmo texto com a mesma voz devolve os mesmos bytes por 24 h (`app/tts/cache.py`, `settings.ia_cache_ttl_segundos`). Uma amostra de calibração vinda do cache duplica a anterior.
7. **Redis em produção sem persistência e com descarte por LRU.** `deploy/ovh/docker-compose.yml:45-48` usa `--maxmemory 256mb --maxmemory-policy allkeys-lru`, sem volume. O cache de áudio (até 2 MB por item) disputa esse espaço. Uma calibração guardada só no Redis seria descartada.
8. **`parametros_sintese` pode ir à rede.** Ele chama `consultar_metadados`, que consulta a ElevenLabs quando o registro tem mais de 1 h (`app/tts/profiles.py:13-35`, `:38-55`). A estimativa feita antes do TTS no `/proxima` não pode usá-lo. Para descobrir modelo e perfil, ela deve ler só o banco: `ConfiguracaoVoz`, `conta.modelo_voz` e `modelo_efetivo`.
9. **Ordem atual dentro de `gerar_proxima_fala`:**
   - LLM e uma reescrita (`:2705-2760`);
   - músicas do bloco (`:2762-2781`);
   - **registros** com o texto: histórico de falas, tema, assunto, `NoticiaHistorico` com `commit` e fio condutor (`:2783-2816`);
   - TTS embutido (`:2818-2898`).

   Qualquer corte feito depois do TTS deixaria os registros com um texto que não foi ao ar.
10. **Diálogo multivoz.**
    - O player toca as linhas uma depois da outra, com 280 ms entre elas (`frontend-painel/lib/continuidadeAudio.ts:28`).
    - O backend sintetiza as linhas em threads e não pode usar o `db` dentro delas (`router.py:1836-1840`, `:1849-1896`).
11. **LLM sem cache de prompt** (`app/llm/client.py:31-34`, `max_tokens=512`, sem `cache_control`). Uma reescrita reenvia o system prompt inteiro e custa mais ou menos o mesmo que a primeira chamada.
12. **O dublê da F0 reconhece a reescrita pelo texto `Reescreva com no máximo (\d+) palavras`** (`docs/melhoria-radio/f0/auditoria.md`, §5.3). O teste `tests/test_live_router.py:2990` também confere esse texto. A frase não pode mudar.
13. **Migrações.**
    - Tabela nova: `Base.metadata.create_all` na inicialização (`app/main.py:152-156`). Existe um único arquivo de migração explícita, `app/db/migrations/consumo_20260925.py`, que usa `create(checkfirst=True)` e uma tabela de versões.
    - Coluna nova: `garantir_colunas_*` com `ALTER TABLE ... ADD COLUMN` (`main.py:344-367`).
14. **CORS sem `expose_headers`** (`main.py:110-116`). Um cabeçalho novo em `/tts` não fica visível para o JavaScript do painel, a menos que seja exposto.

## 2. Testes existentes que tocam esta frente

`pytest --collect-only` encontra 1120 testes no total. Nos arquivos envolvidos:

| Arquivo | Testes |
|---|---|
| `test_live_router.py` | 135 |
| `test_tts_client.py` | 70 |
| `test_tts_router.py` | 18 |
| `test_tts_profiles.py` | 14 |
| `test_postprod_client.py` | 9 |
| `test_live_prewarm.py` | 4 |

Não existe `test_live_formato.py` nem `test_simular_hora.py`: a F0 ainda não foi implementada nesta branch.

| O que já está coberto | Onde |
|---|---|
| Reescrita única por orçamento no musical (84 palavras, limite 25): 2 prompts, `"no máximo 25 palavras"` no segundo, sem "4 a 6 frases" no primeiro | `tests/test_live_router.py:2972-2992` |
| `duracao_alvo_segundos` igual a `[6,12]` (retomada), `[4,8]` (música com pedido) e `[10,18]` (encerramento) | `:2988`, `:3012`, `:3025` |
| Áudio embutido = áudio de `/tts`, mp3 real gerado com `Sine` do pydub e duração preservada (±50 ms) | `:2893-2921` |
| `/tts` com pós-produção falsa (`processar_audio` devolve bytes que não são mp3) | `:798-817` (o conteúdo precisa continuar igual) |
| `/tts` em streaming sem perfil | `:572-587`, `:837` |
| Falha de áudio sem segunda síntese | `:595-650` (invariante que a F2 precisa manter) |
| Multivoz monta o diálogo | `:396-436` (sem TTS) |
| Música sem pedido no musical: sem LLM e sem TTS | `:2935-2958` |
| A pós-produção preserva a duração (±50 ms) | `tests/test_postprod_client.py:30-41` |
| Faixas e limites de `speed` por bloco | `tests/test_tts_client.py:104`, `:114`, `:128`, `:452`, `:466` |
| Payload do prewarm no Redis | `tests/test_live_prewarm.py:48-61` |
| Painel: `incluir_audio === false` e `/tts` com `perfil_pos_producao: "radio_fm"` | `frontend-painel/hooks/__tests__/useLiveEngine.preparo.test.ts:97-99` |

**Não coberto:**
- medição de duração em qualquer endpoint do ao vivo;
- reescrita por duração (só existe por palavras);
- formato padrão com fala longa;
- ordem entre registros e TTS;
- ritmo por voz.

Muitos testes trocam `sintetizar_audio` e `processar_audio` por funções que devolvem `b"mp3"` ou `b"audio-cru"`. **A medição precisa tolerar bytes que não são mp3** e devolver `None`, sem exceção e sem reescrita.

## 3. Itens de `docs/auditoria.md` e `docs/refatoracao.md` que tocam a F2

| Item | Situação | Efeito na F2 |
|---|---|---|
| auditoria 4: rate limit de `/proxima` e `/tts` | parcial (ver F0) | Uma segunda síntese dentro do `/proxima` não passa pelo limite de `/tts` (90/min). A F2 limita isso por construção: no máximo 2 sínteses por `/proxima` de voz única, e nenhuma nova no multivoz. Teste de invariante na §6. |
| auditoria 6: Redis sem timeout | aberto (vai para a F3) | A F2 usa o Redis para o orçamento pendente e para a deduplicação de amostras. Todo acesso fica num `try/except RedisError` que falha aberto: sem Redis, perde-se só o log e a deduplicação. Não depender do Redis para a calibração (fato 7). |
| auditoria 7: N+1 no prewarm | aberto, fora do escopo | O prewarm pode passar a fazer uma ressíntese, no máximo 1 a mais por programa e por dia. |
| refatoração §1: dividir `gerar_proxima_fala`, com a reescrita indo para `service.py` | F3 | A F2 põe a regra em funções puras de um módulo novo e mexe pouco no router: uma chamada antes do TTS, uma depois do TTS e a mudança de lugar dos registros. Assim a F3 move as chamadas sem reescrever a regra. |
| refatoração §3: duplicação | não listado lá | Ficam três medidores de duração duplicados (fato do §1). A F2 cria `duracao_mp3_s` em `app/postprod/audio_io.py`. Unificar patrocinador, biblioteca e vinheta fica **fora** da F2 (é opcional). |
| refatoração §5: troca de funções por nome nos testes | aberto | As funções novas são importadas no namespace de `app.live.router` (`from app.live.orcamento import ...`), para que os testes possam trocar `app.live.router.duracao_mp3_s`. |

## 4. Desenho da mudança

### 4.1 Regra de decisão

Notação:
- `max` é o máximo do orçamento;
- `tol = settings.fala_tolerancia_orcamento`, padrão 0,15;
- `teto = settings.fala_teto_orcamento`, padrão 0,30.

| Momento | Caminho | Condição | Ação | Chamadas extras |
|---|---|---|---|---|
| A. Antes do TTS, 1º texto | todos (voz única e multivoz) | `estimada > (1+tol)·max` **ou** a regra atual de palavras (`palavras > max_palavras`, sem mudança) | O motivo `duracao` entra na **mesma** reescrita única que já existe (`router.py:2727-2753`), com a frase `Reescreva com no máximo {N} palavras`. Não existe uma terceira chamada. | +1 LLM, só quando a duração é o único motivo |
| B. Antes do TTS, depois da reescrita (ou quando a reescrita já foi usada por outro motivo) | voz única | `estimada > (1+tol)·max` | **Corte determinístico:** `encurtar_por_frases(texto, max_palavras_efetivo, preservar=[nome do ouvinte, títulos do bloco])`. Sem resultado possível: bloco de música com faixa e sem pedido → `fala=""` (só música, regra 8); qualquer outro → mantém o texto e marca `fala_ajuste="acima_do_teto"` (nunca deixa silêncio). O encerramento só é encurtado, nunca removido. | 0 |
| B'. Idem | multivoz | idem | Retira linhas do fim pela estimativa, mantendo pelo menos 2 linhas e a linha com o pedido. Acontece antes da síntese, então nenhum áudio é desperdiçado. | 0 |
| C. Depois do TTS, dentro do `/proxima` | voz única com `incluir_audio=True` (prewarm, cliente antigo) | `medida > (1+teto)·max` | `encurtar_por_frases` e **uma** nova síntese com os mesmos `tom`, `modelo`, `perfil` e `pronuncias`. Sem o encurtamento: igual ao B. | +1 TTS (no máximo 2 sínteses por `/proxima`) |
| C'. Idem | multivoz | `medida_total > (1+teto)·max`, com `medida_total = Σ linhas + 0,28 s·(n−1)` | Retira linhas do fim usando as durações **medidas**, com `falas` e `audios_falas_base64` alinhados. | 0 |
| C''. Idem | ambos | `(1+tol)·max < medida ≤ (1+teto)·max` | Aceita e registra `fora_orcamento`. | 0 |
| D. `/tts` avulso (painel) | voz única | qualquer | Mede, devolve o cabeçalho `X-Duracao-Fala-S`, grava uma amostra de calibração e registra o excesso em relação ao orçamento guardado pelo `/proxima`. **Não muda o texto nem o áudio**, porque o texto já está no histórico do painel. | 0 |
| Formato padrão sem relógio | todos | — | **Só observa:** `aplicado=False`. Mede, estima e registra, sem reescrever e sem cortar. Isso preserva o critério da F1 de que programas sem relógio passam nos testes sem alteração. | 0 |

Por que não reescrever com LLM depois do TTS:
- custaria LLM e TTS em dobro;
- no caminho do painel, o texto já saiu (fato 1);
- obrigaria a refazer o que vem depois do texto (fato 9).

A reescrita é decidida pela estimativa **calibrada**. A medição alimenta a calibração (§4.4). Assim o erro da estimativa cai com o uso, e a faixa C'' fica rara.

**Invariantes por `/proxima`** (com teste):
- no máximo 2 chamadas de LLM;
- no máximo 2 sínteses na voz única;
- nenhuma ressíntese no multivoz;
- nenhuma nova síntese depois de `audio_status="falhou"`.

### 4.2 Orçamento: relógio, formato e observação (prepara a F6 sem fazê-la)

Módulo novo `backend/app/live/orcamento.py` (puro, sem banco):

```python
@dataclass(frozen=True)
class OrcamentoFala:
    min_s: float; alvo_s: float; max_s: float
    max_palavras: int | None          # vai ao prompt; None = calculado pelo ritmo
    fonte: Literal["relogio", "formato", "observacao"]
    aplicar: bool                     # False = só mede e registra

ORCAMENTOS_POR_FORMATO: dict[str, dict[str, tuple[float, float, int | None]]]
#   "musical_companhia": construído A PARTIR de formato.ORCAMENTOS (sem copiar números)
#   "padrao": {"*": (15, 30, 45)} só para observação ("4 a 6 frases", router.py:2186; hipótese documentada)

def orcamento_para(formato: str, tipo: str, primeira: bool, teto_relogio_s: float | None = None) -> OrcamentoFala
```

**Sem relógio (`teto_relogio_s=None`):**
- No formato musical, o resultado é `ORCAMENTOS` via `orcamento_fala`, com `fonte="formato"` e `aplicar=True`. O alvo é `(min+max)/2` (hipótese).
- No formato padrão, o resultado tem `fonte="observacao"` e `aplicar=False`.

**Com relógio (vem da F1):**
- `max = min(max_formato, teto)` e `alvo = min(alvo_formato, teto)`;
- `fonte="relogio"` e `aplicar=True`;
- `max_palavras = floor(max · wpm_voz / 60)`.

Se `teto < min_formato`, a função devolve o orçamento assim mesmo e marca que não cabe. A decisão de não gerar a fala é da F1 (entrega 4 dela), não da F2.

**Integração com a F1.** Um único ponto em `gerar_proxima_fala` obtém `teto_relogio_s` do serviço da F1 e o passa a `orcamento_para`. Se a F1 ainda não estiver na branch, fica um gancho privado `_teto_relogio_s(...) -> None`, que os testes trocam.

**Compatibilidade.**
- `formato.ORCAMENTOS`, `orcamento_fala` e `direcao_musical` ficam como estão (com teste de caracterização). O router, o dublê da F0 e `tests/test_live_router.py:2988` dependem deles.
- No formato padrão com relógio, a linha de meta ("Meta de locução: X a Y segundos, no máximo N palavras") entra no prompt pelo mesmo texto de `direcao_musical`, extraído para uma função `linha_meta_locucao(orc)`.

**Preparação para a F6, sem fazê-la.** Ela troca a fonte de `ORCAMENTOS_POR_FORMATO` pela `unidade_fala` do catálogo `app/live/formatos.py` e mantém a assinatura de `orcamento_para`. A F2 **não** cria `formatos.py`, não cria `direcao_formato` e não muda valores. A divergência entre os 6–12 s da retomada e os 10–35 s de link da pesquisa, anotada pela F0, continua sendo decisão da F6.

**Configuração** (em `app/config/settings.py`, porque os números da skill são hipóteses):

| Parâmetro | Padrão | Origem |
|---|---|---|
| `fala_tolerancia_orcamento` | 0,15 | plano |
| `fala_teto_orcamento` | 0,30 | plano |
| `fala_wpm_padrao` | 150 | pesquisa §5, faixa de 130 a 160 |
| `fala_wpm_padrao_por_modelo` | `{"eleven_v3":162,"eleven_v4":158,"eleven_v4_turbo":158,"eleven_flash_v2_5":171}` | benchmark de 08/10 |
| `fala_pausa_explicita_s` | 1,2 | — |
| `fala_pausa_entre_linhas_s` | 0,28 | espelho de `continuidadeAudio.ts:28` |
| `fala_calibracao_min_amostras` | 5 | — |
| `fala_calibracao_max_amostras` | 200 | — |

### 4.3 Estimativa e medição

Funções novas em `app/live/orcamento.py`:
- `estimar_duracao_s(texto, wpm)`: aplica `contar_palavras` sobre `normalizar_texto_fala(texto)` (números expandidos, sem pronúncias, para não ir ao banco), divide por `wpm` e multiplica por 60. Soma `fala_pausa_explicita_s` para cada `......` ou `[pause]`.
- `wpm_observado(palavras, duracao_s, pausas)`: tira as pausas da duração. Descarta amostras com menos de 8 palavras, menos de 2 s ou fora da faixa de 80 a 320 palavras/min (devolve `None`). A F0 usa esta mesma função no modo completo, para não existirem duas fórmulas.
- `encurtar_por_frases(texto, max_palavras, preservar)`:
  - extrativo, sem LLM;
  - divide nas fronteiras `. ! ? …`;
  - corta frases do fim, mas mantém as que contêm algum termo de `preservar`;
  - devolve `None` se não couber;
  - nunca corta no meio de uma frase.
- `cortar_linhas_dialogo(falas, duracoes_s, max_s, pausa_s, preservar)`.

`app/postprod/audio_io.py` ganha `duracao_mp3_s(mp3_bytes) -> float | None`:
- usa `AudioSegment.from_file(...).duration_seconds`, o mesmo método dos medidores atuais;
- qualquer exceção ou entrada vazia devolve `None`;
- custa algumas dezenas de ms por fala, contra duas passadas de ffmpeg que a pós-produção já faz.

Alternativa rejeitada: fazer `processar_audio` devolver a duração. Isso mudaria o tipo de retorno que dezenas de testes trocam por `lambda: bytes`.

**Onde medir:**
- `router.py` depois de `:2848`, na voz única embutida, sobre os bytes **finais**, já pós-produzidos;
- dentro de `_uma_linha` no multivoz, devolvendo `(base64, duracao)`;
- `/tts` depois de `:3185`.

A gravação no banco acontece **depois** que as threads terminam, por causa do fato 10.

**Ordem nova em `gerar_proxima_fala`.** É uma mudança de lugar pequena e protegida por caracterização:

1. LLM e reescrita (momento A).
2. `_extrair_quantidade_musicas`, que hoje está em `:2764`.
3. Momento B.
4. Músicas do bloco (`:2762-2781`), com o texto final.
5. TTS e momento C. O encurtamento preserva os títulos de `musicas_bloco` e do pedido, e por isso o bloco montado continua válido.
6. **Os registros (`:2783-2816`) passam para depois do TTS**, para que `_registrar_fala_gerada`, `NoticiaHistorico` e o tema usem o texto que vai ao ar.
7. Resposta.

### 4.4 Ritmo observado por voz: onde guardar

Decisão: **Postgres**, numa tabela nova `ritmos_voz`, definida em `app/models/perfil_voz.py`, ao lado de `MetadadosVoz` e `ConfiguracaoVoz`, como o plano pede. O Redis fica só para deduplicação.

Motivos:
- o Redis de produção descarta chaves por LRU e não tem volume (fato 7);
- uma leitura indexada por `/proxima` é desprezível perto das dezenas de consultas que a rota já faz.

```
RitmoVoz: id, voz_id, modelo, perfil ("atual"|"natural"), categoria (base de _categoria_tipo_bloco),
          amostras INT, palavras FLOAT (soma), segundos FLOAT (soma, sem pausas), atualizado_em
          UniqueConstraint(voz_id, modelo, perfil, categoria)
```

- **Global por voz, não por conta.** O ritmo é uma propriedade de voz, modelo e configuração, e vozes clonadas já têm id próprio. A tabela guarda **só agregados numéricos**, nenhum texto.
- **Gravação, `registrar_amostra(db, ...)`.**
  - Faz `UPDATE ... SET amostras=amostras+1, palavras=palavras+:p, segundos=segundos+:s`, que funciona igual no SQLite e no Postgres.
  - Se a linha não existir, insere com `begin_nested` e trata `IntegrityError`, no mesmo padrão de `profiles.py:19-26`.
  - Quando as amostras passam de `fala_calibracao_max_amostras`, as três somas caem pela metade. Isso faz as amostras antigas pesarem menos.
  - Falhas no banco são registradas em log e engolidas: o áudio sai de qualquer jeito.
- **Deduplicação.** `SET NX ritmo_voz:visto:{sha1(audio)} EX 86400` evita contar duas vezes uma amostra vinda do cache de TTS (fato 6). Sem Redis, a amostra é gravada mesmo assim.
- **Leitura, `wpm_para(db, voz_id, modelo, perfil, categoria)`.** Segue uma cadeia de alternativas:
  - a categoria com pelo menos `min_amostras`;
  - senão, o agregado da voz e do modelo com pelo menos `min_amostras`;
  - senão, `fala_wpm_padrao_por_modelo[modelo]`;
  - senão, `fala_wpm_padrao`.
- **Modelo e perfil efetivos** saem de `ConfiguracaoVoz`, `conta.modelo_voz` e `modelo_efetivo("tts", ...)`, **sem** `consultar_metadados` (fato 8). Criar um auxiliar público em `app/tts/profiles.py`. Também expor `categoria_tipo_bloco` como pública em `app/tts/client.py`, que hoje é privada (`:225`).
- **Migração aditiva:** `app/db/migrations/ritmo_voz_20261107.py`, no padrão de `consumo_20260925.py`, com `aplicar(engine)` e `RitmoVoz.__table__.create(conn, checkfirst=True)`, chamada em `criar_tabelas` (`main.py:154`) antes de `create_all`. Registrar o modelo em `app/models/__init__.py`. Não altera nenhuma coluna existente.

**Orçamento pendente para o `/tts`.**
- O `/proxima` grava `fala_orcamento:{programa_id}:{sha1(texto_final)}` com `{tipo, categoria, min_s, alvo_s, max_s, fonte, aplicar, estimada_s, wpm_usado, request_id}` e TTL de 15 min.
- O `/tts` com `programa_id` lê esse registro para calcular o excesso.
- Se o registro tiver sido descartado, só se perde o log de excesso. A amostra é gravada mesmo assim, com `categoria` vinda de `dados.tipo`.

### 4.5 Contratos de API (todos aditivos e opcionais)

`LiveProgramResponse` (`router.py:158-215`):
- `duracao_fala_s: float | None = None`: medida no áudio final, quando foi sintetizado no `/proxima`. No multivoz, é a soma das linhas mais as pausas. No caminho do painel (`pendente`), vem `None`.
- `duracao_fala_estimada_s: float | None = None`: vem em toda fala com texto.
- `orcamento_fala_s: OrcamentoFalaResponse | None = None`, com `{min_s, alvo_s, max_s, fonte, aplicado}`.
- `fala_ajuste: Literal["nenhum", "reescrita", "encurtada", "cortada", "acima_do_teto"] | None = None`.
- `duracao_alvo_segundos` continua igual, só no musical, porque os testes conferem esse campo.

O nome `duracao_fala_s` foi escolhido para **não** colidir com `duracao_segundos`. O painel espalha a resposta no segmento (`useLiveEngine.ts:1333`) e depois sobrescreve `duracao_segundos` com a duração real do bloco (`:1262-1268`).

O prewarm serializa a resposta inteira (`prewarm.py:76`), então os campos chegam pelo `/preparo` sem mudança.

`/tts`:
- devolve o cabeçalho `X-Duracao-Fala-S` só no caminho com pós-produção, e só se a medição funcionar;
- o conteúdo não muda (`test_live_router.py:798-817`);
- em `main.py:110-116`, acrescentar `expose_headers=["X-Duracao-Fala-S"]`, para que o painel ou a F11 possam ler o valor.

**Painel:** só tipos. Os campos opcionais entram em `frontend-painel/lib/liveTypes.ts:55-110`. A F2 não muda a interface. Mostrar o ritmo medido no `VozConfigModal` é opcional e pode ficar para a F9 ou a F11.

**Logs** (servem de registro até o as-run da F11):
- `live_fala_duracao request_id programa_id tipo origem=proxima|tts palavras wpm_usado estimada_s medida_s max_s excesso_pct ajuste fonte`;
- `live_fala_revisada motivo=duracao`.

### 4.6 Custo: dimensionamento e registro

Os números estão em chamadas e caracteres, não em dinheiro: quem aprova consulta a tabela vigente, como na F0. O dublê da F0 estima cerca de 225 s de fala por hora no relógio A, ou seja, cerca de 10 a 14 falas por hora no musical. No padrão (popular, variedades), são cerca de 15 a 25 falas por hora.

| Fonte de custo | Hoje | Com a F2 | Teto por fala |
|---|---|---|---|
| LLM | 1 + reescrita única (repetição, palavras, notícia) | o motivo `duracao` entra na **mesma** reescrita | 2 (igual a hoje) |
| Reescrita só por duração | — | Musical sem relógio: ≈ 0, porque o limite de palavras já domina (25 palavras ≈ 10 s a 150 palavras/min, abaixo dos 12 s de máximo). Formato padrão sem relógio: 0 (observação). **Com relógio (F1): a medir.** | +1 LLM |
| TTS no painel (`/tts`) | 1 | 1, mais uma decodificação local e um `UPDATE` | 1 |
| TTS no prewarm ou em cliente antigo | 1 | +1 só se `medida > 130%` | 2 |
| TTS no multivoz | N linhas | N (o corte usa os áudios já pagos) | N |
| Caracteres de TTS | — | a ressíntese de C cobra só o texto **encurtado** | menos que o dobro dos caracteres da fala |

Fórmula por hora de programa:

`ΔLLM/h = N_falas/h × r_duracao`

`ΔTTS/h = N_prewarm × r_teto` (no máximo 1 por programa e por dia)

Meta operacional: `r_duracao ≤ 10%`. No padrão com relógio, isso dá **no máximo cerca de 2,5 chamadas de LLM extras por hora de programa**. Como cada reescrita reenvia o prompt inteiro (fato 11), uma reescrita custa cerca de uma fala.

**Registro:**
- os logs da §4.5;
- os contadores no `resumo.json` da simulação: `revisoes_por_duracao`, `encurtadas`, `cortadas`, `acima_do_teto` e `ressinteses_tts`;
- `chamadas_llm` e `revisada` por evento no `as_run.json`.

**Alternativa mais barata, que fica para depois da F3 e da F7:** uma chamada curta de "encurtar", com só a fala e as restrições. Ela corta muito o número de tokens de entrada. Hoje traz dois riscos:
- o dublê da F0 não a reconhece (o bloqueio de rede contaria a chamada como tentativa de rede);
- ela pode perder regras editoriais (promessa, música confirmada).

Reavaliar com `r_duracao` medido no `--modo llm`.

## 5. Arquivos

**Novos:**

| Arquivo | Conteúdo |
|---|---|
| `backend/app/live/orcamento.py` | `OrcamentoFala`, `ORCAMENTOS_POR_FORMATO`, `orcamento_para`, `estimar_duracao_s`, `wpm_observado`, `avaliar_duracao`, `encurtar_por_frases`, `cortar_linhas_dialogo`, `linha_meta_locucao` |
| `backend/app/live/ritmo_voz.py` | `registrar_amostra`, `wpm_para`, deduplicação (é o único módulo de calibração que acessa banco e Redis) |
| `backend/app/db/migrations/ritmo_voz_20261107.py` | criação idempotente da tabela |
| `backend/tests/test_live_orcamento.py` | testes das funções de orçamento |
| `backend/tests/test_live_ritmo_voz.py` | testes da calibração |
| `backend/tests/test_live_router_duracao.py` | testes de integração |
| `backend/tests/test_postprod_audio_io.py` | testes de `duracao_mp3_s` |

**Alterados:**

| Arquivo | Mudança |
|---|---|
| `app/live/router.py` | modelo de resposta; momentos A, B e C; mudança de lugar dos registros; medição em `_sintetizar_falas_multivoz` e em `/tts` |
| `app/postprod/audio_io.py` | `duracao_mp3_s` |
| `app/models/perfil_voz.py` e `app/models/__init__.py` | `RitmoVoz` |
| `app/tts/client.py` e `app/tts/profiles.py` | auxiliares públicos de categoria e de modelo efetivo, sem mudar o comportamento |
| `app/config/settings.py` | parâmetros da §4.2 |
| `app/main.py` | migração e `expose_headers` |
| `app/live/formato.py` | só se `linha_meta_locucao` for extraída; o texto de `direcao_musical` continua idêntico |
| `frontend-painel/lib/liveTypes.ts` | campos opcionais |
| `backend/scripts/simulacao/*` (da F0, depois do merge dela) | ler `orcamento_fala_s` e `fala_ajuste`; dublê de TTS (§6, simulação) |

## 6. Testes, nesta ordem

**Caracterização** (antes de mexer no router e de mudar os registros de lugar):
1. `test_orcamento_fala_valores_atuais`: todos os tipos de `ORCAMENTOS`, abertura primeira e não primeira, e tipo desconhecido = `(10,20,45)`.
2. `test_direcao_musical_texto_inalterado`: retrato do texto para cada tipo. A meta e o "no máximo N palavras" são lidos pelo dublê da F0.
3. `test_reescrita_unica_combina_repeticao_e_orcamento`: fala parecida e acima do orçamento dão exatamente 2 chamadas de LLM, e os dois motivos aparecem no segundo prompt.
4. `test_padrao_sem_relogio_nao_revisa_fala_longa`: 120 palavras no formato padrão dão 1 chamada de LLM, e a fala volta igual.
5. `test_registros_usam_fala_da_resposta`: o histórico de falas no Redis, o `NoticiaHistorico.fala` e o texto do tema são iguais a `resposta.fala`. Isso protege a mudança de lugar dos registros.
6. Manter verdes, sem editar: `test_live_router.py:2972`, `:2893`, `:798`, `:595`, `:2935`, `test_live_prewarm.py:48`.

**Unitários:**

7. `test_duracao_mp3_s`: `Sine` de 1000 ms dá ≈ 1,0 s (±0,05). Funciona em estéreo. `b"mp3"`, `b""` e `None` dão `None`.
8. `test_estimar_duracao`: palavras ÷ ritmo; ignora `[tags]`; cada `......` ou `[pause]` soma `fala_pausa_explicita_s`; "2026" é expandido.
9. `test_wpm_observado_filtra_amostras_ruins`: menos de 8 palavras, menos de 2 s e fora da faixa de 80 a 320 dão `None`. As pausas são descontadas.
10. `test_orcamento_para`:
    - musical sem relógio = `ORCAMENTOS` (`formato`, `aplicar`);
    - padrão sem relógio = `observacao`, `aplicar=False`;
    - relógio com teto abaixo do máximo: `max=teto`, `alvo ≤ teto`, `fonte=relogio`, `max_palavras` pelo ritmo;
    - teto abaixo do mínimo: marca que não cabe.
11. `test_avaliar_duracao_limites`: os limites exatos de 1,15 e 1,30, lidos de `settings` (com `monkeypatch`).
12. `test_encurtar_por_frases`:
    - preserva a ordem;
    - mantém as frases com o nome do ouvinte e com o título;
    - nunca corta no meio de uma frase;
    - devolve `None` quando não cabe;
    - trata `!`, `?` e `…`;
    - num texto de notícia, não remove a frase que tem a atribuição.
13. `test_cortar_linhas_dialogo`: mantém pelo menos 2 linhas e a linha do pedido, e alinha os índices.
14. `test_ritmo_voz`:
    - cria a linha e depois incrementa;
    - corta as somas pela metade no limite;
    - percorre a cadeia de alternativas (categoria → voz/modelo → modelo → global);
    - deduplica pelo hash do áudio (fakeredis);
    - funciona sem Redis;
    - uma falha no banco não propaga.
15. `test_migracao_ritmo_voz_idempotente`: `aplicar` duas vezes num engine SQLite.

**Integração** (pelo HTTP, trocando funções de `app.live.router.*`):

16. Musical com `incluir_audio=False`: `orcamento_fala_s == {6, 9, 12, "formato", true}`, `duracao_fala_estimada_s` preenchida, `duracao_fala_s` nulo e `duracao_alvo_segundos == [6,12]`.
17. Estimativa acima de 115% com palavras dentro do limite (ritmo calibrado baixo, semeado em `RitmoVoz`) dá uma reescrita com "Reescreva com no máximo"; o resultado é `fala_ajuste="reescrita"`.
18. Reescrita já usada por repetição, com o texto ainda acima: não há terceira chamada de LLM e o resultado é `fala_ajuste ∈ {encurtada, cortada}`. Num bloco de música sem pedido, `fala=""` e a faixa continua.
19. `incluir_audio=True` com `sintetizar_audio` devolvendo um mp3 de 20 s para uma retomada (máximo de 12): o texto é encurtado e há uma segunda síntese. **A segunda síntese recebe `tom`, `modelo`, `perfil` e `pronuncias` iguais aos da primeira** (não acelera a voz). Os registros têm o texto final. São no máximo 2 sínteses.
20. `sintetizar_audio` devolvendo `b"mp3"`: `duracao_fala_s` nulo, sem reescrita, sem exceção e sem amostra.
21. Multivoz com linhas que medem mais de 130% do máximo: as linhas finais são retiradas, `falas` e `audios_falas_base64` ficam alinhados, e não há nenhuma chamada extra de LLM ou TTS.
22. Relógio, pelo gancho `_teto_relogio_s` trocado no teste: o teto menor que o máximo do formato aparece no prompt como "no máximo N palavras" e reduz o orçamento.
23. `/tts` com perfil e `programa_id`, usando mp3 real:
    - o cabeçalho `X-Duracao-Fala-S` vem preenchido;
    - uma linha de `RitmoVoz` é criada;
    - o mesmo áudio duas vezes gera uma amostra só;
    - o log `live_fala_duracao` traz o excesso do orçamento guardado pelo `/proxima` (caplog);
    - sem perfil (streaming), não há cabeçalho nem amostra;
    - com bytes falsos, a resposta é 200, sem cabeçalho e com o conteúdo igual.
24. O prewarm grava os campos novos no payload do Redis.
25. Painel (vitest, opcional): uma resposta com `duracao_fala_s` não muda o fluxo de `useLiveEngine.preparo.test.ts`.

**Simulação** (depende do simulador da F0 já mesclado):

26. O simulador lê `orcamento_fala_s` e `fala_ajuste` do backend quando eles existem (`fonte: "backend"`).
27. `--modo fake` nos três perfis:
    - `fora_orcamento_pct ≤ 5%` e `estouro_max_pct ≤ 30%`, contados só nas falas com `aplicado=true`;
    - as falas em observação são relatadas à parte;
    - `chamadas_llm ≤ 2 × falas`.
28. Injeção nova `excesso_persistente`, em que o dublê ignora o limite da reescrita: passa pelo encurtamento e pelo corte, e nenhuma fala fica acima de 130%.
29. Dublê de TTS (`--tts duble --wpm-real 190`):
    - gera um mp3 silencioso com duração = palavras × 60 ÷ 190, mais as pausas, via pydub e ffmpeg, sem rede;
    - chama `/tts` como o painel;
    - `test_calibracao_converge`: depois de N falas, |estimada − medida| ÷ medida ≤ 10% por voz.
30. `--modo llm` só com aprovação explícita do usuário: mede `r_duracao` real com relógio e grava esse valor no `resumo.json`, para fechar o dimensionamento da §4.6.

## 7. Riscos e o que não fazer

- **Não acelerar a voz.**
  - Não trocar `tom` para `energico`, porque ele soma +0,04 de `speed`.
  - Não trocar o modelo (o Flash é mais rápido).
  - Não usar o perfil `natural` nem `atempo` na pós-produção para caber no orçamento.
  - O teste 19 garante isso.
- **Não criar uma terceira chamada de LLM** nem uma reescrita depois do TTS. A reescrita é uma só e acontece antes do TTS.
- **Não aplicar orçamento ao formato padrão sem relógio.** Isso mudaria o produto e quebraria o critério da F1. O formato padrão só observa até a F1 ou a F6 definirem a unidade de fala.
- **Não mudar o painel para `incluir_audio=True`.** Isso juntaria LLM, TTS e pós-produção no mesmo request, com timeout de 75 s, e desmontaria a fila que entrega o texto antes do áudio.
- **Não mudar a frase "Reescreva com no máximo N palavras"** (dublê da F0 e `test_live_router.py:2990`) nem os valores de `ORCAMENTOS` (decisão da F6).
- **Não fazer a F6:** nada de `formatos.py`, `direcao_formato` ou seleção de formato no painel.
- **Não guardar a calibração só no Redis** (descarte por LRU em produção). Não gravar texto em `ritmos_voz`. Não contar amostras do cache de TTS nem falas curtas.
- **Não usar `parametros_sintese` antes do TTS no `/proxima`** (rede, fato 8). Não acessar o `db` dentro das threads do multivoz.
- **Não deixar silêncio.**
  - Não cortar a fala de um bloco que não tem música; nesse caso, o máximo é encurtar.
  - Nunca remover o encerramento.
  - Nunca remover a frase com o nome do ouvinte nem o título confirmado (isso protege a F4).
- **Não falhar o áudio por causa da calibração.** Medição, Redis e banco falham abertos, com log.
- **Risco: estimativa de duração duplicada com a F1.** O backtiming da F1 precisa estimar a duração das falas que estão na fila. Ele deve usar `estimar_duracao_s` e `wpm_para`. Se a F1 entrar antes com uma fórmula própria, a F2 unifica as duas e não convivem duas fórmulas.
- **Risco: no caminho do painel, o excesso medido não é corrigido**, só registrado. O critério "nenhuma fala acima de 130%" depende de a estimativa calibrada ficar dentro de cerca de 13% do áudio real. O teste 29 mede isso. No modo completo, conferir também com áudio real.
- **Risco: a mudança de lugar dos registros** (passo 6 da §4.3) mexe numa função de mais de 1000 linhas. Os testes 5 e 19 a protegem, e a F3 vai mover o mesmo trecho. Combinar a ordem dos PRs.
- **Risco: o SQLite não é o Postgres.** O incremento por `UPDATE` funciona nos dois, mas a corrida entre `/tts` simultâneos só é exercitada no Postgres. Uma amostra perdida numa corrida é aceitável.

## 8. Dependências

- **F0 (simulador):** é pré-requisito do critério de aceite (§6, simulação). Não é pré-requisito para os testes unitários e de integração.
- **F1:** não bloqueia. O orçamento do relógio entra por parâmetro, e sem ele a F2 usa `ORCAMENTOS` (musical) ou só observa (padrão). Pela ordem do plano (F0 → F1 → F2), o implementador deve plugar o serviço da F1 no gancho `_teto_relogio_s` se ele já estiver na branch.

PRONTA PARA IMPLEMENTAR
