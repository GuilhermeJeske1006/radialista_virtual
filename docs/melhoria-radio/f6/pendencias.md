# Pendências registradas na F6

Achados e ideias fora do escopo da F6 (catálogo de formatos e perfis editoriais), ou fora da leva em andamento.
A leva 1 cobre os commits 0 a 4 do §7 da auditoria (linha de base, caracterização, catálogo sem mudar comportamento,
item 9 e contrato/gerador); a leva 2, os commits 5 a 8 (seção do formato no prompt, popular e variedades, simulador e
coerência, benchmark); a leva 3, o painel (commit 9) e o fechamento (commit 10).

## Decisões (auditoria §11), todas adotadas pelo padrão, a confirmar
- **D1** formato em `perfil_programacao` (coluna existente), sem migração. **D2** alias resolvido na leitura, nada
  reescrito no banco; a API aceita e ecoa o valor gravado.
- **D3** `padrao` continua "Livre (sem formato)", com o comportamento de antes; padrão da API.
- **D4** catálogo em Python (dataclasses congeladas) em `app/live/formatos.py`; `formato.py` como compatibilidade.
- **D5** o musical herda `ORCAMENTOS` sem mudança (retomada 6–12 s × link 10–35 s da pesquisa continua decisão do
  usuário, porque muda a linha de base de quatro frentes).
- **D6** popular no preset A, **D7** relógio do formato só como sugestão (`relogio_padrao`, nunca aplicado), **D9**
  orçamento aplicado sem relógio nos formatos novos: entraram na leva 2 (commit 6).
- **D8** no relógio, com `aplica_orcamento`, vale a unidade do formato para o papel do bloco, limitada depois pela
  etapa e pelo espaço; no musical é igual ao "menor dos dois" de antes (retrato C3 idêntico).
- **D10** `direcao_formato("musical_adulto")` byte a byte igual a `direcao_musical`; seção `_formato(ctx)` nos três
  formatos com promessa e nunca no `padrao` (leva 2, commit 5).
- **D11** `ORCAMENTOS_POR_FORMATO` e `FORMATOS_APLICADOS` derivados do catálogo, mesmos nomes; `orcamento_para`
  resolve o alias e aceita `quadro=` (e também um `Formato`).
- **D12** flags do `Comportamento` em todos os usos; `formato_musical` continua campo derivado em `EntradaEmissao` e
  `ContextoEmissao` (construir só com o booleano ainda funciona e escolhe musical ou padrão).
- **D13** os sete formatos futuros no catálogo com `implementado=False`: 422 na API, fora do gerador, listados em
  `GET /config/formatos`.
- **D14** `perfil_programacao: str` validado na requisição e tolerante na resposta; rota `GET /config/formatos`.
- **D15** gerador lista os implementados com o uso de cada um, aceita o alias, `tipo_radio` como dica
  (`mpb_variedades` e `regional_flashback` → `musical_adulto`; desde a leva 2, `sertaneja` e `popular_mix` →
  `popular_sertanejo`). O exemplo sertanejo passou a `popular_sertanejo` na leva 2.
- **D16** identidade: no ao vivo, `_formato(ctx)` com programa, promessa e público (leva 2); o painel vem na leva 3;
  `montar_system_prompt` intacto.
- **D17** `abertura_apos_intervalo` é `False` em `padrao` e no musical e `True` no popular e no variedades (leva 2).
- **D18** TTL de 30 dias renovado a cada gravação, teto de 5000 entradas, `hlen` no `PADROES_SESSAO`.
- **D19** a **D23**: D19, D20 e D21 entraram na leva 2 (commit 7); D23 vale desde a leva 1 (só o musical ignora
  `ia_pode_adicionar_blocos`, pela flag; os formatos novos respeitam a flag do programa); D22 é do painel (leva 3).

## Desvios e precisões do desenho (leva 1)
- **Validador herdado (risco 2):** no pydantic 2, redeclarar `perfil_programacao: str` em `ProgramaResponse` **não**
  desliga o `field_validator` de `ProgramaRequest` (o decorador é herdado pelo nome do campo). A resposta
  sobrescreve o validador com o mesmo nome (`_formato_do_catalogo`, devolve o valor). O I10 cobre.
