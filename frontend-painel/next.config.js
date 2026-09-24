/** @type {import('next').NextConfig} */
const nextConfig = {
  allowedDevOrigins: ["ecologic-rebeca-unedible.ngrok-free.dev"],
  experimental: {
    // O proxy do rewrite abaixo derruba a conexao em 30s por padrao ("socket hang up" -> 500 no
    // browser). /live/.../tts de fala longa (ElevenLabs + pos-producao) passa disso, e o painel
    // espera ate 60s (/tts) e 75s (/proxima) -- o proxy precisa aguentar mais que o cliente.
    proxyTimeout: 90_000,
  },
  // Proxeia /api/* pro backend server-side. Assim o browser so' fala com a
  // origem do frontend (localhost ou ngrok) e o cookie de sessao (SameSite=Lax)
  // vira same-site sempre, sem depender de CORS/SameSite=None pro tunel.
  async rewrites() {
    const backendUrl = process.env.INTERNAL_API_URL || "http://localhost:8000";
    return [{ source: "/api/:path*", destination: `${backendUrl}/:path*` }];
  },
};

module.exports = nextConfig;
