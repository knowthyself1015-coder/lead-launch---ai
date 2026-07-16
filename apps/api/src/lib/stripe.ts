import Stripe from 'stripe';

if (!process.env.STRIPE_SECRET_KEY) {
  console.warn('⚠ STRIPE_SECRET_KEY is not set — Stripe integration will not work.');
}

export const stripe = new Stripe(process.env.STRIPE_SECRET_KEY || '', {
  apiVersion: '2025-06-15.basil' as any,
  typescript: true,
});

// Stripe Price ID → tier mapping (populated from environment)
export function getTierFromPriceId(priceId: string): string | null {
  const map: Record<string, string> = {};
  if (process.env.STRIPE_PRICE_CREATOR_MONTHLY) map[process.env.STRIPE_PRICE_CREATOR_MONTHLY] = 'creator';
  if (process.env.STRIPE_PRICE_CREATOR_ANNUAL) map[process.env.STRIPE_PRICE_CREATOR_ANNUAL] = 'creator';
  if (process.env.STRIPE_PRICE_PRO_MONTHLY) map[process.env.STRIPE_PRICE_PRO_MONTHLY] = 'pro';
  if (process.env.STRIPE_PRICE_PRO_ANNUAL) map[process.env.STRIPE_PRICE_PRO_ANNUAL] = 'pro';
  if (process.env.STRIPE_PRICE_AGENCY_MONTHLY) map[process.env.STRIPE_PRICE_AGENCY_MONTHLY] = 'agency';
  if (process.env.STRIPE_PRICE_AGENCY_ANNUAL) map[process.env.STRIPE_PRICE_AGENCY_ANNUAL] = 'agency';
  return map[priceId] || null;
}
