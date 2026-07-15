import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";

export async function PATCH(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const body = await request.json();
    const { status, sentCount, openedCount, convertedCount } = body;
    const campaign = await prisma.campaign.update({
      where: { id: params.id },
      data: { status, sentCount, openedCount, convertedCount },
    });
    return NextResponse.json({ campaign });
  } catch (error) {
    return NextResponse.json({ error: "Failed to update campaign" }, { status: 500 });
  }
}