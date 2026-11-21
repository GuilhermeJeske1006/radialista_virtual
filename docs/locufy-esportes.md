# Locufy Esportes — operação automática no programa

O programa esportivo usa o fluxo normal do ao vivo. Ao selecionar **Esportivo**, a pesquisa
externa é habilitada, a editoria de esportes é incluída e um roteiro inicial é preenchido quando
não há blocos cadastrados. A IA pesquisa notícias, resultados e classificação nas fontes do
programa, considerando a cidade da rádio, e prepara as falas. Só utiliza fatos sustentados
pela apuração; sem resultados verificados, omite informações esportivas sem inventar dados.

A seção **Produção esportiva** e seus atalhos foram removidos do cadastro do programa.
Não é necessário criar edições, preencher fichas factuais ou aprovar roteiros manualmente
para usar o programa ao vivo. O endereço antigo `/esportes` redireciona para `/programas`.

## Referência do piloto editorial anterior

As APIs, dados e componentes do piloto pré-gravado abaixo são mantidos como legado.
Eles não são carregados pelo editor de programas nem fazem parte da operação automática.

## Escopo entregue

Produção assistida e pré-gravada, com uma voz e aprovação humana obrigatória. Há boletins de 2 e 3 minutos e um espelho de programa de 30 minutos. A coleta de fatos é manual nas fontes previamente aprovadas pela emissora. O cadastro de API, feed ou página permitida registra a condição de acesso; não ativa um coletor.

O perfil contém nome padrão das edições, região, clubes, campeonatos, modalidades, fuso, estilo, direção sonora, espaço para participação e distribuição editorial sugerida. Quando ainda não há um perfil esportivo personalizado, nome e tom vêm do programa e o fuso vem do radialista. A voz e o dicionário de pronúncias usam a configuração existente do radialista. O perfil é copiado para a edição: alterar o padrão não modifica edições anteriores.

| Programa de 30 minutos | Duração |
| --- | ---: |
| Abertura e pergunta do dia | 1:00 |
| Esporte regional | 5:00 |
| Futebol nacional | 5:00 |
| Intervalo 1 | 1:00 |
| Pauta principal | 5:00 |
| Internacional e outras modalidades | 3:00 |
| Intervalo 2 | 1:00 |
| Torcida ou quadro de reserva | 3:00 |
| Agenda esportiva | 4:00 |
| Encerramento | 2:00 |
| **Total** | **30:00** |

Esta distribuição é uma proposta do piloto; o anexo descreve os critérios mas não inclui uma tabela completa de tempos por bloco. Os blocos podem ser ajustados, preservando abertura, agenda, encerramento, 28 minutos editoriais e 2 de intervalo. Cada bloco tem assunto, responsável, duração-alvo, transição, fala, referências e reserva quando opcional.

No boletim de 2 minutos: abertura 10s, notícias 75s, agenda 25s e encerramento 10s. No de 3 minutos: 15s, 115s, 35s e 15s.

## Operação

1. Em **Programas**, crie ou edite o programa pelo fluxo atual e selecione **Esportivo** em **Perfil do programa**. Use **Criar programa** ou **Salvar programa** normalmente. Depois abra **Produção esportiva** no próprio editor e configure **Perfil editorial**. Não é necessário cadastrar ou selecionar outro programa. O fuso pertence à emissora, independentemente do computador do operador.
2. Em **Fontes**, confira o domínio exato, a organização, temas, região, idioma, método de acesso, frequência permitida, prioridade, data da revisão e condições de uso/retenção. Cadastre somente depois de verificar a legitimidade da página. Não há fontes automaticamente aprovadas ou integrações presumidas.
3. Crie a edição e confira a exibição prevista. O modelo inicial acompanha a duração cadastrada no programa e o horário sugerido é o próximo início da grade, respeitando dias da semana, data avulsa e fuso. Essa data serve à verificação de validade; não adiciona o programa à grade nem agenda sua reprodução.
4. Leia o conteúdo original. Na **Ficha factual**, registre fatos separados, evento, publicação, coleta, validade, confirmação, origem comum, URL e trecho de evidência. Resultados também exigem participantes, competição e placar. Marque a revisão humana depois da leitura. Para temas sensíveis, há um atestado adicional.
5. Vincule os fatos aos blocos e salve. Escreva a fala ou use **Sugerir fala com IA**. A sugestão recebe apenas os fatos vinculados daquele bloco; não pesquisa notícias nem confirma fatos. Revise o resultado antes de salvar.
6. Confira a fala lado a lado com as evidências e aprove o roteiro da versão salva. Essa aprovação atesta correspondência semântica, atribuições, números, contas, nomes e datas. A validação automática de referências não prova que cada frase é verdadeira.
7. Gere a voz dos blocos editoriais ou envie MP3 de até 25 MB por bloco, incluindo inserções, reservas e participação autorizada. Um MP3 enviado exige a mesma revisão de correspondência com o roteiro. Insira vinhetas, trilhas e transições no próprio arquivo; a direção sonora do perfil não aplica mixagem automática. Sem publicidade, envie chamadas ou quadros curtos aprovados para os intervalos.
8. Ouça todos os blocos. Confira pronúncia, pausas, números, negativas e duração medida. Ajuste texto, distribuição ou áudios; o sistema não corta falas nem preenche tempo com silêncio ou fatos inventados. O total precisa ficar a até 5s do alvo. Alterar o conteúdo invalida todos os áudios da edição, exigindo nova produção e aprovação.
9. Aprove os áudios e exporte a edição em MP3. A montagem reúne os arquivos inteiros na ordem do espelho e mede novamente a duração final. **Registro editorial** baixa o JSON com fatos, fontes, versões, assinaturas, responsáveis pelas aprovações e histórico. Exportação não é registro de exibição.

