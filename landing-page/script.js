const appUrl = new URL(window.LOCUFY_CONFIG?.appUrl || 'https://app.locufybr.com');
if (!['http:', 'https:'].includes(appUrl.protocol)) throw new Error('Configure appUrl com uma URL HTTP ou HTTPS.');
const campaign = new URLSearchParams(location.search);
const allowedParams = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term'];
document.querySelectorAll('[data-route]').forEach(link => {
  const target = new URL(link.dataset.route, `${appUrl.href.replace(/\/$/, '')}/`);
  if (['flex'].includes(link.dataset.plan)) target.searchParams.set('plano', link.dataset.plan);
  if (link.dataset.route === 'register') {
    allowedParams.forEach(key => { if (campaign.has(key)) target.searchParams.set(key, campaign.get(key)); });
    link.addEventListener('click', () => {
      // Evento local para integração futura; não envia dados para terceiros.
      window.dispatchEvent(new CustomEvent('locufy:conversion', { detail: { location: link.dataset.location, destination: target.href } }));
    });
  }
  link.href = target.href;
});
document.getElementById('year').textContent = String(new Date().getFullYear());

const dialog = document.querySelector('.image-dialog');
let imageTrigger;
document.querySelectorAll('[data-lightbox]').forEach(link => {
  link.addEventListener('click', event => {
    if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey || event.button !== 0 || !dialog.showModal) return;
    event.preventDefault();
    imageTrigger = link;
    const preview = document.getElementById('image-dialog-image');
    preview.src = link.href;
    preview.alt = link.querySelector('img').alt;
    document.getElementById('image-dialog-caption').textContent = link.dataset.caption;
    dialog.showModal();
    document.body.classList.add('dialog-open');
  });
});
dialog.querySelector('button').addEventListener('click', () => dialog.close());
dialog.addEventListener('click', event => { if (event.target === dialog) { const rect=dialog.getBoundingClientRect(); if(event.clientX<rect.left || event.clientX>rect.right || event.clientY<rect.top || event.clientY>rect.bottom) dialog.close(); } });
dialog.addEventListener('close', () => { document.body.classList.remove('dialog-open'); imageTrigger?.focus({ preventScroll: true }); });

const whatsappNumber = window.LOCUFY_CONFIG?.whatsappNumber;
if (/^\d{10,15}$/.test(whatsappNumber || '')) {
  document.querySelectorAll('[data-whatsapp]').forEach(link => {
    const message = link.dataset.plan
      ? 'Olá! Quero estimar o preço do Locufy para minha rádio.'
      : 'Olá! Quero conhecer o Locufy para minha rádio.';
    const url = new URL(`https://wa.me/${whatsappNumber}`);
    url.searchParams.set('text', message);
    link.href = url.href;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
  });
}

// Enhancement only: without JS all three panels remain readable.
const tabs = [...document.querySelectorAll('.tab')];
const tablist = document.querySelector('.tabs');
if (tablist && tabs.length) {
  tablist.hidden = false;
  tablist.setAttribute('role', 'tablist');
  function selectTab(tab) {
    tabs.forEach(item => {
      const active = item === tab;
      item.setAttribute('role', 'tab');
      item.setAttribute('aria-selected', String(active));
      item.tabIndex = active ? 0 : -1;
      const panel = document.getElementById(item.getAttribute('aria-controls'));
      panel.setAttribute('role', 'tabpanel'); panel.hidden = !active;
    });
  }
  tabs.forEach((tab, index) => {
    tab.addEventListener('click', () => selectTab(tab));
    tab.addEventListener('keydown', event => {
      const next = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : event.key === 'ArrowRight' ? (index + 1) % tabs.length : event.key === 'ArrowLeft' ? (index + tabs.length - 1) % tabs.length : null;
      if (next === null) return;
      event.preventDefault(); selectTab(tabs[next]); tabs[next].focus();
    });
  });
  selectTab(tabs[0]);
}

