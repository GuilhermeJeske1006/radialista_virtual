// Rotulo/cor de cada "status" gravado em InteractionLog (ver backend/app/metrics/router.py) --
// usado tanto na thread de conversas quanto no breakdown de metricas, pra manter os dois com
// a mesma leitura (mesma cor = mesmo significado em qualquer tela do painel).
export const STATUS_LABEL: Record<string, string> = {
  fila_musica: "Pedido de música enviado ao locutor",
  fila_abraco: "Recado/abraço enviado ao locutor",
  bloqueado_horario: "Bloqueada — fora do horário do programa",
  bloqueado_rate_limit: "Bloqueada — limite de mensagens por hora",
  bloqueado_conteudo: "Bloqueada — conteúdo não permitido",
  bloqueado_plano: "Bloqueada — limite de mensagens do plano",
  guardado: "Registrada, sem ação",
};

export const STATUS_COR: Record<string, string> = {
  fila_musica: "text-ciano",
  fila_abraco: "text-ciano",
  bloqueado_horario: "text-laranja",
  bloqueado_rate_limit: "text-laranja",
  bloqueado_conteudo: "text-laranja",
  bloqueado_plano: "text-laranja",
  guardado: "text-fg/55",
};

// Mesma paleta que STATUS_COR, como selo (fundo + texto), pra badges tipo pilula.
export const STATUS_STYLE: Record<string, string> = {
  fila_musica: "bg-ciano/10 text-ciano",
  fila_abraco: "bg-ciano/10 text-ciano",
  bloqueado_horario: "bg-laranja/10 text-laranja",
  bloqueado_rate_limit: "bg-laranja/10 text-laranja",
  bloqueado_conteudo: "bg-laranja/10 text-laranja",
  bloqueado_plano: "bg-laranja/10 text-laranja",
  guardado: "bg-fg/10 text-fg/60",
};

// Mesma paleta que STATUS_COR, em hex, pra usar em preenchimento de SVG (fill nao
// aceita classe utilitaria de cor de texto).
export const STATUS_HEX: Record<string, string> = {
  fila_musica: "#33c2a8",
  fila_abraco: "#33c2a8",
  bloqueado_horario: "#e2543a",
  bloqueado_rate_limit: "#e2543a",
  bloqueado_conteudo: "#e2543a",
  bloqueado_plano: "#e2543a",
  guardado: "#8a8471",
};
