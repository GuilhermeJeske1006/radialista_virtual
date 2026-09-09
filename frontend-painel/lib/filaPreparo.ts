/** Mantém a escrita em ordem e sobrepõe a preparação do áudio dos próximos blocos. */
export class FilaPreparo<Contexto, Texto, Preparado> {
  private fila: Promise<Preparado | null>[] = [];
  private contexto: Promise<Contexto | null>;
  private cancelada = false;

  constructor(
    contextoInicial: Contexto,
    private readonly etapas: {
      gerarTexto: (contexto: Contexto) => Promise<Texto>;
      prepararAudio: (texto: Texto, contexto: Contexto) => Promise<Preparado>;
      avancar: (contexto: Contexto, texto: Texto) => Contexto | null;
      descartar: (preparado: Preparado) => void;
    },
    private readonly antecedencia = 2,
  ) {
    this.contexto = Promise.resolve(contextoInicial);
  }

  get ativa() { return !this.cancelada; }

  preencher() {
    if (this.cancelada) return;
    while (this.fila.length < this.antecedencia) {
      const contexto = this.contexto;
      const texto = contexto.then((base) =>
        base === null || this.cancelada ? null : this.etapas.gerarTexto(base),
      );
      // O próximo texto depende do roteiro anterior, mas não da sua voz ou pós-produção.
      this.contexto = Promise.all([contexto, texto]).then(([base, gerado]) =>
        base === null || gerado === null || this.cancelada ? null : this.etapas.avancar(base, gerado),
      );
      const pronto = Promise.all([contexto, texto]).then(async ([base, gerado]) => {
        if (base === null || gerado === null || this.cancelada) return null;
        const preparado = await this.etapas.prepararAudio(gerado, base);
        if (this.cancelada) {
          this.etapas.descartar(preparado);
          return null;
        }
        return preparado;
      });
      // Uma rejeição inesperada só chega ao consumidor na vez deste bloco, sem
      // unhandled rejection enquanto outro conteúdo ainda está tocando.
      this.contexto.catch(() => {});
      pronto.catch(() => {});
      this.fila.push(pronto);
    }
  }

  retirar(): Promise<Preparado | null> {
    if (this.cancelada) return Promise.resolve(null);
    this.preencher();
    const proximo = this.fila.shift()!;
    this.preencher();
    return proximo;
  }

  cancelar() {
    this.cancelada = true;
    for (const pronto of this.fila) {
      // Resultados que já estavam prontos também precisam liberar seus arquivos.
      // Os ainda em andamento são descartados na própria etapa prepararAudio.
      pronto.then((preparado) => {
        if (preparado !== null) this.etapas.descartar(preparado);
      }).catch(() => {});
    }
    this.fila = [];
  }
}
