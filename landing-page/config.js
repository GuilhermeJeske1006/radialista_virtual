// Contato comercial e destino do painel da landing.
window.LOCUFY_CONFIG = { appUrl: 'https://app.locufybr.com', whatsappNumber: '5547991268815', eventsUrl: 'https://app.locufybr.com/api/funnel/events' };

// Estimativa de preço do Locufy Flex usada pela calculadora da seção #planos.
// Mesma conta do painel (backend/app/billing/combinacoes.py): 6 min de fala nova por hora de
// programa, 12 gerações/h, câmbio R$ 5,50 e fator 2× sobre as tarifas de referência de
// docs/simulacao-plano-consumo.md (24/09/2026). Ao publicar as tarifas contratadas, copie
// preco_hora_brl de GET /billing/combinacoes e atualize também a tabela estática do index.html.
// porMensagem: resposta de WhatsApp com o modelo de texto da combinação (1.500/150 tokens + 3 classificações).
window.LOCUFY_PRECOS = {
  mensalidade: 69.9,
  combinacoes: [
    { id: 'premium', nome: 'Premium', texto: 'Claude Opus', voz: 'ElevenLabs v3', porHora: 8.35, porMensagem: 0.15, recomendada: true },
    { id: 'equilibrada', nome: 'Equilibrada', texto: 'Claude Sonnet', voz: 'ElevenLabs v3', porHora: 7.46, porMensagem: 0.07 },
    { id: 'voz_premium', nome: 'Voz Premium', texto: 'Claude Haiku', voz: 'ElevenLabs v3', porHora: 7.16, porMensagem: 0.05 },
    { id: 'texto_premium', nome: 'Texto Premium', texto: 'Claude Opus', voz: 'ElevenLabs Flash', porHora: 5.05, porMensagem: 0.15 },
    { id: 'agil', nome: 'Ágil', texto: 'Claude Sonnet', voz: 'ElevenLabs Flash', porHora: 4.16, porMensagem: 0.07 },
    { id: 'essencial', nome: 'Essencial', texto: 'Claude Haiku', voz: 'ElevenLabs Flash', porHora: 3.86, porMensagem: 0.05 },
  ],
};
