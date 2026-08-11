import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";

const geistSans = localFont({
  src: "./fonts/GeistVF.woff",
  variable: "--font-geist-sans",
  weight: "100 900",
});
const geistMono = localFont({
  src: "./fonts/GeistMonoVF.woff",
  variable: "--font-geist-mono",
  weight: "100 900",
});

export const metadata: Metadata = {
  title: "AI-ORID System",
  description: "AI-ORID 反思寫作",
  icons: {
    icon: "/images/brand/dilab-favicon-32.png",
    apple: "/images/brand/dilab-favicon-180.png",
  },
  other: {
    google: "notranslate",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-Hant" suppressHydrationWarning className="notranslate" translate="no">
      <body
        className={`${geistSans.variable} ${geistMono.variable} notranslate`}
        translate="no"
      >
        {children}
      </body>
    </html>
  );
}
