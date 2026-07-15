import NextAuth from 'next-auth';
import Google from 'next-auth/providers/google';
import Resend from 'next-auth/providers/resend';
import { PrismaAdapter } from '@auth/prisma-adapter';
import { prisma } from '@affiliate/db';

const nextAuth = NextAuth({
  adapter: PrismaAdapter(prisma),
  session: { strategy: 'jwt' },
  pages: {
    signIn: '/login',
    newUser: '/onboarding',
  },
  providers: [
    Google({
      clientId: process.env.AUTH_GOOGLE_ID!,
      clientSecret: process.env.AUTH_GOOGLE_SECRET!,
    }),
    Resend({
      from: process.env.AUTH_RESEND_FROM || 'noreply@affiliatecontent.ai',
    }),
  ],
  callbacks: {
    async jwt({ token, user }) {
      if (user) {
        token.id = user.id;
        token.onboardingCompleted = (user as any).onboardingCompleted ?? false;
      }
      return token;
    },
    async session({ session, token }) {
      if (session.user) {
        (session.user as any).id = token.id as string;
        (session.user as any).onboardingCompleted = token.onboardingCompleted as boolean;
      }
      return session;
    },
    authorized({ auth, request: { nextUrl } }) {
      const isLoggedIn = !!auth?.user;
      const isOnboarding = (auth?.user as any)?.onboardingCompleted;
      const protectedPaths = ['/dashboard', '/workspace', '/profile'];
      const isProtected = protectedPaths.some((p) => nextUrl.pathname.startsWith(p));
      if (nextUrl.pathname.startsWith('/onboarding')) {
        if (!isLoggedIn) return Response.redirect(new URL('/login', nextUrl));
        if (isOnboarding) return Response.redirect(new URL('/dashboard', nextUrl));
        return true;
      }
      if (isProtected) {
        if (!isLoggedIn) return Response.redirect(new URL('/login', nextUrl));
        if (!isOnboarding) return Response.redirect(new URL('/onboarding', nextUrl));
        return true;
      }
      return true;
    },
  },
});

export const handlers = nextAuth.handlers;
export const auth = nextAuth.auth;
export const signIn = nextAuth.signIn;
export const signOut = nextAuth.signOut;
