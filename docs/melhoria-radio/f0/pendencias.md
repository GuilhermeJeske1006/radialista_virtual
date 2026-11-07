# Pendências registradas na F0

Ideias e achados fora do escopo da F0 (bancada de medição). Nada aqui foi implementado.

## Para as próximas frentes
- **F1 (relógio e hard time):** o encerramento é decidido na geração, dois blocos antes de ir ao ar, e é cortado
  pelo watchdog nos três perfis (ver `baseline.md`, seção Simulação, e `as_run["blocos_nao_tocados"]`). O relógio
  precisa ser consultado com o horário previsto de reprodução. Adotar `inicio_s` nos presets de relógio e testar a
  igualdade com `backend/tests/fixtures/programas/relogios/`.
- **F1/F6:** no formato padrão, a `abertura` do começo de cada volta vira `comentario` quando o bloco anterior é
  patrocinador (regra de `_tipo_proximo_bloco`); em `popular_sertanejo` a segunda volta não tem abertura.
- **F2/F6:** divergência de orçamento no formato musical: o backend limita `retomada` a 6–12 s e `identificacao` a
  3–7 s (`app/live/formato.py`), a pesquisa propõe link de 10–35 s. O formato padrão não tem orçamento nenhum
  (o excesso injetado em `variedades_leves` foi ao ar sem revisão).
- **F2:** rodar o modo `completo` (com aprovação explícita do usuário) para medir `wpm_observado` por voz.
- **F3:** `_musicas_citadas_na_fala` roda também no formato musical para blocos que não são de música (retomada,
  identificação): uma faixa citada numa retomada toca se existir no acervo. A auditoria supunha que no formato
  musical música citada nunca toca; vale só para o bloco de música.
- **F3:** timeout e degradação do Redis (`app/config/redis_client.py` sem `socket_timeout`), item 6 de
  `docs/auditoria.md`.
- **F4:** pedido de música indisponível no fluxo novo vira fala com o nome do ouvinte e estado `nao_atendido`;
  pela regra editorial deveria ficar na fila sem ser anunciado.
- **F6:** TTL ou teto no hash `cache:categoria_bloco_customizado` (item 9 de `docs/auditoria.md`).
- **F8:** a checagem de repetição do backend (Jaccard sobre o conjunto de palavras, sem descontar palavras
  funcionais) dispara com facilidade em falas longas, como os quadros de variedades.
- **F13:** a simulação é de locutor único; diálogo multivoz e o GET `/preparo` ficaram de fora.

## Bancada e ferramentas
- Ajustar a skill `avaliar-locucao` para ler `as_run["eventos"]`, aceitar `musica_anunciada` como lista e
  reaproveitar `resumo.json` em vez de recalcular as métricas.
- Incluir `scripts/simular_hora.py` e `scripts/simulacao` no `ruff check` do CI (`.github/workflows/backend-ci.yml`
  só cobre `app` e `tests`).
- O CLI importa `app.main`, que grava log em `logs/app.log` relativo ao diretório atual: rodar a partir de `backend/`.
- `docs/benchmarks/2026-11-06-formatos/casos.json` ganhou a chave `abertura_repetida` em `esperado` (além das oito
  da auditoria) para dar rótulo determinístico aos casos da F8.

## Fora do plano de rádio
- JWT de 7 dias sem revogação na troca de senha (item 4 de `docs/auditoria.md`): registrar no `RELATORIO.md`.
