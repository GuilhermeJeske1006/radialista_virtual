# Energia das vinhetas e da apresentação musical

21/11/2026. Ajuste solicitado para vinhetas pouco animadas e apresentação de programa musical com voz desanimada.

## Comportamento implementado

- Abertura, passagem e encerramento usam um preset de síntese específico de vinheta, com tom enérgico. A passagem deixa de cair no preset genérico e o encerramento deixa de herdar a leitura calma da despedida comum.
- A direção da vinheta prevalece sobre o perfil neutro da voz durante essa geração, mantendo modelo, formato e glossário da conta. A preferência salva da voz permanece intacta.
- Textos novos pedem entrada de impacto, ritmo vivo e assinatura marcante até o encerramento. O template local também recebe fechamento mais vivo.
- O formato musical deixa de impor tom neutro. A apresentação segue a energia da persona; sem essa escala, respeita um tom explicitamente calmo e usa direção enérgica como padrão musical. Notícias, serviços, comentários e reações a reclamações mantêm a direção editorial do bloco.
- Em apresentações musicais enérgicas, saem as instruções automáticas de começar com pouca energia e de conter o entusiasmo no meio do programa. O roteiro passa a pedir presença e sorriso na voz desde a primeira frase, com articulação clara.
- Retomada e identificação usam a categoria vocal de abertura, inclusive na estimativa de ritmo.
- A trilha de um programa animado pede pulso e impacto mesmo à noite. Não há aumento do alvo de loudness da mixagem para simular animação.
- Flash diferencia a direção enérgica e a calma com parâmetros próprios. No v3, a tag automática de entusiasmo fica restrita à vinheta; no v4, ela também pode dirigir apresentações e chamadas enérgicas. Tags emocionais explícitas no texto continuam tendo precedência e o perfil neutro da locução comum continua disponível.
- v4 e v4 Turbo recebem Stability e Similarity, sem Style, Speed ou Speaker Boost. A filtragem também vale para o perfil neutro. [Contrato atual do modelo](https://elevenlabs.io/docs/overview/capabilities/text-to-speech/eleven-v4).
- O cache de TTS passa à versão 2, para não devolver as leituras anteriores aos novos presets.

## Arquivos principais

- `backend/app/live/direcao_voz.py`: resolução comum da energia e instrução do roteiro.
- `backend/app/live/router.py` e `prompt_emissao.py`: aplicação na síntese e no texto.
- `backend/app/tts/client.py`, `modelos.py` e `cache.py`: presets, capacidades, tags e invalidação do cache.
- `backend/app/vinhetas/servico.py`, `gerador.py` e `trilha.py`: direção da voz, texto e trilha.

## Validação e limites

Os testes novos verificam o tom entregue pelo endpoint ao player, o respeito à persona e aos programas calmos, a preservação da intenção editorial, a direção das três vinhetas e os parâmetros de cada modelo. O teste da vinheta com voz neutra verifica também que a preferência original não é modificada.

Validação concluída: 42 testes de vinhetas e 61 cenários de caracterização/integração passaram nas rodadas finais. Também passaram as verificações de TTS, perfis, direção musical, formatos, player, preparo antecipado, orçamento de fala, ritmo e cache na seleção ampliada. `ruff check backend/app backend/tests` e `git diff --check` passaram. A suíte completa do backend não foi executada.

Os retratos de `/proxima` foram atualizados para a mudança intencional de roteiro e tom. A comparação estruturada dos 13 retratos alterados confirmou que músicas, pedidos, ações de banco, buscas e sorteios permanecem iguais. As outras diferenças são as instruções de energia, o tom e o agrupamento de ritmo de retomadas/identificações.

Os testes técnicos usam provedores simulados. A adequação de cada voz aos novos presets, incluindo o risco de respiração excessiva com `[excited]`, depende da avaliação auditiva. Usar o [protocolo de comparação](2026-11-21-prosodia-gaucha/README.md) com a voz efetiva do programa e acrescentar abertura, passagem e encerramento de vinheta como casos próprios; recalcular o número de sínteses e o orçamento dessa rodada.

## Aplicação aos áudios existentes

As mudanças valem após iniciar o backend com esse código. As próximas sínteses usam os novos presets; vinhetas já salvas como arquivos precisam ser geradas novamente. Remixar apenas a trilha reaproveita a leitura antiga. Para trocar também uma trilha antiga mais calma, gerar uma trilha nova.

Nenhuma voz ou trilha foi gerada com a API real nesta alteração. Não houve alteração das configurações da conta, publicação ou regeneração automática de arquivos existentes.
