import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Prometheus — Autonomous ML Pipeline",
  description: "Describe your ML problem, upload a CSV, and Prometheus builds the pipeline.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-ink-950 text-ink-100 font-sans antialiased h-full">{children}</body>
    </html>
  );
}
