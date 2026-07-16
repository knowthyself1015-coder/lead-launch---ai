'use client';

import { useState, useEffect } from 'react';
import { useSession } from 'next-auth/react';
import Link from 'next/link';

interface SubscriptionData {
  tier: string;
  stripeCustomerId: string | null;
  stripeSubscriptionId: string | null;
  subscriptionStatus: string | null;
  subscriptionCurrentPeriodEnd: string | null;
  cancelAtPeriodEnd: boolean;
  generationsUsedThisMonth: number;
  generationsResetDate: string | null;
}

const tierStyles: Record<string, string> = {
  free: 'bg-gray-100 text-gray-700',
  creator: 'bg-blue-100 text-blue-700',
  pro: 'bg-purple-100 text-purple-700',
  agency: 'bg-amber-100 text-amber-700',
};

const tierNames: Record<string, string> = {
  free: 'Free',
  creator: 'Creator',
  pro: 'Pro',
  agency: 'Agency',
};

export default function BillingPage() {
  const { data: session } = useSession();
  const [sub, setSub] = useState<SubscriptionData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const userId = (session?.user as any)?.id;

  useEffect(() => {
    if (!userId) return;
    fetch(`http://localhost:4000/api/subscriptions/status?userId=${encodeURIComponent(userId)}`)
      .then((r) => r.json())
      .then((data) => {
        if (data.success) setSub(data.data);
        else setError(data.error || 'Failed to load subscription');
      })
      .catch(() => setError('Could not connect to API'))
      .finally(() => setLoading(false));
  }, [userId]);

  const handleUpgrade = async () => {
    setActionLoading('checkout');
    try {
      const res = await fetch('http://localhost:4000/api/subscriptions/create-checkout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          userId,
          userEmail: session?.user?.email,
          priceId: process.env.NEXT_PUBLIC_STRIPE_PRICE_CREATOR_MONTHLY || '',
        }),
      });
      const data = await res.json();
      if (data.success && data.data.url) {
        window.location.href = data.data.url;
      } else {
        setError(data.error || 'Failed to start checkout');
      }
    } catch {
      setError('Checkout request failed');
    } finally {
      setActionLoading(null);
    }
  };

  const handlePortal = async () => {
    setActionLoading('portal');
    try {
      const res = await fetch('http://localhost:4000/api/subscriptions/portal', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ userId }),
      });
      const data = await res.json();
      if (data.success && data.data.url) {
        window.location.href = data.data.url;
      } else {
        setError(data.error || 'Failed to open portal');
      }
    } catch {
      setError('Portal request failed');
    } finally {
      setActionLoading(null);
    }
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-gray-900">Billing & Subscription</h1>
        <div className="bg-white rounded-xl border border-gray-200 p-8 text-center">
          <div className="animate-pulse text-gray-400">Loading subscription details...</div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Billing & Subscription</h1>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-700">
          {error}
          <button onClick={() => setError(null)} className="ml-2 underline">Dismiss</button>
        </div>
      )}

      {/* Current Plan */}
      <section className="bg-white rounded-xl border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Current Plan</h2>

        {sub ? (
          <dl className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <dt className="text-sm text-gray-500">Plan</dt>
              <dd>
                <span className={`inline-block text-sm font-semibold px-2 py-0.5 rounded-full ${tierStyles[sub.tier] || tierStyles.free}`}>
                  {tierNames[sub.tier] || sub.tier}
                </span>
              </dd>
            </div>
            <div>
              <dt className="text-sm text-gray-500">Status</dt>
              <dd className="text-gray-900 capitalize">{sub.subscriptionStatus || 'free'}</dd>
            </div>
            {sub.subscriptionCurrentPeriodEnd && (
              <div>
                <dt className="text-sm text-gray-500">
                  {sub.cancelAtPeriodEnd ? 'Expires' : 'Renews'}
                </dt>
                <dd className="text-gray-900">
                  {new Date(sub.subscriptionCurrentPeriodEnd).toLocaleDateString('en-US', {
                    year: 'numeric',
                    month: 'long',
                    day: 'numeric',
                  })}
                </dd>
              </div>
            )}
            <div>
              <dt className="text-sm text-gray-500">Generations Used</dt>
              <dd className="text-gray-900">
                {sub.generationsUsedThisMonth}
                {sub.generationsResetDate && (
                  <span className="text-xs text-gray-400 ml-1">
                    (resets {new Date(sub.generationsResetDate).toLocaleDateString()})
                  </span>
                )}
              </dd>
            </div>
            {sub.cancelAtPeriodEnd && (
              <div>
                <dt className="text-sm text-gray-500">Renewal</dt>
                <dd className="text-amber-600 font-medium">Cancels at period end</dd>
              </div>
            )}
          </dl>
        ) : (
          <p className="text-gray-500">No subscription data available.</p>
        )}
      </section>

      {/* Actions */}
      <section className="bg-white rounded-xl border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Manage Subscription</h2>

        <div className="flex flex-wrap gap-4">
          {(!sub || sub.tier === 'free') && (
            <button
              onClick={handleUpgrade}
              disabled={actionLoading === 'checkout'}
              className="px-5 py-2.5 bg-brand-600 text-white rounded-lg text-sm font-semibold hover:bg-brand-700 disabled:opacity-50 transition-colors"
            >
              {actionLoading === 'checkout' ? 'Redirecting...' : 'Upgrade to Creator'}
            </button>
          )}

          {sub?.stripeCustomerId && (
            <button
              onClick={handlePortal}
              disabled={actionLoading === 'portal'}
              className="px-5 py-2.5 bg-white border border-gray-300 text-gray-700 rounded-lg text-sm font-semibold hover:bg-gray-50 disabled:opacity-50 transition-colors"
            >
              {actionLoading === 'portal' ? 'Opening...' : 'Manage Subscription'}
            </button>
          )}

          <Link
            href="/pricing"
            className="px-5 py-2.5 bg-white border border-gray-300 text-gray-700 rounded-lg text-sm font-semibold hover:bg-gray-50 transition-colors inline-flex items-center"
          >
            View Plans
          </Link>
        </div>

        <p className="text-xs text-gray-400 mt-4">
          Use the Stripe Customer Portal to update payment methods, change plans, or cancel your subscription.
        </p>
      </section>
    </div>
  );
}
