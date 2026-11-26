# Instagram da Locufy: posts e stories

Peças estáticas de feed (1080x1350) e stories (1080x1920) desenhadas em HTML e renderizadas com Playwright.

| Arquivo | O que é |
| --- | --- |
| `src/pecas.mjs` | Texto e composição de cada peça (carrosséis A, B, C, posts P1 e P2, stories S1 a S3) |
| `src/tendencias.mjs` | Posts de tendência do fim de 2026 (T01 a T14), saída em `out/tendencias/` |
| `reports/`, `research_notes/` | Pesquisa de tendências que embasa os posts T |
| `src/base.css` | Cores, tipografia e componentes da marca |
| `FILOSOFIA.md` | Direção visual ("Sinal Limpo") para peças novas |
| `legendas.md` | Legendas, hashtags, figurinhas dos stories e ordem de publicação |
| `out/` | PNGs, pranchas, prévia da grade do perfil e `checagem.json` (ignorado pelo git) |

## Gerar

```bash
cd marketing/tools
node instagram.mjs            # todas as peças, pranchas e checagem
node instagram.mjs B S3-2     # só um grupo ou peça
node instagram.mjs --autoteste
```

O `--autoteste` renderiza dez peças quebradas de propósito e confirma que a checagem reprova cada uma.

## O que a checagem confere

Bloqueia (código de saída 1):

- tamanho exato do PNG;
- texto fora da área segura: 60 px nas laterais do feed (recorte 3:4 da grade do perfil) e a faixa de 250 a 1670 px nos stories;
- texto sobreposto a outro texto, ao logo, a uma tela do painel, à forma de onda ou à faixa reservada para figurinha;
- conteúdo que estoura a moldura ou a caixa onde está (cartão, balão, linha);
- contraste medido nos pixels do fundo, abaixo de 4,5:1 (3:1 para texto de 64 px ou mais);
- fonte da marca que não carregou, imagem que não carregou e logo distorcido;
- valor em reais que não existe em `landing-page/index.html`, preço por hora sem "estimativa" ou "≈";
- "grátis", "sem cartão", travessão, "não é só", importância inflada, "substituir", "garantia" e emoji na arte;
- palavras comuns sem acento ("radio", "programacao" etc.);
- tela do painel ou conversa sem o aviso de dados fictícios.

Avisa (sem bloquear): texto menor que 24 px.

## Peça nova

1. Acrescente a peça em `src/pecas.mjs`, usando as molduras `feed()` ou `story()`.
2. Rode `node instagram.mjs <id>` e olhe o PNG.
3. Escreva a legenda em `legendas.md` e rode o script inteiro: as legendas passam pelas mesmas regras de texto.
