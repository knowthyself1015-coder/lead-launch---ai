import { NextResponse } from "next/server";
import { stripe, PLANS } from "@/lib/stripe";

export async function GET() {
  // Check if Stripe is configured
  if (!process.env.STRIPE_SECRET_KEY) {
    return NextResponse.json({
      configured: false,
      plans: Object.entries(PLANS).map(([id, plan]) => ({
        id,
        name: plan.name,
        description: plan.description,
        price: plan.price,
        priceDisplay: `$${(plan.price / 100).toFixed(0)}/mo`,
        interval: plan.interval,
        features: plan.features,
      })),
    });
  }

  try {
    // Fetch actual product data from Stripe
    const stripeProducts = await stripe.products.search({
      query: 'metadata["leadlaunch_plan_id"]:"basic" OR metadata["leadlaunch_plan_id"]:"pro" OR metadata["leadlaunch_plan_id"]:"premium"',
      limit: 10,
    });

    const products = Object.entries(PLANS).map(([id, plan]) => {
      const sp = stripeProducts.data.find(
        (p) => p.metadata.leadlaunch_plan_id === id
      );
      return {
        id,
        name: plan.name,
        description: plan.description,
        price: plan.price,
        priceDisplay: `$${(plan.price / 100).toFixed(0)}/mo`,
        interval: plan.interval,
        features: plan.features,
        stripeProductId: sp?.id ?? null,
        active: sp?.active ?? true,
      };
    });

    return NextResponse.json({ configured: true, products });
  } catch (error) {
    return NextResponse.json(
      { error: "Failed to fetch Stripe products", details: String(error) },
      { status: 500 }
    );
  }
}