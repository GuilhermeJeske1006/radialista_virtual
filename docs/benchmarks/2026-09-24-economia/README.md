# Economia de IA: implementação e validação

Executado em 24/09/2026 com APIs reais, dados fictícios e a voz já configurada no
ambiente. Não alterou preferências persistidas nem iniciou uma transmissão.

**Resultado:** aprovar reutilização de áudio e cache de classificações estáveis.
Manter Opus e v3 como padrões. A amostra não aprova migração geral para Haiku/Flash
nem comprova a margem de 60% simulada anteriormente.

## O que foi implementado

- Cache de áudio entre chamadas buffered e streaming, com isolamento por conta,
  credencial, texto, voz, modelo, formato e parâmetros. Mantém o primeiro áudio
  integral, incluindo a prosódia. v3 ignora contexto anterior, como o provedor.
  Cache não guarda streams interrompidos. Lock evita duas gerações simultâneas
  idênticas; prazo de espera esgotado devolve 429 em vez de duplicar a geração.
- Regeração explícita de uma vinheta que já possui voz pode ignorar cache.
  Há chave `reutilizar_audio=False` no cliente para outras regenerações deliberadas.
- Cache de resultados só para tom, categoria, tema, fio condutor, resumo de
  metadados e extração de músicas citadas. **Sugestões de música/pautas não são
  cacheadas**, para não congelar a variedade editorial. Falas criativas também não.
- Cache de prefixo do prompt configurável, sem remover ou reordenar instruções. O provedor exige
  prefixos suficientemente longos/repetidos; medir hits antes de estimar economia.
  O teste curto de classificação não atingiu cache de prefixo, como esperado.
  Ficou **desativado por padrão**: prompts dinâmicos sem reutilização podem aumentar
  custo pela escrita de cache. O cache de resultado das classificações fica ativo.
- Medição e reserva persistentes para LLM/visão/pesquisa, TTS, STT e música gerada.
  Registro em microrreais inclui margem de segurança, tipo/modelo e unidades
  retornadas ou estimadas. Modelos sem tarifa configurada não podem gerar gasto.
- Limite mensal atômico por conta, inclusive threads multivoz, vinhetas, prewarm e
  worker de notícias/assuntos. A reserva captura o mês UTC; concluir é idempotente.
  Timeout/desconexão conserva a reserva até reconciliação, pois pode ter havido cobrança.
- `GET /billing/consumo-ia` expõe orçamento, comprometido, disponível e avisos de
  70%/90%/esgotado. A página de assinatura apresenta percentual e orientação de
  uso, sem expor custos internos ao cliente. Erro na consulta não vira consumo zero.
- O painel não repete automaticamente uma síntese já marcada como falha pelo
  backend, inclusive linhas multivoz. Preserva áudios que chegaram prontos e mantém
  a cama musical; uma falha com cobrança incerta não dispara uma segunda geração.
  Erros estruturados do orçamento são exibidos como mensagem legível.
- Repetições automáticas ocultas do SDK de LLM desativadas para evitar novas
  cobranças em falhas ambíguas. O retry editorial explícito continua existindo e
  cada chamada recebe sua própria reserva.

As tabelas `orcamentos_ia` e `consumos_ia` são criadas pelo `create_all` existente
no startup. O livro é independente da transação da rota, para que um rollback
editorial não apague custos já incorridos.

## Evidência real de cache

Em [cache/cache-real.json](cache/cache-real.json): uma classificação real, repetida
sem segunda chamada; uma síntese v3, repetida em buffered e streaming, sem novas
sínteses. Os três áudios são **idênticos byte a byte**. SHA-256 e tamanho estão no
JSON; [áudio original](cache/original.mp3) está disponível para escuta.

Isso elimina 100% do custo de nova geração **nas repetições atendidas pelo cache**.
A economia mensal depende da taxa de reutilização; não assumir a mesma redução
para falas inéditas. Persistência de áudio de patrocinadores e vinhetas já existia
em alguns fluxos; o novo cache amplia a cobertura, não reinventa essa economia.

## Comparação de texto

Cinco casos por modelo: anúncio musical, evento sem autorização, data incerta,
evento encerrado e diálogo. Mesmas entradas, uma rodada por caso, sem avaliação
estatística nem escuta humana. Resultados integrais em [texto.json](texto.json).

| Modelo | Custo estimado das 5 respostas | Latência média |
|---|---:|---:|
| Opus 5 | US$ 0,075960 | 4,44 s |
| Sonnet 5 | US$ 0,030794 | 3,73 s |
| Haiku 4.5 | US$ 0,011597 | 2,28 s |

