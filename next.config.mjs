/** @type {import('next').NextConfig} */
const nextConfig = {
  poweredByHeader: false,
  reactStrictMode: false,
  async rewrites() {
    return [
      { source: '/api/:path*', destination: 'http://45.79.124.28:8000/:path*' },
      { source: '/c/:path*', destination: '/' },
      { source: '/auth/supabase/:path*', destination: '/' },
      { source: '/auth/verify-email', destination: '/' },
    ];
  },
};

export default nextConfig;
