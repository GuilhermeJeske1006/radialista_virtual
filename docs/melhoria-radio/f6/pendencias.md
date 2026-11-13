# Pendências registradas na F6

Achados e ideias fora do escopo da F6 (catálogo de formatos e perfis editoriais), ou fora da leva em andamento.
A leva 1 cobre os commits 0 a 4 do §7 da auditoria (linha de base, caracterização, catálogo sem mudar comportamento,
item 9 e contrato/gerador).

## Decisões (auditoria §11), todas adotadas pelo padrão, a confirmar
- **D1** formato em `perfil_programacao` (coluna existente), sem migração. **D2** alias resolvido na leitura, nada
  reescrito no banco; a API aceita e ecoa o valor gravado.
- **D3** `padrao` continua "Livre (sem formato)", com o comportamento de antes; padrão da API.
- **D4** catálogo em Python (dataclasses congeladas) em `app/live/formatos.py`; `formato.py` como compatibilidade.
- **D5** o musical herda `ORCAMENTOS` sem mudança (retomada 6–12 s × link 10–35 s da pesquisa continua decisão do
  usuário, porque muda a linha de base de quatro frentes).
- **D6** popular no preset A, **D7** relógio do formato só como sugestão (`relogio_padrao`), **D9** orçamento aplicado
  sem relógio nos formatos novos: entram com os formatos da leva 2.
- **D8** no relógio, com `aplica_orcamento`, vale a unidade do formato para o papel do bloco, limitada depois pela
  etapa e pelo espaço; no musical é igual ao "menor dos dois" de antes (retrato C3 idêntico).
- **D10** `direcao_formato("musical_adulto")` byte a byte igual a `direcao_musical`; seção `_formato(ctx)`: leva 2.
- **D11** `ORCAMENTOS_POR_FORMATO` e `FORMATOS_APLICADOS` derivados do catálogo, mesmos nomes; `orcamento_para`
  resolve o alias e aceita `quadro=` (e também um `Formato`).
- **D12** flags do `Comportamento` em todos os usos; `formato_musical` continua campo derivado em `EntradaEmissao` e
  `ContextoEmissao` (construir só com o booleano ainda funciona e escolhe musical ou padrão).
- **D13** os sete formatos futuros no catálogo com `implementado=False`: 422 na API, fora do gerador, listados em
  `GET /config/formatos`.
- **D14** `perfil_programacao: str` validado na requisição e tolerante na resposta; rota `GET /config/formatos`.
- **D15** gerador lista os implementados com o uso de cada um, aceita o alias, `tipo_radio` como dica
  (`mpb_variedades` e `regional_flashback` → `musical_adulto`). O exemplo sertanejo fica `padrao` até a leva 2.
- **D16** identidade: nada mudou nesta leva (painel e `_formato(ctx)` vêm depois); `montar_system_prompt` intacto.
- **D17** `abertura_apos_intervalo` existe no `Comportamento` e já é lida por `_tipo_proximo_bloco`, mas é `False` em
  `padrao` e no musical: só os formatos novos a ligam.
- **D18** TTL de 30 dias renovado a cada gravação, teto de 5000 entradas, `hlen` no `PADROES_SESSAO`.
- **D19** a **D23** (simulador, coerência no modo fake, log `live_formato_aviso`, `gerarFalaLocal`, blocos extras):
  D23 já vale (só o musical ignora `ia_pode_adicionar_blocos`, pela flag); as outras são das levas seguintes.

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
  declara `quadro` ainda; rever na leva 2 (variedades).

## Riscos até as próximas levas
- **Painel ainda compara a string crua** (`EditarProgramaForm.tsx`, `ProximosBlocosPanel.tsx:133`,
  `useLiveEngine.ts:165`). Desde o commit 4, o gerador por IA oferece o id canônico `musical_adulto`: um programa
  gerado assim aparece como "padrão" no select do painel e a prévia/fala local do painel o tratam como não musical
  (o backend o trata como musical). **Não publicar a F6 antes do commit do painel (leva 3, §6.11).**
- **Rollback:** um backend anterior à F6 falha a leitura de um programa com `musical_adulto` (o `Literal` antigo).
  SQL de volta: `UPDATE programas SET perfil_programacao='musical_companhia' WHERE perfil_programacao='musical_adulto'`
  (e, depois da leva 2, `popular_sertanejo`/`variedades_leves` → `padrao`). Registrar no relatório da frente.
- **Log do resolvedor:** um valor desconhecido ou futuro gravado fora da API gera `formato_desconhecido` /
  `formato_nao_implementado` a cada resolução (várias por `/proxima`). Se aparecer em produção, limitar a um aviso
  por programa (fora do escopo desta leva).

## Fora da F6 (não mexido de propósito)
- `densidade_assunto` continua sem leitor; `Programa.perfil` e `Account.tipo_radio` mantêm o significado.
- O dublê da simulação (`dubles.py`, `emissao.py`) continua com a referência de orçamento da fixture para o musical
  via `orcamento_fala`; a troca pela referência do catálogo é do commit 7 (simulador).
- A divergência de `ORCAMENTOS` com a pesquisa (D5) e o relógio personalizado completo (F1) continuam pendentes.