São custos derivados dos tokens efetivamente retornados e das
[tarifas públicas](https://platform.claude.com/docs/en/about-claude/pricing), não a
fatura. Haiku reduziu aproximadamente 84,7% nessa amostra (inclusive diferença de
tokenização); Sonnet, 59,5%.

A economia não basta para aprovar qualidade. No caso de data incerta, Haiku
acrescentou que o evento era tradicional em Curitiba sem esse fato ter sido
fornecido. Nas respostas sobre divulgação não autorizada, os três modelos
produziram explicações de regras pouco adequadas a uma fala de rádio. O baseline
também tem problemas: manter o modelo atual não significa declará-lo perfeito.

Não foram encurtados arbitrariamente contexto, fatos, histórico ou instruções;
não foram combinadas gerações e metadados em um formato novo sem avaliação.
Essas mudanças exigem uma bateria editorial maior antes de adoção.

## Comparação de voz

Abra [escuta.html](escuta.html). Os nomes ficam em detalhes para permitir ouvir
antes de consultar qual modelo gerou cada amostra. Categoria confirmada da voz:
`professional`; não é validação de todas as vozes de catálogo ou clones.

| Amostra | v3 | Flash | Conferência |
|---|---:|---:|---|
| Curta | 8,16 s | 6,41 s | Áudios íntegros, sem saturação |
| Média | 23,04 s | 20,34 s | Transcrição: 0% de divergência de palavras em ambos |
| Longa | Falhou por timeout | 37,90 s | Flash: 3,2% de divergência, incluindo “para” → “pra” |

WER indicativo desconsidera pontuação, caixa e acentos; inclui erros do próprio
transcritor. Os cinco áudios disponíveis têm amostras numéricas finitas e zero
saturação medida. Ambos receberam o mesmo perfil de pós-produção `radio_fm`.

Houve falhas de conexão na primeira rodada e uma repetição limitada das falhas;
a síntese v3 longa permaneceu indisponível. Assim, não comparar latências dessas
tentativas como desempenho controlado nem interpretar timeout como perda de timbre.
Flash manteve as palavras da amostra média, mas isso **não mede expressividade,
identidade vocal ou preferência humana**. Não foi adotado como padrão.

## Orçamento e implantação

Configuração documentada também em `backend/.env.example`:

```dotenv
IA_CACHE_HABILITADO=true
LLM_PROMPT_CACHE=false
IA_MEDICAO_HABILITADA=true
IA_ORCAMENTO_BLOQUEAR=true
IA_ORCAMENTOS_BRL={"starter":79.2,"growth":139.2,"professional":259.2}
IA_CAMBIO_BRL_USD=5.5
IA_RESERVA_FRACAO=0.15
```

**O bloqueio fica habilitado por padrão no código entregue. Não houve deploy nem
alteração do `.env` em uso.** Para implantação em observação, configurar
`IA_ORCAMENTO_BLOQUEAR=false`: ainda registra consumo atribuído. Falha de persistência
impede novas chamadas pagas, inclusive em observação.

Os tetos são operacionais e ajustáveis; câmbio, preços e STT v1 são estimativas que
precisam refletir o contrato. Mínimos de fornecedores, slots de clonagem,
infraestrutura, tráfego e custos comerciais não são reconciliados automaticamente.
Não prometer margem líquida a partir desse contador. Pacotes pré-pagos de voz,
reajuste de planos e quotas comerciais novas não foram publicados.

Chamadas de LLM reservam um limite conservador para entrada/saída e reconciliam
`usage`. Pesquisa reserva contexto extra: perto do teto uma ação pode ser negada
mesmo que o custo final fosse menor. TTS contabiliza caracteres normalizados,
STT duração decodificada e música duração solicitada. Faturas e possíveis
multiplicadores contratuais ainda precisam ser conciliados.

Reservas incertas **não expiram liberando saldo automaticamente**. Antes de
reconciliar, verificar a cobrança do fornecedor; `concluir(id, custo_usd)` é
idempotente e ajusta o período original. O histórico distingue reservado/concluído.
Não há endpoint público para o cliente zerar consumo.

Cache tem TTL padrão de um dia, até 2 MiB por áudio; dimensionar Redis e sua política
de memória. O orçamento persiste no banco e não desaparece em eviction/reinício
do Redis. Ao atingir teto, só novas chamadas pagas param; conteúdo cacheado e
arquivos existentes permanecem utilizáveis. Clonagem mantém o controle de plano e
rate limit existente, sem afirmar medição de custo por slot.

Jobs externos que chamam clientes pagos precisam de `contexto_conta(account)`;
sem conta, o modo de bloqueio recusa gasto. Scripts isolados de benchmark desativam
esse bloqueio apenas no próprio processo, sem editar configurações persistidas.

## Reprodução

Em `backend`:

```sh
./.venv/bin/python -m pytest tests/test_economia_ia.py tests/test_llm_client.py -q
PYTHONPATH=. ./.venv/bin/python scripts/validar_cache_ia.py --executar-api --output /tmp/cache-ia
PYTHONPATH=. ./.venv/bin/python scripts/benchmark_falas.py texto --output /tmp/comparacao-ia --repeticoes 1
PYTHONPATH=. ./.venv/bin/python scripts/benchmark_falas.py voz --output /tmp/comparacao-ia --repeticoes 1
PYTHONPATH=. ./.venv/bin/python scripts/benchmark_falas.py verificar_audio --output /tmp/comparacao-ia --repeticoes 1
./.venv/bin/python scripts/relatorio_economia_ia.py /tmp/comparacao-ia
```

Os scripts de API consomem créditos; o gerador de relatório é offline. A suíte
completa passou com **1.075 testes**, seguida por **34 testes focados** após a
restrição final do cache para preservar variedade musical. Os focados cobrem
concorrência, limite exato, reserva em timeout, idempotência, troca de mês/plano,
isolamento de contas, streaming interrompido, middleware e regeneração explícita.

Na continuação, a suíte completa do painel passou com **226 testes**, seguida de
testes específicos de continuidade (incluindo a nova cobertura multivoz), consumo
e tipagem TypeScript (`tsc --noEmit`). O backend também passou os dois cenários de
falha de áudio/bloqueio no endpoint do ao vivo após a melhoria da comunicação.
