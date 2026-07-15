import { auth } from '@/lib/auth';
import { NextResponse } from 'next/server';

const protectedPaths = [
  '/dashboard',
  '/products',
  '/writer',
  '/video',
  '/images',
  '/templates',
  '/campaigns',
  '/affiliate',
  '/analytics',
  '/settings',
  '/workspace',
  '/profile',
];

export default auth((req) => {
  const { nextUrl } = req;
  const isLoggedIn = !!req.auth;

  if (protectedPaths.some((p) => nextUrl.pathname.startsWith(p)) && !isLoggedIn) {
    return NextResponse.redirect(new URL('/login', nextUrl));
  }

  return NextResponse.next();
});

export const config = {
  matcher: [
    '/dashboard/:path*',
    '/products/:path*',
    '/writer/:path*',
    '/video/:path*',
    '/images/:path*',
    '/templates/:path*',
    '/campaigns/:path*',
    '/affiliate/:path*',
    '/analytics/:path*',
    '/settings/:path*',
    '/workspace/:path*',
    '/profile/:path*',
  ],
};
