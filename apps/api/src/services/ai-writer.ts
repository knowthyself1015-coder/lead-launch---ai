import OpenAI from "openai";
import type { ContentType } from "./prompt-templates";
import { getTemplate } from "./prompt-templates";

// ── Types ──────────────────────────────────────────────────

export interface WriterRequest {
  contentType: ContentType;
  productTitle: string;
  productDescription?: string;
  productFeatures: string[];
  affiliateLink: string;
  tone?: string;
  additionalInstructions?: string;
  userId?: string;
  productAsin?: string;
}

export interface WriterResponse {
  script: string;
  estimatedDuration: number;
  hashtags: string[];
  seoKeywords: string[];
  metadata: {
    contentType: ContentType;
    platform: string;
    model: string;
    tokensUsed: number;
    generatedAt: string;
  };
}

// ── Retry / Error handling ─────────────────────────────────

class AIWriterError extends Error {
  constructor(
    message: string,
    public code: "API_KEY_MISSING" | "RATE_LIMITED" | "API_ERROR" | "PARSE_ERROR" | "VALIDATION_ERROR",
    public statusCode: number = 500,
    public retryable: boolean = false
  ) {
    super(message);
    this.name = "AIWriterError";
  }
}

async function retryWithBackoff<T>(
  fn: () => Promise<T>,
  maxRetries: number = 3,
  baseDelayMs: number = 1000
): Promise<T> {
  let lastError: Error | undefined;

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      return await fn();
    } catch (error: any) {
      lastError = error;

      // Don't retry on certain errors
      if (error instanceof AIWriterError && !error.retryable) {
        throw error;
      }

      // Check for rate limit (HTTP 429)
      if (error?.status === 429 || error?.message?.includes("rate_limit")) {
        if (attempt < maxRetries) {
          const delay = baseDelayMs * Math.pow(2, attempt) + Math.random() * 1000;
          console.warn(`Rate limited. Retrying in ${Math.round(delay)}ms (attempt ${attempt + 1}/${maxRetries})`);
          await new Promise((resolve) => setTimeout(resolve, delay));
          continue;
        }
        throw new AIWriterError("Rate limit exceeded after retries", "RATE_LIMITED", 429, true);
      }

      // Don't retry auth errors
      if (error?.status === 401 || error?.status === 403) {
        throw new AIWriterError("Invalid API key or unauthorized", "API_ERROR", error.status, false);
      }

      // Retry on server errors (5xx)
      if (error?.status >= 500 && attempt < maxRetries) {
        const delay = baseDelayMs * Math.pow(2, attempt);
        console.warn(`Server error ${error.status}. Retrying in ${delay}ms (attempt ${attempt + 1}/${maxRetries})`);
        await new Promise((resolve) => setTimeout(resolve, delay));
        continue;
      }

      if (attempt >= maxRetries) break;
    }
  }

  throw new AIWriterError(
    `AI generation failed after ${maxRetries} retries: ${(lastError as Error)?.message}`,
    "API_ERROR",
    502,
    true
  );
}

// ── System prompt builder ──────────────────────────────────

function buildSystemPrompt(req: WriterRequest): string {
  const template = getTemplate(req.contentType);
  const tone = req.tone ?? "enthusiastic and professional";

  let prompt = template.systemPrompt;

  // Replace template variables
  prompt = prompt.replace(/\{\{AFFILIATE_LINK\}\}/g, req.affiliateLink);

  // Add product-specific context
  const productContext = [
    ``,
    `PRODUCT TO PROMOTE:`,
    `Title: ${req.productTitle}`,
    req.productDescription ? `Description: ${req.productDescription}` : "",
    `Key Features: ${req.productFeatures.join(", ")}`,
    `Affiliate Link: ${req.affiliateLink}`,
    ``,
    `TONE: ${tone}`,
    req.additionalInstructions ? `ADDITIONAL INSTRUCTIONS: ${req.additionalInstructions}` : "",
  ]
    .filter(Boolean)
    .join("\n");

  return `${prompt}\n${productContext}`;
}

function buildUserMessage(req: WriterRequest): string {
  const template = getTemplate(req.contentType);
  const features = req.productFeatures.length > 0
    ? req.productFeatures.slice(0, 5).join(", ")
    : "high quality, great value";

  return `Write a ${template.label} for: ${req.productTitle}. Key features: ${features}.`;
}

// ── JSON extraction ────────────────────────────────────────

function extractJson(text: string): string {
  // Try to find JSON in the response
  const jsonMatch = text.match(/\{[\s\S]*\}/);
  if (jsonMatch) return jsonMatch[0];

  // If the text looks like it has JSON inside markdown fences
  const fenceMatch = text.match(/```(?:json)?\s*(\{[\s\S]*?\})\s*```/);
  if (fenceMatch) return fenceMatch[1];

  return text;
}

function parseResponse(text: string, contentType: ContentType): Pick<WriterResponse, "script" | "estimatedDuration" | "hashtags" | "seoKeywords"> {
  const jsonStr = extractJson(text);
  let parsed: any;

  try {
    parsed = JSON.parse(jsonStr);
  } catch {
    // If JSON parsing fails, try to salvage: treat the raw text as the script
    return {
      script: text,
      estimatedDuration: Math.ceil(text.split(/\s+/).length / 2.5), // ~150 wpm speaking pace
      hashtags: [],
      seoKeywords: [],
    };
  }

  return {
    script: typeof parsed.script === "string" ? parsed.script : JSON.stringify(parsed),
    estimatedDuration: typeof parsed.estimatedDuration === "number" ? parsed.estimatedDuration : 300,
    hashtags: Array.isArray(parsed.hashtags) ? parsed.hashtags.slice(0, 10) : [],
    seoKeywords: Array.isArray(parsed.seoKeywords) ? parsed.seoKeywords.slice(0, 10) : [],
  };
}

// ── Main generation function ───────────────────────────────

export async function generateContent(req: WriterRequest): Promise<WriterResponse> {
  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) {
    throw new AIWriterError("OPENAI_API_KEY environment variable is not set", "API_KEY_MISSING", 500, false);
  }

  const openai = new OpenAI({ apiKey });
  const template = getTemplate(req.contentType);
  const model = "gpt-4o-mini";

  const systemPrompt = buildSystemPrompt(req);
  const userMessage = buildUserMessage(req);

  const result = await retryWithBackoff(async () => {
    const response = await openai.chat.completions.create({
      model,
      temperature: 0.8,
      max_tokens: template.maxTokens,
      response_format: { type: "json_object" },
      messages: [
        { role: "system", content: systemPrompt },
        { role: "user", content: userMessage },
      ],
    });

    const rawText = response.choices[0]?.message?.content ?? "";
    const tokensUsed = response.usage?.total_tokens ?? 0;

    const parsed = parseResponse(rawText, req.contentType);

    return {
      ...parsed,
      metadata: {
        contentType: req.contentType,
        platform: template.platform,
        model,
        tokensUsed,
        generatedAt: new Date().toISOString(),
      },
    } as WriterResponse;
  });

  return result;
}

export { AIWriterError };
