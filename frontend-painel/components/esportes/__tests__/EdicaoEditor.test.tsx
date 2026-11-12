import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import EdicaoEditor from "../EdicaoEditor";
import type { EdicaoEsportiva, PerfilEsportivo } from "../../../lib/esportes";

const request = vi.fn();
vi.mock("../../../lib/api", () => ({ apiFetch: (...args: unknown[]) => request(...args) }));
const perfil: PerfilEsportivo = { nome: "Esportes", regiao: "Brusque", clubes: [], campeonatos: [], modalidades: ["Futebol"], fuso: "America/Sao_Paulo", estilo: "Moderado", identidade_sonora: "Vinhetas breves", participacao: false, distribuicao: { regional: 40, nacional: 35, internacional: 15, outras: 10 } };
function fixture(): EdicaoEsportiva {
  return { id: 1, programa_id: 1, revisao: 4, estado: "em_revisao", conteudo: { titulo: "Edição teste", modelo: "boletim_2", exibicao_em: "2026-11-11T19:00:00Z", perfil, fatos: [], blocos: [{ id: 'b1', titulo: "Abertura", tipo: "abertura", duracao_s: 120, responsavel: "Apresentador", transicao: "", opcional: false, reserva: "", texto: "Boa tarde.", fato_ids: [] }] }, alertas: [], alertas_audio: ['Áudio pendente'], audios: {}, aprovacao_audio: null, aprovacao_roteiro: null, historico: [] };
}
describe("revisão editorial", () => {
  it("exige atestado do editor e envia a revisão correta", async () => {
    const e = fixture();
    request.mockResolvedValue({ ...e, revisao: 5, aprovacao_roteiro: { usuario_id: 2, em: "2026-11-11T18:00:00Z" } });
    const salvar = vi.fn();
    render(<EdicaoEditor edicao={e} fontes={[]} onSave={salvar} onDirty={vi.fn()} />);
    expect(screen.getByRole('button', { name: 'Aprovar roteiro desta versão' })).toBeDisabled();
    await userEvent.click(screen.getByLabelText(/Conferi cada afirmação/));
    await userEvent.click(screen.getByRole('button', { name: 'Aprovar roteiro desta versão' }));
    expect(JSON.parse(request.mock.calls.at(-1)![1].body)).toEqual({ revisao: 4, conferido: true });
    expect(salvar).toHaveBeenCalled();
  });
  it("impede geração e aprovação enquanto houver alteração local", async () => {
    render(<EdicaoEditor edicao={fixture()} fontes={[]} onSave={vi.fn()} onDirty={vi.fn()} />);
    await userEvent.type(screen.getByLabelText('Fala proposta'), ' Conteúdo revisado.');
    expect(screen.getByRole('button', { name: 'Sugerir fala com IA' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Salvar edição' })).toBeEnabled();
    expect(screen.getByRole('button', { name: 'Aprovar roteiro desta versão' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Exportar edição em MP3' })).toBeDisabled();
  });
  it("expõe bloqueios e suas evidências sem permitir aprovação", () => {
    render(<EdicaoEditor edicao={{ ...fixture(), alertas: ['Fato f1: fontes divergentes.'] }} fontes={[]} onSave={vi.fn()} onDirty={vi.fn()} />);
    expect(screen.getByText('Fato f1: fontes divergentes.')).toBeVisible();
    expect(screen.getByLabelText(/Conferi cada afirmação/)).toBeDisabled();
  });
});
