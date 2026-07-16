import { Router, Request, Response } from "express";
import { importProduct, searchProducts, extractAsin, AmazonProductError } from "../services/amazon-product";

const router = Router();

// ── POST /api/products/import ──────────────────────────────
// Accepts: { input: string, associateTag?: string }
// Input can be Amazon URL, ASIN, or product name

router.post("/import", async (req: Request, res: Response) => {
  const startTime = Date.now();

  try {
    const { input, associateTag } = req.body;

    if (!input || typeof input !== "string" || input.trim().length === 0) {
      return res.status(400).json({
        success: false,
        error: "input is required (Amazon URL, ASIN, or product name)",
        code: "VALIDATION_ERROR",
      });
    }

    const product = await importProduct(input.trim(), associateTag);

    // Persist to database
    try {
      const { prisma } = await import("@affiliate/db");
      await prisma.product.upsert({
        where: { asin: product.asin },
        update: {
          title: product.title,
          description: product.description,
          imageUrl: product.imageUrl,
          price: product.price,
          category: product.category,
          url: product.affiliateUrl,
        },
        create: {
          asin: product.asin,
          title: product.title,
          description: product.description,
          imageUrl: product.imageUrl,
          price: product.price,
          category: product.category,
          url: product.affiliateUrl,
        },
      });
    } catch (dbError: any) {
      console.warn("Failed to persist product to database:", dbError.message);
    }

    return res.json({
      success: true,
      data: {
        ...product,
      },
      meta: {
        latencyMs: Date.now() - startTime,
      },
    });
  } catch (error: any) {
    if (error instanceof AmazonProductError) {
      return res.status(error.statusCode).json({
        success: false,
        error: error.message,
        code: error.code,
      });
    }

    console.error("Product import error:", error);
    return res.status(500).json({
      success: false,
      error: "Internal server error during product import",
      code: "INTERNAL_ERROR",
    });
  }
});

// ── POST /api/products/search ──────────────────────────────
// Accepts: { keyword: string, maxResults?: number }

router.post("/search", async (req: Request, res: Response) => {
  try {
    const { keyword, maxResults } = req.body;

    if (!keyword || typeof keyword !== "string" || keyword.trim().length === 0) {
      return res.status(400).json({
        success: false,
        error: "keyword is required",
      });
    }

    const products = await searchProducts(keyword.trim(), req.body.associateTag, maxResults || 5);

    return res.json({
      success: true,
      data: products,
      meta: {
        total: products.length,
      },
    });
  } catch (error: any) {
    if (error instanceof AmazonProductError) {
      return res.status(error.statusCode).json({
        success: false,
        error: error.message,
        code: error.code,
      });
    }

    console.error("Product search error:", error);
    return res.status(500).json({
      success: false,
      error: "Internal server error during product search",
      code: "INTERNAL_ERROR",
    });
  }
});

// ── GET /api/products ──────────────────────────────────────
// List products from database

router.get("/", async (_req: Request, res: Response) => {
  try {
    const { prisma } = await import("@affiliate/db");
    const products = await prisma.product.findMany({
      orderBy: { createdAt: "desc" },
      take: 50,
      include: {
        _count: {
          select: { generations: true },
        },
      },
    });

    return res.json({
      success: true,
      data: products.map((p) => ({
        ...p,
        createdAt: String(p.createdAt),
        updatedAt: String(p.updatedAt),
        generationCount: (p as any)._count?.generations ?? 0,
      })),
    });
  } catch (error: any) {
    console.warn("Failed to list products from DB:", error.message);
    return res.json({
      success: true,
      data: [],
      error: "Database not connected — product list unavailable",
    });
  }
});

// ── GET /api/products/:asin ────────────────────────────────

router.get("/:asin", async (req: Request, res: Response) => {
  try {
    const asin = (req.params.asin || '').toUpperCase();

    if (!/^[A-Z0-9]{10}$/.test(asin)) {
      return res.status(400).json({
        success: false,
        error: "Invalid ASIN format",
      });
    }

    // Try DB first
    try {
      const { prisma } = await import("@affiliate/db");
      const product = await prisma.product.findUnique({
        where: { asin },
        include: {
          generations: {
            orderBy: { createdAt: "desc" },
            take: 20,
          },
        },
      });

      if (product) {
        return res.json({
          success: true,
          data: {
            ...product,
            createdAt: String(product.createdAt),
            updatedAt: String(product.updatedAt),
            generations: product.generations.map((g) => ({
              ...g,
              createdAt: String(g.createdAt),
              updatedAt: String(g.updatedAt),
            })),
          },
        });
      }
    } catch {}

    // Fall back to live API lookup
    const product = await importProduct(asin);

    return res.json({
      success: true,
      data: {
        ...product,
        generations: [],
      },
    });
  } catch (error: any) {
    if (error instanceof AmazonProductError) {
      return res.status(error.statusCode).json({
        success: false,
        error: error.message,
        code: error.code,
      });
    }
    return res.status(500).json({
      success: false,
      error: "Failed to fetch product",
    });
  }
});

// ── GET /api/products/extract-asin ─────────────────────────

router.post("/extract-asin", (req: Request, res: Response) => {
  const { input } = req.body;
  if (!input) {
    return res.status(400).json({ success: false, error: "input is required" });
  }
  const asin = extractAsin(input);
  return res.json({
    success: true,
    data: { asin, found: !!asin },
  });
});

export default router;
