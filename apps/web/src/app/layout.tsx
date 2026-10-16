import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { LayoutContent } from "@/components/layout/layout-content";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const baseUrl = process.env.NEXT_PUBLIC_SITE_URL || 'https://finance-tracker.example.com';

export const metadata: Metadata = {
  metadataBase: new URL(baseUrl),
  title: {
    default: "Alpha",
    template: "%s | Alpha",
  },
  description: "Advanced AI-powered personal finance management. Track expenses, analyze behavior, and earn rewards.",
  alternates: {
    canonical: '/',
  },
  openGraph: {
    title: "Alpha",
    description: "Advanced AI-powered personal finance management. Track expenses, analyze behavior, and earn rewards.",
    url: baseUrl,
    siteName: "Alpha",
    locale: "en_US",
    type: "website",
    images: [
      {
        url: '/og-image.png',
        width: 1200,
        height: 630,
        alt: 'Alpha — AI-powered personal finance management',
      },
    ],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Alpha',
    description: 'Advanced AI-powered personal finance management. Track expenses, analyze behavior, and earn rewards.',
    images: ['/og-image.png'],
  },
  robots: {
    index: true,
    follow: true,
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const jsonLd = [
    {
      "@context": "https://schema.org",
      "@type": "WebSite",
      "name": "Alpha",
      "url": baseUrl,
      "description": "Advanced AI-powered personal finance management. Track expenses, analyze behavior, and earn rewards."
    },
    {
      "@context": "https://schema.org",
      "@type": "SoftwareApplication",
      "name": "Alpha",
      "url": baseUrl,
      "applicationCategory": "FinanceApplication",
      "operatingSystem": "Web",
      "description": "AI-powered personal finance management app. Track expenses, income, investments, and earn rewards for financial discipline.",
      "offers": {
        "@type": "Offer",
        "price": "0",
        "priceCurrency": "USD"
      }
    }
  ];

  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <head>
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
          suppressHydrationWarning
        />
      </head>
      <body className="min-h-full">
        <LayoutContent>{children}</LayoutContent>
      </body>
    </html>
  );
}
