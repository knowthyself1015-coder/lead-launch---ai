'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';

export function ProductImporter() {
  const router = useRouter();
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<any>(null);

  async function handleImport(e: React.FormEvent) {
    e.preventDefault();
    if (!input.trim()) return;

    setLoading(true);
    setError('');
    setResult(null);

    try {
      // Use the internal API route proxy (same origin to avoid CORS)
      const res = await fetch('/api/proxy/products/import', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ input: input.trim() }),
      });

      const data = await res.json();

      if (!data.success) {
        setError(data.error || 'Import failed');
        return;
      }

      setResult(data.data);

      // Navigate to product workspace after a brief delay
      setTimeout(() => {
        router.push(`/products/${data.data.asin}`);
        router.refresh();
      }, 1000);
    } catch (err: any) {
      setError(err.message || 'Network error');
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="rounded-xl border border-gray-200 bg-white p-6">
      <h2 className="text-lg font-semibold text-gray-900 mb-3">Import Product</h2>
      <form onSubmit={handleImport} className="flex gap-3">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Amazon URL, ASIN, or product name (e.g., B08N5WRWNW or Sony headphones)"
          className="flex-1 rounded-lg border border-gray-300 px-4 py-2.5 text-sm focus:border-brand-500 focus:ring-2 focus:ring-brand-200 focus:outline-none"
          disabled={loading}
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="rounded-lg bg-brand-600 px-6 py-2.5 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50 transition"
        >
          {loading ? 'Importing...' : 'Import'}
        </button>
      </form>

      {error && (
        <div className="mt-3 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {result && (
        <div className="mt-3 rounded-lg border border-green-200 bg-green-50 p-3 text-sm text-green-700">
          ✓ Imported: <strong>{result.title}</strong> — redirecting...
        </div>
      )}
    </section>
  );
}
