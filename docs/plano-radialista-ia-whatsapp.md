# Plano Técnico — Radialista Virtual com IA integrado ao WhatsApp

## 1. Visão Geral do Produto

Um "locutor virtual" configurável que:
- Fala em linguagem natural, com tom ajustável (formal/noticiário ↔ informal/descontraído)
- Responde perguntas de ouvintes via WhatsApp
- Opera dentro de travas de segurança e escopo (conteúdo, horário, volume de mensagens)
- É vendido como SaaS (assinatura mensal) para rádios/emissoras

---

## 2. Stack Tecnológica Recomendada

| Camada | Tecnologia | Motivo |
|---|---|---|
| Backend principal | Python + FastAPI | Rápido de prototipar, ótimo suporte a IA/LLM |
| Fila/Webhooks em tempo real | Node.js (opcional, se escala for grande) | Lida bem com alta concorrência de webhooks |
| LLM | API Claude (Anthropic) ou GPT | Motor de geração de texto do locutor |
| Integração WhatsApp | WuzAPI (self-hosted, Go/whatsmeow) | API REST multiusuário/multidispositivo, sem custo por mensagem, pareamento por QR Code, você controla o servidor |
| Banco de dados | PostgreSQL | Configurações de personalidade, histórico, usuários |
| Cache/Rate limit | Redis | Controle de travas (limite de mensagens, horários) |
| Deploy | Docker + Railway/Render/AWS | Portável e escalável |
| Painel de configuração | React (Next.js) | Onde o cliente (rádio) configura o "personagem" do locutor |

---

## 3. Estrutura de Pastas (implementada na Fase 1)

```
radialista-ia/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config/
│   │   │   ├── settings.py
│   │   │   └── personas.py
│   │   ├── whatsapp/
│   │   │   ├── webhook.py
│   │   │   ├── sender.py
│   │   │   └── session_manager.py
│   │   ├── llm/
│   │   │   ├── client.py
│   │   │   └── prompt_builder.py
│   │   ├── guardrails/        # Fase 2
│   │   ├── models/            # Fase 2
│   │   └── db/                # Fase 2
│   ├── requirements.txt
│   └── Dockerfile
├── wuzapi/
│   ├── docker-compose.yml
│   └── .env.example
├── frontend-painel/            # Fase 3
└── docs/
    └── plano-radialista-ia-whatsapp.md
```

---

## 4. Fluxo de Funcionamento (Passo a Passo)

0. **Pareamento inicial (uma vez por rádio/cliente)**: via `session_manager.py`, cria-se um usuário no WuzAPI (`POST /admin/users`, com token admin) e a rádio escaneia o QR Code (endpoint `/login` do WuzAPI) com o WhatsApp do número que vai atender.
1. **Ouvinte envia mensagem no WhatsApp** → o WuzAPI recebe via WhatsApp (whatsmeow) e dispara um webhook HTTP para `/webhook/whatsapp` no backend.
2. **Camada de travas (guardrails)** — Fase 2: rate limit, horário, filtro de conteúdo.
3. **Prompt Builder** monta o prompt do sistema com base na persona (fixa na Fase 1, configurável na Fase 2).
4. **Chamada ao LLM** (Claude API) com o prompt montado + mensagem do usuário.
5. **Sender.py** envia a resposta de volta chamando o WuzAPI: `POST /chat/send/text`.
6. **Log da interação** — Fase 2, com banco de dados.

---

## 5-8. Configurabilidade, Guardrails, Roadmap e Instrução Claude Code

Ver histórico da conversa / commit inicial para o plano completo de fases 2-4
(configurabilidade via banco, guardrails, painel web, comercial/SaaS).
