"use client";

import { useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  Mail,
  MessageSquare,
  Star,
  Share2,
  Search,
  CheckCircle2,
  Eye,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select } from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";

const typeIcons: Record<string, typeof Mail> = {
  email: Mail,
  sms: MessageSquare,
  review_request: Star,
  social: Share2,
};

const categories = [
  "All Categories",
  "Plumber",
  "Electrician",
  "Landscaper",
  "Dentist",
  "Restaurant",
  "HVAC",
  "Cleaner",
  "Painter",
];

const mockTemplates = [
  {
    id: "1",
    name: "Seasonal Service Reminder",
    type: "email",
    category: "Plumber",
    description:
      "Remind customers about seasonal maintenance services with a warm, professional tone.",
    subject: "Don't Forget Your {{season}} Service!",
    body: "Hi {{customer_name}},\n\nIt's that time of year again! At {{business_name}}, we're here to help you with all your {{season}} service needs.\n\nBook your appointment today and save 10%.",
    popular: true,
  },
  {
    id: "2",
    name: "Follow-Up SMS",
    type: "sms",
    category: "General",
    description:
      "A quick SMS follow-up after a service visit to check in and request feedback.",
    body: "Hi {{customer_name}}, thank you for choosing {{business_name}}! How was your experience? Reply with a rating 1-5.",
    popular: true,
  },
  {
    id: "3",
    name: "Review Request",
    type: "review_request",
    category: "General",
    description:
      "Politely ask satisfied customers to leave a review on Google or Yelp.",
    subject: "We'd love your feedback!",
    body: "Hi {{customer_name}},\n\nWe hope you're happy with the service from {{business_name}}. If you have a moment, we'd love a review on Google!\n\n[Review Link]",
    popular: true,
  },
  {
    id: "4",
    name: "Holiday Promotion",
    type: "email",
    category: "General",
    description:
      "Promote a holiday special or seasonal discount to your customer list.",
    subject: "🎉 {{holiday}} Special — Save 15%!",
    body: "Hi {{customer_name}},\n\nCelebrate {{holiday}} with {{business_name}}! For a limited time, enjoy 15% off all services.\n\nBook now!",
    popular: false,
  },
  {
    id: "5",
    name: "New Customer Welcome",
    type: "email",
    category: "General",
    description:
      "Welcome new customers and introduce them to your services.",
    subject: "Welcome to {{business_name}}!",
    body: "Hi {{customer_name}},\n\nWelcome to {{business_name}}! We're excited to have you. Here's what you can expect from us...",
    popular: false,
  },
  {
    id: "6",
    name: "Service Reminder SMS",
    type: "sms",
    category: "Dentist",
    description:
      "Remind patients of upcoming appointments via SMS.",
    body: "Reminder: You have an appointment with {{business_name}} on {{date}} at {{time}}. Reply CONFIRM to confirm.",
    popular: false,
  },
  {
    id: "7",
    name: "Referral Request",
    type: "email",
    category: "General",
    description:
      "Ask happy customers to refer friends and family.",
    subject: "Know someone who needs us?",
    body: "Hi {{customer_name}},\n\nIf you loved {{business_name}}, tell a friend! Refer a new customer and both get 10% off your next service.",
    popular: false,
  },
  {
    id: "8",
    name: "Social Media Promo",
    type: "social",
    category: "General",
    description:
      "A social media post template for promoting a special offer.",
    body: "Special offer at {{business_name}}! 🎉 Get {{discount}} off when you book this week. Visit our website to learn more! #LocalBusiness #{{city}}",
    popular: false,
  },
];

