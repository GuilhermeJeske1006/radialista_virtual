# Melhorias de clonagem implementadas e verificadas

Data: 10/09/2026. Alterações locais; não houve publicação em produção.

A auditoria e as fontes para gravação, Voice Library e corpora estão em
[analise-clonagem.md](analise-clonagem.md). Os resultados anteriores foram
preservados como histórico; os arquivos `*-depois.json` correspondem ao código
corrigido.

## O que mudou

- **Amostras:** upload de 1–5 arquivos, até 15 MB e 180 segundos somados. O
  servidor decodifica e estima fala com WebRTC VAD, exigindo 20 segundos de fala
  detectada e recomendando 60–120. Silêncio, tons puros, ruído branco do teste e
  preenchimento com silêncio deixam de avançar até a clonagem. A análise avisa
  sobre baixo volume, saturação e fundo alto. Os arquivos originais são enviados
  à ElevenLabs sem processamento destrutivo. O endpoint de criação repete a
  validação, mesmo quando alguém pula a análise no painel.
- **Gravação:** negociação do formato suportado pelo navegador e preservação do
  MIME/extensão, incluindo MP4/M4A. Cronômetro, indicador de nível, interrupção em
  três minutos e liberação de microfone, temporizadores e URLs de reprodução.
  Uma gravação que falha não é apresentada como amostra pronta.
- **Tipo da voz:** metadados persistidos e cache de uma hora. Somente a categoria
  `cloned` recebe os ajustes específicos de clonagem instantânea. A voz padrão
  real foi confirmada como `professional`; vozes profissionais e de categoria
  desconhecida não são presumidas como instantâneas.
- **Verificação:** criação e listagem preservam o estado pendente; ele impede
  seleção e síntese. O painel permite consultar novamente o status depois da
  verificação na ElevenLabs. Falhas na consulta não apagam uma pendência já
  conhecida.
- **Ajustes por conta e voz:** modelos v3, Multilingual v2 e Flash v2.5; perfil
  atual ou neutro; MP3 128 ou 192 kbps; até 30 pronúncias de nomes e marcas. O
  neutro usa estabilidade 0,5, estilo zero e velocidade normal, sem a tag de calma
  automática. Não foi escolhido um vencedor por suposição: o perfil atual
  continua sendo o padrão, e o usuário pode comparar e salvar sua preferência.
- **Texto falado:** normalização de valores monetários, horários, datas válidas,
  frequências, telefones explicitamente formatados, percentuais e temperaturas.
  Pronúncias se aplicam somente ao áudio e sem substituições em cascata. Tags
  desconhecidas, inclusive com espaços e acentos, são removidas; modelos v2/Flash
  não recebem tags v3. O campo `language_code` é omitido no Multilingual v2.
- **Ao vivo:** as preferências chegam à síntese embutida, à resposta completa com
  pós-produção e ao streaming, sem alterar o modelo global de outras contas.

## Validação executada

**252 testes distintos do backend passaram:** a primeira execução teve 247
casos; após os últimos ajustes, foram executados novamente os 152 casos de TTS e
roteamento ao vivo, mais cinco regressões novas, totalizando 157 nessa execução
final. As regressões novas verificam as preferências nos três caminhos de áudio,
o bloqueio da voz padrão pendente e o contrato de idioma nos três modelos.

**22 testes do painel passaram**, cobrindo múltiplas amostras, análise obrigatória,
invalidação após troca de arquivo, verificação pendente, gravação M4A simulada,
liberação do microfone, erro do gravador e salvamento das preferências.
`npx tsc --noEmit` e `git diff --check` também passaram.

**Chromium visível:** navegação real no painel local, com API simulada, em
1365×1000 e 375×812. Confirmados envio de dois arquivos, bloqueio antes da análise,
exibição do resultado, clone pendente indisponível e envio dos ajustes escolhidos.
Sem erros JavaScript. Os modais couberam horizontalmente no celular e os botões
foram alcançados e acionados por rolagem. A página ao fundo apresentou excesso de
largura; o teste de responsividade aprovado se limita aos modais de voz. Não foi
realizado teste com microfone físico ou Safari real.

