"use client";

import { useState } from "react";
import Link from "next/link";
import {
  Megaphone,
  Plus,
  Search,
  Mail,
  MessageSquare,
  Star,
  Share2,
  TrendingUp,
  Eye,
  MousePointerClick,
  CheckCircle2,
  MoreHorizontal,
  Loader2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Select } from "@/components/ui/select";

const typeIcons: Record<string, typeof Mail> = {
  email: Mail,
  sms: MessageSquare,
  review_request: Star,
  social: Share2,
};

const typeLabels: Record<string, string> = {
  email: "Email",
  sms: "SMS",
  review_request: "Review Request",
  social: "Social",
};

// Mock campaigns data
const mockCampaigns = [
  {
    id: "1",
    name: "Summer Plumbing Checkup",
    type: "email",
    status: "active",
    stats: { sent: 1240, opened: 687, converted: 43 },
    createdAt: "2026-06-15",
  },
  {
    id: "2",
    name: "Follow-up: Drain Cleaning",
    type: "sms",
    status: "active",
    stats: { sent: 520, opened: 410, converted: 28 },
    createdAt: "2026-06-20",
  },
  {
    id: "3",
    name: "Request a Review",
    type: "review_request",
    status: "paused",
    stats: { sent: 890, opened: 534, converted: 67 },
    createdAt: "2026-06-10",
  },
  {
    id: "4",
    name: "Holiday Promotion",
    type: "social",
    status: "draft",
    stats: { sent: 0, opened: 0, converted: 0 },
    createdAt: "2026-06-25",
  },
  {
    id: "5",
    name: "Water Heater Special",
    type: "email",
    status: "completed",
    stats: { sent: 2100, opened: 1102, converted: 89 },
    createdAt: "2026-05-01",
  },
];

export default function CampaignsPage() {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState("");

  const filtered = mockCampaigns.filter((c) => {
    const matchesSearch = c.name.toLowerCase().includes(search.toLowerCase());
    const matchesStatus = !statusFilter || c.status === statusFilter;
    const matchesType = !typeFilter || c.type === typeFilter;
    return matchesSearch && matchesStatus && matchesType;
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Campaigns</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Create and manage marketing campaigns for your businesses.
          </p>
        </div>
        <Button asChild>
          <Link href="/dashboard/campaigns/new">
            <Plus className="h-4 w-4" />
            Create Campaign
          </Link>
        </Button>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <div className="relative max-w-xs flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search campaigns..."
            className="pl-9"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <Select
          options={[
            { value: "", label: "All Statuses" },
            { value: "active", label: "Active" },
            { value: "paused", label: "Paused" },
            { value: "draft", label: "Draft" },
            { value: "completed", label: "Completed" },
          ]}
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          placeholder="All Statuses"
          className="w-36"
        />
        <Select
          options={[
            { value: "", label: "All Types" },
            { value: "email", label: "Email" },
            { value: "sms", label: "SMS" },
            { value: "review_request", label: "Review Request" },
            { value: "social", label: "Social" },
          ]}
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
          placeholder="All Types"
          className="w-36"
        />
      </div>

      {/* Campaign list */}
      <div className="space-y-3">
        {filtered.map((campaign) => {
          const TypeIcon = typeIcons[campaign.type] || Mail;
          const rate =
            campaign.stats.sent > 0
              ? Math.round(
                  (campaign.stats.converted / campaign.stats.sent) * 100
                )
              : 0;

          return (
            <Link key={campaign.id} href={`/dashboard/campaigns/${campaign.id}`}>
              <Card className="transition-all hover:shadow-md hover:border-primary/20">
                <CardContent className="flex items-center gap-4 p-5">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                    <TypeIcon className="h-5 w-5" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium">
                        {campaign.name}
                      </span>
                      <Badge
                        variant={
                          campaign.status === "active"
                            ? "success"
                            : campaign.status === "paused"
                              ? "warning"
                              : campaign.status === "draft"
                                ? "secondary"
                                : "default"
                        }
                      >
                        {campaign.status}
                      </Badge>
                      <Badge variant="outline">
                        {typeLabels[campaign.type]}
                      </Badge>
                    </div>
                    <div className="mt-1 flex items-center gap-4 text-xs text-muted-foreground">
                      <span className="flex items-center gap-1">
                        <TrendingUp className="h-3 w-3" />
                        {campaign.stats.sent.toLocaleString()} sent
                      </span>
                      <span className="flex items-center gap-1">
                        <Eye className="h-3 w-3" />
                        {campaign.stats.opened.toLocaleString()} opened
                      </span>
                      <span className="flex items-center gap-1">
                        <MousePointerClick className="h-3 w-3" />
                        {campaign.stats.converted} converted
                      </span>
                      <span className="text-emerald-600 font-medium">
                        {rate}% rate
                      </span>
                    </div>
                  </div>
                  <span className="text-xs text-muted-foreground shrink-0 hidden sm:block">
                    {new Date(campaign.createdAt).toLocaleDateString()}
                  </span>
                </CardContent>
              </Card>
            </Link>
          );
        })}
        {filtered.length === 0 && (
          <div className="rounded-xl border border-border bg-card py-16 text-center">
            <Megaphone className="mx-auto h-8 w-8 text-muted-foreground" />
            <h3 className="mt-4 text-sm font-medium">No campaigns found</h3>
            <p className="mt-1 text-sm text-muted-foreground">
              {search || statusFilter || typeFilter
                ? "Try adjusting your filters."
                : "Create your first campaign to get started."}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}