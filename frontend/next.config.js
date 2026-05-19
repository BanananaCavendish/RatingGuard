/** @type {import('next').NextConfig} */

// API 代理目标，支持通过环境变量配置（用于 Docker 部署）
const API_TARGET = process.env.NEXT_PUBLIC_API_TARGET || "http://localhost:8000";

const nextConfig = {
  // Standalone 模式 —— 用于 Docker 优化构建
  output: process.env.NODE_ENV === "production" ? "standalone" : undefined,

  images: {
    remotePatterns: [
      { protocol: "https", hostname: "**" },
    ],
  },

  // API 请求代理到后端
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${API_TARGET}/api/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
