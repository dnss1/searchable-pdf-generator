/** @type {import('next').NextConfig} */

// Two build modes:
//  - default: talks to the demo server (server/) at NEXT_PUBLIC_API_URL
//  - STATIC_DEMO=1: static HTML for GitHub Pages. API responses come from
//    public/demo-api (made by tools/export_static_api.py). The project site is
//    served under /<repo>, so BASE_PATH is set by the Pages workflow.
const staticDemo = process.env.STATIC_DEMO === '1'
const basePath = process.env.BASE_PATH ?? ''

const nextConfig = {
  reactStrictMode: true,
  ...(staticDemo && {
    output: 'export',
    images: { unoptimized: true },
    trailingSlash: true,
    basePath,
    assetPrefix: basePath || undefined,
  }),
  env: {
    NEXT_PUBLIC_STATIC_DEMO: staticDemo ? '1' : '',
    NEXT_PUBLIC_BASE_PATH: basePath,
    NEXT_PUBLIC_API_URL: staticDemo
      ? `${basePath}/demo-api`
      : process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5015',
  },
}

module.exports = nextConfig
