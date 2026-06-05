/** @type {import('next').NextConfig} */
const nextConfig = {
  typescript: {
    ignoreBuildErrors: true,
  },
  images: {
    unoptimized: true,
  },
  // Proxy /api/* → FastAPI localhost:8000
  // Évite les problèmes CORS en développement
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://localhost:8010/:path*',
      },
    ];
  },
};

export default nextConfig;
