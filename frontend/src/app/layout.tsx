import type { Metadata } from "next";
import "./globals.css";
import Nav from "@/components/Nav";

export const metadata: Metadata = {
  title: "AlphaSight — AI Trading Agent",
  description: "Autonomous AI stock trading agent dashboard",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-surface-950 text-surface-50 antialiased">
        <div className="flex min-h-screen">
          <Nav />
          <main className="flex-1 p-6 lg:p-8 overflow-auto">{children}</main>
        </div>
      </body>
    </html>
  );
}
