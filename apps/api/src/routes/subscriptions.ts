import { Router, Request, Response } from 'express';
import { stripe } from '../lib/stripe';

const router = Router();

/**
 * POST /api/subscriptions/create-checkout
 * Creates a Stripe Checkout session for a given price ID.
 * Body: { priceId: string, userId: string, userEmail: string, successUrl?: string, cancelUrl?: string }
 */
router.post('/create-checkout', async (req: Request, res: Response) => {
  try {
    const { priceId, userId, userEmail, successUrl, cancelUrl } = req.body;

    if (!priceId || typeof priceId !== 'string') {
      return res.status(400).json({ success: false, error: 'priceId is required' });
    }
    if (!userId || typeof userId !== 'string') {
      return res.status(400).json({ success: false, error: 'userId is required' });
    }
    if (!userEmail || typeof userEmail !== 'string') {
      return res.status(400).json({ success: false, error: 'userEmail is required' });
    }

    const baseUrl = process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:3000';

    // Look up the user to reuse an existing Stripe customer if available
    const { prisma } = await import('@affiliate/db');
    const user = await prisma.user.findUnique({
      where: { id: userId },
      select: { stripeCustomerId: true },
    });

    const customerOptions: Record<string, any> = { email: userEmail };

    // If user already has a Stripe customer ID, pass it to avoid duplicates
    if (user?.stripeCustomerId) {
      customerOptions.customer = user.stripeCustomerId;
    } else {
      customerOptions.customer_creation = 'always';
    }

    const session = await stripe.checkout.sessions.create({
      mode: 'subscription',
      line_items: [{ price: priceId, quantity: 1 }],
      customer_email: userEmail,
      client_reference_id: userId,
      metadata: { userId },
      success_url: successUrl || `${baseUrl}/settings/billing?checkout=success`,
      cancel_url: cancelUrl || `${baseUrl}/pricing?checkout=canceled`,
      allow_promotion_codes: true,
      billing_address_collection: 'auto',
      subscription_data: {
        metadata: { userId },
      },
    });

    return res.json({
      success: true,
      data: { url: session.url, sessionId: session.id },
    });
  } catch (error: any) {
    console.error('Stripe checkout error:', error);
    return res.status(500).json({
      success: false,
      error: error.message || 'Failed to create checkout session',
    });
  }
});

/**
 * POST /api/subscriptions/portal
 * Creates a Stripe Customer Portal session for managing an existing subscription.
 * Body: { userId: string }
 */
router.post('/portal', async (req: Request, res: Response) => {
  try {
    const { userId } = req.body;

    if (!userId || typeof userId !== 'string') {
      return res.status(400).json({ success: false, error: 'userId is required' });
    }

    const { prisma } = await import('@affiliate/db');
    const user = await prisma.user.findUnique({
      where: { id: userId },
      select: { stripeCustomerId: true },
    });

    if (!user?.stripeCustomerId) {
      return res.status(400).json({
        success: false,
        error: 'No Stripe customer found for this user. Start a subscription first.',
      });
    }

    const baseUrl = process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:3000';

    const portalSession = await stripe.billingPortal.sessions.create({
      customer: user.stripeCustomerId,
      return_url: `${baseUrl}/settings/billing`,
    });

    return res.json({
      success: true,
      data: { url: portalSession.url },
    });
  } catch (error: any) {
    console.error('Stripe portal error:', error);
    return res.status(500).json({
      success: false,
      error: error.message || 'Failed to create portal session',
    });
  }
});

/**
 * GET /api/subscriptions/status?userId=...
 * Returns the current subscription status for a user.
 */
router.get('/status', async (req: Request, res: Response) => {
  try {
    const userId = req.query.userId as string;

    if (!userId) {
      return res.status(400).json({ success: false, error: 'userId query param is required' });
    }

    const { prisma } = await import('@affiliate/db');
    const user = await prisma.user.findUnique({
      where: { id: userId },
      select: {
        tier: true,
        stripeCustomerId: true,
        stripeSubscriptionId: true,
        subscriptionStatus: true,
        subscriptionCurrentPeriodEnd: true,
        cancelAtPeriodEnd: true,
        generationsUsedThisMonth: true,
        generationsResetDate: true,
      },
    });

    if (!user) {
      return res.status(404).json({ success: false, error: 'User not found' });
    }

    return res.json({
      success: true,
      data: {
        tier: user.tier,
        stripeCustomerId: user.stripeCustomerId,
        stripeSubscriptionId: user.stripeSubscriptionId,
        subscriptionStatus: user.subscriptionStatus,
        subscriptionCurrentPeriodEnd: user.subscriptionCurrentPeriodEnd,
        cancelAtPeriodEnd: user.cancelAtPeriodEnd,
        generationsUsedThisMonth: user.generationsUsedThisMonth,
        generationsResetDate: user.generationsResetDate,
      },
    });
  } catch (error: any) {
    console.error('Fetch subscription error:', error);
    return res.status(500).json({
      success: false,
      error: 'Failed to fetch subscription',
    });
  }
});

export default router;
