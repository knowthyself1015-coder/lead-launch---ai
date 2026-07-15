import { auth } from '@/lib/auth';
import { redirect } from 'next/navigation';
import { prisma } from '@affiliate/db';
import Link from 'next/link';
import { ProductImporter } from './ProductImporter';

export const metadata = {
  title: 'Products — AffiliateContent AI',
};

export default async function ProductsPage() {
  const session = await auth();
  if (!session?.user) redirect('/login');

  let products: any[] = [];
  let dbError = false;

  try {
    products = await prisma.product.findMany({
      orderBy: { createdAt: 'desc' },
      include: {
        _count: { select: { generations: true } },
      },
      take: 50,
    });
  } catch {
    dbError = true;
  }

  return (
    <div className="max-w-6xl mx-auto px-4 py-10">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Products</h1>
          <p className="text-gray-600 mt-1">
            Import and manage your Amazon affiliate products.
          </p>
        </div>
      </div>

      {/* Product Importer */}
      <ProductImporter />

      {/* Product List */}
      <section className="mt-8">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">
          {products.length > 0
            ? `Imported Products (${products.length})`
            : 'No products imported yet'}
        </h2>

        {dbError && (
          <div className="rounded-lg border border-yellow-200 bg-yellow-50 p-4 mb-4 text-sm text-yellow-800">
            Database not connected. Products will appear here once the database is set up.
          </div>
        )}

        {products.length > 0 ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {products.map((product: any) => (
              <Link
                key={product.id}
                href={`/products/${product.asin}`}
                className="group rounded-xl border border-gray-200 bg-white p-4 transition hover:border-brand-300 hover:shadow-md"
              >
                <div className="flex gap-4">
                  {product.imageUrl ? (
                    <img
                      src={product.imageUrl}
                      alt={product.title}
                      className="h-20 w-20 rounded-lg object-cover"
                    />
                  ) : (
                    <div className="flex h-20 w-20 items-center justify-center rounded-lg bg-gray-100 text-gray-400">
                      📦
                    </div>
                  )}
                  <div className="min-w-0 flex-1">
                    <h3 className="font-medium text-gray-900 truncate group-hover:text-brand-600">
                      {product.title}
                    </h3>
                    <p className="text-sm text-gray-500 mt-1">
                      {product.brand || product.category || product.asin}
                    </p>
                    {product.price && (
                      <p className="text-sm font-semibold text-gray-900 mt-1">
                        {product.price}
                      </p>
                    )}
                    <div className="flex items-center gap-3 mt-2 text-xs text-gray-400">
                      <span>ASIN: {product.asin}</span>
                      <span>{product._count?.generations ?? 0} generations</span>
                    </div>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        ) : !dbError ? (
          <div className="rounded-xl border-2 border-dashed border-gray-300 p-12 text-center">
            <span className="text-4xl">📦</span>
            <p className="mt-4 text-gray-500">
              No products yet. Import your first product above.
            </p>
            <p className="mt-1 text-sm text-gray-400">
              Try searching for: Sony WH-1000XM5, AirPods Pro, or Instant Pot
            </p>
          </div>
        ) : null}
      </section>
    </div>
  );
}
