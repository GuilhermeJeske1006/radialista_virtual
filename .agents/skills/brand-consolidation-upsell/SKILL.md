---
name: brand-consolidation-upsell
description: Valida se a "marca" de uma conta (radialista + programa + WhatsApp) está de fato consolidada no locufy, cruza isso com uso vs limite do plano, e recomenda o gatilho de upsell certo (trocar de plano, comprar agente extra ou excedente de mensagens). Use quando o pedido for sobre onboarding incompleto, checklist de configuração inicial, churn por setup mal feito, ou "fazer o sistema empurrar upgrade/compra".
---

# Consolidação de marca + upsell

No locufy, "marca" = o locutor virtual de uma rádio configurado de ponta a ponta: radialista
com voz, programa ativo, WhatsApp conectado. Essa skill junta duas coisas que já existem
soltas no código — validação de onboarding e limites de plano — num processo único: só faz
sentido empurrar upgrade/compra numa conta cuja marca já está consolidada (senão o problema é
onboarding, não dinheiro).

## Implementado

Essa skill já virou código, não é mais só um processo manual:

- [`backend/app/billing/consolidacao.py::marca_consolidada`](../../../backend/app/billing/consolidacao.py) —
  Passo 1 (espelha `useConfiguracaoInicial.ts` no backend).
- [`backend/app/billing/upsell.py::calcular_sinal_upsell`](../../../backend/app/billing/upsell.py) —
  Passo 2+3 (regras de gatilho, dataclass `SinalUpsell` com `tipo`/`titulo`/`mensagem`/`enviar_email`).
- [`backend/app/billing/alertar_upsell.py`](../../../backend/app/billing/alertar_upsell.py) — cron
  (`python -m app.billing.alertar_upsell`, mesmo padrão de `app/onboarding/alertar_desconexao.py`)
  que dispara `notificar_admins` (in-app + e-mail quando `enviar_email=True`) com dedupe por
  `Account.upsell_alerta_tipo`/`upsell_alerta_mes`. **Precisa ser agendado num cron do SO** (não
  roda sozinho) — ver docstring do arquivo.
- [`frontend-painel/components/UpsellBanner.tsx`](../../../frontend-painel/components/UpsellBanner.tsx) —
  mesma regra em tempo real, plugado no Dashboard e na Billing page.
- Testes: `backend/tests/test_billing_upsell.py`, `backend/tests/test_alertar_upsell.py`.

O que falta pra virar gatilho de verdade em produção: registrar o cron
(`app.billing.alertar_upsell`) num scheduler real (cron do SO, ou equivalente no deploy) — hoje
só roda se alguém chamar manualmente.

## Passo 1 — Validar consolidação da marca

`completa = whatsappConectado && radialistaPronto && programaAtivo`, calculado por
`marca_consolidada` (backend) e `useConfiguracaoInicial.ts` (frontend) — mesma lógica nos dois lados.

Se **não** `completa`: pare aqui (é o que `calcular_sinal_upsell` já faz). Essa conta é caso de
onboarding (ver `OnboardingTour`/checklist do dashboard), não de upsell — empurrar compra pra
quem nem terminou de configurar é ruído e queima confiança.

## Passo 2 — Puxar uso vs limite do plano

Só depois de `completa == true`. Fonte de verdade: `GET /billing/status`
(implementado em [`app/billing/router.py`](../../../backend/app/billing/router.py) `_status_plano`,
que usa [`app/billing/limites.py`](../../../backend/app/billing/limites.py)). Retorna:

```json
{
  "plano": "starter|growth|professional",
  "agentes_usados": int, "agentes_limite": int, "agentes_extras": int,
  "mensagens_usadas": int, "mensagens_limite": int, "mensagens_extras": int
}
```

Limites base por plano (`backend/app/planos.py::PLANOS`):

| plano | agentes | mensagens/mês | clonagem_voz | radialistas/programa |
|---|---|---|---|---|
| starter | 1 | 2000 | não | 1 |
| growth | 3 | 3000 | sim | 2 |
| professional | 5 | 7500 | sim | 3 |

## Passo 3 — Regras de gatilho de upsell

Aplicar nessa ordem, primeiro gatilho que bater vence (não empilhar várias ofertas de uma vez):

1. **`agentes_usados >= agentes_limite`** (bloqueado, backend já responde 402 em
   `POST /config/radialistas`) → oferecer **agente extra**: `POST /billing/agentes-extras/checkout`,
   R$ `PRECO_AGENTE_ADICIONAL` (100) fixo/mês. Se a conta já tem vários agentes extras
   acumulados (ex. `agentes_extras >= 2`), sugerir upgrade de tier em vez de acumular mais
   avulso — geralmente sai mais barato pro cliente e é ticket maior pra locufy.
2. **`mensagens_usadas >= mensagens_limite * 0.8`** (perto ou estourando) → oferecer
   **excedente de mensagens**: `POST /billing/excedente-mensagens/checkout`, blocos de 1000 msgs
   a R$ `PRECO_EXCEDENTE_1000_MSG` (50) cada. Se isso se repete mês a mês (não é pico pontual),
   sugerir upgrade de tier — mensagens excedentes recorrentes indicam que o plano tá pequeno.
3. **Radio tenta co-apresentador (`radialistas_por_programa`) acima do limite do plano atual**
   (`starter`=1, sem multi-voz) → só upgrade resolve, não tem avulso pra isso. Empurrar
   `growth` (2) ou `professional` (3) via `POST /billing/trocar-plano`.
4. **Radio tenta clonar voz (`POST /tts/clonar-voz` ou equivalente) em plano `starter`**
   (`clonagem_voz=False`) → só upgrade pra `growth`+ libera. Feature paga na ElevenLabs, é o
   gatilho de upgrade mais direto porque bloqueia uma ação que o usuário já tentou fazer.
5. Nenhum limite estourando: sem gatilho. Não force upsell numa conta com uso confortável —
   vira spam e no notification center (`app/notificacoes/service.py::notificar_admins`) some
   junto com o resto.

## Passo 4 — Como surfar a recomendação

- **In-app**: `notificar_admins(db, account, "billing", titulo, mensagem, link="/billing")` —
  mesmo canal que já avisa sobre assinatura ativada/cancelada, mantém consistência.
- **UI de billing**: página [`frontend-painel/app/billing/page.tsx`](../../../frontend-painel/app/billing/page.tsx)
  já é onde `PRECO_AGENTE_ADICIONAL`/`PRECO_EXCEDENTE_1000_MSG` são mostrados e onde os
  checkouts de agente extra/excedente/troca de plano acontecem — qualquer CTA novo deve
  apontar pra lá, não reinventar fluxo de cobrança em outro lugar.
- **Tom**: direto, número concreto (ex. "3/3 agentes em uso — upgrade pra Growth libera 3 e
  ainda ganha clonagem de voz"), nunca alarmista. O backend já bloqueia com 402 quando o
  limite é ultrapassado de verdade — essa skill é sobre avisar antes de bater no bloqueio,
  não sobre inventar urgência artificial.

## O que essa skill NÃO faz

Não altera enforcement de limite (isso é `app/billing/limites.py` + checagem 402 nos routers
de config/tts — mexer nisso é mudança de regra de negócio, peça confirmação explícita antes).
Só lê estado (`/config/*`, `/billing/status`) e decide qual oferta mostrar.
