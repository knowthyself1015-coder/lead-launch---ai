// ─── Hero Section Generator ──────────────────────────────────────────────

import type { BusinessContext, HeroContent } from "@/types/content";
import { jsonCompletion } from "@/lib/openai";
import {
  buildSystemPrompt,
  buildUserPrompt,
  getCategoryTone,
} from "./helpers";

const SYSTEM_PROMPT_TEMPLATE = `You are an expert local SEO copywriter. Generate hero section content for a local business website.

${getCategoryTone("{category}")}

Generate exactly:
- "headlines": array of exactly 3 compelling headline variations. Each should be under 12 words, benefit-driven, and locally relevant.
- "subheadline": one concise sentence (under 20 words) that expands on the headline and includes the city name.
- "cta_text": a short call-to-action button text (2-4 words, action-oriented like "Get a Free Quote" or "Book Now").

Rules:
- Each headline variation must be truly different in angle, not just word-swapped.
- Include the business location (city, state) naturally.
- Match the tone to the business category.
- Output valid JSON with keys: headlines, subheadline, cta_text.`;

export async function generateHero(
  business: BusinessContext
): Promise<{ data: HeroContent; usage: any }> {
  const systemPrompt = SYSTEM_PROMPT_TEMPLATE.replace(
    "{category}",
    business.category
  );

  const messages = [
    { role: "system" as const, content: systemPrompt },
    { role: "user" as const, content: buildUserPrompt(business) },
  ];

  const { data, usage } = await jsonCompletion<HeroContent>(messages, {
    temperature: 0.9, // Higher temp for creative headline variety
    max_tokens: 500,
  });

  return { data, usage };
}

/**
 * Generate a single hero headline (lightweight, no JSON parse).
 */
export function buildHeroPrompt(business: BusinessContext): {
  system: string;
  user: string;
} {
  return {
    system: SYSTEM_PROMPT_TEMPLATE.replace("{category}", business.category),
    user: buildUserPrompt(business),
  };
}