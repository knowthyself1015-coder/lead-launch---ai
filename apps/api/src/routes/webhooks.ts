import { Router, Request, Response } from 'express';
import { stripe, getTierFromPriceId } from '../lib/stripe';

const router = Router();

/**
 * POST /api/subscriptions/webhook
 * Handles Stripe webhook events for subscription lifecycle management.
 * Requires raw body — must be configured before JSON middleware in Express.
 */

export async function handleStripeWebhook(req: Request, res: Response) {
  const sig = req.headers['stripe-signature'];

  if (!sig || typeof sig !== 'string') {
    return res.status(400).json({ success: false, error: 'Missing stripe-signature header' });
  }

  const webhookSecret = process.env.STRIPE_WEBHOOK_SECRET;
  if (!webhookSecret) {
    console.error('STRIPE_WEBHOOK_SECRET is not set');
    return res.status(500).json({ success: false, error: 'Webhook secret not configured' });
  }

  let event;
  try {
    event = stripe.webhooks.constructEvent(req.body, sig, webhookSecret);
  } catch (err: any) {
    console.error('Stripe webhook signature verification failed:', err.message);
    return res.status(400).json({ success: false, error: `Webhook Error: ${err.message}` });
  }

  const { prisma } = await import('@affiliate/db');

  try {
    const obj = event.data.object as any;
    const sub = obj; // alias for subscription objects

    switch (event.type) {
      // ── Checkout completed → provision subscription ──
      case 'checkout.session.completed': {
        const session = event.data.object as any;
        const userId = session.metadata?.userId || session.client_reference_id;
        if (!userId) break;

        const subscriptionId = session.subscription as string;
        const customerId = session.customer as string;

        if (subscriptionId) {
          const subscription = await stripe.subscriptions.retrieve(subscriptionId);
          const s = subscription as any;
          const priceId = s.items?.data?.[0]?.price?.id || '';
          const tier = getTierFromPriceId(priceId);

          await prisma.user.update({
            where: { id: userId },
            data: {
              stripeCustomerId: customerId,
              stripeSubscriptionId: subscriptionId,
              subscriptionStatus: s.status,
              subscriptionCurrentPeriodEnd: new Date(s.current_period_end * 1000),
              cancelAtPeriodEnd: s.cancel_at_period_end,
              tier: tier || 'free',
              generationsUsedThisMonth: 0,
              generationsResetDate: new Date(s.current_period_end * 1000),
            },
          });

          console.log(`✅ Subscription provisioned: user=${userId} tier=${tier} status=${s.status}`);
        }
        break;
      }

      // ── Subscription updated ──
      case 'customer.subscription.updated': {
        const userId = obj.metadata?.userId;

        if (!userId) {
          const user = await prisma.user.findFirst({
            where: { stripeSubscriptionId: obj.id },
            select: { id: true },
          });
          if (!user) break;

          const priceId = obj.items?.data?.[0]?.price?.id || '';
          const tier = getTierFromPriceId(priceId);

          await prisma.user.update({
            where: { id: user.id },
            data: {
              subscriptionStatus: obj.status,
              subscriptionCurrentPeriodEnd: new Date(obj.current_period_end * 1000),
              cancelAtPeriodEnd: obj.cancel_at_period_end,
              tier: tier || undefined,
            },
          });
          console.log(`✅ Subscription updated (by lookup): user=${user.id} status=${obj.status}`);
          break;
        }

        const priceId = obj.items?.data?.[0]?.price?.id || '';
        const tier = getTierFromPriceId(priceId);

        const currentPeriodEnd = new Date(obj.current_period_end * 1000);
        const existingUser = await prisma.user.findUnique({
          where: { id: userId },
          select: { subscriptionCurrentPeriodEnd: true },
        });

        const shouldReset =
          existingUser?.subscriptionCurrentPeriodEnd &&
          currentPeriodEnd.getTime() > existingUser.subscriptionCurrentPeriodEnd.getTime();

        await prisma.user.update({
          where: { id: userId },
          data: {
            subscriptionStatus: obj.status,
            subscriptionCurrentPeriodEnd: currentPeriodEnd,
            cancelAtPeriodEnd: obj.cancel_at_period_end,
            tier: tier || undefined,
            ...(shouldReset ? {
              generationsUsedThisMonth: 0,
              generationsResetDate: currentPeriodEnd,
            } : {}),
          },
        });

        console.log(`✅ Subscription updated: user=${userId} tier=${tier} status=${obj.status} reset=${shouldReset}`);
        break;
      }

      // ── Subscription deleted ──
      case 'customer.subscription.deleted': {
        let targetUserId = obj.metadata?.userId;
        if (!targetUserId) {
          const user = await prisma.user.findFirst({
            where: { stripeSubscriptionId: obj.id },
            select: { id: true },
          });
          targetUserId = user?.id;
        }

        if (targetUserId) {
          await prisma.user.update({
            where: { id: targetUserId },
            data: {
              subscriptionStatus: 'canceled',
              stripeSubscriptionId: null,
              tier: 'free',
            },
          });
          console.log(`✅ Subscription canceled: user=${targetUserId}`);
        }
        break;
      }

      // ── Payment failed ──
      case 'invoice.payment_failed': {
        const invoice = event.data.object as any;
        const subscriptionId = invoice.subscription as string;

        if (subscriptionId) {
          const user = await prisma.user.findFirst({
            where: { stripeSubscriptionId: subscriptionId },
            select: { id: true },
          });

          if (user) {
            await prisma.user.update({
              where: { id: user.id },
              data: { subscriptionStatus: 'past_due' },
            });
            console.log(`⚠ Subscription past_due: user=${user.id}`);
          }
        }
        break;
      }

      default:
        break;
    }
  } catch (error: any) {
    console.error('Webhook processing error:', error);
    return res.status(500).json({ success: false, error: 'Webhook processing failed' });
  }

  return res.json({ received: true });
}

router.post('/', handleStripeWebhook);

export default router;
