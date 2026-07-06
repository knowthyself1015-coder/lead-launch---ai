// ─── Content Generation Orchestrator ─────────────────────────────────────
//
// Calls all individual generators and assembles the complete content object.
// Supports batch generation and caching.

import type {
  BusinessContext,
  GeneratedContent,
  GenerationOptions,
} from "@/types/content";
import { generateHero } from "./generateHero";
import { generateServices } from "./generateServices";
import { generateAbout } from "./generateAbout";
import { generateFAQ } from "./generateFAQ";
import { generateSEO } from "./generateSEO";
import { createContentFingerprint } from "./helpers";

// ─── Single Business Generation ──────────────────────────────────────────

export interface GenerationResult {
  content: GeneratedContent;
  usage: {
    total_prompt_tokens: number;
    total_completion_tokens: number;
    total_tokens: number;
  };
  business: Pick<BusinessContext, "name" | "city" | "category">;
}

/**
 * Generate complete website content for a single business.
 * Calls all five generators and assembles them into one result.
 */
export async function generateBusinessContent(
  business: BusinessContext,
  options: GenerationOptions = {}
): Promise<GenerationResult> {
  const [hero, services, about, faq, seo] = await Promise.all([
    generateHero(business),
    generateServices(business),
    generateAbout(business),
    generateFAQ(business),
    generateSEO(business),
  ]);

  const usage = {
    total_prompt_tokens:
      hero.usage.prompt_tokens +
      services.usage.prompt_tokens +
      about.usage.prompt_tokens +
      faq.usage.prompt_tokens +
      seo.usage.prompt_tokens,
    total_completion_tokens:
      hero.usage.completion_tokens +
      services.usage.completion_tokens +
      about.usage.completion_tokens +
      faq.usage.completion_tokens +
      seo.usage.completion_tokens,
    total_tokens:
      hero.usage.total_tokens +
      services.usage.total_tokens +
      about.usage.total_tokens +
      faq.usage.total_tokens +
      seo.usage.total_tokens,
  };

  const content: GeneratedContent = {
    hero: hero.data,
    services: services.data,
    about: about.data,
    faq: faq.data,
    seo: seo.data,
    generated_at: new Date().toISOString(),
    model: options.model ?? "gpt-4o-mini",
    fingerprint: createContentFingerprint(business),
  };

  return {
    content,
    usage,
    business: {
      name: business.name,
      city: business.city,
      category: business.category,
    },
  };
}

// ─── Batch Generation ────────────────────────────────────────────────────

export interface BatchGenerationResult {
  results: GenerationResult[];
  total_usage: {
    total_prompt_tokens: number;
    total_completion_tokens: number;
    total_tokens: number;
  };
}

/**
 * Generate content for multiple businesses.
 * Processes them sequentially to respect rate limits.
 */
export async function generateBatchContent(
  businesses: BusinessContext[],
  options: GenerationOptions = {}
): Promise<BatchGenerationResult> {
  const results: GenerationResult[] = [];
  let totalPromptTokens = 0;
  let totalCompletionTokens = 0;
  let totalTokens = 0;

  for (const business of businesses) {
    const result = await generateBusinessContent(business, options);
    results.push(result);
    totalPromptTokens += result.usage.total_prompt_tokens;
    totalCompletionTokens += result.usage.total_completion_tokens;
    totalTokens += result.usage.total_tokens;
  }

  return {
    results,
    total_usage: {
      total_prompt_tokens: totalPromptTokens,
      total_completion_tokens: totalCompletionTokens,
      total_tokens: totalTokens,
    },
  };
}

// ─── Caching Helper ──────────────────────────────────────────────────────

/**
 * Generate a cache key for a business's content based on its fingerprint.
 * Use this to check if content already exists before calling OpenAI.
 */
export function getContentCacheKey(business: BusinessContext): string {
  return `content:${createContentFingerprint(business)}`;
}

/**
 * Check if two business contexts are similar enough to reuse content.
 * Returns true if name, category, and location match.
 */
export function isSameBusiness(
  a: Pick<BusinessContext, "name" | "category" | "city" | "state">,
  b: Pick<BusinessContext, "name" | "category" | "city" | "state">
): boolean {
  return (
    a.name.toLowerCase() === b.name.toLowerCase() &&
    a.category.toLowerCase() === b.category.toLowerCase() &&
    a.city.toLowerCase() === b.city.toLowerCase() &&
    a.state.toLowerCase() === b.state.toLowerCase()
  );
}