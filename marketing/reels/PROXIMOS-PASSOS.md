# Reels da Locufy: estado e próximos passos

Atualizado em 13/10/2026, depois da rodada que revisou e aprovou os 9 Reels (V1 a V9).
Os commits estão em branches locais; nada foi enviado ao GitHub nem publicado.

## Estado atual

Os 9 vídeos estão em `marketing/reels/<id>/out/<id>.mp4` (1080x1920), com a capa em `out/capa.jpg`.
O parecer de cada um está em `marketing/reels/<id>/revisao.md`. Todos estão **APROVADOS**.

| Vídeo | Duração | Revisão |
| --- | --- | --- |
| V1 Esse radialista não existe | ~21,7 s | aprovado em 12/10; mudanças de 13/10 conferidas por quadros |
| V2 Criando uma radialista do zero | ~19,7 s | aprovado em 13/10 (vozes de outra conta não aparecem mais) |
| V3 Conectando o WhatsApp da rádio | ~21,4 s | aprovado em 12/10; mudanças de 13/10 conferidas por quadros |
| V4 Montando um programa | ~30,1 s | reprovado e depois aprovado em 13/10 (destaque do clique) |
| V5 Pedido do ouvinte ao vivo | ~26,9 s | aprovado em 13/10 (resposta do WhatsApp nova) |
| V6 Três radialistas conversando | ~46,5 s | aprovado em 13/10 (Zé, Lia e Beto falam) |
| V7 Patrocinador lido ao vivo | ~21,2 s | aprovado em 13/10 (efeitos com acento) |
| V8 Quanto custa uma hora no ar | ~20,3 s | refeito e aprovado em 14/10: cadastro agora exige assinatura, CTA virou "Crie sua conta pelo link na bio" (commit 7a29064) |
| V9 O que a IA não leva ao ar | ~14,5 s | aprovado em 12/10; mudanças de 13/10 conferidas por quadros |

Mudanças comuns feitas em 13/10, já renderizadas em todos:

- **Legendas:** a paginação é feita por programação dinâmica (`dividir()` em `marketing/tools/preparar.mjs`).
  - Não termina página em de/do/da/na/e/um, não parte números por extenso ("noventa e oito / vírgula sete"), nomes próprios nem número e o que ele conta.
  - A montagem também escolhe a quebra de linha dentro da página (campo `quebra`).
  - A largura de cada palavra é estimada com medidas reais da Nunito 900.
  - Quando a cena usa `legenda` ("R$ 69,90" no lugar de "Sessenta e nove e noventa"), o tempo vem do alinhamento da fala.
- **Selo "Rádio e ouvintes fictícios":** aparece nas cenas de painel e de celular, como no site.
- **Destaques:**
  - o destaque de clique termina no próprio clique;
  - no ao vivo, o painel já entra desfocado;
  - `sem_destaque` tira o holofote de uma ação.
- **Opções novas no roteiro:**
  - `cortar_inicio_s` pula o começo da gravação;
  - rótulo e zoom do roteiro valem sobre a gravação, sem regravar.

## Commits (branches locais, sem push)

- `fix/atendimento-ouvinte`: só as correções do produto, em 4 commits sobre o master.
  - JSON entre crases no filtro e na classificação.
  - Respostas ao ouvinte (frequência escrita no WhatsApp, nome do contato, fila de participações, sem tempo de espera inventado no ao vivo).
  - Acentos nos efeitos sonoros padrão, com renomeação das contas antigas no backfill.
  - Rótulos e falas do painel.
- `marketing/reels-profissionais`: os mesmos 4 commits, mais o pipeline dos Reels e a trilha e os efeitos (`marketing/brand/trilha.mp3`, `marketing/brand/sfx/`).

Push no master = deploy em produção. Caminho sugerido:

1. PR de `fix/atendimento-ouvinte`.
2. Depois, PR de `marketing/reels-profissionais`; a diferença dele cai para só o pipeline.

## Antes de publicar

- **V1, V5 e V6:** o ao vivo foi gravado em 12/10 e fala em "feriado de Nossa Senhora Aparecida". Se for publicar depois, regravar esses três. Use `--refazer` só no que precisar.
- **Link da bio:** precisa levar a https://locufybr.com/#ouvir.
- **Frequência:** numa busca, não apareceu emissora em 98,7 nem "Rádio Cidade FM" em São João Batista (SC); a mais próxima é a Menina Linda 98,3. Só a Anatel confirma.

## Ajustes conhecidos que exigem regravar (nenhum bloqueia)

- **V2:**
  - um quadro de "Carregando..." em 00:09,17;
  - o cursor fica parado sobre "Alegre e acolhedora".
- **V3:** fechar no estado "conectado" exigiria simular o status do WuzAPI.
- **V4:**
  - esperar 400–500 ms antes de cada tópico;
  - clicar "Marcar todos" antes dos horários (o aviso "Nenhum dia marcado" fica atrás da legenda);
  - "Das 5h às 6h" aparece rápido;
  - 2 quadros de efeitos sem acento (gravação antiga).
- **V5:**
  - 4,5 s sem voz enquanto a resposta do WhatsApp fica na tela;
  - "Não posso garantir quando vai ao ar" ainda sugere que vai ao ar.
- **V7:**
  - "spot gravado" é dito sem imagem de spot;
  - "Nada cadastrado nessa categoria." em 4 categorias.
- **V8:** "Nenhum uso registrado" e "Nenhuma fatura emitida" no /billing (exigiria usos e fatura no seed).

## Sugestões para o site (dos revisores)

- Dizer que o texto do patrocinador é lido pela voz do radialista.
- Uma linha sobre programas com mais de uma voz (radialistas conversando).

## Como o pipeline funciona

Ver `marketing/reels/README.md`. Formato dos roteiros: `.claude/agents/roteirista-reels.md`.

Armadilhas, também na memória do projeto (`project_reels_producao.md`):

- **Horário do ao vivo:** só entra no ar sozinho das 6h às 22h.
- **V3:** o clique em "Conectar WhatsApp" troca a credencial WuzAPI da conta demo; o seed restaura.
- **V4:** cria um programa que gera vinhetas no S3 local; o seed apaga as sobras.
- **Bloco do ao vivo:** use `ao_vivo` por texto ou por tipo, nunca por número.
