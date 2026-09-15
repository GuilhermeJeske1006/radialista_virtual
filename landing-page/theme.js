(() => {
  const key = 'locufy-landing-theme';
  const root = document.documentElement;
  root.classList.add('js');
  const system = window.matchMedia('(prefers-color-scheme: dark)');
  const valid = value => value === 'light' || value === 'dark';
  let preference;
  try { preference = localStorage.getItem(key); } catch { /* Preferência apenas nesta visita. */ }

  function apply() {
    const theme = valid(preference) ? preference : system.matches ? 'dark' : 'light';
    root.dataset.theme = theme;
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content', theme === 'dark' ? '#131c2e' : '#ffffff');
    const toggle = document.getElementById('theme-toggle');
    if (toggle) {
      const label = theme === 'dark' ? 'Mudar para tema claro' : 'Mudar para tema escuro';
      toggle.setAttribute('aria-label', label);
      toggle.title = label;
      toggle.hidden = false;
    }
  }

  // Executado no head antes do CSS para evitar um flash do tema incorreto.
  apply();
  document.addEventListener('DOMContentLoaded', () => {
    apply();
    document.getElementById('theme-toggle')?.addEventListener('click', () => {
      preference = root.dataset.theme === 'dark' ? 'light' : 'dark';
      try { localStorage.setItem(key, preference); } catch { /* A troca continua funcionando. */ }
      apply();
    });
  });
  system.addEventListener('change', () => { if (!valid(preference)) apply(); });
  window.addEventListener('storage', event => {
    if (event.key === key || event.key === null) {
      preference = event.newValue;
      apply();
    }
  });
})();
