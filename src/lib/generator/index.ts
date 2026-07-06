// ─── Generator Barrel Exports ────────────────────────────────────────────

export { generateHero, buildHeroPrompt } from "./generateHero";
export { generateServices } from "./generateServices";
export { generateAbout } from "./generateAbout";
export { generateFAQ } from "./generateFAQ";
export { generateSEO } from "./generateSEO";
export {
  generateBusinessContent,
  generateBatchContent,
  getContentCacheKey,
  isSameBusiness,
} from "./generateContent";
export type { GenerationResult, BatchGenerationResult } from "./generateContent";
export {
  buildSystemPrompt,
  buildUserPrompt,
  buildLocalityContext,
  createContentFingerprint,
  getCategoryTone,
} from "./helpers";

// ─── Types ───────────────────────────────────────────────────────────────

export type {
  BusinessContext,
  GeneratedContent,
  GenerationOptions,
  HeroContent,
  ServicesContent,
  AboutContent,
  FAQContent,
  SEOContent,
  ServiceItem,
  FAQItem,
} from "@/types/content";