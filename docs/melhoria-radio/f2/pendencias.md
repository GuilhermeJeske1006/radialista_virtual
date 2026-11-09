# Pendências registradas na F2

Achados e ideias fora do escopo da F2 (duração real da fala). Nada aqui foi implementado.

## Decisões a confirmar com o usuário
- **Ritmo padrão 150 palavras/min, padrão por modelo acima dele.** Um só valor em `settings.fala_wpm_padrao`
  (centro da faixa 130–160 da pesquisa); por modelo, a média do benchmark de 08/10 (v3 162, v4 158, Flash 171).
  O 145 da F0/F1 saiu do código. Como a voz real do v4 vai de 139 a 195 palavras/min, o padrão do modelo é uma
  média, não um limite seguro: até a 5ª fala medida de uma voz nova a estimativa pode ser otimista (ver abaixo).
- **"Peça de reserva" do plano não foi feita.** A auditoria trocou a reserva por encurtamento por frases; quando
  nenhuma frase cabe, só o bloco de música com faixa e sem pedido perde a fala, e qualquer outro mantém o texto
  (`fala_ajuste="acima_do_teto"`, nunca silêncio). Trocar a fala que não cabe por vinheta de passagem mexe no
  estado do relógio (F1) e fica para F3/F6. Hoje o corte (`cortada`) quase não ocorre: com orçamento aplicado,
  música sem pedido não tem fala (formato musical e relógio).
- **Formato padrão sem relógio só observa.** Orçamento de observação 15–30 s (as "4 a 6 frases" do prompt). Na
  simulação, 43% (popular) e 62% (variedades) das falas passam dele, porque a unidade da skill (entrada 20–60 s,
  quadro 2–8 min) é maior. A unidade de fala por formato é decisão da F6.

## Riscos medidos na simulação
- **Voz nova muito mais lenta que o padrão do modelo.** Com voz a 120 palavras/min (26% abaixo do v3), antes da
  5ª amostra a estimativa é otimista: em `variedades_leves` 2 de 14 falas passam do máximo (até 110%, nunca do
  teto de 130%) e em `popular_sertanejo` um hard time atrasa 12 s (critério da F1: 5 s). Em produção a tabela
  `ritmos_voz` é persistente e global por voz, então isso só acontece na primeira hora de uma voz nova. Opções:
  calibração progressiva (pseudoamostras do padrão em vez do corte em 5 amostras) ou padrão por modelo mais
  conservador (quantil baixo do benchmark). Ver `simulacao/<perfil>/voz_120/`.
- **Caminho do painel não corrige o excesso medido.** O `/tts` mede, devolve `X-Duracao-Fala-S`, calibra e
  registra o excesso (log `live_fala_duracao origem=tts`), mas o texto já saiu. Só a estimativa calibrada protege
  o orçamento; o encurtamento depois do TTS (momento C) vale no prewarm e em clientes antigos.
- **Encurtamento não respeita o mínimo do orçamento.** Num caso da simulação (identificação de 3 s com promessa
  injetada) a fala virou uma palavra. Considerar o mínimo ao escolher as frases.

## Para as próximas frentes
- **F3:** a reescrita e o encurtamento estão em funções puras de `app/live/orcamento.py`; o router só chama
  (antes do TTS, depois do TTS) e os registros passaram para depois do TTS. A divisão de `gerar_proxima_fala`
  move essas chamadas sem reescrever a regra.
- **F3:** Redis sem timeout (auditoria item 6): deduplicação de amostras e orçamento pendente falham abertos, mas
  sem `socket_timeout` uma queda ainda trava a chamada.
- **F6:** orçamentos por formato saem de `ORCAMENTOS_POR_FORMATO` (construído de `formato.ORCAMENTOS`); trocar pela
  `unidade_fala` do catálogo mantendo a assinatura de `orcamento_para`. A divergência retomada 6–12 s × link
  10–35 s (F0, D5) continua.
- **F7:** chamada curta de "encurtar" (só a fala e as restrições) em vez de reenviar o prompt inteiro: reavaliar com
  a taxa de reescrita por duração medida no `--modo llm`.
- **F9/F11:** o painel recebe os campos novos só nos tipos; mostrar o ritmo medido no `VozConfigModal` e ler
  `X-Duracao-Fala-S` no player (hoje ele mede ao tocar e não manda ao backend). As-run com `duracao_fala_s`.
- **Multivoz:** retirada de linhas pela estimativa e pela medida existe e tem teste de integração, mas as fixtures
  da simulação não têm diálogo; só vale com orçamento aplicado (formato padrão com relógio).

## Fora do escopo (refatoração e dados)
- Três medidores de duração duplicados (patrocinador, biblioteca, vinheta) podem usar `duracao_mp3_s`.
- Pronúncias da voz (`ConfiguracaoVoz.pronuncias`) não entram na estimativa antes do TTS (exigiria o banco no
  caminho puro); aliases longos subestimam a duração até a calibração absorver.
- `app/numeros.py` lê "R$ 4,5 milhões" errado (benchmark de 08/10); a contagem de palavras faladas herda o erro.
- Categorias sem preset de prosódia (retomada, identificação, quadros) calibram juntas na categoria `padrao`.
- Corrida entre `/tts` simultâneos só é exercitada no Postgres; uma amostra perdida é aceitável.

## Bancada
- `--tts duble` é o padrão do CLI desde a F2 (voz do dublê a `--wpm-real 145`, o ritmo com que a F0/F1 mediam a
  fala); `simular()` mantém `tts="nenhum"` para os testes da F0. O dublê do LLM escreve no ritmo do backend sem
  calibração (`--wpm` ausente = `wpm_para`), então a calibração só corrige a duração, não o texto do dublê.
- Pastas em `simulacao/<perfil>/`: com relógio (padrão do CLI), `sem_relogio/` e `voz_120/` (estresse: voz 26%
  mais lenta que o padrão do v3). Com os parâmetros da F1 (`--tts nenhum --wpm 145 --relogio-backend nenhum`) os
  eventos dos três perfis saem idênticos aos de `f1/simulacao/<perfil>/sem_relogio`: as diferenças das pastas
  `sem_relogio/` da F2 (segundos cortados no fim) vêm só da bancada, com o dublê do LLM escrevendo a 162 e a voz
  falando a 145.
- Modos `llm` e `completo` não rodados (custo): falta medir a taxa real de reescrita por duração e o erro da
  estimativa com áudio real da ElevenLabs.

## Achado do juiz (avaliação da F2)
- `encurtar_por_frases` pode reduzir uma fala a um fragmento sem sentido: no `popular_sertanejo` com relógio, a
  identificação virou "Rádio." (0,4 s) quando a voz falou mais devagar que a estimativa. Regra a aplicar no
  validador pós-geração da F3: se o encurtamento deixa a fala abaixo do mínimo do tipo, não levar o fragmento ao
  ar (música segue, ou reserva quando houver) e registrar no as-run.
