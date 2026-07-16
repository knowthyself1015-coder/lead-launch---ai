import { Request, Response, NextFunction } from 'express';
import { UserTier, checkGenerationLimit } from '@affiliate/shared';

/**
 * Middleware that checks if a user has remaining generations for this month.
 * Requires `userId` in the request body or query.
 * If limit exceeded, returns 429.
 * On success, increments the user's generation counter.
 */
export async function generationLimitMiddleware(req: Request, res: Response, next: NextFunction) {
  try {
    const userId = req.body?.userId || req.query?.userId;

    if (!userId) {
      // No userId — let the route handler decide (may be a public endpoint)
      return next();
    }

    const { prisma } = await import('@affiliate/db');

    const user = await prisma.user.findUnique({
      where: { id: userId },
      select: {
        tier: true,
        generationsUsedThisMonth: true,
        generationsResetDate: true,
      },
    });

    if (!user) {
      return res.status(404).json({ success: false, error: 'User not found' });
    }

    // Check if counter needs to be reset (new month)
    const now = new Date();
    const shouldReset = user.generationsResetDate && now > user.generationsResetDate;

    const used = shouldReset ? 0 : user.generationsUsedThisMonth;
    const tier = (user.tier as UserTier) || 'free';

    const { allowed, limit, remaining } = checkGenerationLimit(tier, used);

    if (!allowed) {
      return res.status(429).json({
        success: false,
        error: `Generation limit reached (${used}/${limit}). Upgrade your plan for more.`,
        code: 'RATE_LIMITED',
        data: { limit, used, remaining: 0 },
      });
    }

    // Increment the counter
    const resetDate = shouldReset
      ? new Date(now.getFullYear(), now.getMonth() + 1, 1) // first day of next month
      : user.generationsResetDate || new Date(now.getFullYear(), now.getMonth() + 1, 1);

    await prisma.user.update({
      where: { id: userId },
      data: {
        generationsUsedThisMonth: used + 1,
        generationsResetDate: shouldReset ? resetDate : undefined,
      },
    });

    // Attach rate limit info to the request for downstream handlers
    (req as any).rateLimit = { limit, used: used + 1, remaining: remaining - 1 };

    next();
  } catch (error: any) {
    console.error('Rate limit middleware error:', error);
    // Don't block on rate limit errors — allow the request through
    next();
  }
}
