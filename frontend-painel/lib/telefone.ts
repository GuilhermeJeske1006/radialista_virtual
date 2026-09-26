// Telefone do WhatsApp chega só com dígitos (ex.: 5547991230010). Formata no padrão
// brasileiro para leitura; número estrangeiro ou fora do padrão aparece como veio.
export function formatarTelefone(telefone: string): string {
  const digitos = telefone.replace(/\D/g, "");
  const nacional = digitos.startsWith("55") && digitos.length >= 12 ? digitos.slice(2) : null;
  if (!nacional) return telefone;
  const ddd = nacional.slice(0, 2);
  const numero = nacional.slice(2);
  if (numero.length === 9) return `+55 (${ddd}) ${numero.slice(0, 5)}-${numero.slice(5)}`;
  if (numero.length === 8) return `+55 (${ddd}) ${numero.slice(0, 4)}-${numero.slice(4)}`;
  return telefone;
}
