# Testes da F7 (persona e oralidade)

## Novos

- `backend/tests/test_oralidade.py` (16): frase longa no limite e acima, mais de uma ideia, sigla sem expansão só na primeira
  ocorrência, sigla com expansão antes e depois (parênteses), sigla falada (FM), número longo em dígitos e por extenso,
  número curto sem aviso, vocabulário burocrático ignorando acento e caixa, texto vazio, e os 4 casos rotulados do
  benchmark `docs/benchmarks/2026-11-06-formatos/casos.json` (cada um pega o mínimo esperado).
- `backend/tests/test_persona.py` (27): sem persona nenhuma linha no system; nulo e vazio; defaults; escala fora de 1 a 5
  rejeitada; mais de 5 exemplos e exemplo acima de 280 caracteres rejeitados; exemplo vazio descartado; faixas de texto
  (baixa, média, alta); regra de não imitar presente; persona entra no system depois do formato e não entra na mensagem
  do bloco; persona inválida no banco vira None sem derrubar a leitura; `ProgramaRequest` aceita e serializa a persona,
  rejeita escala fora da faixa; `ProgramaResponse` lê persona inválida como nula.
- `frontend-painel/components/__tests__/PersonaPrograma.test.tsx` (5): ativar com o padrão, trocar escala grava número,
  remover grava nulo, exemplos (linha vazia descartada e Enter não some), aviso acima de 5 exemplos.

- `backend/tests/test_oralidade_reescrita.py` (7): `desligado` com uma chamada e fala intocada; `avisar` só registra;
  `reescrever` faz a reescrita única com a instrução de oralidade no system; fala limpa não gasta chamada extra;
  reescrita que ainda tem aviso não gera terceira chamada; instrução vazia sem avisos; instrução sem repetir o trecho.

## Alterado

- `backend/tests/test_simular_hora.py::test_metricas_em_as_run_artificial`: a expectativa `aviso_oralidade is None` virou
  a soma do verificador sobre as falas do as_run. O valor medido é 0.

## Medido

- Verificador nos 96 falas rotuladas do benchmark: os 4 com aviso esperado são pegos; 7 falas sem expectativa recebem aviso
  (sobretudo frase longa de abertura). Expectativa é mínimo, não máximo, então não conta como falha.
- Simulador fake `musical_adulto` sem persona: `as_run.json` idêntico ao da F5. `aviso_oralidade` passa de null para 0.

## Reescrita opcional (`settings.oralidade_modo`)

- Padrão `desligado`: nada muda; goldens e simulações sem o modo ligado ficam idênticos (conferido: 193 passed no
  subconjunto ao vivo e simulador `musical_adulto` igual à F5).
- `reescrever`: a instrução entra nas `instrucoes_extras` da mesma reescrita única. Não há chamada nova ao LLM.
- Simulador fake com `ORALIDADE_MODO=reescrever` (`popular_sertanejo`): mesmo número de chamadas (11 no total, 1
  revisão) e nenhuma fala com aviso. O dublê devolve falas fixas sem avisos, então o fake não exercita a reescrita;
  o efeito real só se mede com LLM.

## Decisões

- Persona fica em coluna JSON nula em `programas` (migração aditiva em `garantir_colunas_programa`). Nulo = sem linha no prompt,
  então goldens e simulações sem persona não mudam.
- Verificador só aponta. Reescrita opcional fica fora desta entrega; a redução de 50% depende dela e de LLM.
- Heurística de "mais de uma ideia": pelo menos 18 palavras e dois conectivos. Limites são constantes do módulo.
