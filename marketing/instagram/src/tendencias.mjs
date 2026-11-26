// Posts de feed baseados nas tendências de fim de 2026.
// Pesquisa: ../reports/Tendências Instagram rádio fim de 2026.md (fila de 17 posts; aqui estão 10).
// Dados externos sempre com fonte e recorte na própria arte.
import { tela, forma, ICONE, feed } from './pecas.mjs';

const CAIXA = `<svg viewBox="0 0 44 44" aria-hidden="true"><rect x="3" y="3" width="38" height="38" rx="9" fill="none" stroke="#00B4D8" stroke-width="2.4"/></svg>`;
const item = (txt, ic = ICONE.ok) => `<div class="item">${ic}<span>${txt}</span></div>`;
const FLEX = '<p class="preco-flex" style="margin-top:auto;margin-bottom:52px">Locufy Flex: <b>R$ 69,90/mês</b> + uso de IA.</p>';
const ESPELHO = 'Espelho de dezembro';

// ---------- T01 · NÃOvembro (até 30/11) ----------
const T01 = [{
  id: 'T01', alt: 'NÃOvembro na rádio: não à madrugada sem voz, não à vinheta repetida o ano inteiro, não ao WhatsApp sem resposta, não ao feriado com buraco na escala.',
  html: feed({
    rotulo: 'Trend do mês', base: '',
    miolo: `
    <h1 class="h g" style="margin-top:64px"><span class="acc">NÃO</span>vembro na rádio.</h1>
    <div class="espelho nao" style="margin-top:64px">
      <div class="lin"><span class="n">NÃO</span><span class="t">à madrugada sem voz.</span></div>
      <div class="lin"><span class="n">NÃO</span><span class="t">à vinheta repetida o ano inteiro.</span></div>
      <div class="lin"><span class="n">NÃO</span><span class="t">ao WhatsApp sem resposta no meio do programa.</span></div>
      <div class="lin"><span class="n">NÃO</span><span class="t">ao feriado com buraco na escala.</span></div>
    </div>
    <p class="lead" style="margin-top:auto;margin-bottom:48px">Dezembro chega com dois feriadões. <b>A escala se decide agora.</b></p>`,
  }),
}];

// ---------- T02 · Black Friday (26/11) ----------
const T02 = [
  {
    id: 'T02-1', alt: 'Black Friday é dia de anunciante no ar. Sexta, 27 de novembro: o varejo local quer espaço na rádio o dia inteiro.',
    html: feed({
      rotulo: 'Black Friday · 27/11', cont: '01/04',
      miolo: `
      <h1 class="h g" style="margin-top:72px">Black Friday é dia de <span class="acc">anunciante no ar.</span></h1>
      <p class="lead" style="margin-top:40px">Sexta, 27/11. O varejo local quer espaço na rádio o dia inteiro.</p>
      <div style="margin-top:auto;margin-bottom:56px">${forma({ w: 920, h: 170, semente: 41 })}</div>`,
    }),
  },
  {
    id: 'T02-2', alt: 'O rádio teve 5.982 anunciantes e 2,2 milhões de inserções no 1º semestre de 2026, segundo o Audio Pulse 2026 do Ibope.',
    html: feed({
      rotulo: 'Black Friday · Dados', cont: '02/04',
      miolo: `
      <h2 class="h m" style="margin-top:56px">O comercial do rádio <span class="acc">está vivo.</span></h2>
      <div class="stat m" style="margin-top:80px"><div class="num">5.982</div><p class="rot">anunciantes no rádio no <b>1º semestre de 2026</b>.</p></div>
      <div class="stat m" style="margin-top:64px"><div class="num">2,2<span class="u">mi</span></div><p class="rot">de inserções no mesmo período.</p></div>
      <p class="nota" style="margin-top:auto;margin-bottom:40px">Fonte: Audio Pulse 2026 (Ibope), 1º semestre de 2026.</p>`,
    }),
  },
  {
    id: 'T02-3', alt: 'Na Locufy, o dia cabe no painel: spots e vinhetas por categoria, um programa especial na grade só para a sexta e o ouvinte participando pelo WhatsApp.',
    html: feed({
      rotulo: 'Black Friday · No painel', cont: '03/04',
      miolo: `
      <h2 class="h" style="margin-top:56px">O dia cabe <span class="acc">no painel.</span></h2>
      <div class="itens" style="margin-top:72px;gap:40px">
        ${item('<b>Spots e vinhetas</b> por categoria, com nome e duração à vista.')}
        ${item('<b>Um programa especial</b> na grade, com tema só para a sexta.')}
        ${item('<b>Ouvinte participando</b> pelo WhatsApp durante a programação.')}
      </div>
      <p class="nota" style="margin-top:auto;margin-bottom:40px">Para o ao vivo, o painel fica aberto e ativo no computador da rádio.</p>`,
    }),
  },
  {
    id: 'T02-4', alt: 'Mande este post para quem cuida dos comerciais da rádio. locufybr.com. Locufy Flex: R$ 69,90 por mês mais uso de IA.',
    html: feed({
      rotulo: 'Black Friday', cont: '04/04', base: 'site', luz: 'baixa',
      miolo: `
      <h2 class="h g" style="margin-top:72px">Mande para quem cuida dos <span class="acc">comerciais.</span></h2>
      <p class="lead" style="margin-top:40px">Conheça o painel e ouça as amostras em locufybr.com.</p>
      ${FLEX}`,
    }),
  },
];

