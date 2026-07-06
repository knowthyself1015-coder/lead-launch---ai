"use client";

import { useEffect, useState } from "react";
import {
  Building2,
  Globe,
  Users,
  FileText,
  TrendingUp,
  DollarSign,
  Loader2,
} from "lucide-react";
import { StatsCard } from "@/components/stats-card";

interface DashboardData {
  stats: {
    totalBusinesses: number;
    totalLeads: number;
    totalClaims: number;
    totalWebsites: number;
    claimRate: string;
  };
  recentLeads: {
    id: string;
    customerName: string;
    email: string | null;
    message: string | null;
    createdAt: string;
    business: { name: string };
  }[];
}

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/dashboard")
      .then((res) => res.json())
      .then((data) => {
        setData(data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  const stats = data?.stats;

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Dashboard</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Overview of your lead generation platform.
        </p>
      </div>

      {/* Stats Grid */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
        <StatsCard
          title="Total Businesses"
          value={stats?.totalBusinesses ?? 0}
          icon={<Building2 className="h-5 w-5" />}
          trend={{ value: "discovered", positive: true }}
        />
        <StatsCard
          title="Websites Generated"
          value={stats?.totalWebsites ?? 0}
          icon={<Globe className="h-5 w-5" />}
        />
        <StatsCard
          title="Leads Captured"
          value={stats?.totalLeads ?? 0}
          icon={<Users className="h-5 w-5" />}
          trend={{ value: "new", positive: true }}
        />
        <StatsCard
          title="Claims"
          value={stats?.totalClaims ?? 0}
          icon={<FileText className="h-5 w-5" />}
        />
        <StatsCard
          title="Claim Rate"
          value={stats?.claimRate ?? "0.0%"}
          icon={<TrendingUp className="h-5 w-5" />}
          description="of businesses claimed"
        />
      </div>

      {/* Quick Actions */}
      <div className="rounded-xl border border-border bg-card p-6">
        <h2 className="text-lg font-semibold">Quick Actions</h2>
        <div className="mt-4 flex flex-wrap gap-3">
          <a
            href="/dashboard/businesses"
            className="inline-flex items-center gap-2 rounded-lg bg-primary/10 px-4 py-2 text-sm font-medium text-primary transition-colors hover:bg-primary/20"
          >
            <Building2 className="h-4 w-4" />
            View Businesses
          </a>
          <a
            href="/dashboard/leads"
            className="inline-flex items-center gap-2 rounded-lg bg-primary/10 px-4 py-2 text-sm font-medium text-primary transition-colors hover:bg-primary/20"
          >
            <Users className="h-4 w-4" />
            View Leads
          </a>
          <a
            href="/dashboard/claims"
            className="inline-flex items-center gap-2 rounded-lg bg-primary/10 px-4 py-2 text-sm font-medium text-primary transition-colors hover:bg-primary/20"
          >
            <FileText className="h-4 w-4" />
            Claim Requests
          </a>
        </div>
      </div>

      {/* Recent Activity */}
      <div className="rounded-xl border border-border bg-card">
        <div className="border-b border-border px-6 py-4">
          <h2 className="text-lg font-semibold">Recent Leads</h2>
        </div>
        <div className="divide-y divide-border">
          {data?.recentLeads && data.recentLeads.length > 0 ? (
            data.recentLeads.map((lead) => (
              <div
                key={lead.id}
                className="flex items-center justify-between px-6 py-4"
              >
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium truncate">
                    {lead.customerName}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {lead.business.name}
                    {lead.email && ` · ${lead.email}`}
                  </p>
                </div>
                <p className="text-xs text-muted-foreground shrink-0 ml-4">
                  {new Date(lead.createdAt).toLocaleDateString()}
                </p>
              </div>
            ))
          ) : (
            <div className="px-6 py-12 text-center text-sm text-muted-foreground">
              No leads yet. Generate some websites to start capturing leads.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}