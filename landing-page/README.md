# Landing page Locufy

Site independente em HTML, CSS e JavaScript para **https://locufybr.com/**. Sem dependências de execução, conexão com backend ou alterações no painel. A pasta pode ser copiada para outro repositório.

## Executar

Requer Node.js 18 ou superior; não precisa instalar pacotes.

```sh
cd landing-page
npm run dev
```

Abra http://localhost:3010. Para outra porta: `PORT=3011 npm run dev`.

## Build e publicação

```sh
npm run build
```

Publique o conteúdo de `dist/` em uma hospedagem estática, na raiz de https://locufybr.com/. O servidor Node é uma prévia local. Para conferir o build: `SERVE_DIST=1 PORT=3011 npm run dev`.

- `config.js`: destino do painel (`https://app.locufybr.com`). Se alterar, atualize também os links de fallback no HTML.
- `index.html`: título, descrição, canonical, Open Graph, Twitter Cards e JSON-LD estáticos, disponíveis sem JavaScript.
- `robots.txt` e `sitemap.xml`: rastreamento e URLs canônicas de página/imagens.
- Ao mudar o domínio da landing, atualize todas as ocorrências de `https://locufybr.com/` no HTML e nesses dois arquivos. O domínio do painel é independente.
- Configure HTTPS e redirecionamentos de HTTP, www e `/index.html` para a URL canônica na hospedagem. Ambientes públicos de prévia devem receber `X-Robots-Tag: noindex` pela hospedagem.
- Após publicar, verificar no Search Console e enviar o sitemap. A configuração local não comprova indexação ou desempenho em produção.

## Conteúdo e conversão

CTA principal: `/register` no painel. Recursos baseados no código e central de ajuda. Planos e adicionais são apresentados na landing; a contratação e confirmação das condições acontecem no cadastro.

Parâmetros UTM (`source`, `medium`, `campaign`, `content`, `term`) são preservados nos links de cadastro. Cliques emitem o evento local `locufy:conversion` com `detail.location` e `detail.destination`. Sem cookies, rastreadores ou integração de analytics; o painel precisa implementar armazenamento de atribuição para isso ser medido.

## Imagens e marca

- Logo horizontal branca e símbolo com gradiente vêm de `frontend-painel/public/Logos/`, preservando a arte oficial. As versões usadas estão incorporadas a `assets/`.
- Hero e galeria: capturas novas do painel atual, com dados demonstrativos interceptados somente no navegador. Nenhuma conta real foi alterada.
- Quatro imagens com tratamento editorial: voz/personalidade, grade preenchida, biblioteca de vinhetas e transmissão ao vivo. Enquadramento frontal, texto legível e acabamento azul consistente. Detalhes e origem de cada uma em [design/README.md](design/README.md).
- Galeria ampliada em seções alternadas, com links diretos às imagens e diálogo acessível quando há JavaScript.
- WebP responsivo em 640, 960 e 1440 px, dimensões explícitas e carregamento tardio na galeria.
- Fontes, dados e prompts em [design/README.md](design/README.md). O diretório de design não é publicado no build.

## Movimento e microinterações

Scroll-reveal (IntersectionObserver) nos cards de recursos, galeria, passos e planos; hover com leve elevação em botões, cards e imagens da galeria; glow de fundo sutil no hero; ícone do FAQ e do diálogo de imagem com transição suave. Tudo em CSS/JS nativo, sem dependência nova. A classe `reveal` só é aplicada via JavaScript, então o fallback sem JS mantém o conteúdo sempre visível; `prefers-reduced-motion: reduce` desativa o observer e as animações continuas (glow, diálogo).

## SEO e validação

Skill aplicada: [seo-audit de Corey Haines](https://skills.sh/coreyhaines31/marketingskills/seo-audit), instalada em `.agents/skills/seo-audit/` no projeto principal. Consulte [SEO.md](SEO.md) para achados, implementação e pendências de produção.

Validação no Chromium: larguras 320, 375, 768, 1024 e 1440 px; ausência de transbordamento horizontal; imagens, ampliação, fechamento com Escape e retorno de foco; FAQ; UTMs; teclado; fallback sem JavaScript; JSON-LD renderizado; canonical; robots; sitemap XML e tipos de imagem. Build e sintaxe JavaScript verificados. As animações usam apenas `opacity`/`transform` (sem impacto em CLS) e não atrasam o carregamento do LCP do hero. Nenhuma conta foi criada e nenhum deploy foi realizado.

## Tema claro e escuro

Botão de sol/lua no cabeçalho, acessível por teclado. O tema inicial segue o sistema operacional; uma escolha manual é salva em `locufy-landing-theme`. A inicialização em `theme.js` acontece antes do CSS para evitar flash de tema. Alterações do sistema são acompanhadas enquanto não houver escolha manual; a preferência também é sincronizada entre abas. O botão funciona mesmo se o armazenamento estiver bloqueado.

O tema claro usa a logo azul oficial (`Logo_Locufy_Logotipo_Horizontal_02.png`), superfícies claras e contraste ajustado. Os prints preservam o tema do painel em que foram capturados. Sem JavaScript, a landing mantém o tema escuro e oculta o botão.

## Planos e contato comercial

Seção `#planos` com Starter (R$ 399/mês), Growth (R$ 599/mês) e Professional (R$ 999/mês). Franquias: 2.000, 3.000 e 7.500 mensagens; 1, 3 e 5 radialistas; 1, 2 e 3 radialistas por programa. Clonagem a partir do Growth. Radialista adicional: R$ 100/mês; pacote avulso de 1.000 mensagens: R$ 50, para o mês corrente.

Fontes: `backend/app/planos.py` e regras de cobrança em `backend/app/billing/stripe_client.py`. Há uma divergência preexistente: `frontend-painel/lib/planos.ts` informa 1.000 mensagens no Starter; a landing usa as 2.000 aplicadas pelo backend. O painel não foi alterado nesta tarefa. Os preços comerciais foram obtidos do repositório; os Price IDs ativos no Stripe não foram consultados.

Os CTAs de cadastro levam ao fluxo atual, onde o usuário escolhe e confirma o plano. Não afirmam pré-selecionar um plano, pois o cadastro atual não lê esse parâmetro. Botões de WhatsApp incluem uma mensagem específica quando associados a um plano; abrir o link não envia mensagem automaticamente. Contato flutuante oculto enquanto uma imagem está ampliada.

WhatsApp comercial confirmado: +55 (47) 99126-8815. Configure em `config.js` e atualize também os hrefs estáticos de `[data-whatsapp]` no HTML se o contato mudar.
