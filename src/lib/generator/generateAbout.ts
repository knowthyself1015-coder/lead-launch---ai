// ─── About Section Generator ─────────────────────────────────────────────

import type { BusinessContext, AboutContent } from "@/types/content";
import { jsonCompletion } from "@/lib/openai";
import { buildSystemPrompt, buildUserPrompt, getCategoryTone } from "./helpers";

const SYSTEM_PROMPT = `You are an expert local SEO copywriter. Generate the "About Us" section for a local business website.

Generate exactly:
- "about_paragraph": 2-3 sentences introducing the business, its expertise, and its commitment to the local community. Include the city name.
- "history": 1-2 sentences about the business background (how it started, years in operation, etc.). Keep it authentic-sounding.
- "mission_statement": One clear, memorable sentence about the business's purpose and values.
- "values": Array of 3-5 core values (each 1-3 words) that the business stands for.

Rules:
- Never claim specific years in business unless provided in the business context.
- Sound authentic, not corporate — like a real local business owner wrote it.
- Include location naturally.
- Vary the structure — not every business "was founded" the same way.
- Output valid JSON with keys: about_paragraph, history, mission_statement, values.`;

export async function generateAbout(
  business: BusinessContext
): Promise<{ data: AboutContent; usage: any }> {
  const systemPrompt = SYSTEM_PROMPT + `\n\n${getCategoryTone(business.category)}
  
IMPORTANT: Do NOT fabricate specific dates, years, or names. If the business context doesn't include history details, write generally about their experience.`;

  const messages = [
    { role: "system" as const, content: systemPrompt },
    { role: "user" as const, content: buildUserPrompt(business) },
  ];

  const { data, usage } = await jsonCompletion<AboutContent>(messages, {
    temperature: 0.8,
    max_tokens: 600,
  });

  return { data, usage };
}