import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";

export async function PATCH(
  request: Request,
  { params }: { params: { id: string } }
) {
  try {
    const body = await request.json();
    const { status } = body;

    if (!status || !["VERIFIED", "REJECTED"].includes(status)) {
      return NextResponse.json(
        { error: "Status must be VERIFIED or REJECTED" },
        { status: 400 }
      );
    }

    const claim = await prisma.claim.update({
      where: { id: params.id },
      data: {
        status,
        verifiedAt: status === "VERIFIED" ? new Date() : null,
      },
      include: {
        business: { select: { name: true, slug: true } },
        user: { select: { email: true, name: true } },
      },
    });

    // If approved, mark the business as claimed
    if (status === "VERIFIED" && claim.businessId) {
      await prisma.business.update({
        where: { id: claim.businessId },
        data: { claimed: true },
      });
    }

    return NextResponse.json({ claim });
  } catch (error) {
    return NextResponse.json(
      { error: "Failed to update claim" },
      { status: 500 }
    );
  }
}