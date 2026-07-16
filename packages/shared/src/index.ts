import { z } from 'zod';

// ── User ──
export const UserTier = z.enum(['free', 'creator', 'pro', 'agency']);
export type UserTier = z.infer<typeof UserTier>;

// ── Subscription tiers ──

export interface TierConfig {
  name: string;
  priceMonthly: number;
  priceAnnual: number;
  monthlyPriceId: string;   // Stripe Price ID (set in env or dashboard)
  annualPriceId: string;    // Stripe Price ID (set in env or dashboard)
  generationLimit: number;
  features: string[];
  highlighted?: boolean;
}

export const TIER_CONFIGS: Record<UserTier, TierConfig> = {
  free: {
    name: 'Free',
    priceMonthly: 0,
    priceAnnual: 0,
    monthlyPriceId: '',
    annualPriceId: '',
    generationLimit: 5,
    features: [
      '5 content generations per month',
      'Basic AI Writer',
      'Watermarked exports',
      'Standard Amazon Associates integration',
    ],
  },
  creator: {
    name: 'Creator',
    priceMonthly: 19,
    priceAnnual: 190,
    monthlyPriceId: '',
    annualPriceId: '',
    generationLimit: -1, // unlimited
    features: [
      'Unlimited content generations',
      'HD exports',
      'AI Thumbnail Generator',
      'Full AI Writer suite (scripts, captions, SEO)',
      'Watermark-free exports',
      'Priority support',
    ],
    highlighted: true,
  },
  pro: {
    name: 'Pro',
    priceMonthly: 49,
    priceAnnual: 490,
    monthlyPriceId: '',
    annualPriceId: '',
    generationLimit: -1, // unlimited
    features: [
      'Everything in Creator',
      'Multiple tracking IDs',
      'Team collaboration',
      'Brand kit (logos, fonts, colors)',
      'Advanced analytics',
      'Content calendar',
      'Bulk generation',
      'Priority support',
    ],
  },
  agency: {
    name: 'Agency',
    priceMonthly: 149,
    priceAnnual: 1490,
    monthlyPriceId: '',
    annualPriceId: '',
    generationLimit: -1, // unlimited
    features: [
      'Everything in Pro',
      'Unlimited workspaces',
      'Client management',
      'White-label exports',
      'API access',
      'Dedicated account manager',
      'Custom integrations',
      'SLA guarantee',
    ],
  },
};

// ── Product ──
export const ProductInput = z.object({
  asin: z.string().min(10).max(10),
  title: z.string().min(1),
  description: z.string().optional(),
  imageUrl: z.string().url().optional(),
  price: z.string().optional(),
  category: z.string().optional(),
  url: z.string().url().optional(),
});
export type ProductInput = z.infer<typeof ProductInput>;

// ── Generation ──
export const GenerationType = z.enum(['script', 'thumbnail', 'video', 'caption', 'social_post']);
export type GenerationType = z.infer<typeof GenerationType>;

export const GenerationPlatform = z.enum([
  'youtube',
  'tiktok',
  'instagram',
  'pinterest',
  'blog',
]);
export type GenerationPlatform = z.infer<typeof GenerationPlatform>;

export const GenerationStatus = z.enum(['pending', 'processing', 'completed', 'failed']);
export type GenerationStatus = z.infer<typeof GenerationStatus>;

export const GenerationRequest = z.object({
  type: GenerationType,
  platform: GenerationPlatform.optional(),
  productAsin: z.string().min(10).max(10),
  affiliateTag: z.string().optional(),
});
export type GenerationRequest = z.infer<typeof GenerationRequest>;

// ── API ──
export const ApiResponse = <T extends z.ZodTypeAny>(dataSchema: T) =>
  z.object({
    success: z.boolean(),
    data: dataSchema.optional(),
    error: z.string().optional(),
  });

export const PaginatedResponse = <T extends z.ZodTypeAny>(dataSchema: T) =>
  z.object({
    success: z.boolean(),
    data: z.array(dataSchema),
    total: z.number(),
    page: z.number(),
    pageSize: z.number(),
  });

// ── Rate Limiting ──

/**
 * Check whether a user can make another generation based on their tier limit.
 * Returns { allowed: boolean, limit: number, used: number, remaining: number }
 */
export function checkGenerationLimit(
  tier: UserTier,
  usedThisMonth: number,
): { allowed: boolean; limit: number; used: number; remaining: number } {
  const config = TIER_CONFIGS[tier] || TIER_CONFIGS.free;
  const limit = config.generationLimit;
  // -1 means unlimited
  if (limit === -1) {
    return { allowed: true, limit: -1, used: usedThisMonth, remaining: -1 };
  }
  const remaining = Math.max(0, limit - usedThisMonth);
  return {
    allowed: usedThisMonth < limit,
    limit,
    used: usedThisMonth,
    remaining,
  };
}
