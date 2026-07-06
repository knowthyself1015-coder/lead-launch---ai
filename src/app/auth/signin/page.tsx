import { SignInForm } from "./signin-form";

export default function SignInPage() {
  return (
    <div className="flex min-h-screen items-center justify-center px-4 py-12">
      <div className="w-full max-w-sm space-y-6">
        <div className="text-center">
          <h1 className="text-2xl font-bold">Sign In</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Sign in to your LeadLaunch AI account
          </p>
        </div>
        <SignInForm />
      </div>
    </div>
  );
}
