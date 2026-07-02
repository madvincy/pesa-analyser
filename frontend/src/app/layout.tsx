import type { Metadata } from 'next'
import { Inter, Playfair_Display, Space_Grotesk } from 'next/font/google'
import './globals.css'
import { Providers } from '@/components/providers/Providers'
import { ErrorBoundary } from '@/components/ErrorBoundary'

const inter = Inter({ 
  subsets: ['latin'],
  variable: '--font-inter',
  display: 'swap',
})

const playfair = Playfair_Display({
  subsets: ['latin'],
  variable: '--font-playfair',
  display: 'swap',
})

const spaceGrotesk = Space_Grotesk({
  subsets: ['latin'],
  variable: '--font-space',
  display: 'swap',
})

export const metadata: Metadata = {
  title: 'Pesa Analyser - AI-Powered Financial Insights',
  description: 'Upload your M-PESA or Bank Statement and get instant AI-powered insights into your spending, income, and financial health.',
  keywords: 'financial analysis, mpesa, bank statement, AI, spending tracker, Kenya finance',
  authors: [{ name: 'Pesa Analyser Team' }],
  openGraph: {
    title: 'Pesa Analyser - AI-Powered Financial Insights',
    description: 'Upload your M-PESA or Bank Statement and get instant AI-powered insights',
    type: 'website',
    locale: 'en_KE',
    url: 'https://pesa-analyser.com',
    siteName: 'Pesa Analyser',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Pesa Analyser - AI-Powered Financial Insights',
    description: 'Upload your M-PESA or Bank Statement and get instant AI-powered insights',
  },
  metadataBase: new URL(process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:3000'),
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" suppressHydrationWarning className={`${inter.variable} ${playfair.variable} ${spaceGrotesk.variable}`}>
      <body className="min-h-screen bg-background font-sans antialiased">
        <ErrorBoundary>
          <Providers>
            {children}
          </Providers>
        </ErrorBoundary>
      </body>
    </html>
  )
}