- **Campos a mais em `Formato`:** `direcao_cabecalho` e `direcao_regras` guardam o texto da direção no prompt (o
  musical precisa das frases de condução longas para ficar byte a byte igual; `conducao` fica com a frase curta da
  pesquisa, para o painel). `faixa_fala_pct` aceita `None` (padrão e futuros não têm faixa).
- **`RegraBloco.bloco_musical` saiu do relógio:** o bloco de cada tipo de evento no musical agora vem de
  `Formato.blocos_relogio` (link, curadoria, conversa, quadro, entrevista e resumo → `retomada`); um teste compara com
  a tabela de antes.
- **`popular_sertanejo` e `variedades_leves` não entraram no catálogo nesta leva** (nem como não implementados):
  entram completos na leva 2, com a tabela do §6.4. Até lá a API os recusa (422), como antes.
- **Resolvedor tolera caixa e espaços** (`" Musical_Companhia "` → musical), a API não (valor exato). Antes, qualquer
  valor diferente de `musical_companhia` era padrão; só valores gravados fora da API são afetados.
- **Papel `quadro` pelo nome:** `papel_do_bloco` aplica `_tipo_fala`, então um bloco chamado "Quadro da Receita" tem
  papel `quadro` mesmo sem `quadro=True` quando o formato declara a unidade de quadro. Nenhum formato implementado
  declara `quadro` ainda; rever na leva 2 (variedades). **Resolvido na leva 2** (commit 5): ver abaixo.

## Riscos até as próximas levas
- **Painel comparava a string crua** (`EditarProgramaForm.tsx`, `ProximosBlocosPanel.tsx`, `useLiveEngine.ts`):
  **resolvido na leva 3** (`3ba3ed0`–`bbe3d9f`, `lib/formatoPrograma.ts`). O bloqueio de publicação caiu.
- **Rollback:** um backend anterior à F6 falha a leitura de um programa com `musical_adulto`, `popular_sertanejo` ou
  `variedades_leves` (o `Literal` antigo). SQL de volta: `UPDATE programas SET perfil_programacao='musical_companhia'
  WHERE perfil_programacao='musical_adulto'` e `UPDATE programas SET perfil_programacao='padrao' WHERE
  perfil_programacao IN ('popular_sertanejo','variedades_leves')`. Registrar no relatório da frente.
- **Log do resolvedor:** um valor desconhecido ou futuro gravado fora da API gera `formato_desconhecido` /
  `formato_nao_implementado` a cada resolução (várias por `/proxima`). Se aparecer em produção, limitar a um aviso
  por programa (fora do escopo desta leva).

## Fora da F6 (não mexido de propósito)
- `densidade_assunto` continua sem leitor; `Programa.perfil` e `Account.tipo_radio` mantêm o significado.
- O dublê da simulação (`dubles.py`, `emissao.py`) continua com a referência de orçamento da fixture para o musical
  via `orcamento_fala`; a troca pela referência do catálogo é do commit 7 (simulador). **Feita na leva 2**, só com
  `--formato fixture|<id>` (ver abaixo).
- A divergência de `ORCAMENTOS` com a pesquisa (D5) e o relógio personalizado completo (F1) continuam pendentes.

## Leva 2 (commits 5 a 8)

### Decisões que entraram (todas pelo PADRÃO da auditoria §11)
- **D10:** `_formato(ctx)` em `montar_prompt`, logo antes da direção do formato (`_duracao`), só fora do `padrao`:
  "Programa X, formato Y. Promessa: …" (com " Público: …" quando preenchido), "A promessa do formato prevalece sobre o
  perfil do horário.", a participação, os temas que exigem revisão e, nos papéis `retomada`, `identificacao`,
  `retorno` (patrocinador antes, ou etapa `retorno` do relógio) e `quadro` (quadro fixo), "Reoriente quem acabou de
  chegar: nome do programa e da rádio em uma frase.". O texto mora no catálogo (`linhas_do_formato`, `SECAO_*`,
  `PAPEIS_REORIENTACAO`).
- **D6, D7, D9, D17:** `popular_sertanejo` (relógio sugerido A) e `variedades_leves` (C) com a tabela do §6.4, orçamento
  aplicado sem relógio, abertura aceita depois do patrocinador e `blocos_relogio` padrão (no variedades, o quadro do
  relógio C vira o quadro fixo, `@quadro`). O relógio do formato nunca é aplicado sozinho.
