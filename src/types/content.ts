// ─── Content Generation Types ────────────────────────────────────────────

/** Context about a local business used for content generation */
export interface BusinessContext {
  name: string;
  category: string;
  city: string;
  state: string;
  description?: string;
  services?: string[];
  reviews_summary?: string;
  rating?: number;
  review_count?: number;
  phone?: string;
  address?: string;
  zip?: string;
  hours?: Record<string, string>;
  source?: string;
}

/** Hero section content */
export interface HeroContent {
  headlines: string[];        // 3 variations
  subheadline: string;
  cta_text: string;
}

/** A single service offering */
export interface ServiceItem {
  name: string;
  description: string;
  category?: string;
}

/** Services section content */
export interface ServicesContent {
  services: ServiceItem[];
  heading: string;
}

/** About section content */
export interface AboutContent {
  about_paragraph: string;
  history?: string;
  mission_statement: string;
  values?: string[];
}

/** A single FAQ item */
export interface FAQItem {
  question: string;
  answer: string;
}

/** FAQ section content */
export interface FAQContent {
  faqs: FAQItem[];
  heading: string;
}

/** SEO metadata */
export interface SEOContent {
  seo_title: string;              // ≤60 chars
  meta_description: string;       // ≤160 chars
  keywords: string[];             // 5-10 local SEO keywords
  og_title: string;
  og_description: string;
}

/** Complete generated content for a business */
export interface GeneratedContent {
  hero: HeroContent;
  services: ServicesContent;
  about: AboutContent;
  faq: FAQContent;
  seo: SEOContent;
  generated_at: string;
  model: string;
  fingerprint: string;  // uniqueness fingerprint (hash of business context + timestamp)
}

/** Options passed to the content generator */
export interface GenerationOptions {
  model?: string;          // default: "gpt-4o-mini"
  temperature?: number;    // default: 0.8
  max_retries?: number;    // default: 3
  locale?: string;         // default: "en-US"
}