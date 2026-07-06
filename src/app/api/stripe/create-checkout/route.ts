import { NextRequest, NextResponse } from "next/server";
import { createCheckoutSession, ensureProductsAndPrices } from "@/lib/stripe-products";

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { planId, businessId, businessName, customerEmail } = body;

    if (!planId || !businessId) {
      return NextResponse.json(
        { error: "planId and businessId are required" },
        { status: 400 }
      );
    }

    const validPlans = ["basic", "pro", "premium"];
    if (!validPlans.includes(planId)) {
      return NextResponse.json(
        { error: "Invalid planId. Must be basic, pro, or premium" },
        { status: 400 }
      );
    }

    const origin = request.headers.get("origin") || process.env.NEXT_PUBLIC_APP_URL || "http://localhost:3000";

    // Ensure Stripe products/prices exist
    await ensureProductsAndPrices();

    const session = await createCheckoutSession({
      planId: planId as "basic" | "pro" | "premium",
      businessId,
      businessName: businessName || "Your Business",
      successUrl: `${origin}/dashboard?checkout=success&session_id={CHECKOUT_SESSION_ID}`,
      cancelUrl: `${origin}/dashboard?checkout=cancel`,
      customerEmail,
    });

    return NextResponse.json({ url: session.url, sessionId: session.id });
  } catch (error) {
    console.error("Checkout error:", error);
    return NextResponse.json(
      { error: "Failed to create checkout session", details: String(error) },
      { status: 500 }
    );
  }
}