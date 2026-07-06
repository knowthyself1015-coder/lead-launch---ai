// ─── Prompt Templates & Generator Helpers ─────────────────────────────────

import type { BusinessContext } from "@/types/content";

/**
 * Build a system prompt that instructs the AI to produce unique,
 * locally-relevant content for a local business microsite.
 */
export function buildSystemPrompt(
  task: string,
  format: "text" | "json" = "json"
): string {
  const jsonInstruction =
    format === "json"
      ? "\n\nReturn your response as valid JSON only — no markdown, no extra text."
      : "";

  return `You are an expert local SEO copywriter and content strategist. Your specialty is writing compelling, unique website content for small local businesses that builds trust and drives phone calls and form submissions.

## Core Rules
1. **Never plagiarize** — each piece of content must be original and tailored to the specific business.
2. **Be locally specific** — reference the city, local landmarks, neighborhoods, and community where relevant.
3. **Vary sentence structure and angle** — do not use the same opening pattern across businesses.
4. **Match the category's tone** — a plumber should sound trustworthy and straightforward; a dentist should sound caring and professional; a restaurant should sound warm and appetizing.
5. **Keep it concise** — web content should be scannable. Short paragraphs, clear headings.
6. **Professional but approachable** — write like a knowledgeable local, not a corporate brochure.
7. **Include keywords naturally** — integrate local SEO terms without keyword stuffing.
8. **Output valid JSON only** — follow the requested schema precisely.${jsonInstruction}

${task}`;
}

/**
 * Build a user prompt with full business context.
 */
export function buildUserPrompt(business: BusinessContext): string {
  return [
    `Generate content for the following local business:`,
    ``,
    `Business Name: ${business.name}`,
    `Category: ${business.category}`,
    `Location: ${business.city}, ${business.state}`,
    business.description ? `Description: ${business.description}` : null,
    business.services?.length
      ? `Services: ${business.services.join(", ")}`
      : null,
    business.reviews_summary
      ? `Customer Reviews Summary: ${business.reviews_summary}`
      : null,
    business.rating ? `Rating: ${business.rating}/5 (${business.review_count ?? 0} reviews)` : null,
    ``,
    `IMPORTANT: Make the content specific to ${business.city}, ${business.state}. Mention local context. Do NOT use generic filler.`,
  ]
    .filter(Boolean)
    .join("\n");
}

/**
 * Build a locality context string for richer prompts.
 */
export function buildLocalityContext(business: Pick<BusinessContext, "city" | "state">): string {
  return `The business is located in ${business.city}, ${business.state}. Reference this location naturally throughout the content.`;
}

/**
 * Create a simple content fingerprint from business context to ensure uniqueness.
 */
export function createContentFingerprint(business: BusinessContext): string {
  const raw = [
    business.name.toLowerCase().trim(),
    business.category.toLowerCase().trim(),
    business.city.toLowerCase().trim(),
    business.state.toLowerCase().trim(),
    business.services?.slice(0, 3).map((s) => s.toLowerCase().trim()).join(",") ?? "",
  ].join("|");

  // Simple hash
  let hash = 0;
  for (let i = 0; i < raw.length; i++) {
    const char = raw.charCodeAt(i);
    hash = (hash << 5) - hash + char;
    hash |= 0; // Convert to 32bit integer
  }
  return `fp_${Math.abs(hash).toString(16)}`;
}

/**
 * Category-specific tone guidance for system prompts.
 */
export function getCategoryTone(category: string): string {
  const tones: Record<string, string> = {
    plumber: "Trustworthy, reliable, emergency-ready. Emphasize fast response and quality workmanship.",
    electrician: "Safety-focused, licensed, professional. Highlight expertise and code compliance.",
    dentist: "Gentle, caring, modern. Focus on patient comfort and advanced technology.",
    landscaper: "Creative, dependable, transformative. Emphasize curb appeal and seasonal services.",
    restaurant: "Warm, inviting, flavorful. Make the reader hungry. Mention atmosphere and specialties.",
    "auto mechanic": "Honest, skilled, transparent. Build trust through expertise and fair pricing.",
    roofer: "Durable, protective, experienced. Stress quality materials and workmanship guarantees.",
    cleaner: "Thorough, reliable, trusted. Emphasize consistency and attention to detail.",
    "real estate agent": "Knowledgeable, local, results-driven. Highlight market expertise and community ties.",
    "personal trainer": "Motivating, knowledgeable, supportive. Focus on transformation and personalized plans.",
    photographer: "Artistic, professional, storyteller. Emphasize capturing moments and quality.",
    lawyer: "Experienced, strategic, client-focused. Build confidence through expertise and results.",
    accountant: "Trustworthy, detail-oriented, proactive. Emphasize accuracy and tax knowledge.",
    "pet groomer": "Gentle, caring, skilled. Highlight love for animals and quality grooming.",
    "massage therapist": "Healing, relaxing, professional. Focus on wellness and therapeutic benefits.",
  };

  const key = category.toLowerCase().trim();
  return tones[key] ?? "Professional, local, trustworthy. Speak directly to the customer's needs.";
}