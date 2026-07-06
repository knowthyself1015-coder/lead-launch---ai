// ─── FAQ Section Generator ───────────────────────────────────────────────

import type { BusinessContext, FAQContent } from "@/types/content";
import { jsonCompletion } from "@/lib/openai";
import { buildSystemPrompt, buildUserPrompt, getCategoryTone } from "./helpers";

const SYSTEM_PROMPT = `You are an expert local SEO copywriter. Generate FAQ content for a local business website.

Generate exactly:
- "heading": A section heading like "Frequently Asked Questions" or "Common Questions".
- "faqs": Array of 5-8 FAQ objects, each with:
  - "question": A real question customers might ask (5-15 words).
  - "answer": A clear, helpful answer (1-3 sentences).

Rules:
- Questions must be realistic and commonly asked for this business category.
- Include 1-2 locally-relevant questions (e.g., "Do you service [neighborhood/city area]?").
- Answers should be concise and build trust.
- Cover practical topics: pricing approach, availability, service area, guarantees, etc.
- Do NOT use legal/financial advice language unless appropriate for the category.
- Output valid JSON with keys: heading, faqs.`;

export async function generateFAQ(
  business: BusinessContext
): Promise<{ data: FAQContent; usage: any }> {
  const systemPrompt = SYSTEM_PROMPT + `\n\n${getCategoryTone(business.category)}`;

  const messages = [
    { role: "system" as const, content: systemPrompt },
    { role: "user" as const, content: buildUserPrompt(business) },
  ];

  const { data, usage } = await jsonCompletion<FAQContent>(messages, {
    temperature: 0.7,
    max_tokens: 1000,
  });

  return { data, usage };
}