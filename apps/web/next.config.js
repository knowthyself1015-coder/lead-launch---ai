/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  transpilePackages: ['@affiliate/db', '@affiliate/shared'],
};

module.exports = nextConfig;
