import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "智学 · 课程级智能助教",
  description: "智能体赛道参赛作品：上传课件，随时答疑，答案可溯源",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body className="h-screen">{children}</body>
    </html>
  );
}
