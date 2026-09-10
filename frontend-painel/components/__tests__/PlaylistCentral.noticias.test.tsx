import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import PlaylistCentral from "../live/PlaylistCentral";
import { PesquisaNoticias, ProgramSegment } from "../../lib/liveTypes";

function painel(pesquisa?: PesquisaNoticias) {
  const fala: ProgramSegment = {
    id: 1, tipo: "noticia_local", fala: "Segundo o Jornal da Cidade, uma escola foi inaugurada.",
    criado_em: "2026-09-10T12:00:00Z", origem: "ia", pesquisa_noticias: pesquisa,
  };
  return render(<PlaylistCentral
    programaAtivo={false} musicaAtual={null} musicaFimSegundos={null} estagioAtual="idle"
    gerandoFala={false} falasPrograma={[fala]} onProximaFala={vi.fn()}
    musicPlayerRef={{ current: null }} audioFalaRef={{ current: null }} programa={null} totalFalas={1}
  />);
}

describe("Fontes de notícias no histórico", () => {
  it("permite abrir as fontes consultadas sem sair da transmissão", async () => {
    painel({
      status: "ok", consultado_em: "2026-09-10T11:59:00Z",
      fontes: [{ titulo: "Jornal da Cidade", url: "https://jornal.example.com/escola" }],
    });
    await userEvent.click(screen.getByText(/Fontes consultadas/));
    const link = screen.getByRole("link", { name: "Jornal da Cidade" });
    expect(link).toHaveAttribute("href", "https://jornal.example.com/escola");
    expect(link).toHaveAttribute("target", "_blank");
  });

  it.each([
    ["desabilitada", /Ative “Pode pesquisar”/],
    ["indisponivel", /Não foi possível consultar as fontes/],
    ["sem_resultados", /não encontrou notícias recentes/],
  ] as const)("explica pesquisa %s sem mostrar fontes fictícias", (status, mensagem) => {
    painel({ status, fontes: [], consultado_em: null });
    expect(screen.getByText(mensagem)).toBeInTheDocument();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });

  it("mantém o histórico de blocos anteriores sem pesquisa", () => {
    painel();
    expect(screen.getByText(/uma escola foi inaugurada/)).toBeInTheDocument();
    expect(screen.queryByText(/Fontes consultadas/)).not.toBeInTheDocument();
  });
});
