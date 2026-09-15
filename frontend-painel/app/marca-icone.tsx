/** Símbolo Locufy em branco sobre o gradiente — usado pelos ícones gerados via
 *  next/og (favicon, apple-icon, ícones do PWA). */
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
