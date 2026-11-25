# Mais vozes para o locutor no eleven_v4

Executado em 25/11/2026 com a API real (ElevenLabs shared-voices, TTS eleven_v4 e Scribe v2). Pergunta:
quais vozes pt-BR da biblioteca da ElevenLabs soam bem no v4 e cobrem o maior número de tipos de
programa, para o catálogo do locutor deixar de ter só 6 vozes?

**Conclusão:** 55 vozes candidatas passaram em todos os critérios automáticos (elegibilidade, fidelidade,
idioma e ritmo). Como as métricas não separam as vozes boas das ruins (ver 2026-11-23-entrega-voz), a
escolha é por escuta. A branch `feat/vozes-v4` traz um catálogo proposto de **36 vozes** (6 atuais + 30
novas). Com ele, todo tipo de rádio tem pelo menos 3 vozes masculinas e 3 femininas indicadas. As 30 novas
entram em produção só depois da escuta em `decisao.html`.

## Por que precisava

Com as 6 vozes anteriores, mapeadas por estilo de programa:

| Tipo de rádio | Masculinas | Femininas |
|---|---:|---:|
| Jovem / Pop / Hits | **0** | 1 |
| Eletrônica / Dance | **0** | 1 |
| Jornalismo / Notícia | 1 | 1 |
| Gospel / Cristã | 1 | 1 |
| Regional / Retrô / Flashback | 1 | 1 |
| Sertaneja | 2 | 1 |
| Popular / Variedades | 2 | 1 |
| MPB / Variedades | 3 | 2 |

Não havia voz de interior ou sertanejo, de sotaque regional, de esporte nem voz madura. Com várias rádios
e vários locutores por rádio, as mesmas 6 vozes se repetiam.

## Como foi feito

Script: `backend/scripts/triar_vozes_v4.py` (reproduzível e retomável; consome créditos). Corpus:
`backend/scripts/simulacao/corpus_vozes_v4.json`, com 8 falas curtas no estilo do ao vivo (tag só no início,
números por extenso): triagem (abertura enérgica, ouvida por todas), jornalismo, gospel, jovem, noite,
popular (recado de ouvinte), esporte e interior. O payload é o do ao vivo (`_preparar_sintese`, eleven_v4).

1. **Busca.** 42 consultas a `/v1/shared-voices` (por uso no ano, clonagem e tendência, por gênero, por caso
   de uso e por termos como locutor, rádio, notícia, esporte, sertanejo, gospel, nordestino e gaúcho).
   Resultado: 2.463 vozes, das quais 771 pt-BR.
2. **Elegibilidade (sem custo).** Ficaram 499 vozes que cumprem os quatro critérios:
   - pt-BR verificado no `eleven_v4` (`verified_languages`);
   - sem preço extra (`rate` 1, sem `fiat_rate`): das 2.463, 165 custam 2 a 3 vezes mais por caractere;
   - aviso de remoção (`notice_period`) de pelo menos 365 dias;
   - sem moderação ao vivo, que pode recusar uma fala no meio do programa.
3. **Candidatas.** 55 vozes: as mais usadas de cada perfil e as descritas como locutor de rádio, sotaque
   regional, esporte ou idade madura.
4. **Triagem.** A fala de triagem em cada candidata, transcrita pelo Scribe. A voz seria reprovada com mais de 3
   palavras faltando ou sobrando, idioma fora do português ou ritmo fora de 120 a 230 palavras/min.
   **Nenhuma foi reprovada**: no máximo 2 palavras de diferença (o Scribe escreve "3:15" e "24"),
   português com probabilidade 1,0 em todas e ritmo de 176 a 222 palavras/min.
5. **Escuta.** As 55 candidatas e 4 vozes atuais (Paulo, Yasmin, Diego e Raquel, como referência) falaram as falas
   do próprio perfil: 198 áudios, sem erro de síntese, sem risada ou suspiro sintético e com fidelidade dentro do
   limite em todos.

A síntese funciona com o id da voz da biblioteca, e a primeira síntese já adiciona a voz à conta (medido: voz nunca usada dá `voice_not_found` em `GET /v1/voices/{id}`; depois de uma síntese, aparece com `sharing.status` `copied`). Por isso a conta de dev agora tem as 55 candidatas. Isso não ocupa slot: são 85 vozes na conta e `voice_slots_used` segue em 2.

## Catálogo proposto

Critérios: cobrir cada perfil com voz masculina e feminina, preferir as mais usadas da biblioteca (milhões de
caracteres por ano indicam que muita gente aprovou a voz) e ritmo até ~205 palavras/min. O v4 não aceita
ajuste de velocidade: o ritmo da voz é o que vai ao ar.

