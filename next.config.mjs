/** @type {import('next').NextConfig} */
const nextConfig = {
  poweredByHeader: false,
  reactStrictMode: false,
  async rewrites() {
    return [
      { source: '/c/:path*', destination: '/' },
    ];
  },
};

export default nextConfig;
