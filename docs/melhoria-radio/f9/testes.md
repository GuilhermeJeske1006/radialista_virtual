# F9 — Glossário de pronúncia (passos 1 e 2)

Branch `melhoria/f9-glossario`, base `melhoria/f8-memoria`.

## Entregas

- **Passo 1 (glossário por rádio, precedência sobre a voz):** `Account.glossario_pronuncia` (migração aditiva em
  `garantir_colunas_account`). Em `parametros_sintese` (`app/tts/profiles.py`), o mapa efetivo é o da rádio, sobrescrito
  pelo da voz na mesma chave, sem diferença de caixa (`mesclar_glossarios`). Aplicado pelo `normalizar_texto_fala`, sem
  mudança nele.
- **Validação da API:** `RadioContaRequest.glossario_pronuncia` aceita no máximo 100 termos, 60 caracteres cada; descarta
  chave ou valor vazio e duplicata sem diferença de caixa (`normalizar_glossario`).
- **Passo 2 (sugestões):** `sugerir_termos` aponta siglas (2 a 5 maiúsculas) e nomes com w, y, k ou ph, sem repetição,
  sem o que já está no glossário e sem empréstimos comuns ("show", "shopping" etc.). Heurística; quem cadastra decide.
- **Passo 3 (verificação por STT):** não feito. Exige créditos de STT; depende de aprovação.
- **Painel (CRUD do glossário da rádio):** não feito. O backend já aceita e devolve o campo.

## Testes

- `backend/tests/test_glossario_pronuncia.py` (13 + 13 do tts): validação (vazios, duplicata, limites), precedência
  rádio x voz sem diferença de caixa, radio vale sem voz e vice-versa, efeito no texto falado, sugestões (siglas, w/y/k/ph,
  empréstimo comum, já cadastrado, limite, sem repetição), parâmetros de síntese com e sem configuração da voz, e a
  validação da API.
- Ajuste em `tests/test_tts_profiles.py`: a chave `pronuncias` agora sempre acompanha os parâmetros (vazia sem glossário).
- Ajuste em `tests/test_live_router.py`: os seis stubs de síntese passam a aceitar `pronuncias=None`. Sem isso, a
  suíte completa tinha cinco falhas (`TypeError`), que vinham do contrato novo e não do código de produção.

## Bugs achados durante os testes (corrigidos antes do commit)

- Sugestão pegava "Show" (tem w). Empréstimos comuns entraram numa lista de exclusão.
- Regex de nome não pegava "Phelipe" (ph minúsculo depois de inicial maiúscula). Trocado por busca de palavra capitalizada
  com filtro de letra, sem diferença de caixa.
