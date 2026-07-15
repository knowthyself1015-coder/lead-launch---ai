import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import {
  generateCode,
  storeVerificationCode,
  sendVerificationCode,
} from "@/lib/verification";

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { businessSlug, email } = body;

    if (!businessSlug || !email) {
      return NextResponse.json(
        { error: "businessSlug and email are required" },
        { status: 400 }
      );
    }

    // Validate email format
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      return NextResponse.json(
        { error: "Invalid email format" },
        { status: 400 }
      );
    }

    // Find the business by slug
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

    // Generate and store verification code
    const code = generateCode();
    storeVerificationCode(businessSlug, email, code);

    // Send the code (mocked for now, uses Resend if configured)
    await sendVerificationCode(email, code, business.name);

    return NextResponse.json({
      message: "Verification code sent",
      email,
      expiresIn: "15 minutes",
    });
  } catch (error) {
    console.error("Claim initiation error:", error);
    return NextResponse.json(
      { error: "Failed to initiate claim" },
      { status: 500 }
    );
  }
}