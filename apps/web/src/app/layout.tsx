import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import "./home.css";
import { ToastProvider, Toaster } from "@/components/ui/toast";
import { SakuraThemeShell } from "@/components/ui/SakuraThemeShell";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Shogi AI Learning",
  description: "Annotate, review, and study shogi with engine-powered insights.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ja" className="h-full">
      <body className={`${geistSans.variable} ${geistMono.variable} antialiased h-full`}>
        <ToastProvider>
          <Toaster />
          <SakuraThemeShell>{children}</SakuraThemeShell>
        </ToastProvider>
      </body>
    </html>
  );
}
