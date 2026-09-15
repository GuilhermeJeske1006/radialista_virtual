# SEO da landing page

## Escopo e estratégia

Landing SaaS em português para rádios e web rádios, com conversão para cadastro no painel. URL confirmada pelo responsável: https://locufybr.com/. Skill: [seo-audit](https://skills.sh/coreyhaines31/marketingskills/seo-audit), de `coreyhaines31/marketingskills`, instalada no projeto e revisada antes de aplicar.

Termo principal: **radialista virtual com IA**. Termos relacionados: locução com IA, programação de rádio, grade de programação, WhatsApp para rádios, vinhetas. São hipóteses editoriais baseadas no produto; não foram medidos volume de busca, dificuldade ou posições. Não há acesso ao Search Console ou analytics nesta tarefa.

## Auditoria e correções

| Prioridade | Achado anterior / evidência | Alteração |
| --- | --- | --- |
| Alta | `index.html` sem URL canônica; nenhum sitemap ou robots no build | Canonical estático apontando à raiz HTTPS, `robots.txt`, sitemap com a página e imagens |
| Alta | Título e H1 focados em slogan, sem nomear o produto | Título, H1 e introdução descrevem o radialista virtual com IA; H2 aborda locução e programação |
| Média | Sem dados estruturados no HTML | JSON-LD Organization, WebSite, WebPage e SoftwareApplication, conferido também no navegador |
| Média | Open Graph sem imagem nem URL | URL, nome do site, imagem JPG 1200×630, alt e Twitter Cards |
| Média | Demonstração ilustrativa em HTML e símbolo aproximado | Logo oficial e três novas capturas do painel atual, editadas e identificadas como demonstração, com ampliação |
| Média | Não havia estratégia para imagens raster | WebP, `srcset`, `sizes`, dimensões, nomes descritivos, alt e lazy loading fora do hero |

Os dados estruturados descrevem a aplicação e a organização sem inventar avaliações, preços ou clientes. Não foi adicionada promessa de rich result. FAQ permanece conteúdo visível. O sitemap não usa `lastmod` artificial atualizado a cada build.

## Reauditoria: quarta imagem e animações

| Prioridade | Achado | Alteração |
| --- | --- | --- |
| Alta | Nova captura "Acompanhe a transmissão ao vivo" adicionada à galeria, mas ausente do sitemap de imagens | `<image:image>` de `locufy-aovivo-pro-1440.webp` adicionado em `sitemap.xml` |
| Baixa (confirmação) | Risco de CLS com scroll-reveal, hover e glow de fundo (IntersectionObserver + CSS) | Revisado: todas as animações usam apenas `opacity`/`transform`, sem impacto em layout; nenhuma incide sobre o hero (elemento provável de LCP); testado sem erro de console e sem overflow horizontal em 375 e 1440 px |
| Confirmado | Título (49 caracteres), meta description (151), H1 único, alt text da nova imagem | Dentro das faixas recomendadas, nada a corrigir |

Pendente (não medível localmente): confirmar em produção que o glow animado do hero e o scroll-reveal não afetam INP/CLS reais — ver "Após publicar" abaixo.

## Reauditoria: padronização visual

| Prioridade | Achado | Alteração |
| --- | --- | --- |
| Alta | Galeria alternava lado imagem/texto só na 2ª figura (`nth-child(2)` fixo); com a 4ª imagem (ao vivo) adicionada, o zigue-zague quebrava e repetia o mesmo lado | `nth-child(2)` trocado por `nth-child(even)` em `styles.css` (3 ocorrências) — zigue-zague correto para qualquer número de imagens |
| Média | Scroll-reveal (IntersectionObserver) podia deixar seções com `opacity:0` permanente em cenários de scroll programático incomum (ex.: navegação por âncora disparando múltiplos saltos) | Rede de segurança em `script.js`: força a revelação de tudo 2,5s após o `load`, independente do observer |

Validado com Playwright: scroll real (wheel), salto direto por âncora e captura full-page em light/dark, 1440 e 390px — sem seção invisível, sem overflow, sem erro de console.

## Verificações locais

- Build contém HTML, estilos, JS, fontes, imagens, robots e sitemap; nenhuma dependência do diretório do painel para servir a página.
- Canonical e URLs estruturadas consistentes com https://locufybr.com/.
- JSON-LD parseável no navegador; tipos e referências entre entidades conferidos.
- Sitemap XML válido e referência presente em robots.txt.
- Imagens e arquivos de compartilhamento disponíveis com MIME correto.
- Layout em cinco larguras (320–1440 px), galeria, teclado, FAQ e versão sem JavaScript.
- Imagens editoriais novas em WebP responsivo (640, 960 e 1440 px); arquivos de compartilhamento atualizados.

## Após publicar

1. Verificar HTTPS, respostas 200 para página/assets/sitemap/robots e redirecionamento permanente das variantes HTTP/www/index.html. A configuração depende da hospedagem.
2. Verificar propriedade no Search Console, enviar `https://locufybr.com/sitemap.xml` e inspecionar a URL publicada.
3. Validar marcação publicada no Schema Validator/Rich Results Test. Marcação semanticamente válida não assegura elegibilidade a um resultado enriquecido.
4. Medir Core Web Vitals com dados reais e PageSpeed Insights. Os testes locais não comprovam LCP, INP ou CLS em produção.
5. Avaliar consultas, impressões, cliques e conversões antes de expandir o conteúdo. Não há promessa de posição ou indexação.

## Referências utilizadas

- [Skill seo-audit](https://skills.sh/coreyhaines31/marketingskills/seo-audit)
- [Google: boas práticas para imagens](https://developers.google.com/search/docs/appearance/google-images)
- [Google: URLs canônicas](https://developers.google.com/search/docs/crawling-indexing/consolidate-duplicate-urls)
- [Schema.org: SoftwareApplication](https://schema.org/SoftwareApplication)