O diagnóstico offline [entrada-clone-depois.json](entrada-clone-depois.json)
rejeitou os três controles com HTTP 400, sem chamar o provedor: silêncio de 21 s,
tom senoidal de 21 s e silêncio de 5 s. O fixture de fala dos testes tem origem e
licença documentadas em `backend/tests/fixtures/webrtcvad/README.md`; ele não foi
enviado para treinamento.

**Quatro sínteses reais**, usando a voz já configurada e os clientes modificados,
foram concluídas e decodificadas sem erro. A conferência com FFprobe confirmou
44,1 kHz e os bitrates solicitados. Resultados em
[sintese-depois.json](sintese-depois.json).

| Caso | Caminho | MP3 | Tempo da chamada | Duração do áudio |
| --- | --- | --- | ---: | ---: |
| v3 atual | Completo | 128 kbps | 7,807 s | 16,160 s |
| v3 neutro | Streaming | 192 kbps | 7,220 s | 15,804 s |
| Multilingual v2 neutro | Completo | 192 kbps | 4,234 s | 16,486 s |
| Flash v2.5 neutro | Streaming | 128 kbps | 1,427 s | 13,871 s |

Página de escuta local: `/tmp/locufy-voz-melhorias-2026-09-10/escuta.html`.
Ela contém os áudios originais incorporados. Os tempos de streaming acima medem
a recepção completa, não o primeiro byte. Uma amostra por configuração não mede
p95 nem determina superioridade perceptiva. O teste confirma integração,
formatos e decodificação; não houve avaliação auditiva humana nem comparação de
identidade com uma gravação humana de referência. Os volumes dessa página não
foram equalizados.

## Uso e implantação

No radialista, use **Clonar uma voz** para gravar/enviar amostras, analisar e então
clonar. Use **Ajustar voz selecionada** para escolher modelo, interpretação,
formato e pronúncias. Reinicie a sessão ao vivo para descartar áudio preparado
antes de uma alteração.

A instalação do backend precisa incorporar `webrtcvad-wheels==2.0.14` de
`requirements.txt` e manter FFmpeg disponível. A dependência foi instalada no
ambiente local `backend/.venv`. Reinicie o backend com o código atualizado: seu
startup existente (`Base.metadata.create_all`) cria as duas tabelas novas
`metadados_vozes` e `configuracoes_vozes`, sem alterar as tabelas existentes.
Ambientes que impedem DDL no startup precisam criar essas tabelas pelo seu
processo de migração. O painel precisa ser compilado/publicado com as alterações.

Os avisos de qualidade são heurísticos: não certificam ausência de música, eco,
outros locutores ou fidelidade. A opção de 192 kbps exige plano compatível na
ElevenLabs, confirmado para a conta usada no teste. A criação continua sendo
instantânea; um novo treinamento profissional exige material do titular e o
fluxo de verificação do provedor descrito na auditoria.

## Reproduzir

```sh
cd backend
.venv/bin/python -m pytest tests/test_tts_client.py tests/test_tts_router.py tests/test_tts_quality.py tests/test_tts_profiles.py tests/test_tts_voices.py tests/test_numeros.py tests/test_postprod_client.py tests/test_live_router.py -q
PYTHONPATH=. .venv/bin/python scripts/auditar_entrada_clone.py
# Só descreve o teste, sem chamadas externas:
PYTHONPATH=. .venv/bin/python scripts/validar_melhorias_voz.py --output /tmp/voz-nova-rodada
# Executa quatro sínteses e consome créditos normais; use uma pasta nova:
PYTHONPATH=. .venv/bin/python scripts/validar_melhorias_voz.py --output /tmp/voz-nova-rodada --executar-api
cd ../frontend-painel
npx vitest run components/__tests__/VoiceSelect.test.tsx components/__tests__/VozCloneModal.test.tsx components/__tests__/VozConfigModal.test.tsx
npx tsc --noEmit
```

Script do teste de navegador nesta sessão: `/tmp/playwright-test-vozes.js`.
Capturas: `/tmp/locufy-voz-clone-desktop.png`,
`/tmp/locufy-voz-clone-mobile.png` e `/tmp/locufy-voz-config-mobile.png`.