// ---------- T03 · Plantão de fim de ano (30/11) ----------
const T03 = [
  {
    id: 'T03-1', alt: 'Plantão de fim de ano: quem está no ar? Dois feriadões seguidos em 2026, e a escala se decide agora.',
    html: feed({
      rotulo: `${ESPELHO} · Plantão`, cont: '01/05',
      miolo: `
      <h1 class="h g" style="margin-top:72px">Plantão de fim de ano: <span class="acc">quem está no ar?</span></h1>
      <p class="lead" style="margin-top:40px">Dois feriadões seguidos em 2026. A escala se decide agora.</p>
      <div style="margin-top:auto;margin-bottom:56px">${forma({ w: 920, h: 150, semente: 17 })}</div>`,
    }),
  },
  {
    id: 'T03-2', alt: 'Calendário: 24/12 quinta, véspera, não é feriado; 25/12 sexta, Natal, feriado nacional; 31/12 quinta, véspera, não é feriado; 1/1 sexta, feriado nacional.',
    html: feed({
      rotulo: `${ESPELHO} · Datas`, cont: '02/05',
      miolo: `
      <h2 class="h m" style="margin-top:56px">Quatro dias que <span class="acc">mudam a escala.</span></h2>
      <div class="cal" style="margin-top:56px">
        <div class="dia"><div class="sem">Quinta</div><div class="data">24/12</div><div class="d">Véspera de Natal. Não é feriado.</div></div>
        <div class="dia feriado"><div class="sem">Sexta</div><div class="data">25/12</div><div class="d">Natal. Feriado nacional.</div></div>
        <div class="dia"><div class="sem">Quinta</div><div class="data">31/12</div><div class="d">Véspera de Ano Novo. Não é feriado.</div></div>
        <div class="dia feriado"><div class="sem">Sexta</div><div class="data">01/01</div><div class="d">Confraternização. Feriado nacional.</div></div>
      </div>
      <p class="nota" style="margin-top:auto;margin-bottom:40px">Feriado trabalhado: pagamento em dobro ou folga compensatória. Confira a convenção coletiva do seu sindicato.</p>`,
    }),
  },
  {
    id: 'T03-3', alt: 'Checklist antes de fechar a escala: quem cobre cada faixa nos quatro dias, quais especiais vão ao ar, vinhetas de Natal e Réveillon prontas, quem responde o WhatsApp, como fica a madrugada.',
    html: feed({
      rotulo: `${ESPELHO} · Checklist`, cont: '03/05',
      miolo: `
      <h2 class="h m" style="margin-top:56px">Antes de fechar <span class="acc">a escala.</span></h2>
      <div class="itens" style="margin-top:64px;gap:36px">
        ${item('Quem cobre cada faixa nos quatro dias?', CAIXA)}
        ${item('Quais especiais vão ao ar, e em que horário?', CAIXA)}
        ${item('As vinhetas de Natal e Réveillon estão prontas?', CAIXA)}
        ${item('Quem responde o WhatsApp do ouvinte?', CAIXA)}
        ${item('Como fica a madrugada?', CAIXA)}
      </div>
      <p class="lead" style="margin-top:auto;margin-bottom:48px">Salve para a reunião de escala.</p>`,
    }),
  },
  {
    id: 'T03-4', alt: 'Onde a Locufy entra: radialista com IA nas faixas que você definir na grade, programa especial com tema só para o dia, pedidos e recados pelo WhatsApp com histórico no painel.',
    html: feed({
      rotulo: `${ESPELHO} · Locufy`, cont: '04/05',
      miolo: `
      <h2 class="h" style="margin-top:56px">Onde a Locufy <span class="acc">entra.</span></h2>
      <div class="itens" style="margin-top:72px;gap:40px">
        ${item('<b>Radialista com IA</b> nas faixas que você definir na grade.')}
        ${item('<b>Programa especial</b> com tema só para o dia.')}
        ${item('<b>Pedidos e recados</b> pelo WhatsApp, com histórico no painel.')}
      </div>
      <p class="nota" style="margin-top:auto;margin-bottom:40px">Para o ao vivo, o painel fica aberto e ativo no computador da rádio.</p>`,
    }),
  },
  {
    id: 'T03-5', alt: 'Mande para quem monta a escala da rádio. locufybr.com.',
    html: feed({
      rotulo: ESPELHO, cont: '05/05', base: 'site', luz: 'baixa',
      miolo: `
      <h2 class="h g" style="margin-top:72px">Mande para quem monta <span class="acc">a escala.</span></h2>
      <p class="lead" style="margin-top:40px">E ouça as amostras de locução no site, sem criar conta.</p>
      ${FLEX}`,
    }),
  },
];

