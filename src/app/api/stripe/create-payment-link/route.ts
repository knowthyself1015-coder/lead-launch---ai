import { NextRequest, NextResponse } from "next/server";

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { planId, businessId } = body;

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

    // Import stripe inside the handler to avoid issues if env var not set
    const { ensureProductsAndPrices } = await import("@/lib/stripe-products");
    const { stripe } = await import("@/lib/stripe");
    const { PLANS } = await import("@/lib/stripe");

    const products = await ensureProductsAndPrices();
    const productsMap = products as Record<string, { priceId: string }>;

    if (!productsMap[planId]) {
      return NextResponse.json(
        { error: `Plan ${planId} not found in Stripe` },
        { status: 500 }
      );
    }

    const plan = PLANS[planId as keyof typeof PLANS];

    const paymentLink = await stripe.paymentLinks.create({
      line_items: [
        {
          price: productsMap[planId].priceId,
          quantity: 1,
        },
      ],
      metadata: {
        businessId,
        planId,
      },
      subscription_data: {
        metadata: {
          businessId,
          planId,
        },
      },
      after_completion: {
        type: "redirect",
        redirect: {
          url: `${origin}/dashboard?checkout=success`,
        },
      },
    });

    return NextResponse.json({
      url: paymentLink.url,
      paymentLinkId: paymentLink.id,
      planName: plan.name,
      price: `$${(plan.price / 100).toFixed(0)}/mo`,
    });
  } catch (error) {
    console.error("Payment link error:", error);
    return NextResponse.json(
      { error: "Failed to create payment link", details: String(error) },
      { status: 500 }
    );
  }
}