- **D15:** o gerador lista os quatro formatos com o uso de cada um (`padrao` deixa de citar variedades); `sertaneja` e
  `popular_mix` sugerem `popular_sertanejo`; o exemplo sertanejo usa `popular_sertanejo`; jornalismo e noturno seguem
  `padrao`.
- **D19:** `simular(..., formato=None)` e `--formato {programa,fixture,<id>}`, padrão `programa`; as fixtures de linha
  de base não mudaram; com `programa`, as 12 rodadas são as da F5 byte a byte.
- **D20:** no modo fake, métricas binárias do §9 e `coerencia_automatica`; nenhuma nota sintética.
- **D21:** no `/proxima`, só o log `live_formato_aviso request_id=… programa_id=… formato=… tipo=<categoria>
  avisos=[códigos]`, nunca trecho de fala; nada é reescrito nem removido por coerência.

### Desvios e precisões do desenho (leva 2)
- **Log `live_formato_aviso` no commit 7, não no 5:** os avisos saem de `avisos_da_fala`, que nasceu com a coerência
  (§6.14). O commit 5 só acrescenta texto ao prompt.
- **Papel `quadro` (pendência da leva 1):** só com quadro fixo (`eh_quadro_fixo(programa, tipo)`: pool com conteúdo, a
  mesma regra do relógio). Um bloco chamado "Quadro…" que não é quadro fixo tem papel `*` em todo formato. O quadro
  fixo passa a chegar ao orçamento (`contexto.py`), à direção (`direcao_formato(..., quadro=)`) e à seção. No musical
  e no `padrao` não muda nada (nenhum declara a unidade `quadro`).
- **Meta sem teto de palavras:** os formatos novos não têm `max_palavras` (o teto vem do ritmo da voz, D5). Sem
  orçamento calculado, `direcao_formato` escreve "Meta de locução: X a Y segundos." (`META_LOCUCAO_SEM_PALAVRAS`); no
  `/proxima` o orçamento sempre vem e a frase tem as palavras, na forma que o dublê lê.
- **Limites de coerência no catálogo:** `Formato.limites` (`LimitesCoerencia`) com a sequência musical mínima (540 s),
  as interrupções por hora (10) e as categorias fora do formato (comentário, notícia, escalada, serviço, plantão,
  repórter), só no musical; `ConfigCoerencia` com a tolerância da unidade (0,15, igual a
  `settings.fala_tolerancia_orcamento`, conferido por teste), 5% de falas fora da unidade, fator 1,5 da reorientação,
  100% de instrução, os padrões de convite e as palavras de cada tema que exige revisão.
- **Reorientação com memória:** o aviso por fala só sai com `desde_reorientacao_s` (passou de 1,5 × `reorientacao_s` e a
  fala também não diz o nome do programa nem da rádio). No `/proxima` não há memória (F8), então o log nunca traz
  `reorientacao`; na simulação a memória vem da sequência das falas, e o maior intervalo da hora é o critério.
- **Referência de orçamento do as-run:** a do catálogo só com `--formato fixture|<id>`
  (`FixturePrograma.orcamento_do_catalogo`, campo opcional); com `programa` continua a da fixture (no musical,
  `unidade_fala` de 10 a 35 s), senão o as-run do musical deixaria de ser o da F5. O fallback do dublê sem meta no
  prompt passou a ler a unidade do catálogo (no musical, os mesmos números de `orcamento_fala`).
- **Popular no link de A:** a etapa de 35 s limita a unidade de comentário (60 s): `orcamento_s=(20, 35)` com
  `acao=fala_reduzida` (só o rótulo; nada depende dele).
- **Benchmark:** as chaves da F6 ficam só nos casos da F6 (os 35 anteriores não foram editados);
  `test_casos_de_avaliacao_cobrem_as_regras` aceita as duas formas e os quatro testes de benchmark das frentes
  anteriores passam a contar 96 falas. Casos sem `contexto.formato_coerencia` só são avaliados nos avisos do texto
  (convite, tema, bloco): são trechos de uma ou duas frases, e medidos pela palavra 59 das 70 falas ficariam abaixo do
  mínimo da unidade do papel.
- **I7 (painel antigo, hard time ≤ 5 s):** medido na simulação (S2, variante `sem_inicio_previsto`: 0,0 a 0,02 s); o
  teste de rota confere só que o `/proxima` sem `inicio_previsto` responde e decide pelo relógio do formato.