export default function TemplatesPage() {
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [preview, setPreview] = useState<(typeof mockTemplates)[0] | null>(
    null
  );

  const filtered = mockTemplates.filter((t) => {
    const matchesSearch =
      t.name.toLowerCase().includes(search.toLowerCase()) ||
      t.description.toLowerCase().includes(search.toLowerCase());
    const matchesType = !typeFilter || t.type === typeFilter;
    const matchesCategory =
      !categoryFilter ||
      categoryFilter === "All Categories" ||
      t.category === categoryFilter;
    return matchesSearch && matchesType && matchesCategory;
  });

  return (
    <div className="space-y-6">
      {/* Back link */}
      <div>
        <Link
          href="/dashboard/campaigns/new"
          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Create Campaign
        </Link>
      </div>

      <div>
        <h1 className="text-2xl font-bold tracking-tight">
          Campaign Templates
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Choose a template to get started quickly. All templates are
          customizable.
        </p>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <div className="relative max-w-xs flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search templates..."
            className="pl-9"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
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
        <Select
          options={categories.map((c) => ({ value: c, label: c }))}
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value)}
          placeholder="All Categories"
          className="w-40"
        />
      </div>

      {/* Template grid */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {filtered.map((template) => {
          const TypeIcon = typeIcons[template.type] || Mail;
          return (
            <Card
              key={template.id}
              className="group transition-all hover:shadow-md hover:border-primary/30"
            >
              <CardHeader>
                <div className="flex items-start justify-between">
                  <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
                    <TypeIcon className="h-4 w-4" />
                  </div>
                  {template.popular && (
                    <Badge variant="success">Popular</Badge>
                  )}
                </div>
                <CardTitle className="mt-3 text-base">
                  {template.name}
                </CardTitle>
                <p className="text-sm text-muted-foreground line-clamp-2">
                  {template.description}
                </p>
              </CardHeader>
              <CardContent>
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <Badge variant="outline">
                    {template.type === "review_request"
                      ? "Review Request"
                      : template.type.charAt(0).toUpperCase() +
                        template.type.slice(1)}
                  </Badge>
                  {template.category && (
                    <Badge variant="secondary">{template.category}</Badge>
                  )}
                </div>
                <div className="mt-4 flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    className="flex-1"
                    onClick={() => setPreview(template)}
                  >
                    <Eye className="h-3.5 w-3.5" />
                    Preview
                  </Button>
                  <Button size="sm" className="flex-1" asChild>
                    <Link
                      href={`/dashboard/campaigns/new?template=${template.id}`}
                    >
                      <CheckCircle2 className="h-3.5 w-3.5" />
                      Use Template
                    </Link>
                  </Button>
                </div>
              </CardContent>
            </Card>
          );
        })}
        {filtered.length === 0 && (
          <div className="col-span-full rounded-xl border border-border bg-card py-16 text-center">
            <p className="text-sm text-muted-foreground">
              No templates match your filters.
            </p>
          </div>
        )}
      </div>

      {/* Preview Dialog */}
      <Dialog open={!!preview} onOpenChange={() => setPreview(null)}>
        <DialogContent className="sm:max-w-lg">
          {preview && (
            <>
              <DialogHeader>
                <DialogTitle>{preview.name}</DialogTitle>
                <DialogDescription>{preview.description}</DialogDescription>
              </DialogHeader>
              <div className="space-y-4">
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <Badge variant="outline">
                    {preview.type === "review_request"
                      ? "Review Request"
                      : preview.type.charAt(0).toUpperCase() +
                        preview.type.slice(1)}
                  </Badge>
                  {preview.category && (
                    <Badge variant="secondary">{preview.category}</Badge>
                  )}
                </div>
                {preview.subject && (
                  <div>
                    <p className="text-sm font-medium">Subject</p>
                    <p className="mt-1 rounded-lg border border-border bg-muted/50 px-3 py-2 text-sm">
                      {preview.subject}
                    </p>
                  </div>
                )}
                <div>
                  <p className="text-sm font-medium">Body</p>
                  <div className="mt-1 rounded-lg border border-border bg-muted/50 p-4 text-sm whitespace-pre-wrap">
                    {preview.body}
                  </div>
                </div>
                <Button className="w-full" asChild>
                  <Link
                    href={`/dashboard/campaigns/new?template=${preview.id}`}
                  >
                    <CheckCircle2 className="h-4 w-4" />
                    Use This Template
                  </Link>
                </Button>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}