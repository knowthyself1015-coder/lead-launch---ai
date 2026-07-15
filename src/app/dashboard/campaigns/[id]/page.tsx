"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  ArrowLeft,
  Mail,
  MessageSquare,
  Star,
  Share2,
  TrendingUp,
  Eye,
  MousePointerClick,
  Send,
  Pause,
  Play,
  Copy,
  BarChart3,
  Calendar,
  Target,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StatsCard } from "@/components/stats-card";

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

// Mock campaign detail
const mockCampaign = {
  id: "1",
  name: "Summer Plumbing Checkup",
  type: "email",
  status: "active",
  stats: { sent: 1240, opened: 687, converted: 43 },
  createdAt: "2026-06-15",
  message: {
    subject: "Beat the heat — book your summer plumbing checkup!",
    body: "Hi {{customer_name}},\n\nSummer is here, and your plumbing system works harder than ever. At Johnson's Plumbing, we recommend a seasonal checkup to prevent costly emergency repairs.\n\nBook your summer checkup today and save 10%!",
  },
  audience: "Customers in Austin, TX who haven't had a checkup in 6+ months",
  schedule: "Sends every Monday at 10:00 AM",
};

export default function CampaignDetailPage() {
  const params = useParams();
  const campaign = mockCampaign;
  const TypeIcon = typeIcons[campaign.type] || Mail;
  const rate =
    campaign.stats.sent > 0
      ? Math.round((campaign.stats.converted / campaign.stats.sent) * 100)
      : 0;

  return (
    <div className="space-y-6">
      {/* Back link */}
      <div>
        <Link
          href="/dashboard/campaigns"
          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Campaigns
        </Link>
      </div>

      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
              <TypeIcon className="h-5 w-5" />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight">
                {campaign.name}
              </h1>
              <div className="mt-1 flex items-center gap-2">
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
            </div>
          </div>
        </div>

        {/* Action buttons */}
        <div className="flex flex-wrap gap-2">
          {campaign.status === "active" && (
            <Button variant="outline" size="sm">
              <Pause className="h-3.5 w-3.5" />
              Pause
            </Button>
          )}
          {campaign.status === "paused" && (
            <Button variant="outline" size="sm">
              <Play className="h-3.5 w-3.5" />
              Resume
            </Button>
          )}
          <Button variant="outline" size="sm">
            <Copy className="h-3.5 w-3.5" />
            Duplicate
          </Button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatsCard
          title="Sent"
          value={campaign.stats.sent.toLocaleString()}
          icon={<Send className="h-5 w-5" />}
        />
        <StatsCard
          title="Opened"
          value={campaign.stats.opened.toLocaleString()}
          icon={<Eye className="h-5 w-5" />}
          trend={{
            value: `${Math.round((campaign.stats.opened / campaign.stats.sent) * 100)}% open rate`,
            positive: true,
          }}
        />
        <StatsCard
          title="Converted"
          value={campaign.stats.converted}
          icon={<MousePointerClick className="h-5 w-5" />}
          trend={{ value: `${rate}% conversion`, positive: true }}
        />
        <StatsCard
          title="Performance"
          value={`${rate}%`}
          icon={<BarChart3 className="h-5 w-5" />}
          description="conversion rate"
        />
      </div>

      {/* Details & Message */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Campaign details */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Target className="h-4 w-4" />
              Campaign Details
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <p className="text-sm font-medium">Target Audience</p>
              <p className="mt-1 text-sm text-muted-foreground">
                {campaign.audience}
              </p>
            </div>
            <div>
              <p className="text-sm font-medium">Schedule</p>
              <p className="mt-1 flex items-center gap-1.5 text-sm text-muted-foreground">
                <Calendar className="h-3.5 w-3.5" />
                {campaign.schedule}
              </p>
            </div>
            <div>
              <p className="text-sm font-medium">Created</p>
              <p className="mt-1 text-sm text-muted-foreground">
                {new Date(campaign.createdAt).toLocaleDateString()}
              </p>
            </div>
          </CardContent>
        </Card>

        {/* Message preview */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Mail className="h-4 w-4" />
              Message Preview
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <p className="text-sm font-medium">Subject</p>
              <p className="mt-1 rounded-lg border border-border bg-muted/50 px-3 py-2 text-sm">
                {campaign.message.subject}
              </p>
            </div>
            <div>
              <p className="text-sm font-medium">Body</p>
              <div className="mt-1 rounded-lg border border-border bg-muted/50 p-4 text-sm whitespace-pre-wrap">
                {campaign.message.body}
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}