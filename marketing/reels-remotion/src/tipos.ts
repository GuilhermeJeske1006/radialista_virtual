// Formato de marketing/reels/<id>/montagem.json, gerado por marketing/tools/preparar.mjs.

export type AudioItem = { arquivo: string; inicio_s: number; volume: number };

export type Mensagem = {
  de: "ouvinte" | "locutor" | "sistema";
  texto: string;
  hora?: string;
};

export type Cena = {
  n: number;
  tipo: "tela" | "celular" | "cartela" | "logo";
  titulo: string | null;
  chamada: string | null;
  audios: AudioItem[];
  video?: { arquivo: string; inicio_s: number };
  conversa?: Mensagem[];
  inicio_f: number;
  dur_f: number;
};

export type Legenda = { inicio_f: number; fim_f: number; texto: string; quem: string | null };

export type Montagem = {
  id: string;
  titulo: string;
  fps: number;
  largura: number;
  altura: number;
  total_frames: number;
  trilha: string | null;
  logo: string;
  icone: string;
  cenas: Cena[];
  legendas: Legenda[];
};

export type ReelProps = { id: string; montagem: Montagem | null };
