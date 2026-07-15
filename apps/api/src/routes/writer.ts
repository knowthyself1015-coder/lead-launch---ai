import { Router, Request, Response } from "express";
import { generateContent, AIWriterError } from "../services/ai-writer";
import type { WriterRequest, WriterResponse } from "../services/ai-writer";
import type { ContentType } from "../services/prompt-templates";
import { CONTENT_TYPES_LIST } from "../services/prompt-templates";

const router = Router();

// ── Validation ─────────────────────────────────────────────

const VALID_CONTENT_TYPES = CONTENT_TYPES_LIST.map((ct) => ct.id);

function validateRequest(body: any): WriterRequest {
  const errors: string[] = [];

  if (!body.contentType || !VALID_CONTENT_TYPES.includes(body.contentType)) {
    errors.push(`contentType must be one of: ${VALID_CONTENT_TYPES.join(", ")}`);
  }
  if (!body.productTitle || typeof body.productTitle !== "string" || body.productTitle.trim().length === 0) {
    errors.push("productTitle is required");
  }
  if (!body.affiliateLink || typeof body.affiliateLink !== "string" || body.affiliateLink.trim().length === 0) {
    errors.push("affiliateLink is required");
  }

  if (errors.length > 0) {
    throw new AIWriterError(`Validation failed: ${errors.join("; ")}`, "VALIDATION_ERROR", 400, false);
  }

  return {
    contentType: body.contentType as ContentType,
    productTitle: body.productTitle.trim(),
    productDescription: body.productDescription?.trim(),
    productFeatures: Array.isArray(body.productFeatures) ? body.productFeatures : [],
    affiliateLink: body.affiliateLink.trim(),
    tone: body.tone,
    additionalInstructions: body.additionalInstructions?.trim(),
    userId: body.userId,
    productAsin: body.productAsin,
  };
}

// ── POST /api/writer/generate ──────────────────────────────

router.post("/generate", async (req: Request, res: Response) => {
  const startTime = Date.now();

  try {
    const writerReq = validateRequest(req.body);
    const result: WriterResponse = await generateContent(writerReq);

    // Try to persist to database (fire-and-forget, don't block response)
    try {
      const { prisma } = await import("@affiliate/db");
      await prisma.generation.create({
        data: {
          type: "script",
          status: "completed",
          platform: writerReq.contentType,
          inputData: {
            productTitle: writerReq.productTitle,
            productFeatures: writerReq.productFeatures,
            contentType: writerReq.contentType,
          } as any,
          outputData: {
            script: result.script,
            estimatedDuration: result.estimatedDuration,
            hashtags: result.hashtags,
            seoKeywords: result.seoKeywords,
          } as any,
          userId: writerReq.userId ?? "anonymous",
          productId: undefined, // Link to product when we have product lookup
        },
      });
    } catch (dbError: any) {
      // DB may not be connected — log but don't fail the request
      console.warn("Failed to persist generation to database:", dbError.message);
    }

    const elapsed = Date.now() - startTime;

    return res.json({
      success: true,
      data: {
        ...result,
        metadata: {
          ...result.metadata,
          latencyMs: elapsed,
        },
      },
    });
  } catch (error: any) {
    const elapsed = Date.now() - startTime;

    if (error instanceof AIWriterError) {
      return res.status(error.statusCode).json({
        success: false,
        error: error.message,
        code: error.code,
        retryable: error.retryable,
        latencyMs: elapsed,
      });
    }

    // Unexpected error
    console.error("AI Writer unexpected error:", error);
    return res.status(500).json({
      success: false,
      error: "Internal server error during content generation",
      code: "INTERNAL_ERROR",
      retryable: true,
      latencyMs: elapsed,
    });
  }
});

// ── GET /api/writer/content-types ──────────────────────────

router.get("/content-types", (_req: Request, res: Response) => {
  return res.json({
    success: true,
    data: CONTENT_TYPES_LIST,
  });
});

// ── Health ─────────────────────────────────────────────────

router.get("/health", (_req: Request, res: Response) => {
  return res.json({
    success: true,
    data: {
      status: "ok",
      openaiConfigured: !!process.env.OPENAI_API_KEY,
      model: "gpt-4o-mini",
    },
  });
});

export default router;
