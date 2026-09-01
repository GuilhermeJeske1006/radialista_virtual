import type { Metadata } from "next";
import Link from "next/link";
import { LocufyLogo } from "../../components/LocufyLogo";
import ThemeToggle from "../../components/ThemeToggle";

export const metadata: Metadata = {
  title: "Central de Ajuda — Locufy",
  description: "Documentação da Locufy: como configurar seu radialista virtual, programação, WhatsApp, equipe e planos.",
};

type Secao = { id: string; titulo: string };
type Grupo = { titulo: string; secoes: Secao[] };

const NAV: Grupo[] = [
  {
    titulo: "Primeiros passos",
    secoes: [{ id: "primeiros-passos", titulo: "Configuração inicial" }],
  },
  {
    titulo: "Conteúdo",
    secoes: [
      { id: "radialistas", titulo: "Radialistas virtuais" },
      { id: "programas-grade", titulo: "Programas e grade" },
      { id: "vinhetagem", titulo: "Vinhetagem" },
    ],
  },
  {
    titulo: "Operação",
    secoes: [
      { id: "whatsapp", titulo: "WhatsApp" },
      { id: "conversas", titulo: "Conversas" },
      { id: "ao-vivo", titulo: "Ao Vivo" },
      { id: "metricas", titulo: "Métricas" },
    ],
  },
  {
    titulo: "Conta",
    secoes: [
      { id: "equipe", titulo: "Equipe" },
      { id: "assinatura", titulo: "Assinatura e planos" },
      { id: "dados-radio", titulo: "Dados da rádio" },
      { id: "perfil", titulo: "Perfil" },
    ],
  },
  {
    titulo: "Ajuda",
    secoes: [{ id: "faq", titulo: "Perguntas frequentes" }],
  },
];

function H2({ id, children }: { id: string; children: React.ReactNode }) {
  return (
    <h2 id={id} className="font-display text-lg font-semibold text-fg mb-2 scroll-mt-24">
      {children}
    </h2>
  );
}

function Dica({ children }: { children: React.ReactNode }) {
  return (
    <p className="mt-3 rounded-lg border border-border bg-surface px-4 py-3 text-xs text-fg/65">
      <strong className="text-fg">Dica:</strong> {children}
    </p>
  );
}

function Shot({ src, legenda }: { src: string; legenda: string }) {
  return (
    <figure className="mt-4">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={`/ajuda/screenshots/${src}.png`}
        alt={legenda}
        className="w-full rounded-xl border border-border-strong shadow-theme-xs"
      />
      <figcaption className="mt-1.5 text-xs text-fg/50">{legenda}</figcaption>
    </figure>
  );
}

function Clip({ src, legenda }: { src: string; legenda: string }) {
  return (
    <figure className="mt-4">
      <video
        src={`/ajuda/videos/${src}.mp4`}
        controls
        loop
        muted
        playsInline
        className="w-full rounded-xl border border-border-strong shadow-theme-xs"
      />
      <figcaption className="mt-1.5 text-xs text-fg/50">{legenda}</figcaption>
    </figure>
  );
}

