import type { Metadata, Viewport } from 'next'
import { Inter, Source_Sans_3 } from 'next/font/google'
import { Toaster } from '@/components/ui/sonner'
import './globals.css'

const inter = Inter({ 
  subsets: ['latin'],
  variable: '--font-inter',
})

const sourceSans = Source_Sans_3({ 
  subsets: ['latin'],
  variable: '--font-source-sans',
})

export const metadata: Metadata = {
  title: 'MedRAG - Assistant de pré-consultation médicale',
  description: 'Votre assistant intelligent pour préparer vos consultations médicales. Décrivez vos symptômes, obtenez des orientations et préparez votre rendez-vous.',
  generator: 'MedRAG',
}

export const viewport: Viewport = {
  themeColor: '#3b82f6',
  width: 'device-width',
  initialScale: 1,
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="fr" className="bg-background">
      <body className={`${inter.variable} ${sourceSans.variable} font-sans antialiased`}>
        {children}
        <Toaster position="top-right" />
      </body>
    </html>
  )
}
