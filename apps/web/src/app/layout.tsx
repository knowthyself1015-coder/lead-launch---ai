import type { Metadata } from 'next';
import { auth, signOut } from '@/lib/auth';
import Link from 'next/link';
import './globals.css';

export const metadata: Metadata = {
  title: 'AffiliateContent AI',
  description: 'Turn Amazon affiliate products into ready-to-publish content in minutes.',
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const session = await auth();

  return (
    <html lang="en">
      <body className="min-h-screen flex flex-col">
        <header className="border-b border-gray-200 bg-white">
          <nav className="max-w-6xl mx-auto px-4 h-16 flex items-center justify-between">
            <Link href="/" className="text-xl font-bold text-brand-700">
              AffiliateContent AI
            </Link>
            <div className="flex items-center gap-4">
              {session?.user ? (
                <>
                  <Link href="/dashboard" className="text-sm text-gray-600 hover:text-gray-900">
                    Dashboard
                  </Link>
                  <form
                    action={async () => {
                      'use server';
                      await signOut({ redirectTo: '/' });
                    }}
                  >
                    <button type="submit" className="btn-secondary text-sm">
                      Sign out
                    </button>
                  </form>
                </>
              ) : (
                <>
                  <Link href="/login" className="btn-secondary text-sm">
                    Log in
                  </Link>
                  <Link href="/login" className="btn-primary text-sm">
                    Sign up
                  </Link>
                </>
              )}
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