// ---------- T05 · 5 especiais de fim de ano (04/12) ----------
const ESPECIAIS = [
  ['As 100 mais pedidas', 'A contagem das músicas que o ouvinte mais pediu no ano, na véspera de Natal ou no dia 31.'],
  ['A contagem do dia 31', 'Um dia inteiro em ordem regressiva até a virada.'],
  ['A votação do ouvinte', 'O público escolhe as melhores do ano e a rádio toca o resultado.'],
  ['A mensagem de fim de ano', 'Uma vinheta especial com a voz da rádio para fechar o ano.'],
  ['O Natal temático', 'No dia 25, a programação inteira com clima de Natal.'],
];
const T05 = [
  {
    id: 'T05-1', alt: 'Capa: 5 especiais de fim de ano que as rádios já fazem, com a lista dos cinco.',
    html: feed({
      rotulo: `${ESPELHO} · Especiais`, cont: '01/07',
      miolo: `
      <h1 class="h" style="margin-top:64px">5 especiais de fim de ano que as rádios <span class="acc">já fazem.</span></h1>
      <div class="espelho" style="margin-top:auto;margin-bottom:56px">
        ${ESPECIAIS.map(([t], i) => `<div class="lin" style="padding:22px 0"><span class="n">0${i + 1}</span><span class="t" style="font-size:38px;font-weight:500">${t}</span></div>`).join('')}
      </div>`,
    }),
  },
  ...ESPECIAIS.map(([t, d], i) => ({
    id: `T05-${i + 2}`, alt: `Especial ${i + 1}: ${t}. ${d}`,
    html: feed({
      rotulo: `${ESPELHO} · Especial 0${i + 1}`, cont: `0${i + 2}/07`,
      miolo: `
      <div class="qnum" style="margin-top:56px">0${i + 1}</div>
      <h2 class="h g" style="margin-top:56px">${t}</h2>
      <p class="lead" style="margin-top:40px">${d}</p>
      <p class="nota" style="margin-top:auto;margin-bottom:40px">Formato usado por rádios brasileiras em anos anteriores. Fonte: Tudo Rádio.</p>`,
    }),
  })),
  {
    id: 'T05-7', alt: 'Monte o seu no painel: programa especial na grade com tema e horário só para o dia, pedidos do ouvinte pelo WhatsApp na fila de participações, vinhetas por categoria.',
    html: feed({
      rotulo: `${ESPELHO} · Locufy`, cont: '07/07', base: 'site', luz: 'baixa',
      miolo: `
      <h2 class="h" style="margin-top:56px">Monte o seu <span class="acc">no painel.</span></h2>
      <div class="itens" style="margin-top:64px;gap:36px">
        ${item('<b>Programa especial</b> na grade, com tema e horário só para o dia.')}
        ${item('<b>Pedidos do ouvinte</b> pelo WhatsApp, na fila de participações.')}
        ${item('<b>Vinhetas</b> organizadas por categoria na biblioteca.')}
      </div>
      <p class="lead" style="margin-top:auto;margin-bottom:52px">Salve para montar a grade de dezembro.</p>`,
    }),
  },
];