Não há segunda voz, transcrição/moderação automática, agendamento ou reprodução automática deste módulo. Uma participação real pode ser preparada pelo operador, com autorização e transcrição no bloco; nunca usar mensagens fictícias. Sem mensagens, adotar uma pergunta editorial ou conteúdo verificado de reserva.

## Bloqueios e revisão

- Domínio da evidência deve coincidir exatamente com a fonte aprovada, incluindo `www`. Subdomínios e domínios parecidos não são aceitos por aproximação. URLs devem ser HTTPS, sem credenciais ou portas alternativas.
- Mudança ou bloqueio de fonte exige nova revisão dos fatos vinculados. O cadastro preserva as revisões anteriores. Reativar a fonte não revalida silenciosamente evidências antigas.
- Validade dos fatos usados deve cobrir toda a edição, considerando o maior entre horário previsto e horário da consulta. Coleta/publicação no futuro bloqueiam o fato. Agenda com evento já passado, adiado, cancelado ou anterior ao fim da edição também é bloqueada. Não se infere atualidade da data de publicação.
- Resultado final exige evento passado e encerrado, participantes, competição e placar. Resultados divergentes para o mesmo evento bloqueiam a edição. No piloto, escalações e transferências usadas precisam estar confirmadas; negociação e provável escalação não entram como anúncio definitivo.
- Fatos contestados, evidências não revisadas e temas sensíveis sem revisão específica bloqueiam aprovação. Outras divergências semânticas devem ser marcadas como `contestado` pelo editor; o sistema não resolve conflitos com geração de texto.
- Origem comum e evento permitem detectar republicação e repetição dentro da edição. O reconhecimento semântico de textos com títulos/origens diferentes ainda é manual. Uma fonte oficial pode bastar; não há exigência arbitrária de duas fontes.
- Sugestões e ações de áudio usam a revisão salva. Escritas concorrentes retornam 409. A tela permite descartar alterações e recarregar a versão salva.
- Cada aprovação contém assinatura do conteúdo e editor autenticado. Áudios têm assinatura do conteúdo e SHA-256 do arquivo. Alterar texto, fatos, exibição, perfil ou espelho revoga as aprovações e invalida os áudios. Arquivos antigos permanecem somente para auditoria; não são servidos pelas rotas de reprodução/exportação.
- Reprodução de bloco e exportação passam novamente pela validação editorial. A exportação verifica a assinatura dos arquivos e reconsulta as fontes após a montagem. Respostas de áudio usam `Cache-Control: no-store`.

Um arquivo já baixado está fora do controle da plataforma. O operador deve revalidar a edição antes de colocá-lo no sistema de automação da rádio e impedir reprises vencidas. A integração futura de reprodução deverá aplicar estas mesmas validações imediatamente antes de tocar.

Sem internet, o editor só deve usar fatos já aprovados e ainda válidos ou material atemporal verificado. A IA recebe a ficha fornecida; não há fallback que consulte memória esportiva para preencher a edição.

## Dados, implantação e API

Tabelas novas: `perfis_esportivos`, `fontes_esportivas` e `edicoes_esportivas`, registradas no metadata SQLAlchemy e criadas no startup existente (`Base.metadata.create_all`). Não há alteração das colunas nem dos fluxos dos programas existentes. Perfil e edições são vinculados ao programa com `ON DELETE CASCADE`. Fontes pertencem à conta. Leituras e escritas exigem autenticação e validam a conta do programa/edição.

Os arquivos usam o storage já configurado, local ou S3, em `esportes/<conta>/<edicao>/<uuid>.mp3`. A geração reaproveita o cliente de voz, parâmetros, medição, limites e atribuição de consumo existentes. LLM/TTS são limitados também por conta/hora. FFmpeg é necessário para medir e montar MP3, como nos fluxos existentes de áudio.

