"use client";

import { useEffect, useState } from "react";
import {
  Loader2,
  FileText,
  CheckCircle2,
  XCircle,
  ExternalLink,
  Eye,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Card, CardContent } from "@/components/ui/card";

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
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [selectedClaim, setSelectedClaim] = useState<Claim | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);

  const fetchClaims = async () => {
    try {
      const res = await fetch("/api/claim");
      const data = await res.json();
      setClaims(data.claims ?? []);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchClaims();
  }, []);

  const handleAction = async (claimId: string, status: "VERIFIED" | "REJECTED") => {
    setActionLoading(claimId);
    try {
      const res = await fetch(`/api/claim/${claimId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.error || "Failed to update claim");
      }

      // Refresh the list
      await fetchClaims();
      setDetailOpen(false);
      setSelectedClaim(null);
    } catch (err) {
      console.error("Failed to update claim:", err);
    } finally {
      setActionLoading(null);
    }
  };

  const openDetail = (claim: Claim) => {
    setSelectedClaim(claim);
    setDetailOpen(true);
  };

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
                <div className="flex items-center gap-2 shrink-0 ml-4">
                  <span className="text-xs text-muted-foreground hidden sm:block">
                    {new Date(claim.createdAt).toLocaleDateString()}
                  </span>

                  {/* Pending claims: show action buttons */}
                  {claim.status === "PENDING" && (
                    <>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => openDetail(claim)}
                      >
                        <Eye className="h-3.5 w-3.5 mr-1" />
                        Review
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-emerald-600 hover:text-emerald-700 hover:bg-emerald-50 dark:hover:bg-emerald-950"
                        onClick={() => handleAction(claim.id, "VERIFIED")}
                        disabled={actionLoading === claim.id}
                      >
                        {actionLoading === claim.id ? (
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        ) : (
                          <CheckCircle2 className="h-3.5 w-3.5" />
                        )}
                        <span className="hidden sm:inline ml-1">Approve</span>
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-red-600 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-950"
                        onClick={() => handleAction(claim.id, "REJECTED")}
                        disabled={actionLoading === claim.id}
                      >
                        {actionLoading === claim.id ? (
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        ) : (
                          <XCircle className="h-3.5 w-3.5" />
                        )}
                        <span className="hidden sm:inline ml-1">Reject</span>
                      </Button>
                    </>
                  )}

                  {/* Non-pending claims: show view button */}
                  {claim.status !== "PENDING" && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => openDetail(claim)}
                    >
                      <Eye className="h-3.5 w-3.5 mr-1" />
                      View
                    </Button>
                  )}
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

      {/* Detail Modal */}
      <Dialog open={detailOpen} onOpenChange={setDetailOpen}>
        <DialogContent className="sm:max-w-lg">
          {selectedClaim && (
            <>
              <DialogHeader>
                <DialogTitle>Claim Details</DialogTitle>
                <DialogDescription>
                  Review the claim request for {selectedClaim.business.name}
                </DialogDescription>
              </DialogHeader>

              <div className="space-y-4">
                {/* Business info */}
                <div className="rounded-lg border border-border p-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-medium">
                        {selectedClaim.business.name}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        Slug: /{selectedClaim.business.slug}
                      </p>
                    </div>
                    <Badge
                      variant={
                        selectedClaim.status === "PENDING"
                          ? "warning"
                          : selectedClaim.status === "VERIFIED"
                            ? "success"
                            : "destructive"
                      }
                    >
                      {selectedClaim.status}
                    </Badge>
                  </div>
                </div>

                {/* Claimant info */}
                <div className="rounded-lg border border-border p-4">
                  <p className="text-sm font-medium">Claimant</p>
                  <p className="mt-1 text-sm text-muted-foreground">
                    {selectedClaim.user
                      ? selectedClaim.user.name ?? "No name provided"
                      : "No user account"}
                  </p>
                  {selectedClaim.user && (
                    <p className="text-xs text-muted-foreground">
                      {selectedClaim.user.email}
                    </p>
                  )}
                </div>

                {/* Verification info */}
                <div className="rounded-lg border border-border p-4">
                  <p className="text-sm font-medium">Verification</p>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Method: {selectedClaim.verificationMethod ?? "Not specified"}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    Submitted:{" "}
                    {new Date(selectedClaim.createdAt).toLocaleString()}
                  </p>
                </div>
              </div>

              {/* Action buttons for PENDING */}
              {selectedClaim.status === "PENDING" && (
                <div className="flex gap-3">
                  <Button
                    className="flex-1 bg-emerald-600 hover:bg-emerald-700"
                    onClick={() => handleAction(selectedClaim.id, "VERIFIED")}
                    disabled={actionLoading === selectedClaim.id}
                  >
                    {actionLoading === selectedClaim.id ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <CheckCircle2 className="h-4 w-4" />
                    )}
                    Approve Claim
                  </Button>
                  <Button
                    variant="outline"
                    className="flex-1 border-red-300 text-red-600 hover:bg-red-50 dark:border-red-800 dark:hover:bg-red-950"
                    onClick={() => handleAction(selectedClaim.id, "REJECTED")}
                    disabled={actionLoading === selectedClaim.id}
                  >
                    {actionLoading === selectedClaim.id ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <XCircle className="h-4 w-4" />
                    )}
                    Reject Claim
                  </Button>
                </div>
              )}
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}