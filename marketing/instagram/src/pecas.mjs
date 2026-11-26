// Peças de Instagram da Locufy: feed (1080x1350) e stories (1080x1920).
// Renderizar e checar: cd marketing/tools && node instagram.mjs
// Todo número e promessa aqui precisa existir em https://locufybr.com (landing-page/index.html).

const LOGO = '/marketing/brand/locufy-logo-white.png';
const IMG = {
  radialista: { src: '/landing-page/design/radialista-profissional.png', w: 1448, h: 1086 },
  grade: { src: '/landing-page/design/grade-profissional.png', w: 1448, h: 1086 },
  vinhetas: { src: '/landing-page/design/vinhetagem-profissional.png', w: 1448, h: 1086 },
};
// Recortes (em px da imagem original) que enquadram o cartão de cada tela.
const RECORTE = {
  radialista: { x: 48, y: 158, w: 1356, h: 770 },
  grade: { x: 70, y: 66, w: 1308, h: 760, fade: true },
  vinhetas: { x: 60, y: 200, w: 1330, h: 690 },
};

// ---------- utilidades ----------
function mulberry32(a) {
  return () => {
    a |= 0; a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function tela(nome, largura, extra = '') {
  const img = IMG[nome];
  const r = RECORTE[nome];
  const s = largura / r.w;
  const altura = Math.round(r.h * s);
  const mascara = r.fade ? '-webkit-mask-image:linear-gradient(#000 78%,transparent);mask-image:linear-gradient(#000 78%,transparent);' : '';
  return `<div class="shot" data-tela="${nome}" style="width:${largura}px;height:${altura}px;${mascara}${extra}">` +
    `<img src="${img.src}" alt="" style="left:${(-r.x * s).toFixed(1)}px;top:${(-r.y * s).toFixed(1)}px;width:${(img.w * s).toFixed(1)}px"></div>`;
}

function forma({ w = 920, h = 200, n = 72, semente = 7 } = {}) {
  const r = mulberry32(semente);
  const passo = w / n;
  const bw = Math.max(4, passo * 0.44);
  let barras = '';
  for (let i = 0; i < n; i++) {
    const t = i / (n - 1);
    const env = Math.pow(Math.sin(Math.PI * t), 0.7);
    const v = (0.16 + 0.84 * r()) * env;
    const bh = Math.max(bw, v * h);
    const x = i * passo + (passo - bw) / 2;
    const op = (0.3 + 0.7 * env).toFixed(2);
    barras += `<rect x="${x.toFixed(1)}" y="${((h - bh) / 2).toFixed(1)}" width="${bw.toFixed(1)}" height="${bh.toFixed(1)}" rx="${(bw / 2).toFixed(1)}" fill="#00B4D8" fill-opacity="${op}"/>`;
  }
  return `<svg class="forma" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" aria-hidden="true" style="display:block;flex:none">${barras}</svg>`;
}

// Linhas de sinal no canto inferior esquerdo (só nos stories, abaixo da faixa útil).
function ondas(w, h, n = 8) {
  let p = '';
  for (let i = 0; i < n; i++) {
    const sy = h - 225 + i * 17;
    const ex = 130 + i * 40;
    p += `<path d="M-12 ${sy} C ${190 + i * 6} ${sy + 4}, ${60 + i * 36} ${h - 50}, ${ex} ${h + 14}"/>`;
  }
  return `<svg class="ondas" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" fill="none" aria-hidden="true">` +
    `<defs><linearGradient id="go" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#3E3A98"/><stop offset=".55" stop-color="#3D69BC"/><stop offset="1" stop-color="#138FAE"/></linearGradient></defs>` +
    `<g stroke="url(#go)" stroke-width="2.2" stroke-linecap="round" opacity=".85">${p}</g></svg>`;
}

const ICONE = {
  ok: `<svg viewBox="0 0 44 44" aria-hidden="true"><circle cx="22" cy="22" r="20" fill="rgba(0,180,216,.14)" stroke="#00B4D8" stroke-width="2"/><path d="M13.5 22.5l5.8 5.8L31 16.5" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/></svg>`,
  monitor: `<svg viewBox="0 0 56 56" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="7" y="10" width="42" height="28" rx="4"/><path d="M21 46h14M28 38v8"/><path d="M17 27l5-6 5 4 6-8 6 7" stroke="#00B4D8"/></svg>`,
  mesa: `<svg viewBox="0 0 56 56" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round" aria-hidden="true"><path d="M14 9v38M28 9v38M42 9v38"/><rect x="9" y="30" width="10" height="7" rx="2" fill="#1B263B" stroke="#00B4D8"/><rect x="23" y="16" width="10" height="7" rx="2" fill="#1B263B" stroke="#00B4D8"/><rect x="37" y="25" width="10" height="7" rx="2" fill="#1B263B" stroke="#00B4D8"/></svg>`,
  antena: `<svg viewBox="0 0 56 56" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M28 24L19 49M28 24l9 25M22 41h12"/><circle cx="28" cy="21" r="3" fill="#00B4D8" stroke="#00B4D8"/><path d="M19 12a13 13 0 0 0 0 18M37 12a13 13 0 0 1 0 18M13 7a21 21 0 0 0 0 28M43 7a21 21 0 0 1 0 28" stroke="#00B4D8"/></svg>`,
};

const SETA = `<svg viewBox="0 0 40 16" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M2 8h34M29 2l7 6-7 6"/></svg>`;

// ---------- molduras ----------
function feed({ rotulo, cont, miolo, base = 'arraste', luz = '' }) {
  const direita = cont ? `<div class="cont">${cont}</div>` : '';
  const rodape = base === 'arraste'
    ? `<div class="arraste">Arraste ${SETA}</div>`
    : base === 'site' ? `<div class="site">locufybr.com</div>` : '';
  return `<div class="luz ${luz}"></div>
  <div class="frame">
    <div class="topo"><div class="lab"><span class="dot"></span>${rotulo}</div>${direita}</div>
    <div class="miolo">${miolo}</div>
    <div class="base"><img class="logo" src="${LOGO}" alt="Locufy">${rodape}</div>
  </div>`;
}

function story({ rotulo, miolo, luz = '' }) {
  return `<div class="luz ${luz}"></div>${ondas(1080, 1920)}
  <div class="frame">
    <div class="topo"><div class="lab"><span class="dot"></span>${rotulo}</div><img class="logo" src="${LOGO}" alt="Locufy"></div>
    <div class="miolo">${miolo}</div>
  </div>`;
}

const NOTA_TELA = 'Rádio e locutores fictícios. Tela do painel com dados demonstrativos.';
const NOTA_PRECO = 'Estimativa com tarifas de referência de setembro de 2026 e 6 minutos de fala nova por hora de programa.';

// ---------- A: como funciona (carrossel, 6) ----------
const A = [
  {
    id: 'A1', alt: 'Capa do carrossel: do nome da voz ao programa no ar, em quatro passos: identidade, grade, WhatsApp e ao vivo.',
    html: feed({
      rotulo: 'Como funciona', cont: '01/06',
      miolo: `
      <h1 class="h" style="margin-top:72px">Do nome da voz ao <span class="acc">programa no ar.</span></h1>
      <p class="lead" style="margin-top:32px;max-width:860px">Como colocar um radialista com IA na sua rádio, em quatro passos no painel.</p>
      <div class="espelho" style="margin-top:auto;margin-bottom:56px">
        <div class="lin"><span class="n">01</span><span class="t">Identidade<span class="d">Nome, voz e personalidade</span></span></div>
        <div class="lin"><span class="n">02</span><span class="t">Grade<span class="d">Horários e programas da semana</span></span></div>
        <div class="lin"><span class="n">03</span><span class="t">WhatsApp<span class="d">O ouvinte participa</span></span></div>
        <div class="lin"><span class="n">04</span><span class="t">Ao vivo<span class="d">O programa toca no computador</span></span></div>
      </div>`,
    }),
  },
  {
    id: 'A2', alt: 'Passo 1: tela do painel com nome do locutor, voz do catálogo e personalidade em texto livre. Dados demonstrativos.',
    html: feed({
      rotulo: 'Passo 01 · Identidade', cont: '02/06',
      miolo: `
      <h2 class="h" style="margin-top:56px">Dê nome, voz e <span class="acc">personalidade.</span></h2>
      <div style="margin-top:48px">${tela('radialista', 920)}</div>
      <p class="lead" style="margin-top:44px">Vozes do catálogo e personalidade em texto livre. Ajuste quantas vezes quiser.</p>
      <p class="nota" style="margin-top:auto;margin-bottom:40px">${NOTA_TELA}</p>`,
    }),
  },
  {
    id: 'A3', alt: 'Passo 2: grade semanal com três programas, cada um com horário e radialista. Dados demonstrativos.',
    html: feed({
      rotulo: 'Passo 02 · Grade', cont: '03/06',
      miolo: `
      <h2 class="h" style="margin-top:56px">Monte a semana do <span class="acc">seu jeito.</span></h2>
      <div style="margin-top:48px">${tela('grade', 920)}</div>
      <p class="lead" style="margin-top:8px">Dias, horários e o radialista de cada programa. Repita os fixos ou troque o tema de um dia.</p>
      <p class="nota" style="margin-top:auto;margin-bottom:40px">${NOTA_TELA}</p>`,
    }),
  },
  {
    id: 'A4', alt: 'Passo 3: conversa ilustrativa. O ouvinte pede um abraço para a Ana e a rádio responde que o abraço está na fila de participações.',
    html: feed({
      rotulo: 'Passo 03 · WhatsApp', cont: '04/06',
      miolo: `
      <h2 class="h" style="margin-top:56px">O ouvinte participa pelo <span class="acc">WhatsApp.</span></h2>
      <div class="chat" style="margin-top:52px">
        <div class="quem">Ouvinte</div>
        <div class="bolha ouv">Bom dia! Manda um abraço pra Ana, que está ouvindo enquanto prepara o almoço.</div>
        <div class="quem r" style="margin-top:30px">Rádio</div>
        <div class="bolha rad">Bom dia! Seu abraço para a Ana está na fila de participações do programa.</div>
      </div>
      <p class="lead" style="margin-top:44px">Conexão por QR code. Um número da rádio para todos os radialistas, com o histórico no painel.</p>
      <p class="nota" style="margin-top:auto;margin-bottom:40px">Conversa ilustrativa. Rádio e ouvintes fictícios.</p>`,
    }),
  },
  {
    id: 'A5', alt: 'Passo 4: o painel Ao Vivo toca os blocos e as falas no computador; a saída de áudio vai para a transmissão da rádio. Mantenha a aba aberta e ativa.',
    html: feed({
      rotulo: 'Passo 04 · Ao vivo', cont: '05/06',
      miolo: `
      <h2 class="h" style="margin-top:56px">Painel aberto, <span class="acc">programa no ar.</span></h2>
      <div class="cadeia" style="margin-top:64px">
        <div class="elo"><div class="ic">${ICONE.monitor}</div><div><div class="t">Painel Ao Vivo</div><div class="d">Toca os blocos e as falas no computador.</div></div></div>
        <div class="fio"></div>
        <div class="elo"><div class="ic">${ICONE.mesa}</div><div><div class="t">Saída de áudio</div><div class="d">Você encaminha esse som para a transmissão.</div></div></div>
        <div class="fio"></div>
        <div class="elo"><div class="ic">${ICONE.antena}</div><div><div class="t">Sua rádio</div><div class="d">O programa vai ao ar pela transmissão da rádio.</div></div></div>
      </div>
      <p class="lead" style="margin-top:auto;margin-bottom:48px">Durante o programa, mantenha a aba do painel <b>aberta e ativa</b>.</p>`,
    }),
  },
  {
    id: 'A6', alt: 'Ouça antes de decidir: amostras de locução no site locufybr.com, sem criar conta. Locufy Flex: R$ 69,90 por mês mais uso de IA.',
    html: feed({
      rotulo: 'Ouça antes', cont: '06/06', base: 'site', luz: 'baixa',
      miolo: `
      <h2 class="h g" style="margin-top:72px">Ouça antes de <span class="acc">decidir.</span></h2>
      <p class="lead" style="margin-top:36px;max-width:880px">Amostras de locução e exemplos de cada combinação de vozes no site, sem criar conta.</p>
      <div style="margin-top:72px">${forma({ w: 920, h: 210, semente: 11 })}</div>
      <p class="preco-flex" style="margin-top:auto;margin-bottom:52px">Locufy Flex: <b>R$ 69,90/mês</b> + uso de IA.<br>Ativado no cadastro, com cartão.</p>`,
    }),
  },
];

// ---------- B: quanto custa (carrossel, 6) ----------
const COMBOS = [
  ['Essencial', 'Haiku · Flash', 3.86],
  ['Ágil', 'Sonnet · Flash', 4.16],
  ['Texto Premium', 'Opus · Flash', 5.05],
  ['Voz Premium', 'Haiku · v3 ou v4', 7.16],
  ['Equilibrada', 'Sonnet · v3 ou v4', 7.46],
  ['Premium', 'Opus · v3 ou v4', 8.35],
];
const brl = (v) => v.toFixed(2).replace('.', ',');
const barras = () => `<div class="barras">${COMBOS.map(([n, m, v]) =>
  `<div class="barra"><div class="nome">${n}<span class="mod">${m}</span></div>` +
  `<div class="trilho"><div class="val" style="width:${(v / 9 * 100).toFixed(1)}%"></div></div>` +
  `<div class="preco">R$ ${brl(v)}</div></div>`).join('')}</div>`;

const B = [
  {
    id: 'B1', alt: 'Quanto custa uma hora de programa com IA? A partir de aproximadamente R$ 3,86 por hora no ar, na combinação Essencial. Estimativa.',
    html: feed({
      rotulo: 'Preço', cont: '01/06',
      miolo: `
      <h1 class="h" style="margin-top:72px">Quanto custa uma hora de programa com <span class="acc">IA?</span></h1>
      <div style="margin-top:auto">
        <p class="lead">A partir de</p>
        <div class="hero-num" style="margin-top:20px"><span class="aprox">≈</span><span class="rs">R$</span>3,86</div>
        <p class="lead" style="margin-top:34px">por hora de programa no ar, na combinação Essencial.</p>
      </div>
      <p class="nota" style="margin-top:44px;margin-bottom:40px">${NOTA_PRECO}</p>`,
    }),
  },
  {
    id: 'B2', alt: 'A conta tem duas partes: assinatura Locufy Flex de R$ 69,90 por mês mais o uso de IA, cobrado no fim do ciclo.',
    html: feed({
      rotulo: 'Preço · Como funciona', cont: '02/06',
      miolo: `
      <h2 class="h" style="margin-top:56px">A conta tem <span class="acc">duas partes.</span></h2>
      <div class="par" style="margin-top:72px">
        <div class="cartao"><div class="lab">Assinatura</div><div class="v">R$ 69,90<small style="display:block;margin-top:10px">por mês</small></div><div class="d">Locufy Flex, ativado ao criar a conta, com cartão.</div></div>
        <div class="mais">+</div>
        <div class="cartao"><div class="lab">Uso de IA</div><div class="v">Por hora<small style="display:block;margin-top:10px">de programa no ar</small></div><div class="d">De ≈ R$ 3,86 a R$ 8,35 por hora, cobrado no fim do ciclo.</div></div>
      </div>
      <p class="lead" style="margin-top:auto;margin-bottom:48px">Na renovação: mensalidade do próximo período + uso do período encerrado. <b>Sem uso, R$ 69,90.</b></p>`,
    }),
  },
  {
    id: 'B3', alt: 'Gráfico de barras com o preço estimado por hora no ar: Essencial R$ 3,86; Ágil R$ 4,16; Texto Premium R$ 5,05; Voz Premium R$ 7,16; Equilibrada R$ 7,46; Premium R$ 8,35.',
    html: feed({
      rotulo: 'Preço por hora no ar', cont: '03/06',
      miolo: `
      <h2 class="h m" style="margin-top:56px">O uso depende da <span class="acc">combinação.</span></h2>
      <p class="lead" style="margin-top:24px;font-size:32px">Texto com Claude, voz com ElevenLabs.</p>
      <div style="margin-top:44px">${barras()}</div>
      <p class="nota" style="margin-top:auto;margin-bottom:40px">${NOTA_PRECO}</p>`,
    }),
  },
  {
    id: 'B4', alt: 'O que não entra na conta: música e áudio pronto não geram cobrança; receber mensagem no WhatsApp não gera cobrança de IA; sem franquia de mensagens; vários radialistas sem custo por radialista.',
    html: feed({
      rotulo: 'Preço · Fora da conta', cont: '04/06',
      miolo: `
      <h2 class="h" style="margin-top:56px">O que <span class="acc">não entra</span> na conta.</h2>
      <div class="itens" style="margin-top:72px;gap:40px">
        <div class="item">${ICONE.ok}<span><b>Música e áudio pronto</b> não geram cobrança.</span></div>
        <div class="item">${ICONE.ok}<span><b>Receber mensagem</b> no WhatsApp não gera cobrança de IA.</span></div>
        <div class="item">${ICONE.ok}<span><b>Sem franquia</b> nem pacotes de mensagens no WhatsApp.</span></div>
        <div class="item">${ICONE.ok}<span><b>Vários radialistas</b>, sem custo por radialista.</span></div>
      </div>
      <p class="nota" style="margin-top:auto;margin-bottom:40px">Texto, transcrição, imagem e voz gerados pela IA são medidos pelo uso, dentro do seu limite mensal.</p>`,
    }),
  },
  {
    id: 'B5', alt: 'Você define o teto do mês: ilustração de um medidor de uso com a marca do limite. A conta não passa do valor definido e cada uso aparece no extrato.',
    html: feed({
      rotulo: 'Preço · Limite', cont: '05/06',
      miolo: `
      <h2 class="h" style="margin-top:56px">Você define o <span class="acc">teto do mês.</span></h2>
      <p class="lead" style="margin-top:32px">A conta não passa do valor que você definir. Cada uso aparece no extrato do painel.</p>
      <div style="position:relative;margin-top:150px">
        <div class="lab" style="position:absolute;left:0;top:-82px">Uso medido</div>
        <div class="lab" style="position:absolute;right:0;top:-82px;color:#fff">Seu limite</div>
        <div class="medidor"><div class="uso" style="width:58%"></div><div class="teto" style="left:calc(100% - 128px)"></div></div>
      </div>
      <p class="nota" style="margin-top:auto;margin-bottom:40px">Ilustração. O limite financeiro mensal é definido por você no painel.</p>`,
    }),
  },
  {
    id: 'B6', alt: 'Simule a sua conta no site locufybr.com. Incluso no Locufy Flex: WhatsApp completo sem franquia, programas, grade, ao vivo e vinhetas, limite mensal e extrato.',
    html: feed({
      rotulo: 'Preço · Simulador', cont: '06/06', base: 'site', luz: 'baixa',
      miolo: `
      <h2 class="h" style="margin-top:56px">Simule a sua conta <span class="acc">no site.</span></h2>
      <p class="lead" style="margin-top:32px">Escolha a combinação, as horas de programa por dia e os dias por semana.</p>
      <div class="lab" style="margin-top:72px"><b>Incluso no Locufy Flex</b></div>
      <div class="itens" style="margin-top:32px">
        <div class="item">${ICONE.ok}<span>WhatsApp completo, sem franquia de mensagens</span></div>
        <div class="item">${ICONE.ok}<span>Programas, grade, ao vivo e vinhetas</span></div>
        <div class="item">${ICONE.ok}<span>Limite financeiro mensal e extrato de cada uso</span></div>
      </div>
      <p class="preco-flex" style="margin-top:auto;margin-bottom:52px"><b>R$ 69,90/mês</b> + uso de IA.</p>`,
    }),
  },
];

// ---------- C: perguntas (carrossel, 7) ----------
const PERGUNTAS = [
  ['Eu controlo o que o radialista fala?', 'Você define as regras.',
    'Personalidade, tom, horários e os temas permitidos e proibidos de cada programa. As conversas ficam no painel para revisão.',
    'O conteúdo é gerado por IA: mantenha a supervisão editorial da rádio.'],
  ['Posso escolher a voz?', 'Sim, pelo catálogo.',
    'Vozes femininas e masculinas, cada uma com um jeito de falar. Também dá para clonar uma voz a partir de uma amostra de áudio.',
    'Clone só uma voz que você tem autorização para usar.'],
  ['Dá para usar o WhatsApp que a rádio já tem?', 'Sim, por QR code.',
    'Cada conta usa um número, compartilhado pelos radialistas. Não há franquia nem pacote de mensagens.',
    'A sessão precisa ficar conectada para atender os ouvintes.'],
  ['Preciso saber programar?', 'Não.',
    'Tudo acontece pelo painel: descreva o radialista, conecte o WhatsApp e revise o programa. A central de ajuda explica cada etapa.',
    ''],
  ['Posso ouvir antes de contratar?', 'Sim, no site.',
    'As amostras de locução e os exemplos de cada combinação de vozes estão em locufybr.com, sem criar conta.',
    'A assinatura é ativada no último passo do cadastro, com cartão.'],
];

const C = [
  {
    id: 'C1', alt: 'Capa do carrossel: 5 perguntas antes de colocar IA na rádio, com a lista das perguntas.',
    html: feed({
      rotulo: 'Perguntas', cont: '01/07',
      miolo: `
      <h1 class="h" style="margin-top:72px">5 perguntas antes de colocar <span class="acc">IA na rádio.</span></h1>
      <div class="espelho" style="margin-top:auto;margin-bottom:56px">
        ${PERGUNTAS.map(([p], i) => `<div class="lin" style="padding:24px 0"><span class="n">0${i + 1}</span><span class="t" style="font-size:36px;font-weight:500">${p}</span></div>`).join('')}
      </div>`,
    }),
  },
  ...PERGUNTAS.map(([p, curta, longa, nota], i) => ({
    id: `C${i + 2}`, alt: `Pergunta ${i + 1}: ${p} Resposta: ${curta} ${longa}${nota ? ' ' + nota : ''}`,
    html: feed({
      rotulo: `Pergunta 0${i + 1}`, cont: `0${i + 2}/07`,
      miolo: `
      <div class="qnum" style="margin-top:56px">0${i + 1}</div>
      <h2 class="h" style="margin-top:48px">${p}</h2>
      <div class="resposta" style="margin-top:auto;margin-bottom:${nota ? 0 : 48}px">
        <p class="resp">${curta}</p>
        <p class="lead" style="margin-top:24px">${longa}</p>
      </div>
      ${nota ? `<p class="nota" style="margin-top:44px;margin-bottom:40px">${nota}</p>` : ''}`,
    }),
  })),
  {
    id: 'C7', alt: 'Ficou outra dúvida? Mande no direct ou fale com a equipe pelo WhatsApp no site locufybr.com.',
    html: feed({
      rotulo: 'Fale com a equipe', cont: '07/07', base: 'site', luz: 'baixa',
      miolo: `
      <h2 class="h g" style="margin-top:72px">Ficou outra <span class="acc">dúvida?</span></h2>
      <p class="lead" style="margin-top:40px;max-width:860px">Mande sua pergunta no direct ou fale com a equipe pelo WhatsApp, no site.</p>
      <div style="margin-top:auto;margin-bottom:56px">${forma({ w: 920, h: 170, semente: 29 })}</div>`,
    }),
  },
];

// ---------- P: posts únicos ----------
const P = [
  {
    id: 'P1', alt: 'Biblioteca de áudio do painel: aberturas, assinaturas, passagens e vinhetas com nome e duração, organizadas por categoria. Dados demonstrativos.',
    html: feed({
      rotulo: 'Biblioteca de áudio', base: '',
      miolo: `
      <h1 class="h" style="margin-top:56px">Encontre o <span class="acc">áudio certo.</span></h1>
      <div style="margin-top:48px">${tela('vinhetas', 920)}</div>
      <p class="lead" style="margin-top:44px">Aberturas, assinaturas, passagens e spots por categoria, com nome e duração à vista. Vale para todos os radialistas da rádio.</p>
      <p class="nota" style="margin-top:auto;margin-bottom:40px">Rádio fictícia. Tela do painel com dados demonstrativos.</p>`,
    }),
  },
  {
    id: 'P2', alt: 'Inteligência artificial. Essência de rádio. A voz, a grade e as regras são da sua rádio.',
    html: feed({
      rotulo: 'Locufy', base: '', luz: 'centro',
      miolo: `
      <h1 class="h g" style="margin-top:96px">Inteligência artificial. <span class="acc">Essência de rádio.</span></h1>
      <div style="margin-top:auto">${forma({ w: 920, h: 190, semente: 3 })}</div>
      <p class="lead" style="margin-top:64px;margin-bottom:56px">A voz, a grade e as regras são da sua rádio. A IA ajuda a manter a programação no ar.</p>`,
    }),
  },
];

// ---------- S: stories ----------
const S = [
  {
    id: 'S1-1', alt: 'E se a sua rádio tivesse mais uma voz? Um radialista com IA, com o nome, a voz e o jeito de falar que você escolher.',
    html: story({
      rotulo: 'Radialista com IA',
      miolo: `
      <h1 class="h" style="margin-top:120px">E se a sua rádio tivesse <span class="acc">mais uma voz?</span></h1>
      <p class="lead" style="margin-top:48px">Um radialista com IA, com o nome, a voz e o jeito de falar que você escolher.</p>
      <div style="margin-top:auto">${forma({ w: 912, h: 300, n: 64, semente: 5 })}</div>`,
    }),
  },
  {
    id: 'S1-2', alt: 'Você escolhe a voz e a personalidade: tela do painel com nome do locutor, voz e personalidade. Dados demonstrativos.',
    html: story({
      rotulo: 'Identidade',
      miolo: `
      <h2 class="h m" style="margin-top:110px">Você escolhe a voz e a <span class="acc">personalidade.</span></h2>
      <div style="margin-top:80px">${tela('radialista', 912)}</div>
      <p class="lead" style="margin-top:64px">Vozes do catálogo e personalidade em texto livre. Ajuste quantas vezes quiser.</p>
      <p class="nota" style="margin-top:auto">${NOTA_TELA}</p>`,
    }),
  },
  {
    id: 'S1-3', figurinha: 'Enquete', alt: 'Enquete: em qual horário a sua rádio mais precisa de uma voz?',
    html: story({
      rotulo: 'Enquete',
      miolo: `
      <h2 class="h" style="margin-top:120px">Em qual horário a sua rádio mais precisa de <span class="acc">uma voz?</span></h2>
      <div class="figurinha" data-figurinha style="margin-top:80px;height:560px"></div>`,
    }),
  },
  {
    id: 'S1-4', figurinha: 'Link', alt: 'Ouça as amostras no site locufybr.com, sem criar conta. Locufy Flex: R$ 69,90 por mês mais uso de IA.',
    html: story({
      rotulo: 'Ouça', luz: 'baixa',
      miolo: `
      <h2 class="h" style="margin-top:120px">Ouça as amostras <span class="acc">no site.</span></h2>
      <p class="lead" style="margin-top:48px">Exemplos de locução e de cada combinação de vozes, sem criar conta.</p>
      <div class="figurinha" data-figurinha style="margin-top:64px;height:260px"></div>
      <div style="margin-top:auto">
        <div class="cta-site">locufybr.com</div>
        <p class="preco-flex" style="margin-top:28px;margin-bottom:8px">Locufy Flex: <b>R$ 69,90/mês</b> + uso de IA.</p>
      </div>`,
    }),
  },
  {
    id: 'S2-1', alt: 'Por dentro do painel: três telas, de radialista, grade e vinhetas. Dados demonstrativos.',
    html: story({
      rotulo: 'Tour',
      miolo: `
      <h1 class="h" style="margin-top:110px">Por dentro do <span class="acc">painel.</span></h1>
      <p class="lead" style="margin-top:40px">Três telas que organizam a rotina da sua rádio.</p>
      <div style="position:relative;height:720px;margin-top:auto;margin-bottom:56px">
        <div style="position:absolute;left:0;top:0">${tela('vinhetas', 640, 'transform:rotate(-4deg);opacity:.9')}</div>
        <div style="position:absolute;right:0;top:150px">${tela('radialista', 640, 'transform:rotate(3deg)')}</div>
        <div style="position:absolute;left:60px;top:330px">${tela('grade', 640, 'transform:rotate(-1.5deg)')}</div>
      </div>
      <p class="nota">${NOTA_TELA}</p>`,
    }),
  },
  {
    id: 'S2-2', alt: 'Sua grade, suas regras: grade semanal com programas, horários e radialistas. Dados demonstrativos.',
    html: story({
      rotulo: 'Grade',
      miolo: `
      <h2 class="h" style="margin-top:110px">Sua grade, <span class="acc">suas regras.</span></h2>
      <div style="margin-top:80px">${tela('grade', 912)}</div>
      <p class="lead" style="margin-top:24px">Dias, horários e o radialista de cada programa. Repita os fixos ou troque o tema de um dia.</p>
      <p class="nota" style="margin-top:auto">${NOTA_TELA}</p>`,
    }),
  },
  {
    id: 'S2-3', alt: 'Encontre o áudio certo: biblioteca com aberturas, assinaturas e passagens, com nome e duração. Dados demonstrativos.',
    html: story({
      rotulo: 'Vinhetas',
      miolo: `
      <h2 class="h" style="margin-top:110px">Encontre o <span class="acc">áudio certo.</span></h2>
      <div style="margin-top:80px">${tela('vinhetas', 912)}</div>
      <p class="lead" style="margin-top:64px">Aberturas, assinaturas, passagens e spots por categoria, com nome e duração à vista.</p>
      <p class="nota" style="margin-top:auto">Rádio fictícia. Tela do painel com dados demonstrativos.</p>`,
    }),
  },
  {
    id: 'S2-4', figurinha: 'Link', alt: 'Veja o tour completo no site locufybr.com: o vídeo mostra a voz, a grade e a participação do ouvinte.',
    html: story({
      rotulo: 'Demonstração', luz: 'baixa',
      miolo: `
      <h2 class="h" style="margin-top:110px">Veja o tour completo <span class="acc">no site.</span></h2>
      <p class="lead" style="margin-top:48px">Um vídeo mostra a configuração da voz, os horários na grade e a participação de um ouvinte.</p>
      <div class="figurinha" data-figurinha style="margin-top:64px;height:260px"></div>
      <div class="cta-site" style="margin-top:auto;margin-bottom:24px">locufybr.com</div>`,
    }),
  },
  {
    id: 'S3-1', figurinha: 'Teste', alt: 'Teste: quanto custa uma hora de programa com IA? Toque para ver a resposta.',
    html: story({
      rotulo: 'Teste rápido',
      miolo: `
      <h1 class="h" style="margin-top:110px">Quanto custa uma hora de programa com <span class="acc">IA?</span></h1>
      <div class="figurinha" data-figurinha style="margin-top:80px;height:520px"></div>
      <p class="lead" style="margin-top:auto">Responda e toque para ver.</p>`,
    }),
  },
  {
    id: 'S3-2', figurinha: 'Link', alt: 'Resposta: a partir de aproximadamente R$ 3,86 por hora de programa no ar. Locufy Flex: R$ 69,90 por mês mais uso de IA. Estimativa.',
    html: story({
      rotulo: 'Resposta', luz: 'baixa',
      miolo: `
      <p class="lead" style="margin-top:auto">A partir de</p>
      <div class="hero-num" style="margin-top:24px"><span class="aprox">≈</span><span class="rs">R$</span>3,86</div>
      <p class="lead" style="margin-top:40px">por hora de programa no ar, na combinação Essencial. Música e áudio pronto não geram cobrança.</p>
      <p class="preco-flex" style="margin-top:56px;font-size:40px">Locufy Flex: <b>R$ 69,90/mês</b> + uso de IA.</p>
      <div class="figurinha" data-figurinha style="margin-top:48px;height:200px"></div>
      <p class="nota" style="margin-top:auto;padding-top:48px">${NOTA_PRECO}</p>`,
    }),
  },
];

export const grupos = [
  { id: 'A', nome: 'Carrossel A · Como funciona', formato: 'feed', pecas: A },
  { id: 'B', nome: 'Carrossel B · Quanto custa', formato: 'feed', pecas: B },
  { id: 'C', nome: 'Carrossel C · 5 perguntas', formato: 'feed', pecas: C },
  { id: 'P', nome: 'Posts únicos', formato: 'feed', pecas: P },
  { id: 'S1', nome: 'Stories 1 · Mais uma voz', formato: 'story', pecas: S.slice(0, 4) },
  { id: 'S2', nome: 'Stories 2 · Por dentro do painel', formato: 'story', pecas: S.slice(4, 8) },
  { id: 'S3', nome: 'Stories 3 · Teste do preço', formato: 'story', pecas: S.slice(8) },
];

// Usados pelas peças de tendência (tendencias.mjs).
export { tela, forma, ICONE, SETA, feed, story, NOTA_TELA, LOGO };
