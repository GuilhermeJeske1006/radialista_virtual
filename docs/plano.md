# Plano Técnico — Radialista Virtual

## 1. Visão Geral do Produto

Um "locutor virtual" configurável que:
- Fala em linguagem natural, com tom ajustável (formal/noticiário ↔ informal/descontraído)
- Responde perguntas de ouvintes via WhatsApp
- Conduz uma transmissão "ao vivo" (fala + música + vinhetas/patrocinadores) sozinho, seguindo a grade de programação da rádio
- Opera dentro de travas de segurança e escopo (conteúdo, horário, volume de mensagens)
- É vendido como SaaS (assinatura mensal) para rádios/emissoras

---

## 2. Stack Tecnológica

| Camada | Tecnologia | Motivo |
|---|---|---|
| Backend principal | Python + FastAPI | Rápido de prototipar, ótimo suporte a IA/LLM |
| LLM | API Claude (Anthropic) | Motor de geração de texto do locutor e classificação de intenção |
| Integração WhatsApp | WuzAPI (self-hosted, Go/whatsmeow) | API REST multiusuário/multidispositivo, sem custo por mensagem, pareamento por QR Code |
| TTS | ElevenLabs | Voz sintética do locutor (clonagem de voz e vozes de biblioteca) |
| STT | Whisper (via `app/stt`) | Transcrição de áudio recebido no WhatsApp |
| Banco de dados | PostgreSQL | Configurações, histórico, usuários, multi-tenant |
| Cache/Rate limit | Redis | Controle de travas (limite de mensagens, horários, debounce) |
| Pagamentos | Stripe | Assinatura mensal por plano |
| E-mail transacional | Resend | Redefinição de senha, convites de equipe, boas-vindas |
| Deploy | Docker Compose (self-hosted) | `start.sh` sobe wuzapi + backend + frontend |
| Painel de configuração | Next.js | Onde a rádio configura o locutor, a grade e acompanha métricas |

---

## 3. Estrutura de Pastas (estado atual)

```
radialista_virtual/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── auth/                  # login/registro/sessão (JWT em cookie httpOnly), troca de senha
│   │   ├── equipe/                 # convites e papéis (admin/membro) por conta
│   │   ├── billing/                 # Stripe Checkout + webhook de assinatura
│   │   ├── onboarding/              # provisiona usuário WuzAPI, QR Code, HMAC, status da sessão
│   │   ├── whatsapp/                # webhook de mensagens recebidas + sender
│   │   ├── llm/                     # prompt builder + classificação de intenção
│   │   ├── stt/                     # transcrição de áudio recebido
│   │   ├── tts/                     # síntese de voz (ElevenLabs), vozes e clonagem
│   │   ├── postprod/                # pós-produção do áudio gerado (efeitos, naturalidade)
│   │   ├── guardrails/              # rate limit, filtro de conteúdo, janela de horário
│   │   ├── live/                    # motor do "ao vivo": roteiro, música, fila de pedidos
│   │   ├── biblioteca_audio/        # vinhetas/efeitos avulsos (cartwall)
│   │   ├── categorias_vinheta/      # categorias da biblioteca de áudio
│   │   ├── patrocinadores/          # anúncios gravados/roteirizados
│   │   ├── metrics/                 # totais e séries de interações
│   │   ├── config/                  # settings, CRUD de rádio/radialista/programa
│   │   ├── models/                  # SQLAlchemy
│   │   └── db/
│   ├── tests/                       # pytest, backend+integração (ver CI)
│   └── docker-compose.yml
├── wuzapi/                          # serviço WuzAPI (self-hosted)
├── frontend-painel/                 # painel Next.js
│   ├── app/                         # dashboard, radialista, programas, vinhetagem, ao vivo,
│   │                                 # programação (grade semanal), onboarding, equipe, billing,
│   │                                 # configurações, perfil, auth (login/registro/convite)
│   ├── components/
│   ├── hooks/
│   └── lib/
├── .github/workflows/                # CI (lint + testes backend/frontend)
└── docs/
    └── plano.md                     # este arquivo
```

---

## 4. Fluxo de Funcionamento — WhatsApp