// ---------- T09 · Mais ouvido do que pago (14/12) ----------
const T09 = [
  {
    id: 'T09-1', alt: 'O rádio é mais ouvido do que pago.',
    html: feed({
      rotulo: 'Dados do rádio', cont: '01/04',
      miolo: `
      <h1 class="h g" style="margin-top:72px">O rádio é mais <span class="acc">ouvido</span> do que pago.</h1>
      <p class="lead" style="margin-top:40px">Dois números de 2026 para levar à próxima conversa com anunciante.</p>
      <div style="margin-top:auto;margin-bottom:56px">${forma({ w: 920, h: 150, semente: 53 })}</div>`,
    }),
  },
  {
    id: 'T09-2', alt: '77% da população de 15 anos ou mais ouve rádio, por 3 horas e 38 minutos por dia, nas 13 regiões metropolitanas do Audio Pulse 2026.',
    html: feed({
      rotulo: 'Dados do rádio · Audiência', cont: '02/04',
      miolo: `
      <div class="stat" style="margin-top:96px"><div class="num acc">77<span class="u">%</span></div><p class="rot">das pessoas de 15 anos ou mais <b>ouvem rádio</b>.</p></div>
      <div class="stat m" style="margin-top:80px"><div class="num">3h38</div><p class="rot">de escuta por dia.</p></div>
      <p class="nota" style="margin-top:auto;margin-bottom:40px">Fonte: Audio Pulse 2026 (Ibope). 13 regiões metropolitanas, 15 anos ou mais, abril a junho de 2026.</p>`,
    }),
  },
  {
    id: 'T09-3', alt: '3,4% da verba das agências foi para o rádio no 1º semestre de 2026, ou R$ 475,7 milhões, segundo o Cenp-Meios.',
    html: feed({
      rotulo: 'Dados do rádio · Verba', cont: '03/04',
      miolo: `
      <div class="stat" style="margin-top:96px"><div class="num acc">3,4<span class="u">%</span></div><p class="rot">da verba das agências foi para o rádio no <b>1º semestre de 2026</b>.</p></div>
      <div class="stat m" style="margin-top:80px"><div class="num">R$ 475,7<span class="u">mi</span></div><p class="rot">no período, em 4º lugar entre os meios.</p></div>
      <p class="nota" style="margin-top:auto;margin-bottom:40px">Fonte: Cenp-Meios, 1º semestre de 2026, agências participantes do painel.</p>`,
    }),
  },
  {
    id: 'T09-4', alt: 'A audiência existe. Use os números com o anunciante e mande este post para quem vende o comercial da rádio.',
    html: feed({
      rotulo: 'Dados do rádio', cont: '04/04', base: 'site', luz: 'baixa',
      miolo: `
      <h2 class="h g" style="margin-top:72px">A audiência existe. <span class="acc">Mostre.</span></h2>
      <p class="lead" style="margin-top:40px">Mande este post para quem vende o comercial da rádio.</p>
      <div style="margin-top:auto;margin-bottom:56px">${forma({ w: 920, h: 150, semente: 59 })}</div>`,
    }),
  },
];

