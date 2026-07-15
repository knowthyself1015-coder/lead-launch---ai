import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";

export async function POST(request: Request) {
  try {
    const body = await request.json();

    // Look up or create a user by email for the claim
    let userId: string | undefined;
    if (body.email) {
      const user = await prisma.user.upsert({
        where: { email: body.email },
        update: {},
        create: {
          email: body.email,
          name: body.email.split("@")[0],
        },
      });
      userId = user.id;
    }

    const claim = await prisma.claim.create({
      data: {
        businessId: body.businessId,
        userId: userId ?? body.userId,
        verificationMethod: body.verificationMethod ?? "email",
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