'use client';

import { useRouter } from 'next/navigation';

interface ProductActionsProps {
  asin: string;
  productTitle: string;
}

export function ProductActions({ asin, productTitle }: ProductActionsProps) {
  const router = useRouter();

  const actions = [
    {
      label: 'Create Script',
      icon: '📝',
      desc: 'YouTube, TikTok, or blog script',
      href: `/writer?asin=${asin}&title=${encodeURIComponent(productTitle)}`,
    },
    {
      label: 'Create Video',
      icon: '🎬',
      desc: 'Generate product video',
      href: `/workspace?tab=video&asin=${asin}`,
    },
    {
      label: 'Create Blog',
      icon: '📄',
      desc: 'Full blog article or review',
      href: `/writer?asin=${asin}&type=blog_article&title=${encodeURIComponent(productTitle)}`,
    },
    {
      label: 'Create Social Posts',
      icon: '📱',
      desc: 'Instagram, TikTok, Facebook',
      href: `/writer?asin=${asin}&type=tiktok&title=${encodeURIComponent(productTitle)}`,
    },
    {
      label: 'Export Assets',
      icon: '📦',
      desc: 'Download all content',
      href: `/workspace?tab=export&asin=${asin}`,
    },
  ];

  return (
    <section className="rounded-xl border border-gray-200 bg-white p-6">
      <h2 className="text-lg font-semibold text-gray-900 mb-4">Actions</h2>
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        {actions.map((action) => (
          <button
            key={action.label}
            onClick={() => router.push(action.href)}
            className="flex flex-col items-center gap-2 rounded-lg border border-gray-200 p-4 text-center transition hover:border-brand-300 hover:bg-brand-50"
          >
            <span className="text-2xl">{action.icon}</span>
            <span className="text-sm font-medium text-gray-900">{action.label}</span>
            <span className="text-xs text-gray-500">{action.desc}</span>
          </button>
        ))}
      </div>
    </section>
  );
}
