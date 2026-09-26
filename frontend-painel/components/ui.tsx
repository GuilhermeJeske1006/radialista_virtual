/**
 * Primitivas da marca. As telas ainda repetem classes soltas de cartão e botão;
 * conforme forem mexidas, troque por estes componentes para o raio, o peso e o
 * espaçamento pararem de divergir tela a tela.
 */

export function Cartao({
  children,
  className = "",
  destaque = false,
}: {
  children: React.ReactNode;
  className?: string;
  /** Realce por borda de acento, para o cartão que pede ação agora. */
  destaque?: boolean;
}) {
  return (
    <div
      className={`rounded-3xl bg-surface p-5 shadow-theme-xs border ${
        destaque ? "border-acento/50 ring-1 ring-acento/15" : "border-border"
      } ${className}`}
    >
      {children}
    </div>
  );
}

export function TituloSecao({ children, acao }: { children: React.ReactNode; acao?: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4 mb-3">
      <h2 className="font-display text-base font-semibold text-fg">{children}</h2>
      {acao}
    </div>
  );
}

type BotaoProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variante?: "primario" | "secundario" | "fantasma" | "destrutivo";
};

const VARIANTES: Record<NonNullable<BotaoProps["variante"]>, string> = {
  primario: "bg-acento text-on-brand hover:bg-brand-600",
  secundario: "border border-border-strong text-fg hover:bg-fg/5",
  fantasma: "text-fg/65 hover:bg-fg/5 hover:text-fg",
  destrutivo: "bg-laranja text-grafite hover:opacity-90",
};

/** Pílula: mesma forma da cápsula do símbolo. */
export function Botao({ variante = "primario", className = "", ...props }: BotaoProps) {
  return (
    <button
      {...props}
      className={`inline-flex items-center justify-center gap-2 rounded-full px-4 py-2.5 text-sm font-semibold transition-colors disabled:opacity-60 disabled:cursor-not-allowed ${VARIANTES[variante]} ${className}`}
    />
  );
}

export function Chip({
  children,
  tom = "neutro",
}: {
  children: React.ReactNode;
  tom?: "neutro" | "acento" | "ciano" | "laranja";
}) {
  const tons = {
    neutro: "bg-fg/5 text-fg/65",
    acento: "bg-acento/15 text-acento-claro",
    ciano: "bg-ciano/15 text-ciano",
    laranja: "bg-laranja/15 text-laranja",
  }[tom];
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ${tons}`}>
      {children}
    </span>
  );
}

/** Tela vazia: convite para agir, nunca só "nada aqui". */
export function Vazio({
  titulo,
  descricao,
  acao,
}: {
  titulo: string;
  descricao: string;
  acao?: React.ReactNode;
}) {
  return (
    <div className="rounded-3xl border border-dashed border-border-strong px-6 py-12 text-center">
      <p className="font-display text-base font-semibold text-fg">{titulo}</p>
      <p className="mt-1 text-sm text-fg/65">{descricao}</p>
      {acao && <div className="mt-5 flex justify-center">{acao}</div>}
    </div>
  );
}
