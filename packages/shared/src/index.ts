import { z } from 'zod';

// ── User ──
export const UserTier = z.enum(['free', 'creator', 'pro', 'agency']);
export type UserTier = z.infer<typeof UserTier>;

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
