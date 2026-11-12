/** Pausa progressiva das gerações após falhas; a reprodução segue independente. */
export class RecuperacaoAoVivo {
  private falhas = 0;
  private proximaTentativa = 0;

  disponivel() { return Date.now() >= this.proximaTentativa; }

  sucesso() {
    this.falhas = 0;
    this.proximaTentativa = 0;
  }

  falhou() {
    this.falhas++;
    const espera = Math.min(30_000, 5_000 * 2 ** Math.min(this.falhas - 1, 3));
    this.proximaTentativa = Date.now() + espera + Math.random() * 1_000;
  }

  async aguardar(ativa: () => boolean) {
    // Esperas curtas permitem cancelar ao pausar/trocar o programa.
    while (ativa() && !this.disponivel()) {
      await new Promise((resolve) => setTimeout(resolve, Math.min(250, this.proximaTentativa - Date.now())));
    }
  }
}
