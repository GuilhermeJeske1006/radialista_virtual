/** @type {import('next').NextConfig} */
const nextConfig = {
  allowedDevOrigins: ["ecologic-rebeca-unedible.ngrok-free.dev"],
  // Proxeia /api/* pro backend server-side. Assim o browser so' fala com a
  // origem do frontend (localhost ou ngrok) e o cookie de sessao (SameSite=Lax)
  // vira same-site sempre, sem depender de CORS/SameSite=None pro tunel.
  async rewrites() {
    const backendUrl = process.env.INTERNAL_API_URL || "http://localhost:8000";
    return [{ source: "/api/:path*", destination: `${backendUrl}/:path*` }];
  },
};

module.exports = nextConfig;
