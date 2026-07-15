import { auth } from '@/lib/auth';
import { NextResponse } from 'next/server';

export default auth((req) => {
  const { nextUrl } = req;
  const isLoggedIn = !!req.auth;

  const protectedPaths = ['/dashboard', '/workspace', '/profile'];

  if (protectedPaths.some((p) => nextUrl.pathname.startsWith(p)) && !isLoggedIn) {
    return NextResponse.redirect(new URL('/login', nextUrl));
  }

  return NextResponse.next();
});

export const config = {
  matcher: ['/dashboard/:path*', '/workspace/:path*', '/profile/:path*'],
};
