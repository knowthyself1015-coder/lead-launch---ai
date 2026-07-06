import Stripe from "stripe";
import { stripe, PLANS, type PlanId } from "@/lib/stripe";

/**
 * Ensures Stripe products and prices exist for all subscription tiers.
 * Returns a map of planId → { productId, priceId }.
 *
 * Idempotent — products are looked up by metadata.leadlaunch_plan_id
 * and created if they don't exist.
 */
export async function ensureProductsAndPrices(): Promise<
  Record<PlanId, { productId: string; priceId: string }>
> {
  const result = {} as Record<PlanId, { productId: string; priceId: string }>;

  for (const [planId, plan] of Object.entries(PLANS)) {
    const id = planId as PlanId;

    // Check if product already exists by metadata
    const existingProducts = await stripe.products.search({
      query: `metadata["leadlaunch_plan_id"]:"${planId}"`,
      limit: 1,
    });

    let product: Awaited<ReturnType<typeof stripe.products.create>>;

    if (existingProducts.data.length > 0) {
      product = existingProducts.data[0] as any;
    } else {
      // Create the product
      product = await stripe.products.create({
        name: `LeadLaunch ${plan.name}`,
        description: plan.description,
        metadata: {
          leadlaunch_plan_id: planId,
          leadlaunch_plan_name: plan.name,
        },
      });
    }

    // Check if the product already has an active price for this interval
    const existingPrices = await stripe.prices.list({
      product: product.id,
      active: true,
      limit: 10,
    });

    const matchingPrice = existingPrices.data.find(
      (p) =>
        p.recurring?.interval === plan.interval &&
        p.unit_amount === plan.price &&
        p.currency === "usd"
    );

    if (matchingPrice) {
      result[id] = { productId: product.id, priceId: matchingPrice.id };
    } else {
      // Create the price
      const price = await stripe.prices.create({
        product: product.id,
        unit_amount: plan.price,
        currency: "usd",
        recurring: {
          interval: plan.interval,
          interval_count: 1,
        },
        metadata: {
          leadlaunch_plan_id: planId,
        },
      });

      result[id] = { productId: product.id, priceId: price.id };
    }
  }

  return result;
}

/**
 * Creates a Stripe Checkout Session for a subscription plan.
 */
export async function createCheckoutSession(params: {
  planId: PlanId;
  businessId: string;
  businessName: string;
  successUrl: string;
  cancelUrl: string;
  customerEmail?: string;
}) {
  const { planId, businessId, businessName, successUrl, cancelUrl, customerEmail } = params;
  const products = await ensureProductsAndPrices();
  const { priceId } = products[planId];

  const session = await stripe.checkout.sessions.create({
    mode: "subscription",
    line_items: [
      {
        price: priceId,
        quantity: 1,
      },
    ],
    metadata: {
      businessId,
      planId,
    },
    ...(customerEmail ? { customer_email: customerEmail } : {}),
    success_url: successUrl,
    cancel_url: cancelUrl,
    subscription_data: {
      metadata: {
        businessId,
        planId,
      },
    },
  });

  return session;
}