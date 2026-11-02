/** @type {import('next').NextConfig} */

// GitHub Pages 프로젝트 사이트는 /<repo> 아래에 붙는다.
// 로컬에서 볼 때는 BASE_PATH 를 비워 두면 된다.
const basePath = process.env.BASE_PATH ?? ''

const nextConfig = {
  reactStrictMode: true,
  output: 'export',              // 정적 HTML 로만 빌드 — 서버 없이 동작
  images: { unoptimized: true },
  trailingSlash: true,
  basePath,
  assetPrefix: basePath || undefined,
}

module.exports = nextConfig
