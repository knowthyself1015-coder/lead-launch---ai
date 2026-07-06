import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { auth } from "@/lib/auth";

export async function GET() {
  try {
    const session = await auth();
    const businesses = await prisma.business.findMany({
      orderBy: { createdAt: "desc" },
      take: 100,
    });
    return NextResponse.json({ businesses, session });
  } catch (error) {
    return NextResponse.json(
      { error: "Failed to fetch businesses" },
      { status: 500 }
    );
  }
}

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const business = await prisma.business.create({
      data: {
        name: body.name,
        category: body.category,
        phone: body.phone,
        email: body.email,
        address: body.address,
        city: body.city,
        state: body.state,
        zip: body.zip,
        description: body.description,
        hours: body.hours ?? {},
        website: body.website,
        slug: body.slug,
        source: body.source,
        rating: body.rating,
        reviewsCount: body.reviewsCount ?? 0,
        photos: body.photos ?? [],
      },
    });
    return NextResponse.json({ business }, { status: 201 });
  } catch (error) {
    return NextResponse.json(
      { error: "Failed to create business" },
      { status: 500 }
    );
  }
}