export default function AjudaPage() {
  return (
    <div className="min-h-screen bg-bg">
      <header className="border-b border-border">
        <div className="max-w-5xl mx-auto px-4 py-5 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2">
            <LocufyLogo wordmarkClassName="text-xl" />
          </Link>
          <ThemeToggle />
        </div>
      </header>

      <div className="max-w-5xl mx-auto px-4 py-12 md:grid md:grid-cols-[200px_1fr] md:gap-10">
        <nav className="hidden md:block sticky top-12 self-start space-y-6">
          {NAV.map((grupo) => (
            <div key={grupo.titulo}>
              <div className="text-xs font-medium uppercase tracking-wide text-fg/50 mb-2 font-mono">
                {grupo.titulo}
              </div>
              <ul className="space-y-1">
                {grupo.secoes.map((s) => (
                  <li key={s.id}>
                    <a href={`#${s.id}`} className="text-sm text-fg/65 hover:text-amber-text">
                      {s.titulo}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </nav>

        <main>
          <h1 className="font-display text-2xl font-bold text-fg mb-2">Central de Ajuda</h1>
          <p className="text-sm text-fg/65 mb-10">
            Como configurar e operar sua rádio na Locufy. Não achou o que precisa? Escreva pra{" "}
            <a href="mailto:contato@locufy.com" className="text-amber-text hover:text-amber-dim">
              contato@locufy.com
            </a>
            .
          </p>

          <div className="space-y-10 text-sm leading-relaxed text-fg/80">
            <section>
              <H2 id="primeiros-passos">Configuração inicial</H2>
              <p>Ao criar sua conta, três passos deixam a rádio pronta pra operar:</p>
              <ol className="list-decimal pl-5 mt-2 space-y-1">
                <li>
                  <strong className="text-fg">Criar o radialista</strong> — dê um nome e descreva o
                  perfil (gênero musical, tom, público); a Locufy gera a personalidade e o primeiro
                  programa automaticamente via IA.
                </li>
                <li>
                  <strong className="text-fg">Conectar o WhatsApp</strong> — em{" "}
                  <em>Conta → WhatsApp</em>, escaneie o QR code pra ligar o número da rádio ao
                  radialista.
                </li>
                <li>
                  <strong className="text-fg">Revisar o programa</strong> — confira ou ajuste
                  horários, tom e tópicos gerados em <em>Conteúdo → Programas</em>.
                </li>
              </ol>
              <p className="mt-2">
                Enquanto esses passos não terminam, a barra lateral numera os links correspondentes
                pra guiar o setup.
              </p>
              <Shot src="dashboard" legenda="Dashboard logo após criar a conta, com o checklist de setup." />
            </section>

            <section>
              <H2 id="radialistas">Radialistas virtuais</H2>
              <p>
                Um radialista é a persona de IA que apresenta sua rádio: tem nome, personalidade, voz
                e fuso horário. Ele pode ser gerado a partir de uma descrição livre (IA preenche
                personalidade e voz) ou configurado manualmente.
              </p>
              <Shot src="radialistas-vazio" legenda="Tela de Radialistas antes de criar o primeiro." />
              <p className="mt-2">
                A voz vem de um catálogo pré-definido; nos planos Growth e Professional é possível
                clonar uma voz real enviando uma amostra de áudio (clonagem de voz ElevenLabs).
              </p>
              <p className="mt-2">
                Quantos radialistas sua conta pode ter depende do plano (veja{" "}
                <a href="#assinatura" className="text-amber-text hover:text-amber-dim">
                  Assinatura e planos
                </a>
                ); é possível comprar radialistas extras além do limite do plano.
              </p>
              <Clip src="criar-radialista" legenda="Gerando um radialista com IA a partir de uma descrição curta." />
              <Shot src="radialista-detalhe" legenda="Tela de edição do radialista: nome, voz e programação." />
            </section>

            <section>
              <H2 id="programas-grade">Programas e grade</H2>
              <p>
                Um <strong className="text-fg">programa</strong> define as regras de uma faixa de
                horário: dias da semana, horário de início/fim, tom, tópicos permitidos e proibidos,
                gêneros musicais, mensagem de saudação/recusa e a estrutura de blocos (abertura,
                música, recado, notícia, encerramento). Um programa pode ter mais de um radialista
                como co-apresentador, dependendo do plano.
              </p>
              <p className="mt-2">
                A <strong className="text-fg">grade de programação</strong> (Conteúdo → Grade) mostra
                a semana inteira e qual programa está no ar em cada horário.
              </p>
              <Dica>
                Tópicos como política e religião entram em &quot;proibidos&quot; por padrão em
                programas gerados por IA, a menos que você peça o contrário na descrição.
              </Dica>
              <Shot src="programas" legenda="Lista de programas cadastrados." />
              <Shot src="programacao-grade" legenda="Grade semanal, com o horário de cada programa." />
            </section>

            <section>
              <H2 id="vinhetagem">Vinhetagem</H2>
              <p>
                Biblioteca de áudios (vinhetas, spots de patrocinador) organizada por categoria, com
                busca e paginação dentro de cada categoria. O radialista pode usar esses áudios ao
                montar a programação, conforme as regras do programa.
              </p>
              <Shot src="vinhetagem" legenda="Categorias da vinhetagem, cada uma marcada como biblioteca ou propaganda." />
            </section>

            <section>
              <H2 id="whatsapp">WhatsApp</H2>
              <p>
                Cada conta tem um único número de WhatsApp, compartilhado por todos os radialistas da
                rádio. Conecte em <em>Conta → WhatsApp</em> escaneando o QR code. Se a sessão cair,
                avisamos o admin por e-mail automaticamente até a reconexão.
              </p>
              <Shot src="whatsapp-antes-conectar" legenda="Tela de conexão antes de escanear o QR code." />
              <Clip src="conectar-whatsapp" legenda="Gerando o QR code pra conectar o número da rádio." />
            </section>

            <section>
              <H2 id="conversas">Conversas</H2>
              <p>
                Histórico das mensagens trocadas entre ouvintes e o radialista pelo WhatsApp, com
                filtro por período (últimos 7, 30 ou 90 dias) — útil pra revisar como a IA está
                respondendo.
              </p>
              <Shot src="conversas" legenda="Histórico de conversas, com filtro por período." />
            </section>

            <section>
              <H2 id="ao-vivo">Ao Vivo</H2>
              <p>
                Painel de acompanhamento em tempo real de qual programa está no ar e o que o
                radialista está executando.
              </p>
              <Shot src="ao-vivo" legenda="Painel Ao Vivo." />
            </section>

            <section>
              <H2 id="metricas">Métricas</H2>
              <p>
                Volume de mensagens recebidas por dia, com o mesmo filtro de período de Conversas —
                ajuda a entender o consumo frente à franquia mensal do plano.
              </p>
              <Shot src="metricas" legenda="Métricas de mensagens recebidas por dia." />
            </section>

            <section>
              <H2 id="equipe">Equipe</H2>
              <p>
                Só administradores acessam esta tela. Convide pessoas por e-mail e defina o papel:{" "}
                <strong className="text-fg">admin</strong> (gerencia equipe, configurações e
                assinatura) ou <strong className="text-fg">membro</strong> (opera o dia a dia, sem
                acesso a billing/equipe). Remover alguém desativa o acesso sem apagar o histórico
                associado a esse usuário.
              </p>
              <Shot src="equipe" legenda="Convite de equipe e lista de membros." />
            </section>

            <section>
              <H2 id="assinatura">Assinatura e planos</H2>
              <p>Três planos, cobrados por assinatura recorrente, com período de teste gratuito:</p>
              <div className="overflow-x-auto mt-2">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="border-b border-border text-fg/60">
                      <th className="py-2 pr-4 font-medium">Plano</th>
                      <th className="py-2 pr-4 font-medium">Radialistas</th>
                      <th className="py-2 pr-4 font-medium">Mensagens/mês</th>
                      <th className="py-2 pr-4 font-medium">Co-apresentadores</th>
                      <th className="py-2 font-medium">Clonagem de voz</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr className="border-b border-border">
                      <td className="py-2 pr-4">Starter</td>
                      <td className="py-2 pr-4">1</td>
                      <td className="py-2 pr-4">1.000</td>
                      <td className="py-2 pr-4">1</td>
                      <td className="py-2">—</td>
                    </tr>
                    <tr className="border-b border-border">
                      <td className="py-2 pr-4">Growth</td>
                      <td className="py-2 pr-4">3</td>
                      <td className="py-2 pr-4">3.000</td>
                      <td className="py-2 pr-4">2</td>
                      <td className="py-2">Sim</td>
                    </tr>
                    <tr>
                      <td className="py-2 pr-4">Professional</td>
                      <td className="py-2 pr-4">5</td>
                      <td className="py-2 pr-4">7.500</td>
                      <td className="py-2 pr-4">3</td>
                      <td className="py-2">Sim</td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <p className="mt-2">
                Radialista extra além do limite do plano e excedente de mensagens acima da franquia
                são cobrados à parte, com o valor exibido na tela de Assinatura antes de confirmar.
                O cancelamento pode ser feito a qualquer momento e vale até o fim do período já
                pago.
              </p>
              <Shot src="assinatura" legenda="Comparativo de planos na tela de Assinatura." />
            </section>

            <section>
              <H2 id="dados-radio">Dados da rádio</H2>
              <p>
                Em <em>Conta → Dados da rádio</em> ficam nome, slogan, frequência, telefone, endereço
                e cidade da emissora — usados pra personalizar as respostas do radialista, e a
                cidade também alimenta a previsão do tempo real que o locutor pode citar no ar.
              </p>
              <Shot src="configuracoes-salvo" legenda="Formulário de dados da rádio." />
            </section>

            <section>
              <H2 id="perfil">Perfil</H2>
              <p>
                Seus dados pessoais e o status atual do plano da conta (em teste, ativo ou pagamento
                pendente).
              </p>
              <Shot src="perfil" legenda="Tela de Perfil." />
            </section>

            <section>
              <H2 id="faq">Perguntas frequentes</H2>
              <div className="space-y-4">
                <div>
                  <p className="font-medium text-fg">O radialista pode errar ou inventar algo?</p>
                  <p>
                    Sim — as respostas e roteiros são gerados por IA de forma probabilística e podem
                    conter imprecisões. Vale revisar programas antes de deixar tópicos sensíveis
                    liberados. Detalhes em{" "}
                    <Link href="/termos" className="text-amber-text hover:text-amber-dim">
                      Termos de Uso
                    </Link>
                    .
                  </p>
                </div>
                <div>
                  <p className="font-medium text-fg">Posso ter mais de um radialista?</p>
                  <p>
                    Sim, até o limite do seu plano (veja{" "}
                    <a href="#assinatura" className="text-amber-text hover:text-amber-dim">
                      Assinatura e planos
                    </a>
                    ); dá pra comprar radialistas extras além do limite.
                  </p>
                </div>
                <div>
                  <p className="font-medium text-fg">O conteúdo que envio é usado pra treinar IA?</p>
                  <p>
                    Não. Veja como tratamos seus dados na{" "}
                    <Link href="/privacidade" className="text-amber-text hover:text-amber-dim">
                      Política de Privacidade
                    </Link>
                    .
                  </p>
                </div>
                <div>
                  <p className="font-medium text-fg">O que acontece se a sessão do WhatsApp cair?</p>
                  <p>
                    O admin da conta recebe um alerta por e-mail; basta reconectar escaneando o QR
                    code de novo em <em>Conta → WhatsApp</em>.
                  </p>
                </div>
                <div>
                  <p className="font-medium text-fg">Como cancelo minha assinatura?</p>
                  <p>
                    Em <em>Conta → Assinatura</em> (acesso admin). O acesso continua até o fim do
                    período já pago.
                  </p>
                </div>
              </div>
            </section>
          </div>
        </main>
      </div>
    </div>
  );
}
