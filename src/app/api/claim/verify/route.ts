import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { verifyCode } from "@/lib/verification";
import bcrypt from "bcryptjs";

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { businessSlug, email, code } = body;

    if (!businessSlug || !email || !code) {
      return NextResponse.json(
        { error: "businessSlug, email, and code are required" },
        { status: 400 }
      );
    }

    // Verify the code
    const result = verifyCode(businessSlug, email, code);
    if (!result.valid) {
      return NextResponse.json(
        { error: result.reason || "Verification failed" },
        { status: 400 }
      );
    }

    // Find the business
    const business = await prisma.business.findUnique({
      where: { slug: businessSlug },
    });

    if (!business) {
      return NextResponse.json(
        { error: "Business not found" },
        { status: 404 }
      );
    }

    if (business.claimed) {
      return NextResponse.json(
        { error: "This business has already been claimed" },
        { status: 409 }
      );
    }

    // Find or create the user
    let user = await prisma.user.findUnique({
      where: { email },
    });

    if (!user) {
      user = await prisma.user.create({
        data: {
          email,
          name: email.split("@")[0],
          role: "BUSINESS_OWNER",
        },
      });
    }

    // Create the claim record
    const claim = await prisma.claim.create({
      data: {
        businessId: business.id,
        userId: user.id,
        status: "PENDING",
        verificationMethod: "email",
      },
    });

    return NextResponse.json({
      message: "Claim submitted successfully",
      claim: {
        id: claim.id,
        status: claim.status,
        businessName: business.name,
        businessSlug: business.slug,
      },
    }, { status: 201 });
  } catch (error) {
    console.error("Claim verification error:", error);
    return NextResponse.json(
      { error: "Failed to verify claim" },
      { status: 500 }
    );
  }
}