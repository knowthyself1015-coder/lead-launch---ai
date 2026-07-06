import { NextRequest, NextResponse } from "next/server";

// Stripe requires the raw body for signature verification.
// In App Router, request.text() provides the raw body — no config needed.

export async function POST(request: NextRequest) {
  try {
    const sig = request.headers.get("stripe-signature");
    if (!sig) {
      return NextResponse.json(
        { error: "Missing stripe-signature header" },
        { status: 400 }
      );
    }

    const webhookSecret = process.env.STRIPE_WEBHOOK_SECRET;

    if (!webhookSecret) {
      // If no webhook secret is configured, just acknowledge the event
      const body = await request.text();
      const event = JSON.parse(body);
      console.log(`[Stripe Webhook] Received event: ${event.type} (no verification)`);
      return NextResponse.json({ received: true });
    }

    // For real signature verification
    const { stripe } = await import("@/lib/stripe");
    const body = await request.text();

    let event;
    try {
      event = stripe.webhooks.constructEvent(body, sig, webhookSecret);
    } catch (err) {
      console.error("Stripe webhook signature verification failed:", err);
      return NextResponse.json(
        { error: "Invalid signature" },
        { status: 400 }
      );
    }

    // Handle specific event types
    switch (event.type) {
      case "checkout.session.completed": {
        const session = event.data.object;
        const { businessId, planId } = session.metadata || {};
        console.log(
          `[Stripe] Subscription completed for business ${businessId}, plan ${planId}`
        );
        // TODO: Update business claimed status in DB and link subscription
        break;
      }

      case "customer.subscription.updated": {
        const subscription = event.data.object;
        console.log(
          `[Stripe] Subscription ${subscription.id} updated, status: ${subscription.status}`
        );
        break;
      }

      case "customer.subscription.deleted": {
        const subscription = event.data.object;
        console.log(
          `[Stripe] Subscription ${subscription.id} canceled`
        );
        // TODO: Downgrade business plan
        break;
      }

      case "invoice.payment_succeeded": {
        const invoice = event.data.object;
        console.log(`[Stripe] Invoice ${invoice.id} paid`);
        break;
      }

      case "invoice.payment_failed": {
        const invoice = event.data.object;
        console.log(`[Stripe] Invoice ${invoice.id} payment failed`);
        // TODO: Notify business owner
        break;
      }

      default:
        console.log(`[Stripe] Unhandled event type: ${event.type}`);
    }

    return NextResponse.json({ received: true });
  } catch (error) {
    console.error("Webhook error:", error);
    return NextResponse.json(
      { error: "Webhook handler failed" },
      { status: 500 }
    );
  }
}