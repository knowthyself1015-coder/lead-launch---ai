import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";

export async function GET() {
  try {
    const websites = await prisma.website.findMany({
      include: { business: { select: { name: true, slug: true } } },
      orderBy: { createdAt: "desc" },
    });
    return NextResponse.json({ websites });
  } catch (error) {
    return NextResponse.json(
      { error: "Failed to fetch websites" },
      { status: 500 }
    );
  }
}

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const website = await prisma.website.create({
      data: {
        businessId: body.businessId,
        seoTitle: body.seoTitle,
        seoDescription: body.seoDescription,
        heroHeadline: body.heroHeadline,
        heroSubheadline: body.heroSubheadline,
        content: body.content ?? {},
        theme: body.theme ?? {},
      },
    });
    return NextResponse.json({ website }, { status: 201 });
  } catch (error) {
    return NextResponse.json(
      { error: "Failed to create website" },
      { status: 500 }
    );
  }
}
