type MarkProps = { size?: number; className?: string };

/**
 * Símbolo Locufy: microfone dentro do contorno em cápsula, com as ondas de
 * transmissão saindo à esquerda. Monoline em currentColor — igual ao logo
 * oficial, que é sempre de uma cor só (branco sobre o gradiente, azul sobre
 * fundo claro). Tendo o vetor do manual, troque o conteúdo deste componente e
 * mantenha currentColor.
 */
export function LocufyMark({ size = 34, className = "" }: MarkProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-hidden="true"
    >
      <rect x="21.5" y="7.5" width="33" height="49" rx="16.5" stroke="currentColor" strokeWidth="3" />
      <rect x="30" y="17" width="16" height="21" rx="8" stroke="currentColor" strokeWidth="3" />
      <path d="M28 34a10 10 0 0 0 20 0" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
      <path d="M38 44v5" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
      <path d="M15 27a8 8 0 0 1 2.4-5.7" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" />
      <path d="M9.5 28a14 14 0 0 1 4-9.9" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" />
      <path d="M4 29a20 20 0 0 1 5.7-14.1" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" />
    </svg>
  );
}

export function LocufyWordmark({ className = "" }: { className?: string }) {
  return <span className={`font-display font-medium tracking-tight ${className}`}>Locufy</span>;
}

/** Lockup completo. Herda a cor do container, então serve tanto em cima do
 *  gradiente quanto de fundo neutro, sem variante extra. */
export function LocufyLogo({
  size = 30,
  wordmarkClassName = "text-lg",
  tagline = false,
}: {
  size?: number;
  wordmarkClassName?: string;
  tagline?: boolean;
}) {
  return (
    <span className="flex items-center gap-2.5">
      <LocufyMark size={size} />
      <span className="flex flex-col">
        <LocufyWordmark className={wordmarkClassName} />
        {tagline && (
          <span className="text-[10px] font-semibold opacity-75">Transforme audiência em conexão.</span>
        )}
      </span>
    </span>
  );
}

/** LED de status piscando: no ar / conectado / gravando. */
export function LocufyLed({ color = "acento" as "acento" | "ciano" | "laranja", pulse = true }) {
  const dot = {
    acento: "bg-acento-claro shadow-[0_0_8px_var(--color-acento-claro)]",
    ciano: "bg-ciano shadow-[0_0_8px_var(--color-ciano)]",
    laranja: "bg-laranja shadow-[0_0_8px_var(--color-laranja)]",
  }[color];
  return (
    <span className="relative flex h-2.5 w-2.5 shrink-0">
      {pulse && <span className={`absolute inline-flex h-full w-full rounded-full opacity-75 animate-ping ${dot}`} />}
      <span className={`relative inline-flex rounded-full h-2.5 w-2.5 ${dot}`} />
    </span>
  );
}

/** Indicador de carregamento no lugar do "Carregando..." de texto puro. */
export function LocufySpin({ size = 20 }: { size?: number }) {
  return (
    <span className="inline-flex animate-spin" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <circle cx="12" cy="12" r="10" stroke="var(--color-border-strong)" strokeWidth="2" />
        <path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      </svg>
    </span>
  );
}

/** Forma de onda animada: áudio ao vivo / geração em andamento. */
export function LocufyWaveform({ bars = 10, className = "" }: { bars?: number; className?: string }) {
  return (
    <span className={`inline-flex items-end gap-[2px] h-4 ${className}`} aria-hidden="true">
      {Array.from({ length: bars }).map((_, i) => (
        <i
          key={i}
          className="w-[2px] bg-current rounded-full animate-pulse"
          style={{
            height: `${30 + ((i * 37) % 70)}%`,
            animationDelay: `${i * 0.1}s`,
            animationDuration: "1s",
          }}
        />
      ))}
    </span>
  );
}
