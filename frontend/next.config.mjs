/** @type {import('next').NextConfig} */
const nextConfig = {
  // Use standalone output for local/Docker builds; omit in native Vercel builds
  ...(process.env.VERCEL ? {} : { output: 'standalone' }),
  reactStrictMode: true,
  poweredByHeader: false,
  cleanDistDir: false,
  images: {
    remotePatterns: [
      {
        protocol: 'http',
        hostname: 'localhost',
      },
    ],
  },
};

export default nextConfig;