| Rotas sob `/esportes` | Uso |
| --- | --- |
| `GET /modelos` | Espelhos dos três tempos |
| `GET/PUT /programas/{id}/perfil` | Padrão editorial |
| `GET/POST /fontes`, `PUT /fontes/{id}` | Cadastro e revisão de fontes |
| `GET/POST /programas/{id}/edicoes` | Histórico e criação |
| `GET/PUT /edicoes/{id}` | Revisão da edição |
| `POST /edicoes/{id}/blocos/{bloco}/sugerir` | Sugestão com fatos vinculados |
| `POST /edicoes/{id}/aprovar-roteiro` | Aprovação editorial humana |
| `POST /edicoes/{id}/blocos/{bloco}/gerar-audio` | Voz do radialista |
| `POST/GET /edicoes/{id}/blocos/{bloco}/audio` | Upload medido / escuta |
| `POST /edicoes/{id}/aprovar-audio` | Aprovação dos áudios e duração |
| `GET /edicoes/{id}/exportar` | Montagem final revalidada |
| `GET /edicoes/{id}/manifesto` | Registro de auditoria |

Estados do piloto: rascunho, em revisão, roteiro aprovado, áudio em produção, áudio para revisão, aprovado para exportar, bloqueado e expirado. A aprovação final não implica agendamento ou exibição. Mudanças pendentes no cadastro do programa precisam ser salvas para retomar a produção. Rascunhos de edição, perfil editorial e fonte impedem recolher o módulo ou trocar o perfil do programa até serem salvos ou descartados. Esses estados exigirão integração própria com o operador/automação da rádio.

## Validação e piloto de dez edições

Os testes automatizados usam fontes e eventos fictícios, sem consultar notícias nem provedores reais. Cobrem isolamento entre contas, domínio parecido, fuso, confirmação de resultado, especulação de transferência, revisão sensível, alteração de fonte, invalidação de áudio, falha de TTS e montagem MP3 medida. A cobertura de navegação no navegador usa respostas simuladas da API; não equivale ao piloto em uma emissora.

O piloto editorial real deve ser executado e registrado pela emissora antes de ampliar a autonomia:

| Edição | Cenário | Verificação principal |
| --- | --- | --- |
| 1 | Boletim de 2 minutos | Evidências e pronúncia por voz |
| 2 | Boletim de 3 minutos | Agenda, datas e duração real |
| 3 | Dia com pouca pauta | Reduzir edição ou reservar conteúdo atemporal verificado |
| 4 | Rodada cheia / programa de 30 minutos | Regionalização, deduplicação e 28+2 minutos |
| 5 | Partida adiada após o áudio | Corrigir fato, salvar, invalidar áudio e refazer aprovação |
| 6 | Fontes divergentes | Marcar fato contestado e bloquear sua utilização |
| 7 | Sem mensagens de ouvintes | Pergunta editorial ou reserva verificada |
| 8 | Falha de voz | Enviar reserva aprovada ou repetir geração |
| 9 | Fonte oficial desatualizada, publicação nova sobre evento antigo | Revisão da evidência e validade, sem priorizar pela publicação |
| 10 | Mudança de fuso, manchete diferente do corpo e falta de evidência tática | Datas no fuso da rádio; omitir conclusões sem suporte |

Por edição, registrar: tempo e custo de produção, duração real, proporção de texto alterada, correções, pronúncias revisadas, reservas utilizadas e aprovação final. Retenção por bloco e participação dependem de integração com a infraestrutura de exibição. Não há resultados de audiência ou de dez edições reais alegados nesta entrega.

Próximas etapas: seleção comercial e técnica das fontes; coleta autorizada com abertura do original e extração de evidências; deduplicação semântica; revalidação automática das fontes; invalidação dos blocos dependentes em vez de toda a edição; correções entre edições; memória de fatos exibidos; participação moderada/transcrita; segunda voz; integração de grade, reprodução e auditoria da versão efetivamente exibida; pré/pós-jogo por status confirmado. Cobertura ao vivo exige projeto próprio.

Comandos de verificação:

```sh
cd backend
.venv/bin/pytest tests/test_esportes.py tests/test_config_router.py tests/test_config_relogio.py tests/test_tts_router.py -q
.venv/bin/ruff check app/esportes app/models/esportes.py tests/test_esportes.py
```

```sh
cd frontend-painel
npx vitest run lib/__tests__/esportes.test.ts components/esportes/__tests__/EdicaoEditor.test.tsx components/__tests__/EditarProgramaForm.test.tsx
npx tsc --noEmit
```

Validação local em 11 de novembro de 2026 após integrar o módulo a Programas: suíte completa do frontend com 335 testes e os 30 testes do módulo no backend aprovados; TypeScript e Ruff aprovados. O fluxo de criar um programa esportivo, abrir sua produção no modal atual, herdar o horário da grade e editar a edição foi verificado com Playwright em desktop/mobile e API simulada. Não há formulários aninhados nem seletor duplicado de programa. As exportações de 2 e 30 minutos foram montadas e medidas com FFmpeg nos testes.

O build de produção passou com `npm run build -- --webpack`, incluindo a rota legada `/esportes` (agora um redirecionamento para Programas). O comando padrão com Turbopack falhou no processamento das fontes Google do layout existente (`next/font/google`, resolução de `@vercel/turbopack-next/internal/font/google/font`). Não houve mudança de fontes, dependências ou configuração do compilador nesta entrega.
