import Link from 'next/link';

export default function SettingsPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Settings</h1>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <Link
          href="/settings/billing"
          className="bg-white rounded-xl border border-gray-200 p-6 hover:border-brand-300 hover:shadow-sm transition-all"
        >
          <div className="text-2xl mb-2">💳</div>
          <h2 className="text-lg font-semibold text-gray-900">Billing & Subscription</h2>
          <p className="text-sm text-gray-500 mt-1">
            Manage your plan, payment methods, and invoices.
          </p>
        </Link>

        <Link
          href="/profile"
          className="bg-white rounded-xl border border-gray-200 p-6 hover:border-brand-300 hover:shadow-sm transition-all"
        >
          <div className="text-2xl mb-2">👤</div>
          <h2 className="text-lg font-semibold text-gray-900">Profile</h2>
          <p className="text-sm text-gray-500 mt-1">
            Update your name, email, and affiliate settings.
          </p>
        </Link>

        <div className="bg-white rounded-xl border border-gray-100 p-6 opacity-50">
          <div className="text-2xl mb-2">🔔</div>
          <h2 className="text-lg font-semibold text-gray-900">Notifications</h2>
          <p className="text-sm text-gray-500 mt-1">Coming soon</p>
        </div>
      </div>
    </div>
  );
}
