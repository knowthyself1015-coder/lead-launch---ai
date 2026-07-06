/** @type {import('next').NextConfig} */
const nextConfig = {
  experimental: {
    serverComponentsExternalPackages: ["@prisma/client", "bcryptjs"],
  },
  output: "standalone",
  typescript: {
    // We handle serve.ts separately (Bun runner, not part of Next.js app)
    tsconfigPath: "tsconfig.json",
  },
};

export default nextConfig;
