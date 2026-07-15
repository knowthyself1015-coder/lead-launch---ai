"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  Loader2,
  CheckCircle2,
  Mail,
  KeyRound,
  ArrowRight,
  Sparkles,
  Shield,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

interface ClaimButtonProps {
  businessId: string;
  businessName: string;
  businessSlug: string;
}

export function ClaimButton({
  businessId,
  businessName,
  businessSlug,
}: ClaimButtonProps) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleInitiate = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (!email.trim()) {
      setError("Please enter your email address.");
      return;
    }

    setLoading(true);

    try {
      const res = await fetch("/api/claim/initiate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          businessSlug,
          email: email.trim(),
        }),
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.error || "Failed to send verification code");
      }

      setLoading(false);
      setStep(2);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Something went wrong. Please try again."
      );
      setLoading(false);
    }
  };

  const handleVerify = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (!code.trim()) {
      setError("Please enter the verification code.");
      return;
    }

    setLoading(true);

    try {
      const res = await fetch("/api/claim/verify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          businessSlug,
          email: email.trim(),
          code: code.trim(),
        }),
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.error || "Verification failed");
      }

      setLoading(false);
      setStep(3);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Verification failed. Please try again."
      );
      setLoading(false);
    }
  };

  const handleRedirect = () => {
    setOpen(false);
    router.push("/auth/signin");
  };

  const handleClose = () => {
    setOpen(false);
    // Reset after a brief delay so the animation plays
    setTimeout(() => {
      setStep(1);
      setEmail("");
      setCode("");
      setError("");
    }, 300);
  };

  return (
    <>
      {/* Claim Button */}
      <div className="border-t border-border px-4 py-8">
        <div className="mx-auto max-w-lg text-center">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
            <Shield className="h-6 w-6 text-primary" />
          </div>
          <h3 className="mt-4 text-lg font-semibold">
            Is this your business?
          </h3>
          <p className="mt-1 text-sm text-muted-foreground">
            Claim this website to manage your online presence, respond to leads,
            and update your business information.
          </p>
          <Button
            size="lg"
            className="mt-6"
            onClick={() => setOpen(true)}
          >
            <Sparkles className="h-4 w-4" />
            Claim This Site
            <ArrowRight className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Claim Modal */}
      <Dialog open={open} onOpenChange={handleClose}>
        <DialogContent className="sm:max-w-md">
          {step === 1 && (
            <>
              <DialogHeader>
                <DialogTitle>Claim Your Website</DialogTitle>
                <DialogDescription>
                  Enter your email to verify you own {businessName}.
                </DialogDescription>
              </DialogHeader>
              <form onSubmit={handleInitiate} className="space-y-4">
                <div className="space-y-2">
                  <label
                    htmlFor="claim-email"
                    className="text-sm font-medium"
                  >
                    Email Address
                  </label>
                  <div className="relative">
                    <Mail className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                    <Input
                      id="claim-email"
                      type="email"
                      placeholder="you@example.com"
                      className="pl-9"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                    />
                  </div>
                </div>
                {error && (
                  <p className="text-sm text-red-500">{error}</p>
                )}
                <Button type="submit" className="w-full" disabled={loading}>
                  {loading ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Sending code...
                    </>
                  ) : (
                    <>
                      Send Verification Code
                      <ArrowRight className="h-4 w-4" />
                    </>
                  )}
                </Button>
              </form>
            </>
          )}

          {step === 2 && (
            <>
              <DialogHeader>
                <DialogTitle>Check Your Email</DialogTitle>
                <DialogDescription>
                  We sent a verification code to {email}. Enter it below to
                  confirm ownership.
                </DialogDescription>
              </DialogHeader>
              <form onSubmit={handleVerify} className="space-y-4">
                <div className="space-y-2">
                  <label
                    htmlFor="claim-code"
                    className="text-sm font-medium"
                  >
                    Verification Code
                  </label>
                  <div className="relative">
                    <KeyRound className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                    <Input
                      id="claim-code"
                      placeholder="Enter 6-digit code"
                      className="pl-9 text-center text-lg tracking-widest"
                      value={code}
                      onChange={(e) => setCode(e.target.value)}
                      maxLength={6}
                    />
                  </div>
                </div>
                {error && (
                  <p className="text-sm text-red-500">{error}</p>
                )}
                <Button type="submit" className="w-full" disabled={loading}>
                  {loading ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Verifying...
                    </>
                  ) : (
                    <>
                      Verify Ownership
                      <ArrowRight className="h-4 w-4" />
                    </>
                  )}
                </Button>
                <button
                  type="button"
                  onClick={() => {
                    setStep(1);
                    setError("");
                  }}
                  className="w-full text-center text-sm text-muted-foreground underline hover:text-foreground"
                >
                  Use a different email
                </button>
              </form>
            </>
          )}

          {step === 3 && (
            <>
              <DialogHeader>
                <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-emerald-100 dark:bg-emerald-900">
                  <CheckCircle2 className="h-8 w-8 text-emerald-600 dark:text-emerald-400" />
                </div>
                <DialogTitle className="text-center mt-4">
                  Claim Submitted!
                </DialogTitle>
                <DialogDescription className="text-center">
                  Your claim for <strong>{businessName}</strong> has been
                  submitted. An admin will review and verify your ownership
                  shortly.
                </DialogDescription>
              </DialogHeader>
              <div className="flex flex-col gap-3 pt-2">
                <Button className="w-full" onClick={handleRedirect}>
                  Sign In to Your Account
                  <ArrowRight className="h-4 w-4" />
                </Button>
                <Button
                  variant="ghost"
                  className="w-full"
                  onClick={handleClose}
                >
                  Close
                </Button>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}