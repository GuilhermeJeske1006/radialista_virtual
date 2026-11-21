const { chromium, expect } = require('playwright/test');
const TARGET_URL = process.env.TARGET_URL || 'http://localhost:3001';
(async () => {
  const browser = await chromium.launch({ headless: false });
  try {
    const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, serviceWorkers: 'block' });
    await context.addInitScript(() => {
      localStorage.setItem('locufy-tour-concluido', 'true');
      window.__eventos = [];
      window.EventSource = class {
        constructor() { this.callbacks = []; window.__eventos.push(this); setTimeout(() => this.onopen?.(), 10); }
        addEventListener(tipo, cb) { this.callbacks.push(cb); }
        close() {}
      };
      window.__atualizar = () => window.__eventos.forEach(f => f.callbacks.forEach(cb => cb({ data: '{}' })));
    });
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    let humano = false;
    const mensagens = [{ id: '1', log_id: 1, origem: 'ouvinte', texto: 'Oceano marcou minha infância', status: 'guardado', em: '2026-11-12T12:00:00Z' }];
    const notas = [], contribuicoes = [];
    const conversa = () => ({ id: 1, nome: 'Carla', telefone: '5511999999999', humano, nao_lidas: 1, ultima_mensagem: mensagens.at(-1).texto });
    await page.route('**/api/**', async route => {
      const req = route.request(), url = new URL(req.url()), path = url.pathname.replace(/^\/api/, '');
      const body = req.postDataJSON();
      let data = {};
      if (path === '/auth/me') data = { id: 1, nome: 'Operador de teste', email: 'teste@locufy.test', role: 'admin', plano_status: 'ativo', plano: 'flex', cobranca_isenta: true, tem_radio_config: true };
      else if (path === '/config/radio') data = { nome_radio: 'Rádio Teste', wuzapi_token: 'test', frequencia: '98.5' };
      else if (path === '/config/radialistas') data = [{ id: 1, ativo: true, voz_id: 'teste', nome_locutor: 'Ana' }];
      else if (path.includes('/programas') && path.startsWith('/config/')) data = [{ id: 1, ativo: true, nome: 'Tarde Musical' }];
      else if (path === '/onboarding/status') data = { data: { loggedIn: true, connected: true } };
      else if (path === '/live/no-ar') data = { no_ar: false };
      else if (path.startsWith('/notificacoes')) data = [];
      else if (path === '/ouvintes/central') data = { conversas: [conversa()], total_paginas: 1 };
      else if (path === '/ouvintes/conversas/1' && req.method() === 'PATCH') { humano = body.humano; data = { humano }; }
      else if (path === '/ouvintes/conversas/1/mensagens') {
        if (req.method() === 'POST') { mensagens.push({ id: '2', log_id: 2, origem: 'radio', texto: body.texto, status: 'pendente', em: '2026-11-12T12:01:00Z', usuario_id: 1 }); data = { estado: 'pendente' }; }
        else data = { mensagens, conversa: conversa(), antes: null, ultimo_log_id: 2 };
      }
      else if (path === '/ouvintes/conversas/1/contexto') data = { programa_id: 1, publico: { pergunta: 'Qual música marcou sua infância?', discussao_id: 1 }, pedidos: [{ id: 1, tipo: 'musica', estado: 'aguardando_revisao' }], notas, contribuicoes };
      else if (path === '/ouvintes/conversas/1/notas') { notas.push({ id: 1, texto: body.texto }); data = { status: 'ok' }; }
      else if (path === '/ouvintes/conversas/1/contribuicoes') { contribuicoes.push({ id: 1, estado: 'aguardando_revisao' }); data = { id: 1 }; }
      else if (path === '/ouvintes/contribuicoes/1') { contribuicoes[0].estado = 'aprovada'; data = { estado: 'aprovada' }; }
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(data) });
    });
    await page.goto(TARGET_URL + '/conversas');
    await page.getByRole('button', { name: /Carla/ }).click();
    await expect(page.getByLabel('Mensagens da conversa').getByText('Oceano marcou minha infância')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Enviar mensagem' })).toBeDisabled();
    await page.getByRole('button', { name: 'Assumir conversa' }).click();
    await page.getByLabel('Resposta da equipe').fill('Obrigada pelo recado, Carla!');
    await page.getByRole('button', { name: 'Enviar mensagem' }).click();
    await expect(page.getByLabel('Mensagens da conversa').getByText('Obrigada pelo recado, Carla!', { exact: true })).toBeVisible();
    await page.getByLabel('Nota interna').fill('Conferir a dedicatória antes de publicar.');
    await page.getByRole('button', { name: 'Salvar nota' }).click();
    await expect(page.getByText('Conferir a dedicatória antes de publicar.', { exact: true })).toBeVisible();
    await page.getByRole('button', { name: 'Sugerir para pauta' }).click();
    await page.getByText('Revisar contribuição #1').click();
    await page.getByLabel('Título da pauta').fill('Memória musical dos ouvintes');
    await page.getByLabel('Somente conteúdo autorizado para o ar').fill('Uma ouvinte lembra de Oceano na infância.');
    await expect(page.getByRole('button', { name: 'Aprovar pauta' })).toBeDisabled();
    await page.getByLabel('Conferi a autorização para divulgar este conteúdo.').check();
    await page.getByRole('button', { name: 'Aprovar pauta' }).click();
    await expect(page.getByText('#1 · aprovada')).toBeVisible();
    mensagens.push({ id: '3', log_id: 3, origem: 'ouvinte', texto: 'Mensagem nova recebida em tempo real', status: 'guardado', em: '2026-11-12T12:02:00Z' });
    await page.evaluate(() => window.__atualizar());
    await expect(page.getByLabel('Mensagens da conversa').getByText('Mensagem nova recebida em tempo real', { exact: true })).toBeVisible();
    await page.screenshot({ path: '/tmp/locufy-whatsapp-desktop.png', fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.waitForFunction(() => getComputedStyle(document.querySelector('header.sticky').parentElement).paddingLeft === '0px');
    await expect(page.getByRole('button', { name: 'Voltar', exact: true })).toBeVisible();
    await page.screenshot({ path: '/tmp/locufy-whatsapp-mobile.png', fullPage: true });
    const overflow = await page.evaluate(() => [...document.querySelectorAll('body *')].map(e => ({tag: e.tagName, classe: e.className, direita: e.getBoundingClientRect().right, largura: e.getBoundingClientRect().width})).filter(e => e.direita > window.innerWidth + 1 && e.largura > 0).slice(0,20));
    console.log('overflow', JSON.stringify(overflow));
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
    await page.getByRole('button', { name: 'Voltar', exact: true }).click();
    await expect(page.getByLabel('Buscar conversa')).toBeVisible();
    expect(errors).toEqual([]);
    console.log('PASS: desktop, mobile, assumir conversa, envio manual, notas, revisão, eventos e ausência de overflow. APIs simuladas; nenhuma mensagem real enviada.');
  } finally { await browser.close(); }
})();
