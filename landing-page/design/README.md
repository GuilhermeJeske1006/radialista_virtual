# Capturas profissionais do painel

## Captura nova

As imagens foram capturadas com Playwright no **painel atual rodando localmente**, em viewport 1440×1000 e escala 2×. Os arquivos completos e os recortes estão em `capturas/`.

As respostas de API foram interceptadas somente no navegador para apresentar uma rádio demonstrativa: Marina Costa, Lucas Almeida e Clara Santos; programas de manhã, tarde e noite; vinhetas e passagens preenchidas. Não houve alteração de contas ou dados no backend. Os dados usados estão em `capturas/dados-demonstrativos.json`.

O tema azul é o tema nativo da aplicação. Na captura, a interface de desenvolvimento do Next.js foi ocultada e animações foram desativadas. A grade foi rolada até 06h. A voz Marina aparece selecionada.

## Edição e entregáveis

Ferramenta: **imagegen integrada**, usando cada captura nova como alvo de edição. Prompts completos: [prompts-profissionais.json](prompts-profissionais.json).

| Arquivo mestre | Origem | Tratamento |
| --- | --- | --- |
| `radialista-profissional.png` | `capturas/radialista-detalhe.png` | Foco em nome, voz selecionada e personalidade; remoção de campos periféricos e ação de exclusão |
| `grade-profissional.png` | `capturas/grade-detalhe.png` | Foco de segunda a quinta, 06h–18h, preservando programas, horários e radialistas |
| `vinhetagem-profissional.png` | `capturas/vinhetagem-detalhe.png` | Foco nas duas categorias preenchidas e nas seis faixas, com nomes e durações |

Composição frontal em 4:3, enquadramento próximo, fundo azul, sombras discretas e acabamento consistente. São recortes editoriais, não capturas integrais sem edição. A página identifica os dados demonstrativos e o tratamento.

Versões finais em `assets/locufy-*-pro-{640,960,1440}.webp`. Imagem de compartilhamento: `assets/locufy-painel-social-v3.jpg` (1200×630). Sharp foi usado apenas na otimização de tamanho/formato das imagens editadas. Executar e compilar a landing continua sem dependências.

## Captura "Ao vivo" (quarta imagem da galeria)

| Arquivo mestre | Origem | Tratamento |
| --- | --- | --- |
| `ao-vivo-profissional.png` | `frontend-painel/public/ajuda/screenshots/ao-vivo.png` (recorte em `capturas/aovivo-detalhe.png`) | Foco no card "Transmitindo / Programa no ar" e na sequência de faixas; recorte remove o banner de erro e o tour de onboarding visíveis na captura original |

O imagegen integrado exigiu plano pago no momento da edição (indisponível). O acabamento — fundo navy `#131c2e`, respiro, sombra suave e brilho de borda azul — foi composto localmente com Pillow, sem IA generativa, reproduzindo o mesmo padrão visual das três imagens acima. Versões responsivas em `assets/locufy-aovivo-pro-{640,960,1440}.webp`, geradas com `cwebp`.

As logos oficiais incorporadas à página permanecem preservadas. Os arquivos da primeira versão estão mantidos como histórico, mas não são referenciados pelo HTML atual.