// ---------- T10 · IA no rádio: mito ou verdade? (16/12) ----------
const MITOS = [
  ['Toda rádio já usa IA.', 'parte', 'Em parte',
    'Numa pesquisa com 19 emissoras, 7 usam IA de forma permanente e outras 7 estão testando.',
    'Fonte: Revista da SET, via Tudo Rádio, 2026. A amostra não representa o país.'],
  ['IA no rádio é só para cortar custo.', 'mito', 'Mito',
    'Mais da metade das emissoras da mesma pesquisa disse não planejar trocar funcionários por IA. Em Los Angeles, a Entravision, dona da José FM, disse que o DJ de IA custou mais que alguns apresentadores.',
    'Fontes: Revista da SET, via Tudo Rádio; LA Times, outubro de 2026.'],
  ['O ouvinte rejeita IA.', 'parte', 'Depende',
    'Num estudo nos EUA, 33% veriam a rádio de forma menos favorável e 47% não mudariam de opinião.',
    'Estudo com 1.326 ouvintes de rádio nos EUA, 2026. Não há dado equivalente no Brasil.'],
  ['A lei obriga a avisar o ouvinte.', 'mito', 'Ainda não',
    'O Brasil não tem lei geral de IA em vigor. O PL 2338/2023 passou no Senado em 2024 e está em análise na Câmara.',
    'Situação em novembro de 2026.'],
];
const T10 = [
  {
    id: 'T10-1', alt: 'IA no rádio: mito ou verdade? Quatro afirmações conferidas com dados.',
    html: feed({
      rotulo: 'IA no rádio', cont: '01/06',
      miolo: `
      <h1 class="h g" style="margin-top:72px">IA no rádio: <span class="acc">mito ou verdade?</span></h1>
      <p class="lead" style="margin-top:40px">Quatro frases que circulam entre radialistas, conferidas com dados.</p>
      <div style="margin-top:auto;margin-bottom:56px;display:flex;gap:20px"><span class="selo mito">Mito</span><span class="selo verdade">Verdade</span><span class="selo parte">Em parte</span></div>`,
    }),
  },
  ...MITOS.map(([af, cls, selo, txt, fonte], i) => ({
    id: `T10-${i + 2}`, alt: `${af} ${selo}. ${txt}`,
    html: feed({
      rotulo: `IA no rádio · 0${i + 1}`, cont: `0${i + 2}/06`,
      miolo: `
      <p class="afirma" style="margin-top:72px">${af}</p>
      <span class="selo ${cls}" style="margin-top:56px">${selo}</span>
      <p class="lead" style="margin-top:44px">${txt}</p>
      <p class="nota" style="margin-top:auto;margin-bottom:40px">${fonte}</p>`,
    }),
  })),
  {
    id: 'T10-6', alt: 'Na dúvida, avise o ouvinte. Salve e mande para a equipe da rádio.',
    html: feed({
      rotulo: 'IA no rádio', cont: '06/06', base: 'site', luz: 'baixa',
      miolo: `
      <h2 class="h g" style="margin-top:72px">Na dúvida, <span class="acc">avise o ouvinte.</span></h2>
      <p class="lead" style="margin-top:40px">Transparência hoje é escolha da rádio. É a que a gente recomenda.</p>
      <p class="lead" style="margin-top:auto;margin-bottom:52px"><b>Salve e mande para a equipe.</b></p>`,
    }),
  },
];

