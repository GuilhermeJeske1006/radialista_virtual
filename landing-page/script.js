const appUrl = new URL(window.LOCUFY_CONFIG?.appUrl || 'https://app.locufybr.com');
if (!['http:', 'https:'].includes(appUrl.protocol)) throw new Error('Configure appUrl com uma URL HTTP ou HTTPS.');
const campaign = new URLSearchParams(location.search);
const allowedParams = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term'];
document.querySelectorAll('[data-route]').forEach(link => {
  const target = new URL(link.dataset.route, `${appUrl.href.replace(/\/$/, '')}/`);
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

const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
if (!reduceMotion && 'IntersectionObserver' in window) {
  const revealTargets = document.querySelectorAll('.feature, .secondary-features article, .gallery-grid figure, .steps li, .price-card');
  const observer = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (!entry.isIntersecting) return;
      entry.target.classList.add('is-visible');
      observer.unobserve(entry.target);
    });
  }, { threshold: 0.15, rootMargin: '0px 0px -8% 0px' });
  revealTargets.forEach(el => {
    el.classList.add('reveal');
    observer.observe(el);
  });
  // Rede de segurança: se algum elemento não revelar sozinho (ex.: navegação
  // programática rápida entre âncoras), garante que nada fique invisível.
  window.addEventListener('load', () => {
    setTimeout(() => revealTargets.forEach(el => el.classList.add('is-visible')), 2500);
  });
}

const whatsappNumber = window.LOCUFY_CONFIG?.whatsappNumber;
if (/^\d{10,15}$/.test(whatsappNumber || '')) {
  document.querySelectorAll('[data-whatsapp]').forEach(link => {
    const message = link.dataset.plan
      ? `Olá! Gostaria de saber mais sobre o plano ${link.dataset.plan} do Locufy para minha rádio.`
      : 'Olá! Quero conhecer o Locufy e escolher um plano para minha rádio.';
    const url = new URL(`https://wa.me/${whatsappNumber}`);
    url.searchParams.set('text', message);
    link.href = url.href;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
  });
}
