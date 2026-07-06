// ─── Services Section Generator ──────────────────────────────────────────

import type { BusinessContext, ServicesContent } from "@/types/content";
import { jsonCompletion } from "@/lib/openai";
import { buildSystemPrompt, buildUserPrompt, getCategoryTone } from "./helpers";

const SYSTEM_PROMPT = `You are an expert local SEO copywriter. Generate the services section for a local business website.

Each service should have:
- "name": A clear, benefit-driven service name (2-5 words).
- "description": 1-2 sentences explaining what the service includes, why it matters, and any local relevance.
- "category" (optional): A grouping label if services fall into clear categories (e.g., "Residential", "Commercial").

Also include:
- "heading": A section heading (3-7 words) like "What We Offer" or "Our Services".
- "services": Array of 4-8 service objects.

Rules:
- Services must be specific to the business category and location.
- Descriptions should be scannable and benefit-focused.
- Use natural local SEO keywords.
- Output valid JSON with keys: heading, services.`;

export async function generateServices(
  business: BusinessContext
): Promise<{ data: ServicesContent; usage: any }> {
  const systemPrompt = SYSTEM_PROMPT + `\n\n${getCategoryTone(business.category)}`;

  const messages = [
    { role: "system" as const, content: systemPrompt },
    { role: "user" as const, content: buildUserPrompt(business) },
  ];

  const { data, usage } = await jsonCompletion<ServicesContent>(messages, {
    temperature: 0.7,
    max_tokens: 800,
  });

  return { data, usage };
}