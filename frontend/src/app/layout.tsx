import type { Metadata } from "next";
import { DashboardCacheProvider } from "@/components/dashboard-cache";
import "./globals.css";

export const metadata: Metadata = {
  title: "Paddock Brief",
  description: "한국어 그랑프리 인터뷰와 레이스 컴패니언",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ko">
      <head>
        <link rel="preconnect" href="https://cdn.jsdelivr.net" />
        <link
          crossOrigin="anonymous"
          href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css"
          rel="stylesheet"
        />
      </head>
      <body><DashboardCacheProvider>{children}</DashboardCacheProvider></body>
    </html>
  );
}