// ---------- T11 · Diga ao ouvinte que é IA (18/12) ----------
const T11 = [
  {
    id: 'T11-1', alt: 'Diga ao ouvinte que é IA. Dois casos recentes mostram por quê.',
    html: feed({
      rotulo: 'Opinião', cont: '01/05',
      miolo: `
      <h1 class="h g" style="margin-top:72px">Diga ao ouvinte que é <span class="acc">IA.</span></h1>
      <p class="lead" style="margin-top:40px">Dois casos recentes mostram por quê.</p>
      <div style="margin-top:auto;margin-bottom:56px">${forma({ w: 920, h: 150, semente: 67 })}</div>`,
    }),
  },
  {
    id: 'T11-2', alt: 'Austrália, 2025: uma rádio manteve uma locutora de IA no ar por seis meses sem contar ao público. Quando veio à tona, a notícia foi a omissão.',
    html: feed({
      rotulo: 'Caso 01 · Austrália, 2025', cont: '02/05',
      miolo: `
      <h2 class="h g" style="margin-top:72px">Seis meses <span class="acc">sem avisar.</span></h2>
      <p class="lead" style="margin-top:48px">Uma rádio australiana manteve uma locutora de IA no ar e não contou ao público. Quando veio à tona, a notícia foi a omissão.</p>
      <p class="nota" style="margin-top:auto;margin-bottom:40px">Fonte: Tudo Rádio, 2025.</p>`,
    }),
  },
  {
    id: 'T11-3', alt: 'Los Angeles, 2026: a José FM põe um co-apresentador de IA ao lado de uma apresentadora humana e avisa o ouvinte no ar. O quadro foi levado para outras cidades.',
    html: feed({
      rotulo: 'Caso 02 · Los Angeles, 2026', cont: '03/05',
      miolo: `
      <h2 class="h g" style="margin-top:72px">Avisa no ar, <span class="acc">e foi adiante.</span></h2>
      <p class="lead" style="margin-top:48px">A José FM põe um co-apresentador de IA ao lado de uma apresentadora humana e avisa o ouvinte. O quadro foi levado para outras cidades da rede.</p>
      <p class="nota" style="margin-top:auto;margin-bottom:40px">Fonte: LA Times, outubro de 2026; Entravision, junho de 2026.</p>`,
    }),
  },
  {
    id: 'T11-4', alt: 'No Brasil, avisar é escolha: não há lei geral de IA em vigor. Avisar o ouvinte é uma decisão editorial da rádio.',
    html: feed({
      rotulo: 'No Brasil', cont: '04/05',
      miolo: `
      <h2 class="h g" style="margin-top:72px">No Brasil, avisar <span class="acc">é escolha.</span></h2>
      <p class="lead" style="margin-top:48px">Não há lei geral de IA em vigor. Avisar o ouvinte é uma decisão editorial da rádio, e é a que a gente recomenda.</p>
      <p class="nota" style="margin-top:auto;margin-bottom:40px">PL 2338/2023 em análise na Câmara, em novembro de 2026.</p>`,
    }),
  },
  {
    id: 'T11-5', alt: 'Como avisar sem perder o clima: apresente o radialista com IA na abertura, diga no perfil e no site da rádio, responda com clareza quando o ouvinte perguntar.',
    html: feed({
      rotulo: 'Como fazer', cont: '05/05', base: 'site', luz: 'baixa',
      miolo: `
      <h2 class="h" style="margin-top:56px">Como avisar sem <span class="acc">perder o clima.</span></h2>
      <div class="itens" style="margin-top:64px;gap:36px">
        ${item('Apresente o radialista com IA na abertura do programa.')}
        ${item('Diga no perfil e no site da rádio.')}
        ${item('Responda com clareza quando o ouvinte perguntar.')}
      </div>
      <p class="lead" style="margin-top:auto;margin-bottom:52px"><b>Mande para quem decide a programação.</b></p>`,
    }),
  },
];

