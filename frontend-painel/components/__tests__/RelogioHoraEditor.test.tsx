import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import RelogioHoraEditor from "../RelogioHoraEditor";
import { RelogioHora } from "../../lib/types";
import { presetsFixture } from "../../lib/__tests__/relogioFixtures";

function Controlado({ inicial = null, onChange }: { inicial?: RelogioHora | null; onChange?: (r: RelogioHora | null) => void }) {
  const [valor, setValor] = useState<RelogioHora | null>(inicial);
  return (
    <RelogioHoraEditor
      valor={valor}
      presets={presetsFixture()}
      janelaSegundos={3600}
      onChange={(r) => { setValor(r); onChange?.(r); }}
    />
  );
}

function linhas() {
  return within(screen.getByRole("table")).getAllByRole("row").slice(1);
}

describe("RelogioHoraEditor", () => {
  it("escolher o preset A mostra 12 etapas que somam 60:00, com horário fixo", async () => {
    render(<Controlado />);
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText("Relógio da hora"), "A");
    expect(linhas()).toHaveLength(12);
    expect(screen.getByTestId("relogio-total")).toHaveTextContent("Total: 60:00");
    expect(linhas()[0]).toHaveTextContent("00:00");
    expect(linhas()[4]).toHaveTextContent("24:00");
    expect(within(linhas()[4]).getByText("horário fixo")).toBeInTheDocument();
    expect(screen.getByText(/a sequência deixa de rodar em loop/)).toBeInTheDocument();
    expect(screen.getByText(/os tempos são hipóteses/i)).toBeInTheDocument();
  });

  it("ajustar o link de 0:35 para 0:50 tira 15 s da música seguinte e mantém 60:00", async () => {
    const mudancas = vi.fn();
    render(<Controlado onChange={mudancas} />);
    await userEvent.selectOptions(screen.getByLabelText("Relógio da hora"), "A");
    const campo = screen.getByLabelText("Duração do evento 3 (Link com um assunto)");
    await userEvent.clear(campo);
    await userEvent.type(campo, "0:50");
    fireEvent.blur(campo);
    const ultimo = mudancas.mock.calls.at(-1)![0] as RelogioHora;
    expect(ultimo.eventos[2].duracao_s).toBe(50);
    expect(ultimo.eventos[3].duracao_s).toBe(670);
    expect(screen.getByLabelText("Duração do evento 4 (Sequência musical B)")).toHaveValue("11:10");
    expect(linhas()[4]).toHaveTextContent("24:00");
    expect(screen.getByTestId("relogio-total")).toHaveTextContent("Total: 60:00");

    await userEvent.click(screen.getByRole("button", { name: "Aumentar 5 s: Passagem de hora" }));
    expect((mudancas.mock.calls.at(-1)![0] as RelogioHora).eventos[10].duracao_s).toBe(205);
  });

  it("mostra o erro e mantém o valor quando não dá para compensar", async () => {
    render(<Controlado />);
    await userEvent.selectOptions(screen.getByLabelText("Relógio da hora"), "A");
    const campo = screen.getByLabelText("Duração do evento 10 (Intervalo)");
    await userEvent.clear(campo);
    await userEvent.type(campo, "6:20{Enter}");
    expect(screen.getByRole("alert")).toHaveTextContent(/mínimo é 00:30/);
    expect(screen.getByLabelText("Duração do evento 11 (Música de fechamento)")).toHaveValue("03:30");
  });

  it("'Sem relógio' devolve null e esconde a tabela", async () => {
    const mudancas = vi.fn();
    render(<Controlado onChange={mudancas} />);
    await userEvent.selectOptions(screen.getByLabelText("Relógio da hora"), "A");
    await userEvent.selectOptions(screen.getByLabelText("Em feriados"), "sem_intervalos");
    expect((mudancas.mock.calls.at(-1)![0] as RelogioHora).em_feriado).toBe("sem_intervalos");
    await userEvent.selectOptions(screen.getByLabelText("Relógio da hora"), "");
    expect(mudancas).toHaveBeenLastCalledWith(null);
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });
});
