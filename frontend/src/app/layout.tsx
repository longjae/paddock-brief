import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Paddock Brief",
  description: "한국어 그랑프리 인터뷰와 레이스 컴패니언",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
