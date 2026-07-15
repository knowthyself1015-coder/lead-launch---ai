import { auth } from '@/lib/auth';
import { redirect } from 'next/navigation';
import { prisma } from '@affiliate/db';
import Link from 'next/link';
import { ProductActions } from './ProductActions';

export const metadata = {
  title: 'Product Workspace — AffiliateContent AI',
};

interface ProductPageProps {
  params: Promise<{ id: string }>;
}

export default async function ProductWorkspacePage({ params }: ProductPageProps) {
  const session = await auth();
  if (!session?.user) redirect('/login');

  const { id } = await params;
  const asin = id.toUpperCase();

  let product: any = null;
  const generations: any[] = [];

  try {
    product = await prisma.product.findUnique({
      where: { asin },
      include: {
        generations: {
          orderBy: { createdAt: 'desc' },
          take: 20,
        },
      },
    });
  } catch {
    // DB not connected — will show mock data
  }

  if (!product) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-10">
        <div className="rounded-xl border border-gray-200 bg-white p-12 text-center">
          <span className="text-5xl">📦</span>
          <h1 className="mt-4 text-xl font-semibold text-gray-900">Product Not Found</h1>
          <p className="mt-2 text-gray-500">
            ASIN: <code className="font-mono bg-gray-100 px-1 rounded">{asin}</code>
          </p>
          <p className="mt-1 text-sm text-gray-400">
            Try importing this product first from the{' '}
            <Link href="/products" className="text-brand-600 underline">
              Products page
            </Link>
            .
          </p>
          <Link
            href="/products"
            className="mt-6 inline-block rounded-lg bg-brand-600 px-6 py-2 text-sm font-medium text-white hover:bg-brand-700"
          >
            ← Back to Products
          </Link>
        </div>
      </div>
    );
  }

  // Parse features from generations
  const recentGenerations = (product.generations || []).map((g: any) => ({
    ...g,
    createdAt: g.createdAt ? new Date(g.createdAt).toLocaleDateString() : '',
    outputPreview: g.outputData
      ? typeof g.outputData === 'object' && (g.outputData as any).script
        ? (g.outputData as any).script.slice(0, 150) + '...'
        : JSON.stringify(g.outputData).slice(0, 150) + '...'
      : '',
  }));

  return (
    <div className="max-w-6xl mx-auto px-4 py-10">
      {/* Breadcrumb */}
      <div className="mb-6">
        <Link href="/products" className="text-sm text-brand-600 hover:text-brand-700">
          ← Back to Products
        </Link>
      </div>

      {/* Product Header */}
      <div className="rounded-xl border border-gray-200 bg-white p-6 mb-6">
        <div className="flex flex-col sm:flex-row gap-6">
          {/* Image */}
          {product.imageUrl ? (
            <img
              src={product.imageUrl}
              alt={product.title}
              className="h-48 w-48 rounded-xl object-cover"
            />
          ) : (
            <div className="flex h-48 w-48 items-center justify-center rounded-xl bg-gray-100 text-6xl text-gray-300">
              📦
            </div>
          )}

          {/* Details */}
          <div className="flex-1 min-w-0">
            <h1 className="text-2xl font-bold text-gray-900">{product.title}</h1>

            <div className="flex flex-wrap gap-2 mt-3">
              {product.brand && (
                <span className="rounded-full bg-blue-50 px-3 py-1 text-xs font-medium text-blue-700">
                  {product.brand}
                </span>
              )}
              {product.category && (
                <span className="rounded-full bg-green-50 px-3 py-1 text-xs font-medium text-green-700">
                  {product.category}
                </span>
              )}
              {product.price && (
                <span className="rounded-full bg-yellow-50 px-3 py-1 text-xs font-medium text-yellow-700">
                  {product.price}
                </span>
              )}
            </div>

            {product.description && (
              <p className="mt-4 text-sm text-gray-600 line-clamp-3">{product.description}</p>
            )}

            {/* Affiliate URL */}
            <div className="mt-4">
              <label className="text-xs font-medium text-gray-500">Affiliate URL</label>
              <div className="mt-1 flex gap-2">
                <input
                  readOnly
                  value={product.url || `https://www.amazon.com/dp/${asin}?tag=${(session.user as any).affiliateTag || 'affiliatecontent-20'}`}
                  className="flex-1 rounded-lg border border-gray-300 bg-gray-50 px-3 py-2 font-mono text-xs text-gray-600"
                />
                <CopyButton text={product.url || `https://www.amazon.com/dp/${asin}`} />
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Action Buttons */}
      <ProductActions asin={asin} productTitle={product.title} />

      {/* Generated Content History */}
      <section className="mt-8">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">
          Generated Content History
        </h2>

        {recentGenerations.length > 0 ? (
          <div className="space-y-3">
            {recentGenerations.map((gen: any) => (
              <div
                key={gen.id}
                className="rounded-lg border border-gray-200 bg-white p-4"
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span className="rounded bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600">
                      {gen.type}
                    </span>
                    {gen.platform && (
                      <span className="rounded bg-brand-50 px-2 py-0.5 text-xs font-medium text-brand-600">
                        {gen.platform}
                      </span>
                    )}
                    <span
                      className={`rounded px-2 py-0.5 text-xs font-medium ${
                        gen.status === 'completed'
                          ? 'bg-green-50 text-green-600'
                          : gen.status === 'failed'
                            ? 'bg-red-50 text-red-600'
                            : 'bg-yellow-50 text-yellow-600'
                      }`}
                    >
                      {gen.status}
                    </span>
                  </div>
                  <span className="text-xs text-gray-400">{gen.createdAt}</span>
                </div>
                {gen.outputPreview && (
                  <p className="text-sm text-gray-600">{gen.outputPreview}</p>
                )}
              </div>
            ))}
          </div>
        ) : (
          <div className="rounded-xl border-2 border-dashed border-gray-300 p-8 text-center">
            <span className="text-3xl">📝</span>
            <p className="mt-3 text-gray-500">
              No content generated yet. Use the actions above to start creating.
            </p>
          </div>
        )}
      </section>
    </div>
  );
}

// ── Copy Button (client component) ──

function CopyButton({ text }: { text: string }) {
  'use client';
  return (
    <button
      onClick={() => {
        navigator.clipboard.writeText(text);
      }}
      className="rounded-lg border border-gray-300 px-3 py-2 text-xs font-medium text-gray-600 hover:bg-gray-50 transition"
    >
      Copy
    </button>
  );
}