### Limites do §9 medidos na primeira rodada (fake, `--formato fixture`, semente 7, `PYTHONHASHSEED=0`)
Nada foi afrouxado: `tests/test_simulacao_f6.py::MEDIDO_FORA_DO_LIMITE` guarda o valor medido de cada item que não
fechou e falha se ele mudar.

| Perfil / variante | Item fora | Medido | Limite | Hipótese |
|---|---|---|---|---|
| musical / relógio e painel antigo | `falas_fora_da_unidade` | 1 de 6 (16,7%): abertura de 16,97 s | ≤ 5% (abertura de 20 a 30 s) | Dublê (fato 7): decide "primeira" por `total_falas`, que conta a vinheta de abertura, e usa o banco curto da retomada. Era igual na F5. |
| musical / sem relógio | `falas_fora_da_unidade` | 1 de 8 (12,5%): retomada de 4,14 s | ≤ 5% (6 a 12 s) | Dublê: o banco da retomada saiu com dez palavras para uma meta de nove segundos. |
| popular / relógio e painel antigo | `fora_orcamento_pct` (herdado) | 10% (1 de 10) | 0% | Identificação de reserva antes do intervalo (unidade de 3 a 10 s, espaço de 7 s): 18 palavras pelo ritmo estimado (162/min) duraram 7,45 s na voz de 145/min (+6%, dentro da tolerância de 15%, sem reescrita); o ritmo da identificação ainda não foi calibrado. O musical tem teto de 14 palavras e não sofre isso. Hard time em 2,09 s. |
| popular / voz 120 | `reorientacao` | 3052 s | ≤ 1800 s | Dublê: a chamada da volta do intervalo não diz o nome (ignora a linha de reorientação que o backend pôs no prompt). |
| variedades / relógio, voz 120 e painel antigo | `convites_fora_da_politica` e `reorientacao` | 2 a 3 convites; 3466 a 3472 s | 0; ≤ 1350 s | Dublê: o banco do quadro tem "Quem testar pode contar pelo WhatsApp da rádio como foi." e diz o nome do quadro, não o do programa; nenhum bloco do relógio C usa os modelos do banco que dizem o nome. |
| variedades / sem relógio | `convites_fora_da_politica` | 3 | 0 | O mesmo banco do quadro. Reorientação dentro (1088 s). |

- **Fecha nas 12 rodadas:** direção do formato em 100% dos blocos de fala (nenhuma de outro formato), fala dentro da
  faixa do formato (musical 1,9 a 2,2%; popular 8,0 a 17,9%; variedades 24,5 a 30,8%), nenhum bloco fora do formato,
  nenhum tema de revisão no ar e, no musical, a sequência musical (552 a 1194 s) e as interrupções (6 a 8 por hora).
  Herdados: anúncio sem confirmação, promessa vencida, pedido indevido, ouvinte inexistente, dado sem fonte e dado
  vencido em 0; no máximo 2 LLM e 1 síntese por fala.
- **`coerencia_automatica`:** verdadeira em 4 de 12 (musical voz 120; popular relógio, sem relógio e painel antigo). O
  aceite do §9 ("verdadeira nos três perfis com e sem relógio") não fecha no fake pelos motivos acima, quase todos do
  banco do dublê; o S7 (`--modo llm`, juiz ≥ 4/5) depende de aprovação de custo.
- **Contra a linha de base (§3):** popular sem relógio passou de 3600 s para 1197 s sem reorientação (D17: a abertura de
  cada volta sobrevive ao patrocinador e o dublê usa a reabertura com o nome); variedades sem relógio de 1159 s para
  1088 s; variedades com C ficou igual (3459 → 3467 s), pelo dublê.

### Ideias fora do escopo (leva 2)
- **Dublê obediente ao formato** (como `duble_usa_dados` da F5, ligado por campo da fixture): reagir à linha de
  reorientação e à política de convite, para o fake medir a decisão do backend e não o banco. Ligado por padrão,
  mudaria o as-run das linhas de base.
- **"Primeira" do dublê:** decidir pela meta do prompt ou pelo bloco, não por `total_falas` (muda as linhas de base da
  F0 à F5).