// ---------- T12 · Querido Papai Noel (21/12) ----------
const T12 = [{
  id: 'T12', alt: 'Carta: Querido Papai Noel, a lista da rádio para 2027: madrugada com voz, vinheta nova no ar, feriado sem buraco na escala, ouvinte respondido no WhatsApp. Assinado, a equipe da rádio.',
  html: feed({
    rotulo: ESPELHO, base: '',
    miolo: `
    <div class="carta" style="margin-top:auto">
      <div class="ola">Querido <span class="acc">Papai Noel,</span></div>
      <p class="sub">a lista da rádio para 2027:</p>
      <div class="itens" style="margin-top:48px;gap:30px">
        ${item('Madrugada com voz.', CAIXA)}
        ${item('Vinheta nova no ar.', CAIXA)}
        ${item('Feriado sem buraco na escala.', CAIXA)}
        ${item('Ouvinte respondido no WhatsApp.', CAIXA)}
      </div>
      <p class="ass">Ass.: a equipe da rádio</p>
    </div>
    <p class="lead" style="margin-top:auto;margin-bottom:48px">Marque quem precisa ler esta carta.</p>`,
  }),
}];

// ---------- T13 · POV (23/12) ----------
const T13 = [{
  id: 'T13', alt: 'POV: 24 de dezembro, 23 horas. A equipe está na ceia e a rádio continua no ar, com voz e com o ouvinte participando.',
  html: feed({
    rotulo: 'POV', base: '', luz: 'centro',
    miolo: `
    <h1 class="h g" style="margin-top:72px">POV: <span class="acc">24/12, 23h.</span></h1>
    <p class="lead" style="margin-top:44px;font-size:44px">A equipe está na ceia e a rádio continua no ar, com voz e com o ouvinte participando.</p>
    <div style="margin-top:auto">
      <div class="relogio"><span class="dot"></span>23:00 · No ar</div>
      <div style="margin-top:28px">${forma({ w: 920, h: 150, semente: 73 })}</div>
    </div>
    <p class="nota" style="margin-top:40px;margin-bottom:40px">Para o ao vivo, o painel fica aberto e ativo no computador da rádio.</p>`,
  }),
}];

