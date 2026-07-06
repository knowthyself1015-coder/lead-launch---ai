import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { auth } from "@/lib/auth";

export async function GET(request: NextRequest) {
  const session = await auth();
  if (!session?.user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const userId = (session.user as any).id;

  try {
    const user = await prisma.user.findUnique({
      where: { id: userId },
      include: {
        business: {
          include: { subscription: true },
        },
      },
    });

    if (!user?.business) {
      return NextResponse.json({ subscription: null });
    }

    return NextResponse.json({
      subscription: user.business.subscription,
      business: {
        id: user.business.id,
        name: user.business.name,
        claimed: user.business.claimed,
      },
    });
  } catch (error) {
    return NextResponse.json(
      { error: "Failed to fetch subscription" },
      { status: 500 }
    );
  }
}

export async function PUT(request: NextRequest) {
  const authSession = await auth();
  if (!authSession?.user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const userId = (authSession.user as any).id;

  try {
    const body = await request.json();
    const { planId } = body;

    if (!planId || !["basic", "pro", "premium"].includes(planId)) {
      return NextResponse.json({ error: "Invalid planId" }, { status: 400 });
    }

    const user = await prisma.user.findUnique({
      where: { id: userId },
      include: { business: true },
    });

    if (!user?.business) {
      return NextResponse.json(
        { error: "Business not found" },
        { status: 404 }
      );
    }

    // Update subscription plan in local DB
    // The actual Stripe changes happen through checkout/portal
    const subscription = await prisma.subscription.upsert({
      where: { businessId: user.business.id },
      create: {
        businessId: user.business.id,
        planId,
        status: "INCOMPLETE",
      },
      update: {
        planId,
        status: "INCOMPLETE",
      },
    });

    return NextResponse.json({ subscription });
  } catch (error) {
    return NextResponse.json(
      { error: "Failed to update subscription" },
      { status: 500 }
    );
  }
}