const metricsEnabled = navigator.doNotTrack !== '1' && !navigator.globalPrivacyControl;
const campaignCodes = Object.fromEntries(allowedParams.filter(key => /^[a-zA-Z0-9_-]{1,80}$/.test(campaign.get(key) || '')).map(key => [key, campaign.get(key)]));
const once = new Set();
function track(evento, local, plano = '') {
  if (!metricsEnabled || !window.LOCUFY_CONFIG?.eventsUrl || !crypto.randomUUID) return;
  const key = `${evento}:${local}:${plano}`;
  if (once.has(key)) return;
  once.add(key);
  // text/plain avoids a preflight while navigating away. The server validates JSON,
  // origin, size and a closed list of event names; credentials are never sent.
  fetch(window.LOCUFY_CONFIG.eventsUrl, { method: 'POST', credentials: 'omit', keepalive: true,
    headers: { 'Content-Type': 'text/plain' },
    body: JSON.stringify({ id: crypto.randomUUID(), evento, local, plano, campanha: campaignCodes }),
  }).catch(() => once.delete(key));
}
track('landing_view', 'landing');
document.querySelectorAll('[data-route="register"]').forEach(link => link.addEventListener('click', () => track('register_click', link.dataset.location || 'hero', link.dataset.plan || '')));
document.querySelectorAll('[data-whatsapp]').forEach(link => link.addEventListener('click', () => track('whatsapp_click', link.dataset.plan ? `pricing-${link.dataset.plan.toLowerCase()}` : link.dataset.location || 'contact', link.dataset.plan?.toLowerCase() || '')));
const mediaElements = [...document.querySelectorAll('audio,video')];
mediaElements.forEach(media => {
  media.addEventListener('play', () => {
    mediaElements.filter(other => other !== media).forEach(other => other.pause());
    track(media.tagName === 'VIDEO' ? 'video_play' : 'demo_play', media.dataset.demo || 'video');
  });
});

// Enhancement only: without JS each <audio controls> keeps working with native controls.
function formatTime(seconds) {
  if (!isFinite(seconds) || seconds < 0) return '0:00';
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60).toString().padStart(2, '0');
  return `${m}:${s}`;
}
document.querySelectorAll('.sound-demo audio[data-demo]').forEach(audio => {
  audio.controls = false;
  audio.classList.add('is-enhanced');
  audio.preload = 'metadata';

  const player = document.createElement('div');
  player.className = 'player';
  player.innerHTML = `
    <button type="button" class="player-btn" aria-label="Reproduzir">
      <svg class="icon-play" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M8 5v14l11-7z"/></svg>
      <svg class="icon-pause" viewBox="0 0 24 24" aria-hidden="true" hidden><path fill="currentColor" d="M7 5h4v14H7zM13 5h4v14h-4z"/></svg>
    </button>
    <div class="player-bar">
      <input type="range" class="player-range" min="0" max="100" step="0.1" value="0" aria-label="Progresso do áudio">
      <span class="player-time">0:00 / 0:00</span>
    </div>
    <div class="player-wave" aria-hidden="true"><b></b><b></b><b></b><b></b><b></b></div>
  `;
  audio.insertAdjacentElement('afterend', player);

  const btn = player.querySelector('.player-btn');
  const iconPlay = player.querySelector('.icon-play');
  const iconPause = player.querySelector('.icon-pause');
  const range = player.querySelector('.player-range');
  const time = player.querySelector('.player-time');
  const durationLabel = document.querySelector(`[data-duration-for="${audio.dataset.demo}"]`);
  let seeking = false;

  function paintRange() {
    range.style.background = `linear-gradient(to right, var(--ciano) ${range.value}%, #2c3852 ${range.value}%)`;
  }
  function paintTime(currentTime) {
    if (isFinite(audio.duration) && audio.duration > 0) time.textContent = `${formatTime(currentTime)} / ${formatTime(audio.duration)}`;
  }
  audio.addEventListener('loadedmetadata', () => {
    paintTime(audio.currentTime);
    if (durationLabel && isFinite(audio.duration)) durationLabel.textContent = `${Math.round(audio.duration)} s`;
  });
  audio.addEventListener('timeupdate', () => {
    if (!seeking && audio.duration) { range.value = (audio.currentTime / audio.duration) * 100; paintRange(); }
    paintTime(audio.currentTime);
  });
  audio.addEventListener('play', () => { iconPlay.setAttribute('hidden', ''); iconPause.removeAttribute('hidden'); btn.setAttribute('aria-label', 'Pausar'); player.classList.add('is-playing'); });
  audio.addEventListener('pause', () => { iconPlay.removeAttribute('hidden'); iconPause.setAttribute('hidden', ''); btn.setAttribute('aria-label', 'Reproduzir'); player.classList.remove('is-playing'); });
  audio.addEventListener('ended', () => { range.value = 0; paintRange(); player.classList.remove('is-playing'); });

  btn.addEventListener('click', () => { audio.paused ? audio.play() : audio.pause(); });
  range.addEventListener('input', () => {
    seeking = true;
    paintRange();
    if (audio.duration) paintTime((range.value / 100) * audio.duration);
  });
  range.addEventListener('change', () => {
    if (audio.duration) audio.currentTime = (range.value / 100) * audio.duration;
    seeking = false;
  });
  paintRange();
});

