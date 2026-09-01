import type { Metadata } from "next";
import Link from "next/link";
import { LocufyLogo } from "../../components/LocufyLogo";
import ThemeToggle from "../../components/ThemeToggle";

export const metadata: Metadata = {
  title: "Termos de Uso — Locufy",
  description: "Termos de Uso da Locufy, plataforma de radialista virtual com inteligência artificial.",
};

const ATUALIZADO_EM = "31 de agosto de 2026";

export default function TermosPage() {
  return (
    <div className="min-h-screen bg-bg">
      <header className="border-b border-border">
        <div className="max-w-3xl mx-auto px-4 py-5 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2">
            <LocufyLogo wordmarkClassName="text-xl" />
          </Link>
          <ThemeToggle />
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-4 py-12">
        <h1 className="font-display text-2xl font-bold text-fg mb-2">Termos de Uso</h1>
        <p className="text-sm text-fg/50 mb-10">Última atualização: {ATUALIZADO_EM}</p>

        <div className="space-y-8 text-sm leading-relaxed text-fg/80">
          <section>
            <h2 className="font-display text-lg font-semibold text-fg mb-2">1. Aceitação</h2>
            <p>
              Estes Termos de Uso regem o acesso e uso da Locufy (locufy.com), plataforma que permite
              a uma rádio criar e operar um radialista virtual assistido por inteligência artificial.
              Ao criar uma conta ou usar o serviço, você concorda com estes Termos e com a nossa{" "}
              <Link href="/privacidade" className="text-amber-text hover:text-amber-dim">
                Política de Privacidade
              </Link>
              . Se você não concorda, não utilize a Locufy.
            </p>
          </section>

          <section>
            <h2 className="font-display text-lg font-semibold text-fg mb-2">2. O Serviço</h2>
            <p>
              A Locufy é um serviço pago por assinatura (planos Starter, Growth e Professional, com
              período de teste gratuito) que gera, a partir de uma descrição fornecida pela rádio,
              a configuração de um ou mais radialistas virtuais e de sua programação (roteiros,
              locução em áudio por síntese de voz e, quando ativado, atendimento automatizado via
              WhatsApp aos ouvintes). Podemos ajustar, suspender ou descontinuar funcionalidades a
              qualquer momento, avisando com antecedência razoável sempre que possível.
            </p>
          </section>

          <section>
            <h2 className="font-display text-lg font-semibold text-fg mb-2">3. Quem pode contratar</h2>
            <p>
              A Locufy é destinada a rádios e profissionais de radiodifusão agindo em caráter
              profissional (uso B2B), não a consumidores finais. Para criar uma conta, você declara
              ter pelo menos 18 anos e capacidade civil para contratar em nome próprio ou da emissora
              que representa.
            </p>
          </section>

          <section>
            <h2 className="font-display text-lg font-semibold text-fg mb-2">4. Conta, equipe e segurança</h2>
            <p>
              A conta pertence à rádio (o &quot;tenant&quot;); pessoas físicas da equipe (papéis
              admin ou membro) acessam com login próprio. Você é responsável por manter suas
              credenciais em sigilo e por toda atividade realizada na conta com seu login. Avise-nos
              imediatamente em caso de uso não autorizado.
            </p>
          </section>

          <section>
            <h2 className="font-display text-lg font-semibold text-fg mb-2">5. Ouvintes e o canal de WhatsApp</h2>
            <p>
              Quando você conecta um número de WhatsApp, o radialista virtual passa a responder
              mensagens dos ouvintes daquele número automaticamente, via inteligência artificial.
              Os ouvintes não são parte destes Termos — a relação com eles, incluindo eventual
              obrigação de informá-los sobre o uso de IA e de coletar consentimentos exigidos por
              lei, é de responsabilidade da rádio titular da conta.
            </p>
          </section>

          <section>
            <h2 className="font-display text-lg font-semibold text-fg mb-2">6. Uso aceitável</h2>
            <p>É proibido usar a Locufy para:</p>
            <ul className="list-disc pl-5 mt-2 space-y-1">
              <li>Gerar ou veicular conteúdo ilegal, discurso de ódio, assédio ou material que exponha ou explore menores;</li>
              <li>Infringir direitos autorais, de imagem, de voz ou outros direitos de terceiros;</li>
              <li>Fazer engenharia reversa, contornar limites de uso ou medidas de segurança do serviço;</li>
              <li>Usar o canal de WhatsApp para spam, disparo em massa não solicitado ou burlar políticas do WhatsApp/Meta;</li>
              <li>Enviar conteúdo ou instruções que você não tem o direito legal de usar ou reproduzir.</li>
            </ul>
            <p className="mt-2">
              Podemos investigar violações e suspender ou encerrar contas que descumpram esta seção.
            </p>
          </section>

          <section>
            <h2 className="font-display text-lg font-semibold text-fg mb-2">7. Conteúdo que você envia</h2>
            <p>
              Você mantém a titularidade sobre as descrições, textos, áudios de patrocinadores e
              demais materiais que envia (&quot;Seu Conteúdo&quot;). Você nos concede uma licença
              limitada, não exclusiva, para processar Seu Conteúdo com a finalidade de operar o
              serviço (gerar configuração, roteiros, áudio e respostas aos ouvintes). Você garante
              ter os direitos necessários sobre o que envia.
            </p>
          </section>

          <section>
            <h2 className="font-display text-lg font-semibold text-fg mb-2">8. Clonagem de voz</h2>
            <p>
              Planos Growth e Professional permitem enviar uma amostra de voz para clonagem (via
              ElevenLabs Instant Voice Cloning). Ao enviar uma amostra, você declara que a pessoa
              cuja voz está sendo clonada consentiu expressamente com esse uso, e que a voz clonada
              será usada apenas dentro da sua programação na Locufy.
            </p>
          </section>

          <section>
            <h2 className="font-display text-lg font-semibold text-fg mb-2">9. Conteúdo gerado</h2>
            <p>
              Você é o titular do conteúdo gerado para sua conta (roteiros, configurações de
              programa, áudio sintetizado) e pode usá-lo comercialmente na sua programação. Como o
              conteúdo é gerado por IA, você é responsável por revisar antes de veicular — inclusive
              quanto a precisão factual, adequação ao seu público e eventual conflito com direitos de
              terceiros mencionados no conteúdo (ex.: nomes de músicas, marcas, notícias).
            </p>
          </section>

          <section>
            <h2 className="font-display text-lg font-semibold text-fg mb-2">10. Aviso sobre inteligência artificial</h2>
            <p>
              O radialista virtual, os roteiros, as respostas a ouvintes e a locução em áudio são
              produzidos por modelos de IA de forma probabilística. Podem conter imprecisões,
              informações desatualizadas ou respostas inesperadas. A Locufy é uma ferramenta de
              produção de conteúdo, não uma fonte de veracidade factual — a responsabilidade editorial
              final é sempre da rádio.
            </p>
          </section>

          <section>
            <h2 className="font-display text-lg font-semibold text-fg mb-2">11. Serviços de terceiros</h2>
            <p>
              Para operar, a Locufy usa provedores de terceiros, cujos termos também se aplicam ao
              processarem dados enviados por você: Anthropic (geração de texto/roteiro via API
              Claude), ElevenLabs (síntese e clonagem de voz), WuzAPI (integração com WhatsApp),
              Stripe (cobrança), AWS (armazenamento de arquivos) e Sentry (monitoramento de erros).
              Veja detalhes na nossa{" "}
              <Link href="/privacidade" className="text-amber-text hover:text-amber-dim">
                Política de Privacidade
              </Link>
              .
            </p>
          </section>

          <section>
            <h2 className="font-display text-lg font-semibold text-fg mb-2">12. Planos, cobrança e cancelamento</h2>
            <p>
              Os planos Starter, Growth e Professional são cobrados por assinatura recorrente via
              Stripe, com franquia mensal de mensagens e número de radialistas por plano; uso acima
              da franquia ou agentes adicionais podem gerar cobrança extra, conforme exibido na tela
              de billing antes da confirmação. Você pode cancelar a assinatura a qualquer momento; o
              cancelamento produz efeito ao fim do período já pago, sem reembolso proporcional salvo
              disposição legal em contrário.
            </p>
          </section>

          <section>
            <h2 className="font-display text-lg font-semibold text-fg mb-2">13. Propriedade intelectual</h2>
            <p>
              A Locufy, sua marca, logotipo, software e design de interface são de titularidade da
              Locufy ou de seus licenciantes. Nenhuma disposição destes Termos transfere a você
              direitos sobre essa propriedade intelectual, exceto o direito de uso do serviço nos
              termos aqui descritos.
            </p>
          </section>

          <section>
            <h2 className="font-display text-lg font-semibold text-fg mb-2">14. Suspensão e encerramento</h2>
            <p>
              Podemos suspender ou encerrar contas que violem a Seção 6 (Uso Aceitável) ou fiquem
              inadimplentes. Você pode encerrar sua conta a qualquer momento entrando em contato
              conosco. Cláusulas que por natureza devem sobreviver ao encerramento (propriedade
              intelectual, isenções, limitação de responsabilidade, indenização, lei aplicável)
              permanecem em vigor.
            </p>
          </section>

          <section>
            <h2 className="font-display text-lg font-semibold text-fg mb-2">15. Isenção de garantias</h2>
            <p>
              O SERVIÇO É FORNECIDO &quot;COMO ESTÁ&quot; E &quot;CONFORME DISPONÍVEL&quot;, SEM
              GARANTIAS DE QUALQUER TIPO, EXPRESSAS OU IMPLÍCITAS, INCLUINDO GARANTIAS DE
              ADEQUAÇÃO A UM PROPÓSITO ESPECÍFICO OU NÃO VIOLAÇÃO. NÃO GARANTIMOS QUE O SERVIÇO SERÁ
              ININTERRUPTO OU LIVRE DE ERROS, NEM QUE O CONTEÚDO GERADO POR IA SERÁ PRECISO OU
              ADEQUADO A TODO CONTEXTO.
            </p>
          </section>

          <section>
            <h2 className="font-display text-lg font-semibold text-fg mb-2">16. Limitação de responsabilidade</h2>
            <p>
              Na máxima extensão permitida por lei, a Locufy não será responsável por danos
              indiretos, incidentais ou consequenciais. Nossa responsabilidade total por qualquer
              reclamação relacionada ao serviço fica limitada ao valor pago por você nos 12 meses
              anteriores ao fato gerador. Em jurisdições que não permitem essa limitação, ela se
              aplica na maior extensão permitida por lei.
            </p>
          </section>

          <section>
            <h2 className="font-display text-lg font-semibold text-fg mb-2">17. Indenização</h2>
            <p>
              Você concorda em indenizar a Locufy por reclamações de terceiros decorrentes do
              conteúdo que você enviou, do uso que deu ao conteúdo gerado, ou de violação destes
              Termos ou de direitos de terceiros (incluindo direitos de imagem/voz de pessoas cujo
              áudio foi enviado para clonagem sem consentimento).
            </p>
          </section>

          <section>
            <h2 className="font-display text-lg font-semibold text-fg mb-2">18. Lei aplicável e foro</h2>
            <p>
              Estes Termos são regidos pelas leis da República Federativa do Brasil. Fica eleito o
              foro do domicílio da Locufy para dirimir eventuais controvérsias, com renúncia a
              qualquer outro, por mais privilegiado que seja.
            </p>
          </section>

          <section>
            <h2 className="font-display text-lg font-semibold text-fg mb-2">19. Alterações</h2>
            <p>
              Podemos atualizar estes Termos periodicamente. Mudanças relevantes serão publicadas
              nesta página com nova data de &quot;última atualização&quot;. O uso continuado da
              Locufy após a publicação de alterações constitui aceitação dos novos Termos.
            </p>
          </section>

          <section>
            <h2 className="font-display text-lg font-semibold text-fg mb-2">20. Contato</h2>
            <p>
              Dúvidas sobre estes Termos: <a href="mailto:contato@locufy.com" className="text-amber-text hover:text-amber-dim">contato@locufy.com</a>.
            </p>
          </section>
        </div>
      </main>
    </div>
  );
}
