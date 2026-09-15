type MarkProps = { size?: number; className?: string };

/**
 * Símbolo Locufy: cápsula de microfone dentro do contorno arredondado, com as
 * ondas de transmissão saindo à esquerda.
 *
 * Isto é a reconstrução em SVG inline (herda a cor do tema via CSS vars). Se o
 * arquivo vetorial oficial do manual estiver disponível, troque o conteúdo
 * deste componente pelo SVG exportado do original.
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
    >
      <rect
        x="20.5"
        y="6.5"
        width="35"
        height="51"
        rx="17.5"
        stroke="var(--color-roxo-claro)"
        strokeWidth="3"
      />
      <rect
        x="30"
        y="16"
        width="16"
        height="21"
        rx="8"
        stroke="var(--color-roxo-claro)"
        strokeWidth="3"
      />
      <path
        d="M27 33a11 11 0 0 0 22 0"
        stroke="var(--color-roxo-claro)"
        strokeWidth="3"
        strokeLinecap="round"
      />
      <path d="M38 44v5" stroke="var(--color-roxo-claro)" strokeWidth="3" strokeLinecap="round" />
      <path d="M14 27a9 9 0 0 1 2.6-6.4" stroke="var(--color-ciano)" strokeWidth="2.6" strokeLinecap="round" />
      <path d="M8 28a15 15 0 0 1 4.4-10.6" stroke="var(--color-ciano)" strokeWidth="2.6" strokeLinecap="round" />
      <path d="M2 29a21 21 0 0 1 6.2-14.8" stroke="var(--color-ciano)" strokeWidth="2.6" strokeLinecap="round" />
    </svg>
  );
}

export function LocufyWordmark({ className = "" }: { className?: string }) {
  return <span className={`font-display font-bold tracking-tight ${className}`}>Locufy</span>;
}

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
      <span className="flex flex-col leading-none">
        <LocufyWordmark className={wordmarkClassName} />
        {tagline && (
          <span className="mt-1 text-[10px] text-fg/50">Transforme audiência em conexão.</span>
        )}
      </span>
    </span>
  );
}

/** LED de status piscando, ex.: "no ar" / conectado / gravando. */
export function LocufyLed({ color = "roxo" as "roxo" | "ciano" | "laranja", pulse = true }) {
  const dot = {
    roxo: "bg-roxo-claro shadow-[0_0_8px_var(--color-roxo-claro)]",
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
        <path d="M12 2a10 10 0 0 1 10 10" stroke="var(--color-roxo-claro)" strokeWidth="2" strokeLinecap="round" />
      </svg>
    </span>
  );
}

/** Forma de onda animada, indica áudio ao vivo / geração em andamento. */
export function LocufyWaveform({ bars = 10, className = "" }: { bars?: number; className?: string }) {
  return (
    <span className={`inline-flex items-end gap-[2px] h-4 ${className}`}>
      {Array.from({ length: bars }).map((_, i) => (
        <i
          key={i}
          className="w-[2px] bg-ciano rounded-full animate-pulse"
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
