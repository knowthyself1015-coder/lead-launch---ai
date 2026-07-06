import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { generateBusinessContent } from "@/lib/generator";
import type { BusinessContext } from "@/types/content";

export async function POST(
  _request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const business = await prisma.business.findUnique({
      where: { id: params.id },
      include: { websites: true },
    });

    if (!business) {
      return NextResponse.json(
        { error: "Business not found" },
        { status: 404 }
      );
    }

    if (business.websites.length > 0) {
      return NextResponse.json(
        { error: "Website already exists for this business" },
        { status: 409 }
      );
    }

    // Map Prisma Business to the generator's BusinessContext
    const ctx: BusinessContext = {
      name: business.name,
      category: business.category || "General",
      city: business.city || "",
      state: business.state || "",
      description: business.description || undefined,
      phone: business.phone || undefined,
      address: business.address || undefined,
      zip: business.zip || undefined,
      hours: business.hours as Record<string, string> | undefined,
      source: business.source || undefined,
      rating: business.rating || undefined,
      review_count: business.reviewsCount || undefined,
    };

    // Generate content via the AI pipeline
    // Falls back to templates if OPENAI_API_KEY isn't set (handled by generator)
    const result = await generateBusinessContent(ctx);
    const content = result.content;

    const website = await prisma.website.create({
      data: {
        businessId: business.id,
        seoTitle: content.seo.seo_title,
        seoDescription: content.seo.meta_description,
        heroHeadline: content.hero.headlines[0] || business.name,
        heroSubheadline: content.hero.subheadline,
        content: {
          hero: content.hero,
          about: content.about,
          services: content.services,
          faq: content.faq,
          seo: content.seo,
        },
        published: true,
        theme: {
          hue: "240",
        },
      },
    });

    return NextResponse.json({
      website,
      aiGenerated: !!process.env.OPENAI_API_KEY,
      usage: result.usage,
    }, { status: 201 });
  } catch (error) {
    console.error("Generate error:", error);
    return NextResponse.json(
      { error: "Failed to generate website" },
      { status: 500 }
    );
  }
}