import { auth } from '@/lib/auth';
import { redirect } from 'next/navigation';
import { prisma } from '@affiliate/db';
import { revalidatePath } from 'next/cache';

export default async function OnboardingPage() {
  const session = await auth();

  if (!session?.user) {
    redirect('/login');
  }

  if ((session.user as any).onboardingCompleted) {
    redirect('/dashboard');
  }

  async function saveTrackingId(formData: FormData) {
    'use server';
    const session = await auth();
    if (!session?.user) redirect('/login');

    const affiliateTag = formData.get('affiliateTag') as string;
    const trackingId = formData.get('trackingId') as string;

    await prisma.user.update({
      where: { id: (session.user as any).id },
      data: {
        affiliateTag: affiliateTag || null,
        trackingId: trackingId || null,
        onboardingCompleted: true,
      },
    });

    revalidatePath('/dashboard');
    redirect('/dashboard');
  }

  return (
    <div className="min-h-[80vh] flex items-center justify-center">
      <div className="w-full max-w-md p-8 space-y-6">
        <div className="text-center">
          <h1 className="text-3xl font-bold text-gray-900">Set up your affiliate ID</h1>
          <p className="mt-2 text-gray-600">
            Connect your Amazon Associates account to start generating content with your tracking ID.
          </p>
        </div>

        <form action={saveTrackingId} className="space-y-5">
          <div>
            <label htmlFor="affiliateTag" className="block text-sm font-medium text-gray-700 mb-1">
              Amazon Associates Tag
            </label>
            <input
              id="affiliateTag"
              name="affiliateTag"
              type="text"
              required
              placeholder="youramazontag-20"
              className="w-full rounded-lg border border-gray-300 px-4 py-3 text-gray-900 placeholder-gray-400 focus:border-brand-500 focus:ring-2 focus:ring-brand-200 outline-none"
            />
            <p className="mt-1 text-xs text-gray-500">
              Found in your Amazon Associates dashboard under &quot;Tracking IDs&quot;.
            </p>
          </div>

          <div>
            <label htmlFor="trackingId" className="block text-sm font-medium text-gray-700 mb-1">
              Tracking ID (optional)
            </label>
            <input
              id="trackingId"
              name="trackingId"
              type="text"
              placeholder="Custom tracking identifier"
              className="w-full rounded-lg border border-gray-300 px-4 py-3 text-gray-900 placeholder-gray-400 focus:border-brand-500 focus:ring-2 focus:ring-brand-200 outline-none"
            />
          </div>

          <button
            type="submit"
            className="w-full rounded-lg bg-brand-600 px-4 py-3 text-white font-medium hover:bg-brand-700 transition-colors"
          >
            Complete Setup
          </button>

          <p className="text-center text-xs text-gray-500">
            You can change this anytime in your profile settings.
          </p>
        </form>
      </div>
    </div>
  );
}
