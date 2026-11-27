---
description: Continua o plano de redução de custo do Flashback / formato musical com curadoria (o que falta fazer)
argument-hint: "[passo opcional: aprovar-ab | deploy | configurar-prod | medir | tudo]"
---

Você está continuando, em uma sessão nova, o plano de **redução de custo de tokens sem perder qualidade** da Locufy (Rádio Guabiruba FM, programa 3 "Flashback do Meio-Dia"). Responda em português. O usuário prefere respostas curtas (modo caveman ultra, se ainda ativo). Argumento recebido: `$ARGUMENTS` (vazio = faça a checagem de estado e proponha o próximo passo).

## 1. Leia primeiro (nesta ordem, sem reler o que não precisa)
1. `docs/plano-reducao-custo-flashback.md`, seções 9 (plano validado) e 10 (execução, custo, margem).
2. Memórias do projeto: `project_plano_custo_musical_curado`, `project_incidente_creditos_27_11`, `project_ovh_deploy`.
3. `git log --oneline origin/master..master` e `git status` (deve haver 4 commits locais não publicados: `da9fed3`, `15bc80f`, `ebb7a8d`, `9fbe493`).

## 2. Onde parou (27/11/2026)
- Produção roda `ce26699` (disjuntores de IA, chave do YouTube mascarada nos logs, 1 busca por faixa, `/reserva` com rodízio). Os 4 commits acima estão **só no master local**.
- Feito no código local: formato `flashback` virou **`musical_curado`** ("Musical com curadoria", alias `flashback` mantém o programa 3 sem migração, módulo `app/live/musical_curado.py`, `configurar_musical.py`); cache de prompt (system dividido em estável/variável, só com `LLM_PROMPT_CACHE=true`); `LLM_MODEL_FALAS_CURTAS` e parâmetros dos modelos 5.5; `backend/scripts/custo_log.py` (custo/h e margem a partir de logs).
- Testes: backend 2 835 passam; frontend e lint limpos.
- Custo medido antes do plano: ≈ US$ 3,8/h (promessa do site: US$ 0,76/h = R$ 8,35/h cobrado). Meta: ≈ US$ 0,95/h. Margem do plano Flex: ≈ 30–32% com cobrança de 2× o uso medido.
- Prod, programa 3: `perfil_programacao=flashback`, mas `estrutura_blocos` antiga, `pode_pesquisar=true`, `musicas_permitidas` vazio (só o perfil foi trocado).

## 3. O que falta fazer (cada item que gasta dinheiro, publica ou muda produção pede aprovação explícita do usuário antes)
1. **A/B com LLM real (pago, ≈ US$ 0,3–0,6 por rodada, ≈ US$ 2 no total).** Rodadas: formato `padrao` (baseline), `musical_curado` com Opus 5 sem cache, com cache (`LLM_PROMPT_CACHE=true`), e mix Opus 5.5 + `LLM_MODEL_FALAS_CURTAS=claude-sonnet-5-5`. Comando base, a partir de `backend/`: `PYTHONPATH=. .venv/bin/python scripts/simular_hora.py --programa musical_adulto --saida <pasta> --modo llm --formato musical_curado --confirmo-custo` (capture o log de INFO e passe por `scripts/custo_log.py`). **Só rode com aprovação explícita:** o controle de permissões bloqueia o `--confirmo-custo` sem ela. Depois avalie a qualidade com a skill `avaliar-locucao` (agente `juiz-locucao`) sobre os `as_run.json`: falas acima do teto, reescritas por bloco, repetição, fato sem fonte, naturalidade. Critérios de parada na seção 9.5 do plano.
2. **Push do master e deploy** (push no master = CI + deploy automático com rollback no VPS OVH). As flags novas ficam desligadas. Confirme com o usuário antes.
3. **Completar a configuração do programa 3 em prod:** `docker compose exec backend python -m app.live.configurar_flashback --account-id 1 --programa-id 3` (prévia) e depois `--aplicar`, **fora de 12h–14h** (recusa com player ativo; faz backup em `config_backups/`). Mostre a prévia ao usuário primeiro.
4. **Ligar as flags só depois do A/B e de escuta humana:** `LLM_PROMPT_CACHE=true` e, se o Sonnet 5.5 passar, `LLM_MODEL_FALAS_CURTAS=claude-sonnet-5-5` no `.env.backend` do VPS (nunca imprimir valores do `.env`). Confira `cache_read_input_tokens` > 0 e o tamanho mínimo cacheável dos modelos.
5. **Medir a primeira hora real depois da mudança:** puxe os logs `llm_consumo` e `tts_consumo` do backend no VPS (`docker compose logs -t --no-log-prefix --since ... backend | grep -E 'llm_consumo|tts_consumo'`) e passe por `scripts/custo_log.py --horas 2`. Os logs do docker somem a cada deploy (container recriado): puxe logo após o programa. Compare com a tabela da seção 10.2 e atualize o plano.
6. **Pendências do usuário a confirmar:** crédito da Anthropic recarregado (com recarga automática), **rotação da chave da YouTube API** (aparecia em logs antigos), conferir o preço real da voz na fatura da ElevenLabs (premissa US$ 0,10 por mil caracteres).
7. **Decisões de negócio abertas:** corrigir a estimativa de preço do site (hoje promete R$ 8,35/h; realista R$ 10–14/h depois das otimizações), meta de fala por hora (formato já limita a 8–18%), segundo provedor de LLM só como contingência (seção 8; exige atualizar a política de privacidade).
8. **Adiado:** descarte seletivo do pré-preparo no painel; medição de custo para contas isentas (gravar `usos_ia`); anúncio sem LLM (C1), só se o Sonnet 5.5 não servir.

## 4. Regras de trabalho
- Acesso a produção: `ssh-add --apple-use-keychain ~/.ssh/id_ed25519` e `ssh ubuntu@40.160.150.84`; SQL somente leitura via `docker compose exec -T postgres psql` com `PGOPTIONS="-c default_transaction_read_only=on"`. Nunca imprimir segredos nem `.env`.
- Testes: `cd backend && .venv/bin/python -m pytest tests -q` (≈ 14 min; rode subconjuntos durante o desenvolvimento) e `.venv/bin/python -m ruff check app tests`; frontend: `cd frontend-painel && npx vitest run && npx tsc --noEmit -p .`.
- Commits terminam com `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`. Não faça push sem o usuário pedir.
- Economize créditos: sem múltiplos agentes, sem rodadas pagas sem aprovação.

Comece confirmando o estado (git, produção saudável, programa 3) em poucas linhas e pergunte qual item da seção 3 o usuário quer executar primeiro.