0. **Onboarding (uma vez por rádio)**: a rádio se cadastra no painel (`/register`), assina um plano via Stripe e, em `/onboarding`, o backend provisiona um usuário no WuzAPI (`app/onboarding/router.py`), configura HMAC de assinatura e entrega de mídia em base64, e a rádio escaneia o QR Code com o WhatsApp que vai atender.
1. **Ouvinte envia mensagem** → WuzAPI recebe via whatsmeow e chama `POST /webhook/whatsapp` no backend, assinado com HMAC-SHA256 (`app/whatsapp/webhook.py::_verificar_assinatura`).
2. **Debounce**: mensagens em bolhas seguidas do mesmo ouvinte são agrupadas (Redis) antes de classificar a intenção, pra reagir ao pedido completo em vez de um fragmento.
3. **Guardrails** processam antes de qualquer resposta: rate limit por ouvinte/mês (conforme plano), janela de horário do programa no ar, filtro de tópicos permitidos/proibidos, restrição de pedido de música por estilo/horário.
4. **Classificação de intenção** (LLM) decide se é pedido de música, pergunta livre, abraço/recado, etc., e monta o prompt do sistema com a persona/config daquela rádio.
5. **Chamada ao LLM** (Claude) gera a resposta; se for áudio, passa por TTS (ElevenLabs) e pós-produção.
6. **Sender** devolve a resposta via WuzAPI (`POST /chat/send/text` ou envio de mídia).
7. **Log da interação** salvo no banco para métricas e auditoria (`app/metrics`).

## 5. Fluxo de Funcionamento — Ao Vivo

O motor do "ao vivo" (`app/live`, `frontend-painel/hooks/useLiveEngine.ts`) roda o loop cliente-side no painel: gera a próxima fala (texto + TTS) com base no roteiro do programa e no histórico recente, toca músicas do repertório permitido (com corte pontual de início/fim analisado no backend), insere vinhetas/patrocinadores, atende pedidos da fila do WhatsApp, e respeita o horário de início/fim do programa (inclusive um watchdog que corta no horário exato). O operador pode pular pra próxima fala, pausar a transmissão (interrompendo qualquer áudio em andamento) e inserir um item do Cartwall/Biblioteca de áudio diretamente na transmissão a qualquer momento.

---

## 6. Guardrails — Detalhamento

- **Rate limiting**: Redis, chave por ouvinte/janela; limite efetivo depende do plano da conta (`app/billing/limites.py`).
- **Filtro de conteúdo**: tópicos permitidos/proibidos configuráveis pela rádio + filtro de segurança geral sempre ativo.
- **Horário**: janela de atendimento por programa, com fuso horário da rádio (`app/guardrails/schedule.py`).
- **Autenticação do webhook**: assinatura HMAC-SHA256 por conta (ver seção "Segurança" abaixo — cobertura em andamento).
- **Fallback**: qualquer trava disparada responde com mensagem padrão, nunca expõe erro técnico ao ouvinte.

---

## 7. O que já está pronto

- Autenticação (registro/login/sessão via cookie httpOnly, troca de senha, redefinição por e-mail), multi-tenant por conta, equipe multiusuário com papéis e convites por e-mail.
- Onboarding automatizado do WuzAPI (criação de usuário, QR Code, HMAC, status da sessão) com e-mail de boas-vindas.
- Billing via Stripe (checkout, webhook de assinatura, limites por plano).
- Atendimento no WhatsApp com guardrails (rate limit, horário, conteúdo), STT para áudio recebido, restrição de música por estilo/horário, fila de pedidos ao vivo.
- Transmissão "Ao Vivo": roteiro gerado por IA, música com corte pontual, vinhetas/patrocinadores, Cartwall/Biblioteca de áudio com inserção direta na transmissão, grade de programação semanal por radialista.
- Pós-produção de áudio gerado (efeitos, naturalidade) com perfis por estilo de rádio.
- Métricas de interações (backend pronto, painel ainda não expõe — ver próximos passos).
- Suite de testes (backend + frontend) e CI via GitHub Actions.

## 8. Próximos passos

Ver acompanhamento vivo de tarefas priorizadas com o time (segurança, observabilidade, funcionalidades de painel) — este documento cobre o "o quê" e "por quê" arquitetural; a lista de tarefas em andamento fica fora dele pra não desatualizar a cada sprint.

Eixos identificados na última revisão, em ordem de prioridade:

1. **Segurança**: mover o JWT do painel pra cookie httpOnly (mitiga roubo via XSS) e fechar a brecha de contas sem HMAC configurado no webhook do WhatsApp.
2. **Observabilidade**: alertar quando a sessão do WhatsApp cair, integrar monitoramento de erros (ex.: Sentry), e evoluir o CI atual para deploy automatizado.
3. **Painel**: expor as métricas que o backend já calcula, extrair uma tela dedicada de conversas (hoje embutida no onboarding), exportação de relatórios em CSV, histórico da fila de pedidos ao vivo, e um indicador de "quem está no ar agora".
