import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Conductor — Multi-Agent Research",
  description: "LangGraph multi-agent orchestration platform"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-slate-950 text-slate-100">{children}</body>
    </html>
  );
}