import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { auth } from "@/lib/auth";

export async function GET() {
  const session = await auth();
  if (!session?.user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  try {
    const campaigns = await prisma.campaign.findMany({
      include: { business: { select: { name: true } } },
      orderBy: { createdAt: "desc" },
    });
    return NextResponse.json({ campaigns });
  } catch (error) {
    return NextResponse.json({ error: "Failed to fetch campaigns" }, { status: 500 });
  }
}

export async function POST(request: NextRequest) {
  const session = await auth();
  if (!session?.user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  try {
    const body = await request.json();
    const { businessId, name, type, targetAudience, message, schedule, templateId } = body;
    if (!businessId || !name || !type) {
      return NextResponse.json({ error: "businessId, name, and type are required" }, { status: 400 });
    }
    const campaign = await prisma.campaign.create({
      data: { businessId, name, type, targetAudience, message, schedule, templateId },
    });
    return NextResponse.json({ campaign }, { status: 201 });
  } catch (error) {
    return NextResponse.json({ error: "Failed to create campaign" }, { status: 500 });
  }
}