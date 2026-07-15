import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'AffiliateContent AI',
  description: 'Turn Amazon affiliate products into ready-to-publish content in minutes.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen flex flex-col">
        <header className="border-b border-gray-200">
          <nav className="max-w-6xl mx-auto px-4 h-16 flex items-center justify-between">
            <a href="/" className="text-xl font-bold text-brand-700">
              AffiliateContent AI
            </a>
            <div className="flex items-center gap-4">
              <a href="/login" className="btn-secondary text-sm">Log in</a>
              <a href="/signup" className="btn-primary text-sm">Sign up</a>
            </div>
          </nav>
        </header>
        <main className="flex-1">{children}</main>
        <footer className="border-t border-gray-200 py-8 text-center text-sm text-gray-500">
          &copy; {new Date().getFullYear()} AffiliateContent AI. All rights reserved.
        </footer>
      </body>
    </html>
  );
}