- **Teto de palavras na identificação** dos formatos novos (como o musical), ou o critério herdado aceitar a tolerância
  do orçamento antes da calibração.
- **Critério de unidade em contagem** (no máximo uma fala fora por hora) nos formatos com poucas falas: com 6 a 8 falas,
  uma fala fora já passa de 5%.
- **Reorientação com memória no `/proxima`** (F8) e um aviso por programa e hora, se o log ficar ruidoso.
- **Palavras dos temas de revisão:** lista curta e literal; um classificador (com a revisão humana da F12) fica para
  depois.

## Leva 3 (commits 9 e 10: painel e fechamento)

### Decisões que entraram (pelo PADRÃO da auditoria §11)
- **D2:** o select mostra o id canônico (`musical_companhia` aparece como "Musical adulto") e o valor gravado só muda
  quando o usuário troca; salvar sem tocar reenvia `musical_companhia`. Um valor fora do catálogo deste painel
  (ex.: um formato implementado só no backend) é avisado abaixo do select, mostrado como "Livre" e preservado ao
  salvar.
- **D7:** "Usar relógio sugerido (A|C)" aparece ao lado do editor do relógio só enquanto o preset sugerido não está
  aplicado; nunca é aplicado sozinho. **D13:** `formatosImplementados` filtra `implementado`. **D16:** cartão
  "Identidade da rádio" (somente leitura, link para `/configuracoes`) e seção "Identidade do programa" (nome,
  sobre, formato com promessa/conteúdo/condução/unidade/participação/temas, público). **D22:** `gerarFalaLocal`
  reorienta com `falaReservaNeutra` em toda fala. **D23:** checkbox de blocos extras desabilitado só quando o formato
  não permite (musical).

### Desvios e precisões do desenho (leva 3)
- **Posição da identidade:** a seção "Identidade do programa" foi para o topo do formulário (antes de "No ar"), não
  logo antes de "Persona e conteúdo" como o §6.11 escreveu: o nome do programa precisa continuar o primeiro campo, e
  os botões de sugestão ficaram onde agem (relógio ao lado do editor do relógio; sequência ao lado do editor de
  blocos). "O que rende conversa aqui" (`publico_alvo`) saiu de "Assuntos e notícias" para a identidade, porque é o
  "Público" que a seção `_formato(ctx)` lê.
- **Espelho estrutural, textos só da rota:** `lib/formatoPrograma.ts` guarda id, nome, alias, roteiro, relógio
  sugerido e blocos extras dos quatro implementados (o que a prévia e a fala local precisam sem rede); promessa e os
  outros textos só aparecem quando `GET /config/formatos` responde. `lib/__tests__/formatoPrograma.test.ts` confere o
  espelho contra a cópia da rota (`formatosFixtures.ts`); se o catálogo do backend mudar, os dois precisam acompanhar.
- **`ehMusical` pelo id:** o ciclo musical não vem na rota (é flag do `Comportamento`), então o painel decide por
  `id === "musical_adulto"`. Um formato futuro com ciclo musical pede atualização do painel.
- **D22 em três frases, não duas:** além de "Ja volto com mais" (música) e "assim que a fonte confirmar eu trago
  certinho" (notícia), "manda mensagem no WhatsApp que eu leio aqui" (comentário) também prometia; as três viraram a
  reorientação neutra. O tipo da fala local passou a seguir a regra do motor (estrutura em loop ou abertura na largada
  e roteiro do formato por n-1), inclusive no `padrao`, cuja ordem de emergência era diferente de propósito.
- **`ProximosBlocosPanel` lê a rota:** terceira chamada (`/config/formatos`) além de patrocinadores e vinhetas; com a
  rota fora, o espelho.

### Fora do escopo e pendente
- **S7 (`--modo llm`, juiz ≥ 4/5):** depende de aprovação de custo; o aceite do plano fica medido só pelo proxy fake.
- **Painel no navegador:** não conferido (precisa do backend e do banco de pé); os 389 testes do vitest e o `tsc`
  cobrem o comportamento.
- **Editor completo do relógio e seleção de faixa por duração-alvo:** continuam pendências da F1 (§10).
- As ideias da leva 2 (dublê obediente ao formato, "primeira" pela meta, teto de palavras na identificação, critério
  de unidade em contagem, reorientação com memória no `/proxima`, classificador de temas) seguem abertas.
