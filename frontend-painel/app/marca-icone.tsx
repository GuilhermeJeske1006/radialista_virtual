/** Símbolo Locufy em branco sobre o gradiente — usado pelos ícones gerados via
 *  next/og (apple-icon, ícones do PWA), onde o mark é grande o bastante para
 *  mostrar o microfone completo com as ondas de transmissão. */
export function MarcaIcone({ canvas, mark }: { canvas: number; mark: number }) {
  return (
    <div
      style={{
        width: canvas,
        height: canvas,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "linear-gradient(110deg, #631BF6 0%, #3167E7 52%, #00B4D8 100%)",
      }}
    >
      <svg width={mark} height={mark} viewBox="0 0 64 64" fill="none">
        <rect x="21.5" y="7.5" width="33" height="49" rx="16.5" stroke="#FFFFFF" strokeWidth="3" />
        <rect x="30" y="17" width="16" height="21" rx="8" stroke="#FFFFFF" strokeWidth="3" />
        <path d="M28 34a10 10 0 0 0 20 0" stroke="#FFFFFF" strokeWidth="3" strokeLinecap="round" />
        <path d="M38 44v5" stroke="#FFFFFF" strokeWidth="3" strokeLinecap="round" />
        <path d="M15 27a8 8 0 0 1 2.4-5.7" stroke="#FFFFFF" strokeWidth="2.6" strokeLinecap="round" />
        <path d="M9.5 28a14 14 0 0 1 4-9.9" stroke="#FFFFFF" strokeWidth="2.6" strokeLinecap="round" />
        <path d="M4 29a20 20 0 0 1 5.7-14.1" stroke="#FFFFFF" strokeWidth="2.6" strokeLinecap="round" />
      </svg>
    </div>
  );
}

/** Versão do símbolo para o favicon (16–32px): sem as ondas de transmissão
 *  (viram ruído nesse tamanho) e recortado/centrado na cápsula do microfone,
 *  com traço mais grosso para não sumir na aba do navegador. */
export function MarcaIconeFavicon({ canvas, mark }: { canvas: number; mark: number }) {
  return (
    <div
      style={{
        width: canvas,
        height: canvas,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        borderRadius: canvas * 0.26,
        background: "linear-gradient(110deg, #631BF6 0%, #3167E7 52%, #00B4D8 100%)",
      }}
    >
      <svg width={mark} height={mark} viewBox="9 3 58 58" fill="none">
        <rect x="21.5" y="7.5" width="33" height="49" rx="16.5" stroke="#FFFFFF" strokeWidth="4.5" />
        <rect x="30" y="17" width="16" height="21" rx="8" stroke="#FFFFFF" strokeWidth="4.5" />
        <path d="M28 34a10 10 0 0 0 20 0" stroke="#FFFFFF" strokeWidth="4.5" strokeLinecap="round" />
        <path d="M38 44v5" stroke="#FFFFFF" strokeWidth="4.5" strokeLinecap="round" />
      </svg>
    </div>
  );
}
