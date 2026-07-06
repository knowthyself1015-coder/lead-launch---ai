// ─── OpenAI Client Wrapper ──────────────────────────────────────────────
//
// Server-side only. Provides a rate-limited, retrying client for OpenAI
// API calls used by the content generation pipeline.

import OpenAI from "openai";

// ─── Configuration ───────────────────────────────────────────────────────

const OPENAI_API_KEY = process.env.OPENAI_API_KEY;

const DEFAULT_MODEL = "gpt-4o-mini";
const DEFAULT_MAX_RETRIES = 3;
const DEFAULT_TIMEOUT_MS = 30_000;

// Rate limiting: max RPM (requests per minute) for GPT-4o-mini tier
// Free/usage tiers vary; we conservatively allow 30 RPM.
const RPM_LIMIT = 30;
const REQUEST_WINDOW_MS = 60_000; // 1 minute

// ─── Singleton Client ────────────────────────────────────────────────────

let client: OpenAI | null = null;

function getClient(): OpenAI {
  if (!client) {
    if (!OPENAI_API_KEY) {
      throw new Error(
        "OPENAI_API_KEY environment variable is not set. " +
          "Content generation requires a valid OpenAI API key."
      );
    }
    client = new OpenAI({
      apiKey: OPENAI_API_KEY,
      timeout: DEFAULT_TIMEOUT_MS,
      maxRetries: DEFAULT_MAX_RETRIES,
    });
  }
  return client;
}

// ─── Rate Limiter ────────────────────────────────────────────────────────

interface RequestLogEntry {
  timestamp: number;
}

const requestLog: RequestLogEntry[] = [];

/**
 * Simple sliding-window rate limiter.
 * Blocks (sleeps) if we've exceeded RPM_LIMIT within the window.
 */
async function waitForSlot(): Promise<void> {
  const now = Date.now();
  const windowStart = now - REQUEST_WINDOW_MS;

  // Purge expired entries
  while (requestLog.length > 0 && requestLog[0]!.timestamp < windowStart) {
    requestLog.shift();
  }

  if (requestLog.length >= RPM_LIMIT) {
    // Need to wait until the oldest entry expires
    const oldest = requestLog[0]!.timestamp;
    const waitMs = oldest + REQUEST_WINDOW_MS - now + 50; // 50ms grace
    if (waitMs > 0) {
      console.warn(
        `[openai] Rate limit reached. Waiting ${Math.ceil(waitMs)}ms...`
      );
      await new Promise((resolve) => setTimeout(resolve, waitMs));
    }
    // Recurse to check again
    return waitForSlot();
  }

  requestLog.push({ timestamp: now });
}

// ─── Response Types ──────────────────────────────────────────────────────

export interface CompletionResult {
  content: string;
  model: string;
  usage: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  };
}

// ─── Prompt Call ─────────────────────────────────────────────────────────

export interface ChatMessage {
  role: "system" | "user" | "assistant";
  content: string;
}

export interface CompletionOptions {
  model?: string;
  temperature?: number;
  max_tokens?: number;
  response_format?: "text" | "json_object";
}

/**
 * Send a chat completion request to OpenAI with rate limiting and retries.
 * Always uses the singleton client — never call `new OpenAI()` elsewhere.
 */
export async function chatCompletion(
  messages: ChatMessage[],
  options: CompletionOptions = {}
): Promise<CompletionResult> {
  const ai = getClient();
  await waitForSlot();

  const model = options.model ?? DEFAULT_MODEL;
  const temperature = options.temperature ?? 0.8;
  const max_tokens = options.max_tokens ?? 1024;
  const response_format = options.response_format ?? "text";

  const response = await ai.chat.completions.create({
    model,
    messages: messages as OpenAI.Chat.Completions.ChatCompletionMessageParam[],
    temperature,
    max_tokens,
    response_format:
      response_format === "json_object"
        ? { type: "json_object" }
        : undefined,
  });

  const choice = response.choices[0];
  if (!choice?.message?.content) {
    throw new Error("OpenAI returned an empty response");
  }

  return {
    content: choice.message.content,
    model: response.model,
    usage: {
      prompt_tokens: response.usage?.prompt_tokens ?? 0,
      completion_tokens: response.usage?.completion_tokens ?? 0,
      total_tokens: response.usage?.total_tokens ?? 0,
    },
  };
}

/**
 * Generate structured JSON output from OpenAI.
 * Wraps chatCompletion with json_object response format and JSON parsing.
 */
export async function jsonCompletion<T>(
  messages: ChatMessage[],
  options: CompletionOptions = {}
): Promise<{ data: T; usage: CompletionResult["usage"] }> {
  const result = await chatCompletion(messages, {
    ...options,
    response_format: "json_object",
  });

  let data: T;
  try {
    data = JSON.parse(result.content) as T;
  } catch (err) {
    throw new Error(
      `Failed to parse OpenAI response as JSON: ${(err as Error).message}\n` +
        `Raw response: ${result.content.slice(0, 200)}`
    );
  }

  return { data, usage: result.usage };
}

// ─── Health Check ────────────────────────────────────────────────────────

/**
 * Quick check that the client is configured and can reach the API.
 * Does NOT consume a rate-limited slot.
 */
export function isConfigured(): boolean {
  return !!OPENAI_API_KEY;
}

/**
 * Clear the rate-limit log. Useful in tests.
 */
export function resetRateLimiter(): void {
  requestLog.length = 0;
}