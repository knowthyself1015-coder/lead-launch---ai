import Link from 'next/link';
import { auth } from '@/lib/auth';

const tiers = [
  {
    name: 'Free',
    priceMonthly: 0,
    priceAnnual: 0,
    description: 'Try it out with basic features',
    features: [
      '5 content generations / month',
      'Basic AI Writer',
      'Watermarked exports',
      'Amazon Associates integration',
    ],
    cta: 'Get Started Free',
    href: '/login',
    highlighted: false,
  },
  {
    name: 'Creator',
    priceMonthly: 19,
    priceAnnual: 190,
    description: 'For solo affiliate creators',
    features: [
      'Unlimited content generations',
      'HD exports',
      'AI Thumbnail Generator',
      'Full AI Writer suite',
      'Watermark-free exports',
      'Priority support',
    ],
    cta: 'Start Creator',
    href: '/login',
    highlighted: true,
  },
  {
    name: 'Pro',
    priceMonthly: 49,
    priceAnnual: 490,
    description: 'For growing affiliate businesses',
    features: [
      'Everything in Creator',
      'Multiple tracking IDs',
      'Team collaboration',
      'Brand kit',
      'Advanced analytics',
      'Content calendar',
      'Bulk generation',
    ],
    cta: 'Start Pro',
    href: '/login',
    highlighted: false,
  },
  {
    name: 'Agency',
    priceMonthly: 149,
    priceAnnual: 1490,
    description: 'For agencies and teams',
    features: [
      'Everything in Pro',
      'Unlimited workspaces',
      'Client management',
      'White-label exports',
      'API access',
      'Dedicated account manager',
      'Custom integrations',
    ],
    cta: 'Start Agency',
    href: '/login',
    highlighted: false,
  },
];

export default async function PricingPage() {
  const session = await auth();
  const isLoggedIn = !!session?.user;

  return (
    <div className="max-w-6xl mx-auto px-4 py-16 sm:py-24">
      <div className="text-center mb-16">
        <h1 className="text-4xl font-bold text-gray-900 sm:text-5xl">
          Simple, transparent pricing
        </h1>
        <p className="mt-4 text-lg text-gray-600 max-w-2xl mx-auto">
          Choose the plan that fits your affiliate content needs. Upgrade, downgrade, or cancel anytime.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {tiers.map((tier) => (
          <div
            key={tier.name}
            className={`relative rounded-2xl border bg-white p-8 flex flex-col ${
              tier.highlighted
                ? 'border-brand-500 ring-2 ring-brand-500 shadow-lg scale-[1.02]'
                : 'border-gray-200 shadow-sm'
            }`}
          >
            {tier.highlighted && (
              <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-brand-600 text-white text-xs font-semibold px-3 py-1 rounded-full">
                Most Popular
              </div>
            )}

            <div className="mb-6">
              <h3 className="text-xl font-bold text-gray-900">{tier.name}</h3>
              <p className="text-sm text-gray-500 mt-1">{tier.description}</p>
            </div>

            <div className="mb-6">
              {tier.priceMonthly === 0 ? (
                <p className="text-4xl font-bold text-gray-900">Free</p>
              ) : (
                <div>
                  <p className="text-4xl font-bold text-gray-900">
                    ${tier.priceMonthly}
                    <span className="text-lg font-normal text-gray-500">/mo</span>
                  </p>
                  <p className="text-sm text-gray-400 mt-1">
                    ${tier.priceAnnual}/yr (2 months free)
                  </p>
                </div>
              )}
            </div>

            <ul className="space-y-3 mb-8 flex-1">
              {tier.features.map((feature) => (
                <li key={feature} className="flex items-start gap-2 text-sm text-gray-600">
                  <svg
                    className="h-5 w-5 text-brand-500 shrink-0 mt-0.5"
                    fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" d="m4.5 12.75 6 6 9-13.5" />
                  </svg>
                  {feature}
                </li>
              ))}
            </ul>

            <Link
              href={isLoggedIn ? '/settings/billing' : tier.href}
              className={`block text-center py-2.5 px-4 rounded-lg text-sm font-semibold transition-colors ${
                tier.highlighted
                  ? 'bg-brand-600 text-white hover:bg-brand-700'
                  : tier.priceMonthly === 0
                    ? 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                    : 'bg-brand-600 text-white hover:bg-brand-700'
              }`}
            >
              {tier.cta}
            </Link>
          </div>
        ))}
      </div>

      <p className="text-center text-sm text-gray-400 mt-12">
        All prices in USD. Subscriptions auto-renew until cancelled.{' '}
        <Link href="/login" className="text-brand-600 hover:underline">Sign in</Link>{' '}
        to manage your subscription.
      </p>
    </div>
  );
}
