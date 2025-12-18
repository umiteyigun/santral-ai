import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'Sesli Sohbet',
  description: 'Ollama ile sesli sohbet',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="tr">
      <body>{children}</body>
    </html>
  )
}

