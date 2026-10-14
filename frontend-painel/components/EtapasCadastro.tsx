const ETAPAS = ["Seus dados", "Sua rádio", "Assinatura"];

/** Etapas do cadastro, também no topo de /onboarding/assinatura (conta que parou antes de pagar). */
export default function EtapasCadastro({ atual }: { atual: 1 | 2 | 3 }) {
  return (
    <ol aria-label="Etapas do cadastro" className="flex gap-3 mb-8">
      {ETAPAS.map((label, i) => (
        <li
          key={label}
          aria-current={atual === i + 1 ? "step" : undefined}
          className={`flex-1 text-sm border-b-2 pb-3 ${atual === i + 1 ? "border-acento-claro text-fg font-semibold" : "border-border text-fg/65"}`}
        >
          <span aria-hidden="true">{i + 1}. </span>
          {label}
          {i + 1 < atual && <span className="sr-only"> (concluída)</span>}
        </li>
      ))}
    </ol>
  );
}