| Perfil | Vozes novas |
|---|---|
| Comunicador popular | Rômulo (radialista), Mário, Lendário, Camilla (locutora), Christine |
| Jovem e hits | Eddy (locutor de FM), Victor Pinho, Keren, Amanda |
| Jornalismo | Borges, Cássio, Ana Dias (e Sérgio, Christine) |
| Noite e romântico | Adam, Léo Antônio, Nina, Lívia |
| Gospel e reflexão | Victor Power, Aninha (e Léo Antônio, Lívia) |
| Sertanejo e interior | Silas (caipira), Tomaz (interior mineiro), Jenifer (interior paulista) |
| Sotaque regional | Eduardo (Sul), Gaúcha, Cícero (nordestino), Thayane (Norte), Dani (carioca) |
| Esporte | Nassif (narrador), Lendário |
| Voz madura | Sérgio, Manoel, Ester |

Ritmo medido no catálogo proposto: mediana de 186 palavras/min. As falas calmas (noite, gospel) ficam em 145 a 168
e as enérgicas em 171 a 207, dentro da faixa natural de rádio. O v4 ajusta o ritmo ao texto sozinho.

Com o catálogo proposto:

| Tipo de rádio | Masculinas | Femininas |
|---|---:|---:|
| Jovem / Pop / Hits | 3 | 3 |
| Eletrônica / Dance | 3 | 3 |
| Jornalismo / Notícia | 6 | 3 |
| Gospel / Cristã | 5 | 4 |
| Regional / Retrô / Flashback | 7 | 6 |
| Sertaneja | 9 | 5 |
| Popular / Variedades | 8 | 4 |
| MPB / Variedades | 10 | 7 |

Ficaram de fora como alternativas (estão em `decisao.html`): Matheus (217 palavras/min) e Lucas (222), rápidos
demais sem ajuste de velocidade; Dyego (212), Nassif talk show (209) e Jairo Moraes (211), pelo mesmo motivo;
Daniel Mercer, Fabio Manarin, Clarice Rodrigues, Taiguara Torro, Roberta, Ana Alice, Betina, Fernanda, Carla,
Alex, Nassif notícia, Fernando Borges, Lair, Adriano, Miranda, Sulamita, Raquel do interior, Nayara Técia,
Felipe Leão e Sara, que têm perfil coberto por voz mais usada.

## O que mudou no código

- `app/tts/voices.py`: `PERFIS_VOZ` (estilo de programa → tipos de rádio indicados), campo `perfis` em cada voz
  e as 30 vozes novas. `/tts/voices` devolve `perfis_rotulos`. As previews faltantes são buscadas em paralelo:
  em série, a primeira listagem faria até 2 chamadas por voz, 72 com 36 vozes. URL de preview fixa no código não
  serve, porque a da Yasmin é assinada e tem data.
- `app/llm/config_generator.py`: o catálogo que o LLM recebe para escolher a voz da persona traz os estilos
  de cada voz, com as indicadas para o tipo da rádio primeiro e marcadas.
- `frontend-painel/components/VoiceSelect.tsx`: filtro por gênero e por estilo no catálogo, e estilos embaixo
  de cada voz. A voz escolhida continua visível mesmo fora do filtro.
- `backend/scripts/adicionar_vozes_biblioteca.py`: adiciona à conta da ElevenLabs as vozes da biblioteca que estão
  no catálogo e avisa se alguma saiu da biblioteca. O aviso de remoção de 730 dias só vale para quem tem a voz na
  conta. A primeira síntese já adiciona a voz, mas até esse primeiro uso em produção a voz ficaria sem a
  proteção.
- Testes: cada tipo de rádio tem voz masculina e feminina indicada, os perfis existem, ids e nomes não se repetem,
  o prompt põe as indicadas primeiro, o filtro do painel funciona.

## Pendências (nesta ordem)

1. **Escuta.** Abrir `decisao.html` (os áudios ficam na máquina que rodou o script), aprovar ou reprovar cada
   voz e copiar as decisões. As reprovadas saem de `VOZES_DISPONIVEIS` e as alternativas aprovadas entram.
   `escuta.html` é a versão às cegas (nota de 1 a 5), se preferir não ver os nomes.
2. **Adicionar as vozes à conta**, em dev e em produção (chaves diferentes):
   `scripts/adicionar_vozes_biblioteca.py` lista o que falta; `--aplicar` adiciona.
3. **Merge no master = deploy.** Nenhuma migração: a voz já escolhida de cada locutor não muda.

Riscos conhecidos:

- **Scheila** (catálogo atual) não tem `notice_period` na biblioteca: pode sumir sem aviso. Vale trocar por
  Ana Dias ou Cássio se ela sair.
- Falas longas (700+ caracteres) nas vozes novas não foram ouvidas.
- A amostra de cada voz no painel é a preview do dono na biblioteca, às vezes em outro estilo. Gerar uma amostra
  própria no estilo do Locufy (a fala de triagem) é a melhoria seguinte.

## Custo

~21,6 mil caracteres de TTS (198 sínteses) mais as transcrições do Scribe. A busca e a elegibilidade não têm custo.
