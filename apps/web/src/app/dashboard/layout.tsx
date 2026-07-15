import { auth } from '@/lib/auth';
import { redirect } from 'next/navigation';
import Sidebar from '@/components/Sidebar';

export default async function DashboardLayout({ children }: { children: React.ReactNode }) {
  const session = await auth();

  if (!session?.user) redirect('/login');
  if (!(session.user as any).onboardingCompleted) redirect('/onboarding');

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex-1 bg-gray-50">
        <div className="p-8">{children}</div>
      </main>
    </div>
  );
}
