import { prisma } from '@affiliate/db';
import { auth } from '@/lib/auth';

export default async function DashboardPage() {
  const session = await auth();
  const userId = (session?.user as any)?.id as string;

  const user = await prisma.user.findUnique({
    where: { id: userId },
    select: {
      name: true,
      email: true,
      affiliateTag: true,
      trackingId: true,
      tier: true,
      createdAt: true,
    },
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="text-gray-600 mt-1">Welcome{user?.name ? `, ${user.name}` : ''}!</p>
      </div>

      {/* Account Info */}
      <section className="bg-white rounded-xl border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Account</h2>
        <dl className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <dt className="text-sm text-gray-500">Email</dt>
            <dd className="text-gray-900">{user?.email}</dd>
          </div>
          <div>
            <dt className="text-sm text-gray-500">Plan</dt>
            <dd className="text-gray-900 capitalize">{user?.tier}</dd>
          </div>
          <div>
            <dt className="text-sm text-gray-500">Member since</dt>
            <dd className="text-gray-900">
              {user?.createdAt ? new Date(user.createdAt).toLocaleDateString() : '—'}
            </dd>
          </div>
        </dl>
      </section>

      {/* Affiliate Info */}
      <section className="bg-white rounded-xl border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Amazon Associates</h2>
        <dl className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <dt className="text-sm text-gray-500">Affiliate Tag</dt>
            <dd className="text-gray-900 font-mono">{user?.affiliateTag || '—'}</dd>
          </div>
          <div>
            <dt className="text-sm text-gray-500">Tracking ID</dt>
            <dd className="text-gray-900 font-mono">{user?.trackingId || '—'}</dd>
          </div>
        </dl>
      </section>

      {/* Quick Actions */}
      <section className="bg-white rounded-xl border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Quick Actions</h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <a
            href="/workspace"
            className="flex flex-col items-center gap-2 rounded-lg border border-gray-200 p-4 hover:border-brand-300 hover:bg-brand-50 transition-colors"
          >
            <span className="text-2xl">🎬</span>
            <span className="text-sm font-medium text-gray-900">Create Content</span>
          </a>
          <a
            href="/profile"
            className="flex flex-col items-center gap-2 rounded-lg border border-gray-200 p-4 hover:border-brand-300 hover:bg-brand-50 transition-colors"
          >
            <span className="text-2xl">⚙️</span>
            <span className="text-sm font-medium text-gray-900">Edit Profile</span>
          </a>
          <a
            href="/workspace?tab=history"
            className="flex flex-col items-center gap-2 rounded-lg border border-gray-200 p-4 hover:border-brand-300 hover:bg-brand-50 transition-colors"
          >
            <span className="text-2xl">📋</span>
            <span className="text-sm font-medium text-gray-900">View History</span>
          </a>
        </div>
      </section>
    </div>
  );
}