// ---------- T14 · 2026 no rádio em 6 números (28/12) ----------
const T14 = [
  {
    id: 'T14-1', alt: 'Retrospectiva: 2026 no rádio em 6 números.',
    html: feed({
      rotulo: 'Retrospectiva 2026', cont: '01/05',
      miolo: `
      <h1 class="h g" style="margin-top:72px">2026 no rádio em <span class="acc">6 números.</span></h1>
      <p class="lead" style="margin-top:40px">Audiência, música, verba e IA. Arraste e salve.</p>
      <div style="margin-top:auto;margin-bottom:56px">${forma({ w: 920, h: 150, semente: 79 })}</div>`,
    }),
  },
  {
    id: 'T14-2', alt: '77% das pessoas de 15 anos ou mais ouvem rádio, por 3 horas e 38 minutos por dia, nas 13 regiões metropolitanas do Audio Pulse 2026.',
    html: feed({
      rotulo: 'Retrospectiva · Audiência', cont: '02/05',
      miolo: `
      <div class="stat m" style="margin-top:80px"><div class="num acc">77<span class="u">%</span></div><p class="rot">das pessoas de 15 anos ou mais ouvem rádio.</p></div>
      <div class="stat m" style="margin-top:72px"><div class="num">3h38</div><p class="rot">de escuta por dia.</p></div>
      <p class="nota" style="margin-top:auto;margin-bottom:40px">Fonte: Audio Pulse 2026 (Ibope). 13 regiões metropolitanas, 15 anos ou mais.</p>`,
    }),
  },
  {
    id: 'T14-3', alt: 'Música: 10 de 10 no top 10 da Crowley foram sertanejas no 1º semestre de 2026, e 67 das 100 mais tocadas na ConectMix.',
    html: feed({
      rotulo: 'Retrospectiva · Música', cont: '03/05',
      miolo: `
      <div class="stat m" style="margin-top:80px"><div class="num acc">10<span class="u">de 10</span></div><p class="rot">músicas do top 10 da Crowley eram <b>sertanejas</b> no 1º semestre.</p></div>
      <div class="stat m" style="margin-top:72px"><div class="num">67<span class="u">de 100</span></div><p class="rot">das mais tocadas na ConectMix, também sertanejas.</p></div>
      <p class="nota" style="margin-top:auto;margin-bottom:40px">Fontes: Crowley (360 rádios do Sul, Sudeste e Centro-Oeste) e ConectMix, via Billboard Brasil. 1º semestre de 2026.</p>`,
    }),
  },
  {
    id: 'T14-4', alt: 'Verba: 3,4% do investimento das agências foi para o rádio no 1º semestre de 2026. IA: em fevereiro de 2026, a UNESCO dedicou o Dia Mundial do Rádio à inteligência artificial.',
    html: feed({
      rotulo: 'Retrospectiva · Verba e IA', cont: '04/05',
      miolo: `
      <div class="stat m" style="margin-top:80px"><div class="num acc">3,4<span class="u">%</span></div><p class="rot">da verba das agências foi para o rádio no 1º semestre.</p></div>
      <div class="stat m" style="margin-top:72px"><div class="num">13/02</div><p class="rot">A UNESCO dedicou o Dia Mundial do Rádio de 2026 à <b>inteligência artificial</b>.</p></div>
      <p class="nota" style="margin-top:auto;margin-bottom:40px">Fontes: Cenp-Meios, 1º semestre de 2026; UNESCO, via Tudo Rádio.</p>`,
    }),
  },
  {
    id: 'T14-5', alt: 'Qual número mais te surpreendeu? Salve e mande para a equipe da rádio.',
    html: feed({
      rotulo: 'Retrospectiva 2026', cont: '05/05', base: 'site', luz: 'baixa',
      miolo: `
      <h2 class="h g" style="margin-top:72px">Qual número mais <span class="acc">te surpreendeu?</span></h2>
      <p class="lead" style="margin-top:40px">Conta nos comentários. E mande para a equipe da rádio.</p>
      <div style="margin-top:auto;margin-bottom:56px">${forma({ w: 920, h: 150, semente: 83 })}</div>`,
    }),
  },
];

const g = (id, nome, pecas) => ({ id, nome, formato: 'feed', colecao: 'tendencias', pasta: `tendencias/${id}`, pecas });
export const grupos = [
  g('T01', 'T01 · NÃOvembro (até 30/11)', T01),
  g('T02', 'T02 · Black Friday (26/11)', T02),
  g('T03', 'T03 · Plantão de fim de ano (30/11)', T03),
  g('T05', 'T05 · 5 especiais de fim de ano (04/12)', T05),
  g('T09', 'T09 · Mais ouvido do que pago (14/12)', T09),
  g('T10', 'T10 · IA no rádio: mito ou verdade (16/12)', T10),
  g('T11', 'T11 · Diga ao ouvinte que é IA (18/12)', T11),
  g('T12', 'T12 · Querido Papai Noel (21/12)', T12),
  g('T13', 'T13 · POV 24/12 (23/12)', T13),
  g('T14', 'T14 · 2026 no rádio em 6 números (28/12)', T14),
];
