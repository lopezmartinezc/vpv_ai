import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { AppShell } from "@/components/layout/app-shell";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Liga VPV Fantasy",
  description: "Liga fantasy de futbol entre amigos - La Liga espanola",
  manifest: "/site.webmanifest",
  themeColor: "#f97316",
  icons: {
    icon: [
      { url: "/favicon.svg", type: "image/svg+xml" },
      { url: "/icon-192.png", sizes: "192x192", type: "image/png" },
      { url: "/icon-512.png", sizes: "512x512", type: "image/png" },
    ],
    apple: [
      { url: "/apple-touch-icon.png", sizes: "180x180", type: "image/png" },
    ],
  },
  openGraph: {
    title: "Liga VPV Fantasy",
    description: "Liga fantasy de futbol entre amigos - La Liga espanola",
    url: "https://new.ligavpv.com",
    siteName: "Liga VPV",
    images: [{ url: "/og-image.png", width: 1200, height: 1200 }],
    locale: "es_ES",
    type: "website",
  },
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "Liga VPV",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="es" suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `try{if(localStorage.getItem("vpv-theme")==="dark"){document.documentElement.classList.add("dark")}}catch(e){}`,
          }}
        />
      </head>
      <body className={`${inter.variable} font-sans antialiased`}>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
