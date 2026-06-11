import path from 'node:path'
import type { NextConfig } from 'next'

const nextConfig: NextConfig = {
  // Emit a self-contained server bundle (.next/standalone) for the Docker image.
  output: 'standalone',
  // Skip the TypeScript type-check ONLY inside the Docker image build
  // (the Dockerfile sets DOCKER_BUILD=1). It keeps peak build memory low on
  // constrained hosts. The normal `bun run build` (e.g. `verify:web:build`)
  // still type-checks — the image build is the only place types are skipped.
  typescript: {
    ignoreBuildErrors: process.env.DOCKER_BUILD === '1',
  },
  // Enable React strict mode
  reactStrictMode: true,
  turbopack: {
    root: path.resolve(__dirname, '..'),
  },

  // Optimize images
  images: {
    unoptimized: true,
  },

  async rewrites() {
    const backendUrl = process.env.AGENT_BACKEND_URL?.replace(/\/$/, '')
    if (!backendUrl) {
      return []
    }

    return [
      {
        source: '/api/get_config',
        destination: `${backendUrl}/get_config`,
      },
      {
        source: '/api/startAgent',
        destination: `${backendUrl}/startAgent`,
      },
      {
        source: '/api/stopAgent',
        destination: `${backendUrl}/stopAgent`,
      },
    ]
  },
}

export default nextConfig
