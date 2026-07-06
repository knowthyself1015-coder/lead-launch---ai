"use client";

import { useEffect, useState } from "react";
import { Loader2, FileText } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

interface Claim {
  id: string;
  status: string;
  verificationMethod: string | null;
  createdAt: string;
  business: { name: string; slug: string };
  user: { email: string; name: string | null } | null;
}

export default function ClaimsPage() {
  const [claims, setClaims] = useState<Claim[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/claim")
      .then((res) => res.json())
      .then((data) => {
        setClaims(data.claims ?? []);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Claim Requests</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Business owners claiming their generated websites
        </p>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-24">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
        </div>
      ) : (
        <div className="rounded-xl border border-border bg-card">
          <div className="divide-y divide-border">
            {claims.map((claim) => (
              <div
                key={claim.id}
                className="flex items-center justify-between px-6 py-4 transition-colors hover:bg-muted/50"
              >
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <FileText className="h-4 w-4 text-muted-foreground shrink-0" />
                    <span className="text-sm font-medium">
                      {claim.business.name}
                    </span>
                    <Badge
                      variant={
                        claim.status === "PENDING"
                          ? "warning"
                          : claim.status === "VERIFIED"
                            ? "success"
                            : "destructive"
                      }
                    >
                      {claim.status}
                    </Badge>
                  </div>
                  <div className="mt-1 text-xs text-muted-foreground">
                    {claim.user
                      ? `${claim.user.name ?? claim.user.email}`
                      : "No user associated"}
                    {claim.verificationMethod &&
                      ` · ${claim.verificationMethod}`}
                  </div>
                </div>
                <div className="flex items-center gap-3 shrink-0 ml-4">
                  <span className="text-xs text-muted-foreground">
                    {new Date(claim.createdAt).toLocaleDateString()}
                  </span>
                  <Button variant="ghost" size="sm">
                    Review
                  </Button>
                </div>
              </div>
            ))}
            {claims.length === 0 && (
              <div className="px-6 py-12 text-center text-sm text-muted-foreground">
                No claim requests yet.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}