// Enhancement only: sem JavaScript a tabela estática de preço por hora continua visível.
const precos = window.LOCUFY_PRECOS;
const calc = document.querySelector('[data-calc]');
if (calc && precos?.combinacoes?.length) {
  const reais = valor => valor.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
  const select = calc.elements.combinacao;
  precos.combinacoes.forEach(c => {
    const opcao = new Option(`${c.nome} · ≈ ${reais(c.porHora)}/h`, c.id);
    select.add(opcao);
  });
  select.value = (precos.combinacoes.find(c => c.recomendada) || precos.combinacoes[0]).id;
  const total = calc.querySelector('[data-total]');
  const detalhe = calc.querySelector('[data-detalhe]');
  const exemplo = calc.querySelector('[data-exemplo]');
  const numero = (campo, min, max) => Math.min(max, Math.max(min, Number(campo.value) || 0));

  function atualizar() {
    const c = precos.combinacoes.find(item => item.id === select.value);
    const horasMes = numero(calc.elements.horas, 1, 24) * numero(calc.elements.dias, 1, 7) * 30 / 7;
    const locucao = c.porHora * horasMes;
    const whatsapp = c.porMensagem * numero(calc.elements.mensagens, 0, 100000);
    total.textContent = `≈ ${reais(precos.mensalidade + locucao + whatsapp)}`;
    detalhe.textContent = `Mensalidade ${reais(precos.mensalidade)} + locução ≈ ${reais(locucao)} (${Math.round(horasMes)} h no mês) + WhatsApp ≈ ${reais(whatsapp)}`;
    const src = `assets/combinacao-${c.id}.mp3`;
    if (!exemplo.src.endsWith(src)) { exemplo.pause(); exemplo.src = src; }
  }
  calc.addEventListener('input', atualizar);
  calc.addEventListener('submit', event => event.preventDefault());
  calc.hidden = false;
  atualizar();
}

// Sobre o hero, o botão flutuante do WhatsApp fica só com o ícone para não cobrir o card de áudio.
const botaoWhatsapp = document.querySelector('.wa');
const hero = document.querySelector('.hero-shell');
if (botaoWhatsapp && hero && 'IntersectionObserver' in window) {
  new IntersectionObserver(([entrada]) => botaoWhatsapp.classList.toggle('is-compact', entrada.isIntersecting), { threshold: 0.25 }).observe(hero);
}
