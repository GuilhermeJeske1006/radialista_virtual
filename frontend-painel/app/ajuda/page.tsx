import type { Metadata } from "next";
import Link from "next/link";
import { LocufyLogo } from "../../components/LocufyLogo";
import ThemeToggle from "../../components/ThemeToggle";

export const metadata: Metadata = {
  title: "Central de Ajuda — Locufy",
  description: "Documentação da Locufy: como configurar seu radialista virtual, programação, WhatsApp, equipe, assinatura e consumo.",
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
      { id: "conversas", titulo: "Conversas e WhatsApp" },
      { id: "ao-vivo", titulo: "Ao Vivo" },
      { id: "metricas", titulo: "Métricas" },
    ],
  },
  {
    titulo: "Conta",
    secoes: [
      { id: "equipe", titulo: "Equipe" },
      { id: "assinatura", titulo: "Assinatura e consumo" },
      { id: "dados-radio", titulo: "Configuração" },
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
    <p className="mt-3 rounded-xl border border-border bg-surface px-4 py-3 text-xs text-fg/65">
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
      <figcaption className="mt-1.5 text-xs text-fg/65">{legenda}</figcaption>
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
              <div className="text-xs font-medium uppercase tracking-wide text-fg/65 mb-2 font-mono">
                {grupo.titulo}
              </div>
              <ul className="space-y-1">
                {grupo.secoes.map((s) => (
                  <li key={s.id}>
                    <a href={`#${s.id}`} className="text-sm text-fg/65 hover:text-acento-claro">
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
            <a href="mailto:contato@locufy.com" className="text-acento-claro underline hover:text-acento-dim">
              contato@locufy.com
            </a>
            .
          </p>

          <div className="space-y-10 text-sm leading-relaxed text-fg/80">
            <section>
              <H2 id="primeiros-passos">Configuração inicial</H2>
              <p>
                Ao criar sua conta, a <em>Visão geral</em> mostra um checklist com os passos que
                faltam pra rádio ficar pronta:
              </p>
              <ol className="list-decimal pl-5 mt-2 space-y-1">
                <li>
                  <strong className="text-fg">Criar o radialista</strong> — descreva o perfil (gênero
                  musical, tom, público) e a Locufy gera nome, voz, personalidade e o primeiro programa.
                  Ou configure cada campo manualmente.
                </li>
                <li>
                  <strong className="text-fg">Cadastrar o programa</strong> — confira ou ajuste
                  horários, tom e tópicos em <em>Conteúdo → Programas</em>. É preciso ao menos um
                  programa ativo.
                </li>
                <li>
                  <strong className="text-fg">Conectar o WhatsApp</strong> — em{" "}
                  <em>Conta → Configuração → WhatsApp da rádio</em>, clique em &quot;Conectar
                  WhatsApp&quot; e escaneie o QR code com o celular da rádio.
                </li>
                <li>
                  <strong className="text-fg">Instalar o app e liberar o som</strong> — em cada
                  computador que toca a rádio, para o ao vivo sair sozinho, sem precisar clicar.
                </li>
              </ol>
              <p className="mt-2">
                Os mesmos quatro passos aparecem no guia do canto da tela e no progresso da barra
                lateral. Completar os dados da rádio e cadastrar vinhetagem são opcionais. Criar a
                conta não tem custo: você configura radialista e programa à vontade, e a assinatura
                é pedida na primeira geração com IA ou para colocar a rádio no ar.
              </p>
              <Shot src="dashboard" legenda="Visão geral logo após criar a conta, com o checklist de setup." />
            </section>

            <section>
              <H2 id="radialistas">Radialistas virtuais</H2>
              <p>
                Um radialista é a persona de IA que apresenta sua rádio: tem nome, personalidade, voz
                e fuso horário. Ele pode ser gerado a partir de uma descrição livre (IA preenche
                personalidade e voz) ou configurado manualmente.
              </p>
              <Shot
                src="radialistas-vazio"
                legenda="Tela de Radialistas logo após criar a conta, com o radialista inicial pronto para configurar."
              />
              <p className="mt-2">
                A voz vem de um catálogo pré-definido; também é possível clonar uma voz real enviando
                uma amostra de áudio, desde que você tenha autorização para usar essa voz.
              </p>
              <p className="mt-2">
                Você pode ter vários radialistas e até dez no mesmo programa. Não há cobrança por
                radialista: o que entra na conta é o uso de IA de cada geração (veja{" "}
                <a href="#assinatura" className="text-acento-claro underline hover:text-acento-dim">
                  Assinatura e consumo
                </a>
                ).
              </p>
              <Shot src="radialista-detalhe" legenda="Tela de edição do radialista: nome, voz e programação." />
            </section>

            <section>
              <H2 id="programas-grade">Programas e grade</H2>
              <p>
                Um <strong className="text-fg">programa</strong> define as regras de uma faixa de
                horário: dias da semana (ou uma data só, no programa avulso), horário de início/fim,
                perfil (musical, jornalismo, esportivo, variedades, religioso ou comunitário), tom,
                tópicos permitidos e proibidos, gêneros musicais e o roteiro de blocos (abertura,
                música, comentário, notícia, serviço, chamada ao ouvinte, entre outros). Vinhetas e
                propagandas cadastradas na Vinhetagem também entram como blocos do roteiro. Um
                programa pode ter até dez radialistas como co-apresentadores.
              </p>
              <p className="mt-2">
                Dá pra descrever o programa em texto livre e usar <em>Ajustar com IA</em> para
                preencher os campos. Com a pesquisa ativada (&quot;Pode pesquisar&quot;), o
                radialista busca notícias recentes nas fontes indicadas. Cada programa usa um modelo
                de texto e um de voz, que definem o preço por hora (veja{" "}
                <a href="#assinatura" className="text-acento-claro underline hover:text-acento-dim">
                  Assinatura e consumo
                </a>
                ).
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
                Inserções organizadas por categoria, com busca e paginação dentro de cada categoria.
                Cada categoria é marcada como <strong className="text-fg">biblioteca</strong>{" "}
                (vinhetas em áudio, tipo cartwall) ou <strong className="text-fg">propaganda</strong>{" "}
                (spot de patrocinador). Uma propaganda pode ser um áudio pronto ou um texto que o
                próprio radialista lê no ar, com a voz que você escolher. Para tocar no ar, encaixe a
                vinheta ou a propaganda como um bloco no roteiro do programa; as vinhetas da
                biblioteca também viram botões no Cartwall do Ao Vivo.
              </p>
              <Shot src="vinhetagem" legenda="Categorias da vinhetagem, cada uma marcada como biblioteca ou propaganda." />
            </section>

            <section>
              <H2 id="conversas">Conversas e WhatsApp</H2>
              <p>
                Cada conta tem um único número de WhatsApp, compartilhado por todos os radialistas da
                rádio. Conecte em <em>Conta → Configuração → WhatsApp da rádio</em>, clicando em
                &quot;Conectar WhatsApp&quot; e escaneando o QR code. Se a sessão cair, avisamos o admin por e-mail
                automaticamente até a reconexão. Pra trocar de número, use &quot;Desconectar
                WhatsApp&quot; e escaneie um QR code novo.
              </p>
              <Shot src="whatsapp-antes-conectar" legenda="Conexão do WhatsApp antes de escanear o QR code." />
              <p className="mt-2">
                Em <em>Conversas</em> fica o histórico das mensagens trocadas entre ouvintes e o
                radialista, com filtro por período (últimos 7, 30 ou 90 dias) e exportação em CSV —
                útil pra revisar como a IA está respondendo.
              </p>
              <Shot src="conversas" legenda="Histórico de conversas, com filtro por período." />
            </section>

            <section>
              <H2 id="ao-vivo">Ao Vivo</H2>
              <p>
                Painel em tempo real do programa no ar: o que o radialista está executando, o
                histórico de falas geradas e o que vem a seguir na sequência de blocos. Dá pra pausar
                a transmissão, disparar vinhetas da Biblioteca/Cartwall manualmente e editar o
                radialista ou o programa sem saltar de tela.
              </p>
              <p className="mt-2">
                <strong className="text-fg">Atendimento aos ouvintes</strong> (administradores
                ativam no próprio Ao Vivo): pedidos de música e recados que chegam pelo WhatsApp
                entram numa fila de revisão. Antes de ir ao ar, a equipe confere a autorização do
                ouvinte, define o nome e o texto que o radialista vai ler e aprova. Também dá pra
                transferir o pedido para outro programa, recusar com motivo ou continuar a conversa
                pessoalmente no WhatsApp da rádio.
              </p>
              <Dica>
                Instale o app da Locufy no computador que toca a rádio. Sem isso, o navegador
                bloqueia o som até alguém clicar na página.
              </Dica>
              <Shot src="ao-vivo" legenda="Painel Ao Vivo." />
            </section>

            <section>
              <H2 id="metricas">Métricas</H2>
              <p>
                Volume de mensagens recebidas (total, últimos 7 e últimos 30 dias, por dia e por
                status), com o mesmo filtro de período e exportação em CSV. Para ver o
                uso de IA e o limite financeiro, acesse{" "}
                <a href="#assinatura" className="text-acento-claro underline hover:text-acento-dim">
                  Assinatura e consumo
                </a>
                .
              </p>
              <Shot src="metricas" legenda="Métricas de mensagens recebidas por dia." />
            </section>

            <section>
              <H2 id="equipe">Equipe</H2>
              <p>
                Só administradores acessam esta tela. Convide pessoas por e-mail e defina o papel:{" "}
                <strong className="text-fg">admin</strong> (também gerencia Equipe e Assinatura) ou{" "}
                <strong className="text-fg">membro</strong> (opera o dia a dia — radialistas,
                programas, conversas — sem acesso a Equipe nem Assinatura). Remover alguém desativa
                o acesso sem apagar o histórico associado a esse usuário.
              </p>
              <Shot src="equipe" legenda="Convite de equipe e lista de membros." />
            </section>

            <section>
              <H2 id="assinatura">Assinatura e consumo</H2>
              <p>
                Só administradores acessam esta tela (<em>Conta → Assinatura</em>). A Locufy tem um
                plano só, o <strong className="text-fg">Locufy Flex</strong>: R$ 69,90 por mês de acesso
                mais o uso de IA, pago com cartão via Stripe.
              </p>
              <ul className="list-disc pl-5 mt-2 space-y-1">
                <li>
                  A primeira mensalidade é cobrada na adesão. Em cada renovação, a fatura traz a
                  mensalidade do próximo período mais o uso de IA do período encerrado. Sem uso, só a
                  mensalidade.
                </li>
                <li>WhatsApp completo, sem franquia nem pacotes de mensagens, e sem cobrança por radialista.</li>
                <li>
                  O uso é medido por geração (texto, voz, transcrição de áudio, trilha de vinheta) e
                  depende da combinação de modelos de cada programa. Em <em>Modelos em uso</em> você
                  vê o preço por hora de programa de cada combinação e pode trocar quando quiser; a
                  troca vale para as próximas falas geradas.
                </li>
                <li>
                  Você define um <strong className="text-fg">limite financeiro</strong> mensal. Ele
                  controla o total comprometido: uso do ciclo atual, operações em andamento e uso
                  ainda não pago de ciclos anteriores. A Visão geral avisa quando esse total chega a
                  90% do limite. Ao atingir, novas gerações pausam até você aumentar o limite ou a
                  fatura com esse uso ser paga.
                </li>
                <li>
                  Com pagamento pendente, novas gerações também pausam até você clicar em
                  &quot;Regularizar pagamento&quot;.
                </li>
                <li>Reproduzir áudio já gerado (vinhetas, falas prontas) não gera nova cobrança.</li>
                <li>
                  O extrato lista cada uso com modelo, quantidade e preço; as faturas ficam no
                  histórico. Em <em>Tarifas e testes</em> estão as tarifas vigentes de cada modelo.
                </li>
              </ul>
              <p className="mt-2">
                O cancelamento pode ser feito a qualquer momento pelo portal de pagamento e vale até o
                fim do período já pago, sem reembolso proporcional. No cancelamento sai uma fatura
                final só com o uso de IA ainda não cobrado.
              </p>
              <Shot
                src="assinatura"
                legenda="Assinatura de uma rádio de demonstração, com o modelo e a estimativa mensal de cada programa pelas tarifas vigentes."
              />
              <Shot
                src="assinatura-consumo"
                legenda="Consumo do ciclo, limite financeiro e extrato de cada uso da mesma rádio."
              />
            </section>

            <section>
              <H2 id="dados-radio">Configuração</H2>
              <p>
                Em <em>Conta → Configuração</em> ficam a conexão do{" "}
                <a href="#conversas" className="text-acento-claro underline hover:text-acento-dim">
                  WhatsApp da rádio
                </a>{" "}
                e três blocos preenchidos manualmente (nada aqui é gerado por IA, pra não inventar
                lugar ou fato errado sobre sua rádio):
              </p>
              <ol className="list-decimal pl-5 mt-2 space-y-1">
                <li>
                  <strong className="text-fg">Dados da rádio</strong> — nome, slogan, frequência,
                  telefone, endereço, cidade e tipo de rádio. Usados pra personalizar as respostas do
                  radialista; a cidade também alimenta a previsão do tempo real que o locutor pode
                  citar no ar.
                </li>
                <li>
                  <strong className="text-fg">Conhecimento local</strong> — gentílico, bairros,
                  pontos de referência, eventos recorrentes e gírias da região, pra deixar as
                  respostas com cara de quem é dali.
                </li>
                <li>
                  <strong className="text-fg">Bíblia da rádio</strong> — história da emissora, rotina
                  real (parcerias, transmissões fixas), outros programas da grade fora da IA, equipe
                  que existe na rádio mas não fica ao vivo, e hábitos de trabalho reais.
                </li>
              </ol>
              <Shot src="configuracoes-salvo" legenda="Formulário de dados da rádio, na tela de Configuração." />
            </section>

            <section>
              <H2 id="perfil">Perfil</H2>
              <p>
                Seus dados pessoais e o status atual da assinatura: aguardando assinatura (conta
                criada, ainda sem pagamento), ativa, pagamento pendente ou cancelada.
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
                    <Link href="/termos" className="text-acento-claro underline hover:text-acento-dim">
                      Termos de Uso
                    </Link>
                    .
                  </p>
                </div>
                <div>
                  <p className="font-medium text-fg">Posso ter mais de um radialista?</p>
                  <p>
                    Sim, sem custo por radialista. O que entra na conta é o uso de IA (veja{" "}
                    <a href="#assinatura" className="text-acento-claro underline hover:text-acento-dim">
                      Assinatura e consumo
                    </a>
                    ).
                  </p>
                </div>
                <div>
                  <p className="font-medium text-fg">O conteúdo que envio é usado pra treinar IA?</p>
                  <p>
                    Não. Veja como tratamos seus dados na{" "}
                    <Link href="/privacidade" className="text-acento-claro underline hover:text-acento-dim">
                      Política de Privacidade
                    </Link>
                    .
                  </p>
                </div>
                <div>
                  <p className="font-medium text-fg">O que acontece se a sessão do WhatsApp cair?</p>
                  <p>
                    O admin da conta recebe um alerta por e-mail; basta reconectar escaneando o QR
                    code de novo em <em>Conta → Configuração → WhatsApp da rádio</em>.
                  </p>
                </div>
                <div>
                  <p className="font-medium text-fg">Por que o radialista parou de gerar falas novas?</p>
                  <p>
                    Normalmente é o limite financeiro atingido, um pagamento pendente ou a assinatura
                    cancelada. Confira em <em>Conta → Assinatura</em>: aumente o limite, regularize o
                    pagamento ou reative a assinatura.
                  </p>
                </div>
                <div>
                  <p className="font-medium text-fg">Como cancelo minha assinatura?</p>
                  <p>
                    Em <em>Conta → Assinatura</em> (acesso admin), clique em &quot;Gerenciar
                    pagamento&quot; — isso abre o portal seguro da Stripe, onde dá pra cancelar. O
                    acesso continua até o fim do período já pago.
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
