# Flashback: repertório, escrita e operação

O formato `flashback` aplica as melhorias levantadas na edição da Guabiruba FM de 26/11/2026.

- Anúncios: 5–15 segundos, com alvo de 10. Identificações: 3–8 segundos.
- Comentários e chamadas: 15–30 segundos, uma intenção por entrada.
- Duas músicas entre as entradas de comentário, identificação e participação. Abertura repetida vira retomada; não há inserção aleatória de comentários.
- Uma faixa por bloco. Citação histórica não acrescenta música à fila.
- A direção usa a grade cadastrada e identifica expressões saturadas no histórico recente. Alegações históricas sem apoio no banco editorial são removidas antes da síntese.
- A identidade musical é validada por artista e obra; nomes de canal e metadados de upload não viram locução.
- O repertório inicial de reserva fica em `backend/app/live/flashback.py`. Há 36 obras de 1970–1999. A lista de músicas permitidas do programa pode substituí-lo por curadoria explícita.
- No flashback, não há fallback para “sucessos musica brasileira”. Busca indisponível usa outra faixa aprovada, respeitando o intervalo de 45 minutos por artista, sem relaxá-lo silenciosamente.
- Demo, cover, medley, versões desaceleradas e apresentações de TV/show não entram automaticamente. Remasterizações não são confundidas com obras novas.
- Pedidos de ouvintes também passam pelo repertório verificado. Um pedido indisponível é recusado pelo fluxo existente e substituído por programação regular, sem inventar atendimento.

## Aplicar a um programa existente

Execute dentro do contêiner do backend. A prévia não altera o cadastro:

```sh
python -m app.live.configurar_flashback --account-id 1 --programa-id 3
```

Com `--aplicar`, o comando verifica a conta e o nome do programa, recusa aplicação com player ativo, guarda backup dos campos alterados no storage privado e só depois confirma a nova configuração. A resposta inclui a chave do backup. Não há alteração da voz ou da identidade do radialista.

```sh
python -m app.live.configurar_flashback --account-id 1 --programa-id 3 --aplicar
```

O piloto desabilita pesquisa aberta para esse programa: curiosidades usam fatos editoriais com fonte, sem inventar créditos, datas, vendas ou bastidores. O banco editorial inicial é pequeno e pode ser ampliado com novas fontes verificadas. A produção principal de uma faixa e os créditos de um remix devem permanecer distintos.

## Reprodução e recuperação

O limite de segurança acompanha a duração real da música ou do trecho, com margem de 30 segundos e teto operacional de 25 minutos. Não se interrompe uma faixa legítima aos seis minutos. Há vigilância de início e de progresso; falhas e travamentos solicitam uma substituta. No flashback a substituta também vem do repertório aprovado.

Após uma substituição, textos antecipados são descartados para não comentar uma música que não tocou. O histórico e a telemetria passam a guardar as faixas efetivamente concluídas. A tabela `blocos_reproduzidos.reproducao` registra início, fim, duração e motivo de falha; medições do TTS são associadas ao bloco quando disponível. Preparos expirados e reproduções abandonadas são encerrados sem serem considerados concluídos. O as-run novo conserva até 16 mil caracteres por fala; registros antigos continuam com a extensão original.

## Gravação e avaliação sonora

Na operação manual, permita a captura de áudio da aba no navegador. Ao exportar, o MP3 completo é baixado e uma cópia autenticada fica disponível em **Gravações do programa**, no Ao Vivo, durante sete dias. O backend faz transferência em fluxo para evitar carregar um programa inteiro na memória. O acesso é restrito à conta e ao programa; gravações expiradas deixam de ser acessíveis e são removidas pelo job horário.

Sem captura de áudio da aba — inclusive quando o navegador não permite iniciá-la por agendamento — a exportação mantém o comportamento anterior de somente falas. Esse arquivo parcial não é arquivado como programa completo. Se o arquivo completo for exportado, mas o storage falhar, o download é preservado e o painel avisa que a cópia não foi arquivada.

Na próxima edição, comparar identidade das faixas, repetição de artista, duração e sequência de falas, falhas recuperadas e participação real aproveitada. Ouvir a gravação para avaliar nomes estrangeiros, energia, mixagem e eventuais silêncios; essas qualidades não se comprovam apenas por confirmação do player.

## Fontes do banco editorial inicial

- [Créditos oficiais de Like a Prayer](https://www.madonna.com/products/like-a-prayer-single).
- [Thriller — discografia oficial](https://www.michaeljackson.com/albums/thriller/).
- [Time After Time — metadados da gravação oficial](https://www.youtube.com/watch?v=7wBgcalM4c4).
