import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const claim = await prisma.claim.create({
      data: {
        businessId: body.businessId,
        userId: body.userId,
        verificationMethod: body.verificationMethod,
        status: "PENDING",
      },
    });
    return NextResponse.json({ claim }, { status: 201 });
  } catch (error) {
    return NextResponse.json(
      { error: "Failed to create claim" },
      { status: 500 }
    );
  }
}

export async function GET() {
  try {
    const claims = await prisma.claim.findMany({
      include: {
        business: { select: { name: true, slug: true } },
        user: { select: { email: true, name: true } },
      },
      orderBy: { createdAt: "desc" },
    });
    return NextResponse.json({ claims });
  } catch (error) {
    return NextResponse.json(
      { error: "Failed to fetch claims" },
      { status: 500 }
    );
  }
}
