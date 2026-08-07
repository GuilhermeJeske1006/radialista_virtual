type MarkProps = { size?: number; className?: string };

/** Dial/tuner needle — the signature ONDA motif, reused across the app. */
export function OndaMark({ size = 34, className = "" }: MarkProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      <circle cx="32" cy="32" r="30" stroke="var(--color-amber)" strokeWidth="2" />
      <circle cx="32" cy="32" r="19" stroke="var(--color-teal)" strokeWidth="1" strokeDasharray="2 4" />
      <line
        x1="32"
        y1="10"
        x2="32"
        y2="26"
        stroke="var(--color-amber)"
        strokeWidth="2"
        strokeLinecap="round"
        transform="rotate(-28 32 32)"
      />
      <circle cx="32" cy="32" r="3" fill="var(--color-fg)" />
    </svg>
  );
}

export function OndaWordmark({ className = "" }: { className?: string }) {
  return (
    <span className={`font-display font-bold tracking-tight ${className}`}>
      ONDA
      <span className="text-amber">.</span>
    </span>
  );
}

export function OndaLogo({ size = 30, wordmarkClassName = "text-lg" }: { size?: number; wordmarkClassName?: string }) {
  return (
    <span className="flex items-center gap-2.5">
      <OndaMark size={size} />
      <OndaWordmark className={wordmarkClassName} />
    </span>
  );
}

/** Small blinking status LED, e.g. "no ar" / conectado / gravando. */
export function OndaLed({ color = "amber" as "amber" | "teal" | "rust", pulse = true }) {
  const dot = { amber: "bg-amber shadow-[0_0_8px_var(--color-amber)]", teal: "bg-teal shadow-[0_0_8px_var(--color-teal)]", rust: "bg-rust shadow-[0_0_8px_var(--color-rust)]" }[color];
  return (
    <span className="relative flex h-2.5 w-2.5 shrink-0">
      {pulse && <span className={`absolute inline-flex h-full w-full rounded-full opacity-75 animate-ping ${dot}`} />}
      <span className={`relative inline-flex rounded-full h-2.5 w-2.5 ${dot}`} />
    </span>
  );
}

/** Compact spinning dial, used as a loading indicator in place of plain "Carregando..." text. */
export function OndaSpin({ size = 20 }: { size?: number }) {
  return (
    <span className="inline-flex animate-spin" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <circle cx="12" cy="12" r="10" stroke="var(--color-border-strong)" strokeWidth="2" />
        <path d="M12 2a10 10 0 0 1 10 10" stroke="var(--color-amber)" strokeWidth="2" strokeLinecap="round" />
      </svg>
    </span>
  );
}

/** Tiny animated waveform, used to indicate live audio/generation. */
export function OndaWaveform({ bars = 10, className = "" }: { bars?: number; className?: string }) {
  return (
    <span className={`inline-flex items-end gap-[2px] h-4 ${className}`}>
      {Array.from({ length: bars }).map((_, i) => (
        <i
          key={i}
          className="w-[2px] bg-teal rounded-full animate-pulse"
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
