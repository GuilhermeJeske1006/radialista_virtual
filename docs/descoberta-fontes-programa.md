# Descoberta de fontes ao criar um programa

O cadastro de programas e a revisão de radialista + programa gerados com IA buscam
automaticamente até seis sites de apuração. A busca considera os dados da rádio
(nome, tipo, slogan e cidade) e o contexto editorial do programa (descrição, perfil,
público, temas, gêneros musicais, assuntos ao vivo e regras de pesquisa).

Depois de dois segundos sem alteração nesse contexto, o painel consulta
`POST /config/programas/fontes/descobrir`. Só aceita URLs que constam nos resultados
da busca web. Não cria endereços de memória. A seleção aparece com nome, link e
motivo, pode ser desmarcada e é salva como URL completa em `fontes_noticias` e
`fontes_pesquisa` junto com o programa. Os links dos dois campos continuam visíveis
ao reabrir o cadastro, mesmo sem executar outra busca.
Adicionar fontes ativa `pode_pesquisar`, usado pela apuração web do ao vivo.

As gerações via IA (programa avulso ou radialista + programa, com ou sem preview)
também devolvem os links nos dois campos, antes de responder ao painel. O commit
preserva a seleção revisada e não faz outra busca. O programa pertence ao radialista
(`radio_config_id`), que pertence à rádio (`RadioConfig.account_id`); as rotas de leitura
e edição conferem esse vínculo, sem compartilhar a configuração entre rádios ou programas.

Sites sem RSS também funcionam nessa pesquisa. A descoberta não cadastra feeds
RSS compartilhados nem altera a coleta periódica de notícias da rádio.

Alterar o contexto de um programa novo refaz a busca, substituindo apenas as fontes
adicionadas automaticamente e preservando as manuais. Respostas de buscas anteriores
são descartadas pelo painel. É possível pausar a busca automática; programas com
dosagem de notícia “Nenhuma” recebem sugestões apenas em pesquisa externa. Na edição, o botão “Buscar fontes”
permite solicitar a descoberta.

Nenhum cadastro é gravado pela descoberta. O salvamento aguarda a busca em andamento;
se ela falhar ou não encontrar fontes, é possível salvar normalmente e tentar depois.

A implementação usa a integração Anthropic/web search e a medição de IA existentes.
O cache Redis dura uma hora para resultados e um minuto para falhas/ausência de
resultados, separado por conta, dados da rádio e contexto editorial. O endpoint
autenticado admite até 30 solicitações por conta por hora.

A descoberta usa as citações da busca web, sem exigir JSON na mesma resposta.
Respostas antigas em JSON continuam aceitas, inclusive com texto antes/depois, mas
todos os links precisam constar nos resultados reais. Uma busca adicional com erro
não descarta fontes já citadas e confirmadas. Os logs registram o motivo da parada,
quantidade de resultados, fontes selecionadas e códigos de erro da ferramenta.
O botão de nova tentativa envia `atualizar=true`, refazendo a pesquisa sem reutilizar
o resultado anterior em cache; o limite de solicitações continua valendo.
Se a atualização falhar e houver fontes confirmadas para esse mesmo perfil dentro
do cache de uma hora, elas são preservadas sem estender o prazo original do cache.
