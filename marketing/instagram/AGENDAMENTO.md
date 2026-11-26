# Agendamento no Meta Business Suite: estado e como continuar

Atualizado em 26/11/2026 (noite: legendas corrigidas nos 28 agendados; tarde: reels V5/V7 e stories S1-S3 agendados). Conta: Locufy Brasil (Facebook) + locufybrasil (Instagram), publicando nos dois.
Fonte de tudo (datas, arquivos, legendas): `marketing/instagram/out/agenda.json`.

## Já agendado (19:00, FB + IG, sem turbinar)

| Data | Post |
|---|---|
| qui 26/11 | T02 Black Friday (4) |
| sáb 28/11 | T01 NÃOvembro (1) |
| seg 30/11 | T03 Plantão (5) |
| qui 03/12 | A Como funciona (6) |
| sex 04/12 | T05 5 especiais (7) |
| ter 08/12 | Post05 Patrocinadores (1) |
| seg 14/12 | T09 Mais ouvido que pago (4) |
| qua 16/12 | T10 Mito ou verdade (6) |
| sex 18/12 | T11 Avise o ouvinte (5) |
| seg 21/12 | T12 Papai Noel (1) |
| ter 22/12 | B Quanto custa (6) |
| qua 23/12 | T13 POV (1) |
| ter 01/12 | Reel V5 Pedido ao vivo (19:00) |
| qui 10/12 | Reel V7 Patrocinador (19:00) |
| qui 03/12 12:30 | Story S1 (3 imagens) |
| qua 09/12 12:30 | Story S2 (4 imagens, link #demonstracao no 4º, só FB) |
| ter 22/12 12:30 | Story S3 (S3-2, link #simulador, só FB) |

## Falta agendar

Feed (composer de post, 19:00):

| Data | Post | Arquivos |
|---|---|---|
| seg 28/12 | T14 Retrospectiva (5) | `out/drive/Tendências/T14-*` |
| ter 05/01/2027 | Post06 Travas (1) | `out/legado/Post06-Travas.png` |
| ter 12/01 | C 5 perguntas (7) | `out/drive/Feed/C*` |
| qui 14/01 | Post04 Vozes (1) | `out/legado/Post04-Vozes.png` |
| ter 19/01 | P1 Biblioteca (1) | `out/drive/Feed/P1*` |
| qui 21/01 | P2 Essência de rádio (1) | `out/drive/Feed/P2*` |

Reels (composer de reel, 19:00):

| Data | Reel | Arquivo |
|---|---|---|
| ter 01/12 | V5 Pedido ao vivo | `marketing/reels/V5/out/V5.mp4` |
| qui 10/12 | V7 Patrocinador | `marketing/reels/V7/out/V7.mp4` |
| ter 29/12 | V8 Quanto custa | `marketing/reels/V8/out/V8.mp4` (versão 14/10, sem "grátis") |
| qui 07/01 | V9 O que a IA não leva | `marketing/reels/V9/out/V9.mp4` |
| ter 26/01 | V4 Montando um programa | `out/legado/V4-27s.mp4` (cortado em 27 s, sem "conta grátis") |

Stories (composer de story, 12:30, até 10 mídias por story):

| Data | Story | Arquivos | Obs. |
|---|---|---|---|
| qui 03/12 | S1 | S1-1, S1-2, S1-4 | S1-3 (enquete) vai à mão no app |
| qua 09/12 | S2 | S2-1 a S2-4 | S2-4: link `https://locufybr.com/#demonstracao` se o composer tiver figurinha de link |
| ter 22/12 | S3 | S3-2 | S3-1 (teste) vai à mão antes das 12:30; S3-2: link `#simulador` |

Fora do calendário, por decisão do usuário: V6 (fala do feriado de 12/10) e Post 07 antigo ("sem cartão", "grátis").

## Como foi feito (repetir)

1. Aba nova, `https://business.facebook.com/latest/composer/?business_id=2985981885092456&asset_id=1379415998583420`, esperar ~6 s.
2. Rodar o JS abaixo (intercepta o seletor de arquivos e cria os auxiliares).
3. Clicar "Adicionar foto/vídeo"; `find` "file input labeled Captura de upload Locufy"; `file_upload` com os caminhos absolutos (até 10 MB por chamada).
4. `window.__legenda("<legenda do agenda.json>")`, depois `window.__ligar()` e `JSON.stringify(window.__campos())` para as coordenadas.
5. Para Facebook e Instagram: triple_click na data, digitar `dd/mm/aaaa`, Enter; clicar na hora, digitar `19`; clicar no minuto, digitar `00`. Conferir com zoom.
6. Clicar "Programar" (pegar a posição pelo `find`: a janela mudou de tamanho no meio da sessão). No aviso "Turbinar", sair sem turbinar.

Cuidado: não clicar na linha "Definir data e hora" depois de preencher (desliga o agendamento).

```js
(() => { if (!window.__capUpload) { window.__capUpload = true; const orig = HTMLInputElement.prototype.click; HTMLInputElement.prototype.click = function () { if (this.type === 'file') { document.querySelectorAll('input[data-captura]').forEach(e => { if (e !== this) { e.removeAttribute('data-captura'); e.removeAttribute('aria-label'); } }); this.setAttribute('data-captura', '1'); this.setAttribute('aria-label', 'Captura de upload Locufy'); if (!this.isConnected) { this.style.cssText = 'position:fixed;left:0;top:0;width:1px;height:1px;opacity:0'; document.body.appendChild(this); } return; } return orig.call(this); }; }
window.__legenda = (texto) => { const ed = document.querySelector('div[contenteditable=true]'); if (!ed) return 'sem editor'; ed.focus(); document.execCommand('selectAll'); document.execCommand('delete'); texto.split('\n').forEach((p, i) => { if (i) document.execCommand('insertParagraph'); if (p) document.execCommand('insertText', false, p); }); return ed.innerText.length; };
window.__campos = () => { const S = 1455 / innerWidth; /* trocar 1455 pela largura do quadro da captura de tela atual */ return [...document.querySelectorAll('input')].filter(i => i.offsetParent && (i.placeholder === 'dd/mm/aaaa' || i.getAttribute('role') === 'spinbutton')).map(i => { const r = i.getBoundingClientRect(); return { t: i.placeholder ? 'data' : i.getAttribute('aria-label'), v: i.value, x: Math.round((r.x + r.width / 2) * S), y: Math.round((r.y + r.height / 2) * S) }; }); };
window.__ligar = () => { const sw = [...document.querySelectorAll('[role=switch]')].find(e => (e.getAttribute('aria-label') || '') === 'Definir data e hora'); if (!sw) return 'sem switch'; sw.scrollIntoView({block: 'center'}); if (!window.__campos().length) sw.click(); return 'ok'; };
return 'ok'; })()
```

Reels e stories ainda não foram testados: o composer de reel e o de story (`/latest/story_composer/`) podem ter campos diferentes. Olhar a tela antes de seguir o mesmo roteiro.

No fim, conferir tudo no Planner (`/latest/content_calendar`, visão Mês) e na aba Programados.

## Aprendizados de 26/11 (tarde)

- **Limite de 29 dias, vale para feed, reel e story.** Mensagem do Meta: "Os posts programados precisam ser compartilhados entre 20 minutos e 29 dias após o momento da criação". Em 26/11 o limite é 25/12. O calendário do composer de feed e de story já esconde os dias além; o de reel mostra, mas a validação recusa ao preencher a hora (testado com V8 em 29/12). Não burlar. Voltar a agendar o resto conforme as datas entram na janela (dia D só dá para agendar item com data <= D+29).
- **Digitar data não funciona**: clicar no campo abre calendário; usar a seta de próximo mês e clicar no dia. Hora/minuto: clicar no campo da hora, digitar, clicar no minuto, digitar (as coordenadas mudam com o tamanho da janela: sempre fazer zoom e conferir).
- **Reel**: `https://business.facebook.com/latest/reels_composer/?business_id=2985981885092456&asset_id=1379415998583420`. Passos: Adicionar vídeo → upload → legenda (`__legenda`) → Avançar → Avançar (Editar: nada) → na aba Compartilhar clicar **Programar** (o botão principal vira "Compartilhar agora" = publica na hora se não trocar a aba!) → datas FB e IG → botão Programar → Concluir.
- **Story**: `.../latest/story_composer/?business_id=...&asset_id=...`. Upload múltiplo, aba Programar, datas FB e IG. Cada imagem tem "Adicionar link" (link de deslizar só vale no Facebook; no Instagram precisa figurinha de link via Editar, não feito). Planner semanal não mostra stories; conferir em Conteúdo > Stories > Programado.
- **Quando agendar cada item que falta** (data de publicação menos 29 dias): T14 28/12 → a partir de 29/11; V8 29/12 → 30/11; Post06 05/01 → 07/12; V9 07/01 → 09/12; C 12/01 → 14/12; Post04 14/01 → 16/12; P1 19/01 → 21/12; P2 21/01 → 23/12; V4 26/01 → 28/12.
- Falta ainda: feed T14 (28/12), Post06, C, Post04, P1, P2; reels V8 (29/12), V9 (07/01), V4-27s (26/01); figurinha de link do Instagram nos stories S2-4 e S3-2; enquete S1-3 e teste S3-1 à mão.

## ATENÇÃO: legenda (corrige o roteiro acima)

- **O `window.__legenda` (execCommand) NÃO persiste**: o texto aparece no editor mas o Meta agenda sem legenda (lista mostra "Este post não tem texto"). Todos os 14 itens agendados em 26/11 saíram sem legenda e foram corrigidos à mão (editar post agendado, 28 linhas = 14 itens x FB/IG).
- **Método que funciona**: clicar no campo de texto (ou `document.querySelector('div[contenteditable=true]').focus()` via JS) e digitar com a ação `type` do computer (texto real, com emoji ok). Conferir a prévia à direita mostrando a legenda antes de salvar.
- **Nunca digitar sem ter certeza de que o editor está focado**: se o foco estiver na caixa "Comente como Locufy Brasil" do painel de detalhes, cada Enter da legenda posta um comentário. Aconteceu uma vez (post B, FB, 22/12): 5 comentários foram criados e já foram apagados.
- **Rascunho não guarda legenda** (nem digitada). (O rascunho T14 de teste foi apagado.)
- **Editar agendado**: Conteúdo > Programados > clicar na linha > "..." do painel de detalhes > "Editar post" > editor com campo Texto > Programar (salva). Reel do Instagram abre um modal (Criar > Avançar > Programar). Cada post agendado é duplo (uma linha FB e uma IG): são 2 edições por item. Após editar, a ordem FB/IG das linhas troca.
- Na lista, `find` enxerga todas as linhas (gridcell com data e plataforma) depois de rolar com Page_Down; o `ref` clica a linha sem precisar rolar.
