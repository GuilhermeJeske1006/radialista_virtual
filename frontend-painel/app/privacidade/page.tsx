import type { Metadata } from "next";
import Link from "next/link";
import { LocufyLogo } from "../../components/LocufyLogo";
import ThemeToggle from "../../components/ThemeToggle";

export const metadata: Metadata = {
  title: "Política de Privacidade — Locufy",
  description: "Como a Locufy coleta, usa e protege dados na plataforma de radialista virtual com IA.",
};

const ATUALIZADO_EM = "31 de agosto de 2026";

export default function PrivacidadePage() {
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
        <h1 className="font-display text-2xl font-bold text-fg mb-2">Política de Privacidade</h1>
        <p className="text-sm text-fg/50 mb-10">Última atualização: {ATUALIZADO_EM}</p>

        <div className="space-y-8 text-sm leading-relaxed text-fg/80">
          <section>
            <h2 className="font-display text-lg font-semibold text-fg mb-2">1. Quem somos</h2>
            <p>
              A Locufy (locufy.com) opera uma plataforma que permite a rádios criar e operar um
              radialista virtual com inteligência artificial. Esta política explica quais dados
              coletamos, para quê e com quem compartilhamos. Contato:{" "}
              <a href="mailto:contato@locufy.com" className="text-amber-text hover:text-amber-dim">
                contato@locufy.com
              </a>
              .
            </p>
          </section>

          <section>
            <h2 className="font-display text-lg font-semibold text-fg mb-2">2. Dados que coletamos</h2>
            <p className="mb-2"><strong className="text-fg">Dados de conta:</strong> nome, e-mail e senha (armazenada com hash, nunca em texto puro) de cada pessoa da equipe, e seu papel (admin ou membro).</p>
            <p className="mb-2"><strong className="text-fg">Dados da rádio (conta/tenant):</strong> nome, slogan, frequência, telefone, endereço e cidade informados no perfil da emissora.</p>
            <p className="mb-2"><strong className="text-fg">Conteúdo que você envia:</strong> descrições em texto usadas para gerar o radialista e a programação, áudios de patrocinadores e, quando aplicável, uma amostra de voz enviada para clonagem.</p>
            <p className="mb-2"><strong className="text-fg">Mensagens de WhatsApp:</strong> quando você conecta um número, processamos o número de telefone e o conteúdo das mensagens trocadas entre os ouvintes e o radialista virtual, para gerar as respostas.</p>
            <p className="mb-2"><strong className="text-fg">Dados de pagamento:</strong> processados diretamente pela Stripe; não armazenamos número de cartão em nossos servidores, apenas identificadores de cliente/assinatura da Stripe.</p>
            <p><strong className="text-fg">Dados técnicos:</strong> logs de erro de aplicação (via Sentry) para diagnóstico e estabilidade.</p>
          </section>

          <section>
            <h2 className="font-display text-lg font-semibold text-fg mb-2">3. O que não coletamos</h2>
            <ul className="list-disc pl-5 space-y-1">
              <li>Não usamos cookies de publicidade, rastreamento entre sites ou ferramentas de analytics de terceiros;</li>
              <li>Não armazenamos número de cartão de crédito (isso fica só com a Stripe);</li>
              <li>Não usamos seu conteúdo enviado para treinar modelos de IA de terceiros.</li>
            </ul>
          </section>

          <section>
            <h2 className="font-display text-lg font-semibold text-fg mb-2">4. Como usamos os dados</h2>
            <p>Usamos os dados acima para: (i) operar o serviço — gerar configuração, roteiros, áudio e respostas de WhatsApp; (ii) processar cobrança; (iii) enviar e-mails operacionais (boas-vindas, alertas de conexão do WhatsApp, convites de equipe); (iv) monitorar e corrigir erros; (v) cumprir obrigações legais.</p>
          </section>

          <section>
            <h2 className="font-display text-lg font-semibold text-fg mb-2">5. Uso de IA e treinamento de modelo</h2>
            <p>
              Suas descrições e o conteúdo de mensagens de ouvintes são enviados à API da Anthropic
              (modelos Claude) para gerar texto e respostas, e à ElevenLabs para síntese e clonagem
              de voz. Ambos processam os dados via API para atender ao seu pedido e, conforme os
              termos desses provedores para uso via API, não usam esses dados para treinar seus
              modelos de propósito geral.
            </p>
          </section>

          <section>
            <h2 className="font-display text-lg font-semibold text-fg mb-2">6. Cookies</h2>
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse mt-2">
                <thead>
                  <tr className="border-b border-border text-fg/60">
                    <th className="py-2 pr-4 font-medium">Cookie</th>
                    <th className="py-2 pr-4 font-medium">Finalidade</th>
                    <th className="py-2 font-medium">Duração</th>
                  </tr>
                </thead>
                <tbody>
                  <tr className="border-b border-border">
                    <td className="py-2 pr-4">Sessão (JWT, httpOnly)</td>
                    <td className="py-2 pr-4">Manter você autenticado no painel</td>
                    <td className="py-2">7 dias</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <p className="mt-2">Esse é o único cookie que usamos — estritamente necessário, não é de rastreamento ou publicidade, então não exige banner de consentimento.</p>
          </section>

          <section>
            <h2 className="font-display text-lg font-semibold text-fg mb-2">7. Com quem compartilhamos (processadores)</h2>
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse mt-2">
                <thead>
                  <tr className="border-b border-border text-fg/60">
                    <th className="py-2 pr-4 font-medium">Provedor</th>
                    <th className="py-2 font-medium">Finalidade</th>
                  </tr>
                </thead>
                <tbody>
                  <tr className="border-b border-border">
                    <td className="py-2 pr-4">Anthropic (Claude)</td>
                    <td className="py-2">Geração de texto, roteiro e respostas por IA</td>
                  </tr>
                  <tr className="border-b border-border">
                    <td className="py-2 pr-4">ElevenLabs</td>
                    <td className="py-2">Síntese e clonagem de voz</td>
                  </tr>
                  <tr className="border-b border-border">
                    <td className="py-2 pr-4">WuzAPI</td>
                    <td className="py-2">Integração com WhatsApp</td>
                  </tr>
                  <tr className="border-b border-border">
                    <td className="py-2 pr-4">Stripe</td>
                    <td className="py-2">Processamento de pagamento e cobrança</td>
                  </tr>
                  <tr className="border-b border-border">
                    <td className="py-2 pr-4">AWS (S3)</td>
                    <td className="py-2">Armazenamento de arquivos de áudio enviados</td>
                  </tr>
                  <tr className="border-b border-border">
                    <td className="py-2 pr-4">Sentry</td>
                    <td className="py-2">Monitoramento e diagnóstico de erros</td>
                  </tr>
                  <tr>
                    <td className="py-2 pr-4">Provedor de e-mail (SMTP)</td>
                    <td className="py-2">Envio de e-mails operacionais</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

          <section>
            <h2 className="font-display text-lg font-semibold text-fg mb-2">8. Retenção de dados</h2>
            <p>
              Dados de conta e da rádio são mantidos enquanto a conta estiver ativa. Mensagens de
              WhatsApp e conteúdo enviado ficam associados à conta para permitir o histórico de
              conversas e a operação do radialista. Logs técnicos são mantidos por tempo limitado
              para fins de segurança e diagnóstico. Ao encerrar a conta, você pode solicitar a
              exclusão dos dados pelo contato abaixo.
            </p>
          </section>

          <section>
            <h2 className="font-display text-lg font-semibold text-fg mb-2">9. Seus direitos (LGPD)</h2>
            <p>
              Como titular de dados sob a Lei Geral de Proteção de Dados (Lei 13.709/2018), você
              pode solicitar confirmação de tratamento, acesso, correção, anonimização, portabilidade
              ou eliminação dos seus dados, além de revogar consentimentos dados. Para exercer esses
              direitos, escreva para{" "}
              <a href="mailto:contato@locufy.com" className="text-amber-text hover:text-amber-dim">
                contato@locufy.com
              </a>
              ; respondemos em até 15 dias úteis.
            </p>
          </section>

          <section>
            <h2 className="font-display text-lg font-semibold text-fg mb-2">10. Transferência internacional</h2>
            <p>
              Alguns dos provedores listados na Seção 7 (Anthropic, ElevenLabs, AWS, Stripe, Sentry)
              podem processar dados fora do Brasil. Nesses casos, exigimos que o processamento siga
              salvaguardas contratuais e padrões de segurança adequados exigidos pela LGPD.
            </p>
          </section>

          <section>
            <h2 className="font-display text-lg font-semibold text-fg mb-2">11. Crianças</h2>
            <p>
              A Locufy é uma ferramenta profissional voltada a rádios (uso B2B) e não é direcionada a
              menores de 18 anos. Não coletamos intencionalmente dados de contas de menores de idade.
            </p>
          </section>

          <section>
            <h2 className="font-display text-lg font-semibold text-fg mb-2">12. Segurança</h2>
            <p>
              Usamos conexão criptografada (HTTPS/TLS) em trânsito, senhas armazenadas com hash e
              autenticação por sessão httpOnly. Nenhum sistema é 100% imune a incidentes; em caso de
              violação de dados relevante, notificaremos os titulares afetados conforme exigido por
              lei.
            </p>
          </section>

          <section>
            <h2 className="font-display text-lg font-semibold text-fg mb-2">13. Alterações</h2>
            <p>
              Podemos atualizar esta Política periodicamente. Mudanças relevantes serão publicadas
              nesta página com nova data de &quot;última atualização&quot;.
            </p>
          </section>

          <section>
            <h2 className="font-display text-lg font-semibold text-fg mb-2">14. Contato</h2>
            <p>
              Dúvidas sobre privacidade ou dados pessoais:{" "}
              <a href="mailto:contato@locufy.com" className="text-amber-text hover:text-amber-dim">
                contato@locufy.com
              </a>
              . Veja também nossos{" "}
              <Link href="/termos" className="text-amber-text hover:text-amber-dim">
                Termos de Uso
              </Link>
              .
            </p>
          </section>
        </div>
      </main>
    </div>
  );
}
