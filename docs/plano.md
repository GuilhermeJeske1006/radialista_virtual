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

## 3. Estrutura de Pastas Sugerida (para o Claude Code criar)

```
radialista-ia/
├── backend/
│   ├── app/
│   │   ├── main.py                # FastAPI entrypoint
│   │   ├── config/
│   │   │   └── personas.py        # Definições de personalidade/tom
│   │   ├── whatsapp/
│   │   │   ├── webhook.py         # Recebe eventos do WuzAPI (mensagens recebidas)
│   │   │   ├── sender.py          # Envia respostas via WuzAPI (POST /chat/send/text)
│   │   │   └── session_manager.py # Cria/gerencia usuários e sessões no WuzAPI (QR code, conexão)
│   │   ├── llm/
│   │   │   ├── client.py          # Chamada à API do modelo (Claude/GPT)
│   │   │   └── prompt_builder.py  # Monta o system prompt com base na config
│   │   ├── guardrails/
│   │   │   ├── content_filter.py  # Filtro de temas permitidos
│   │   │   ├── rate_limiter.py    # Limite de mensagens por usuário/hora
│   │   │   └── schedule.py        # Janela de horário de atendimento
│   │   ├── models/                # Modelos do banco (SQLAlchemy)
│   │   └── db/
│   ├── requirements.txt
│   └── Dockerfile
├── wuzapi/                          # Serviço WuzAPI (imagem oficial, self-hosted)
│   ├── docker-compose.yml           # Sobe o container do WuzAPI + Postgres próprio dele
│   └── .env                         # WUZAPI_ADMIN_TOKEN, WEBHOOK_FORMAT, etc.
├── frontend-painel/                # Painel de configuração (Next.js)
│   └── ...
└── docs/
    └── plano-radialista-ia-whatsapp.md
```

---

## 4. Fluxo de Funcionamento (Passo a Passo)

0. **Pareamento inicial (uma vez por rádio/cliente)**: via `session_manager.py`, cria-se um usuário no WuzAPI (`POST /admin/users`, com token admin) e a rádio escaneia o QR Code (endpoint `/login` do WuzAPI) com o WhatsApp do número que vai atender. A partir daí a sessão fica conectada e persistente no container.
1. **Ouvinte envia mensagem no WhatsApp** → o WuzAPI recebe via WhatsApp (whatsmeow) e dispara um **webhook HTTP** configurado (`WUZAPI_GLOBAL_WEBHOOK` ou webhook por usuário) para o seu endpoint `/webhook/whatsapp` no backend.
2. **Camada de travas (guardrails)** processa antes de qualquer resposta:
   - `rate_limiter.py`: verifica se o usuário excedeu o limite de mensagens (ex: 10/hora).
   - `schedule.py`: verifica se está dentro do horário configurado de atendimento.
   - `content_filter.py`: verifica se o assunto está dentro dos tópicos permitidos pela rádio.
   - Se qualquer trava bloquear → responde com mensagem padrão de recusa educada.
3. **Prompt Builder** monta o prompt do sistema dinamicamente, puxando do banco:
   - Tom de voz configurado (formal/informal)
   - Nome/persona do locutor
   - Tópicos e regras específicas daquela rádio
4. **Chamada ao LLM** (Claude API) com o prompt montado + mensagem do usuário.
5. **Resposta é formatada** no estilo do locutor (curta, natural, adequada ao WhatsApp).
6. **Sender.py** envia a resposta de volta chamando o WuzAPI: `POST /chat/send/text`, com o header `token` do usuário/rádio e o corpo `{"Phone": "...", "Body": "..."}`.
7. **Log da interação** salvo no banco para métricas e auditoria.

> Observação: como o WuzAPI é self-hosted (roda em container seu), você precisa manter esse serviço no ar 24/7 — ele é o elo entre seu backend e o WhatsApp de cada rádio. Cada rádio = um "usuário" dentro do WuzAPI, com seu próprio token e sessão.

---

## 5. Sistema de Configuração (o "enlatado" do programa)

Painel onde o cliente (rádio) define, via formulário:
- Nome do locutor virtual
- Tom: slider entre "Informal/descontraído" ↔ "Formal/noticiário"
- Lista de temas permitidos (ex: trânsito, clima, música, notícias locais)
- Lista de temas proibidos (ex: política, temas sensíveis)
- Horário de funcionamento do bot
- Limite de mensagens por ouvinte/dia
- Mensagens padrão (saudação, despedida, recusa)

Essas configurações ficam salvas como um registro JSON no banco, vinculado ao número de WhatsApp daquela rádio, e são carregadas a cada requisição pelo `prompt_builder.py`.

---

## 6. Guardrails — Detalhamento

- **Rate limiting**: Redis com chave `user_id:hora`, expira a cada 1h.
- **Filtro de conteúdo**: duas camadas — (1) lista de tópicos permitidos/proibidos definida pela rádio, (2) filtro de segurança geral (violência, ilegalidade, etc.) sempre ativo, não configurável pelo cliente.
- **Horário**: comparação simples de `datetime.now()` contra janela configurada, com fuso horário do cliente.
- **Fallback**: se qualquer trava disparar, resposta padrão amigável, nunca erro técnico exposto ao usuário.

---

## 7. Roadmap de Implementação (MVP → Produto)

**Fase 1 — MVP**
- Subir o WuzAPI via Docker (`docker pull asternic/wuzapi`), configurar `.env` com `WUZAPI_ADMIN_TOKEN`
- Criar um usuário de teste no WuzAPI e parear via QR Code
- Backend FastAPI com endpoint `/webhook/whatsapp` recebendo eventos do WuzAPI
- Um único perfil de locutor fixo (sem painel ainda)
- Chamada direta à API do Claude, resposta enviada de volta via `POST /chat/send/text` do WuzAPI

**Fase 2 — Configurabilidade**
- Banco de dados com tabela de configurações por cliente
- Prompt builder dinâmico
- Guardrails básicos (rate limit + horário)

**Fase 3 — Painel Web**
- Painel Next.js para o cliente configurar o locutor sem precisar mexer em código
- Autenticação multi-cliente (multi-tenant)

**Fase 4 — Comercial**
- Sistema de planos/assinatura (Stripe ou gateway nacional)
- Métricas de uso por cliente
- Automatizar criação de novo usuário no WuzAPI para cada rádio que assina o plano (via `session_manager.py`), com fluxo de onboarding guiado (mostrar QR Code no painel para a rádio escanear)

---

## 8. Instrução Sugerida para o Claude Code

Ao rodar este plano no Claude Code, use algo como:

> "Crie a estrutura de pastas descrita na seção 3 deste documento. Suba o WuzAPI via Docker Compose. Implemente a Fase 1 do roadmap (seção 7): um backend FastAPI com endpoint `/webhook/whatsapp` que recebe eventos do WuzAPI, monta um prompt fixo de locutor de rádio e chama a API do Claude para gerar a resposta, devolvendo-a via `POST /chat/send/text` do WuzAPI. Use variáveis de ambiente para as chaves de API e para o token do WuzAPI."

Depois, iterar fase por fase, pedindo para adicionar o banco de dados, os guardrails e por fim o painel.