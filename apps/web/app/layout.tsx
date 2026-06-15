import type { Metadata } from "next";
import Providers from "./providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "AgentLens — AI Agent Observability",
  description: "Complete real-time visibility into autonomous AI agent execution",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  // In local mode, skip ClerkProvider entirely.
  // The mock auth in lib/auth.tsx handles everything.
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <body className="min-h-screen bg-slate-950 text-slate-50 antialiased selection:bg-indigo-500/30" suppressHydrationWarning>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
