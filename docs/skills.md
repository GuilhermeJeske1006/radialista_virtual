# Skills de agente

Skills versionadas no repo pra agentes de código (Claude Code e compatíveis com o ecossistema
[`npx skills`](https://github.com/vercel-labs/skills)). Cada skill é uma pasta com `SKILL.md`
(frontmatter `name` + `description` decide quando o agente carrega) e, às vezes, `references/`.

## Onde ficam

| Pasta | Quem enxerga |
|---|---|
| `.claude/skills/` | Claude Code (carregada automaticamente na sessão) |
| `.agents/skills/` | Pasta padrão do `npx skills` — Claude Code **não** lê daqui; pra ativar, criar symlink em `.claude/skills/` (como já feito com `text-to-speech`) |

`skills-lock.json` registra origem e hash das skills instaladas via `npx skills add`. Skill
escrita à mão (sem origem externa) não entra no lock.

## Disponíveis

| Skill | Pasta | Origem | Ativa no Claude Code | Uso |
|---|---|---|---|---|
| `text-to-speech` | `.agents/skills/` (symlink em `.claude/skills/`) | `elevenlabs/skills` | sim | API de TTS da ElevenLabs: modelos, `voice_settings`, streaming. Base dos benchmarks de voz ([vozes-padrao-catalogo.md](benchmarks/2026-09-10/vozes-padrao-catalogo.md)) |
| `speech-to-text` | `.claude/skills/` | `elevenlabs/skills` | sim | Transcrição com Scribe v2 (batch e realtime). Usada pra calcular WER nos benchmarks de combinações ([README](benchmarks/2026-09-25-combinacoes/README.md)) |
| `llm-evaluation` | `.claude/skills/` | `wshobson/agents` | sim | Métricas automáticas, LLM-as-judge, A/B e benchmarks de apps com LLM. Padrão do juiz nos benchmarks de combinações |
| `frontend-design` | `.agents/skills/` | `anthropics/skills` | não | Direção visual pra UI nova ou redesenho (paleta, tipografia, layout fora do template) |
| `seo-audit` | `.agents/skills/` | `coreyhaines31/marketingskills` | não | Auditoria de SEO técnico e on-page (meta tags, indexação, Core Web Vitals) — relevante pra `landing-page/` |
| `find-skills` | `.agents/skills/` | `vercel-labs/skills` | não | Busca e instala skills do marketplace (`npx skills find`) |

## Gerenciar

```
npx skills find <termo>              # buscar no marketplace
npx skills add <owner/repo@skill>    # instalar (vai pra .agents/skills + skills-lock.json)
npx skills update                    # atualizar todas as instaladas
ln -s ../../.agents/skills/<skill> .claude/skills/<skill>   # expor pro Claude Code
```

Skills globais do usuário (`~/.claude/skills`) e de plugins não são versionadas aqui e variam
por máquina.
