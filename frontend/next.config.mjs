/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "standalone", // 产出独立运行包（服务器无需 npm install）
  // 同源部署：前端 /api 请求由 Next.js 服务端代理到本地后端 8000
  // （前端代码使用相对路径，无需配置后端地址，免跨域）
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.BACKEND_URL ?? "http://127.0.0.1:8000"}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
