# Como usar o pacote de melhoria de rádio

1. Descompacte na raiz do repositório `radialista_virtual` (os caminhos já batem):
   - `docs/plano-melhoria-radio.md` — o plano, frente por frente
   - `docs/pesquisa-radio-locufy.md` — a pesquisa de origem
   - `.claude/skills/melhoria-radio/` — o comando `/melhoria-radio`
   - `.claude/skills/referencia-radio/`, `.claude/skills/avaliar-locucao/` — skills de apoio
   - `.claude/agents/auditor-radio.md`, `implementador-locufy.md`, `testador-locufy.md`, `juiz-locucao.md`
2. Commit desses arquivos numa branch própria (o comando para se houver alterações pendentes).
3. Abra o Claude Code na raiz do repositório e rode, nesta ordem:

```
/melhoria-radio f0                 # linha de base + simulador de uma hora (sem custo)
/melhoria-radio p0 --so-auditar    # confere o estado real das frentes F1–F5 sem mexer em código
/melhoria-radio p0                 # implementa, testa e avalia F1–F5
/melhoria-radio p1
/melhoria-radio p2
```

Também dá para rodar uma frente só: `/melhoria-radio f4`.

O resultado de cada frente fica em `docs/melhoria-radio/<frente>/` e o resumo em
`docs/melhoria-radio/RELATORIO.md`. Cada frente vira uma branch `melhoria/<frente>-…`, sem push.

Chamadas pagas (Anthropic, ElevenLabs) só acontecem se você aprovar no chat quando o comando
pedir — necessárias para a avaliação de qualidade das falas (`--modo llm`).

Atualize a tabela de `docs/skills.md` com as duas skills novas, se quiser mantê-la completa.
