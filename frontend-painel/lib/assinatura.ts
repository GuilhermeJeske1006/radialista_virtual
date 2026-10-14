import { Conta } from "./types";

/** Sem assinatura ativa: geração com IA e ao vivo pedem o Locufy Flex. Conta isenta de cobrança
 * gera sem assinatura. */
export function precisaAssinar(conta: Conta | null): boolean {
  if (!conta || conta.cobranca_isenta) return false;
  return conta.plano_status === "trial" || conta.plano_status === "cancelado";
}

/** Conta que nunca pagou (cadastro parou antes do pagamento): o painel fica fechado até ativar,
 * em /onboarding/assinatura. Cancelada continua entrando para ver extrato e reativar. */
export function assinaturaObrigatoria(conta: Conta | null): boolean {
  return precisaAssinar(conta) && conta?.plano_status === "trial";
}
