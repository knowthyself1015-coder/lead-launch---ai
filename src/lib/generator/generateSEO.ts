// ─── SEO Metadata Generator ──────────────────────────────────────────────

import type { BusinessContext, SEOContent } from "@/types/content";
import { jsonCompletion } from "@/lib/openai";
import { buildSystemPrompt, buildUserPrompt, getCategoryTone } from "./helpers";

const SYSTEM_PROMPT = `You are an expert local SEO strategist. Generate SEO metadata for a local business website.

Generate exactly:
- "seo_title": Page title tag — max 60 characters. Include business name, primary keyword, and city.
- "meta_description": Meta description — max 160 characters. Compelling summary with CTA and location.
- "keywords": Array of 5-10 local SEO keywords. Include the city name in most of them.
- "og_title": Open Graph title — max 60 characters. Slightly different from seo_title but similar keywords.
- "og_description": Open Graph description — max 160 characters. Optimized for social sharing.

Rules:
- Every keyword must be relevant to the specific business category and location.
- Mix short-tail ("plumber Austin") and long-tail ("emergency plumbing repair Austin TX") keywords.
- Do NOT repeat the same keyword with just word order changed.
- Titles and descriptions must be compelling for both search engines and humans.
- Include location (city, state) in title and meta description.
- Output valid JSON with keys: seo_title, meta_description, keywords, og_title, og_description.`;

export async function generateSEO(
  business: BusinessContext
): Promise<{ data: SEOContent; usage: any }> {
  const systemPrompt = SYSTEM_PROMPT + `\n\n${getCategoryTone(business.category)}`;

  const messages = [
    { role: "system" as const, content: systemPrompt },
    { role: "user" as const, content: buildUserPrompt(business) },
  ];

  const { data, usage } = await jsonCompletion<SEOContent>(messages, {
    temperature: 0.6,
    max_tokens: 500,
  });

  return { data, usage };
}