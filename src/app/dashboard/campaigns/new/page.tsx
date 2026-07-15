"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import {
  ArrowLeft,
  ArrowRight,
  Mail,
  MessageSquare,
  Star,
  Share2,
  CheckCircle2,
  Eye,
  Loader2,
  Sparkles,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";

const campaignTypes = [
  {
    id: "email",
    label: "Email Campaign",
    description: "Send targeted email campaigns to your customer list.",
    icon: Mail,
    color: "text-blue-600 bg-blue-100 dark:bg-blue-950",
  },
  {
    id: "sms",
    label: "SMS Campaign",
    description: "Reach customers directly with text messages.",
    icon: MessageSquare,
    color: "text-green-600 bg-green-100 dark:bg-green-950",
  },
  {
    id: "review_request",
    label: "Review Request",
    description: "Automatically request reviews after service completion.",
    icon: Star,
    color: "text-amber-600 bg-amber-100 dark:bg-amber-950",
  },
  {
    id: "social",
    label: "Social Media",
    description: "Create and schedule social media posts.",
    icon: Share2,
    color: "text-purple-600 bg-purple-100 dark:bg-purple-950",
  },
];

const mockTemplates = [
  {
    id: "1",
    name: "Seasonal Service Reminder",
    type: "email",
    category: "Plumber",
    description: "Remind customers about seasonal maintenance services.",
    subject: "Don't Forget Your {{season}} Service!",
    body: "Hi {{customer_name}},\n\nIt's that time of year again! At {{business_name}}, we're here to help you with all your {{season}} service needs.\n\nBook your appointment today and save 10%.",
  },
  {
    id: "2",
    name: "Follow-Up SMS",
    type: "sms",
    category: "General",
    description: "A quick SMS follow-up after a service visit.",
    subject: "",
    body: "Hi {{customer_name}}, thank you for choosing {{business_name}}! How was your experience? Reply with a rating 1-5.",
  },
  {
    id: "3",
    name: "Review Request",
    type: "review_request",
    category: "General",
    description: "Ask satisfied customers to leave a review.",
    subject: "We'd love your feedback!",
    body: "Hi {{customer_name}},\n\nWe hope you're happy with the service from {{business_name}}. If you have a moment, we'd love a review on Google!\n\n[Review Link]",
  },
  {
    id: "4",
    name: "Holiday Promotion",
    type: "email",
    category: "General",
    description: "Promote a holiday special or seasonal discount.",
    subject: "🎉 {{holiday}} Special — Save 15%!",
    body: "Hi {{customer_name}},\n\nCelebrate {{holiday}} with {{business_name}}! For a limited time, enjoy 15% off all services.\n\nBook now!",
  },
];

export default function CreateCampaignPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const templateId = searchParams.get("template");

  const [step, setStep] = useState(1);
  const [type, setType] = useState("");
  const [selectedTemplate, setSelectedTemplate] = useState<
    (typeof mockTemplates)[0] | null
  >(
    templateId
      ? mockTemplates.find((t) => t.id === templateId) ?? null
      : null
  );
  const [campaignName, setCampaignName] = useState("");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [loading, setLoading] = useState(false);
  const [launched, setLaunched] = useState(false);

  const handleSelectTemplate = (template: (typeof mockTemplates)[0]) => {
    setSelectedTemplate(template);
    setCampaignName(template.name);
    setSubject(template.subject || "");
    setBody(template.body);
  };

  const handleLaunch = async () => {
    setLoading(true);
    // Simulate API call
    await new Promise((resolve) => setTimeout(resolve, 1500));
    setLoading(false);
    setLaunched(true);
  };

  const steps = [
    { num: 1, label: "Type" },
    { num: 2, label: "Template" },
    { num: 3, label: "Customize" },
    { num: 4, label: "Review" },
  ];

  if (launched) {
    return (
      <div className="mx-auto max-w-lg py-24 text-center">
        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-emerald-100 dark:bg-emerald-900">
          <CheckCircle2 className="h-8 w-8 text-emerald-600 dark:text-emerald-400" />
        </div>
        <h1 className="mt-6 text-2xl font-bold">Campaign Launched!</h1>
        <p className="mt-2 text-muted-foreground">
          Your campaign &ldquo;{campaignName}&rdquo; has been created and is
          being processed.
        </p>
        <div className="mt-8 flex justify-center gap-4">
          <Button asChild>
            <Link href="/dashboard/campaigns">View Campaigns</Link>
          </Button>
          <Button variant="outline" asChild>
            <Link href="/dashboard/campaigns/new">Create Another</Link>
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl space-y-8">
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

      <div>
        <h1 className="text-2xl font-bold tracking-tight">
          Create Campaign
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Build a new marketing campaign in 4 simple steps.
        </p>
      </div>

      {/* Step indicator */}
      <div className="flex items-center justify-center gap-4">
        {steps.map((s, i) => (
          <div key={s.num} className="flex items-center gap-2">
            <div
              className={`flex h-8 w-8 items-center justify-center rounded-full text-sm font-medium ${
                step > s.num
                  ? "bg-primary text-primary-foreground"
                  : step === s.num
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-muted-foreground"
              }`}
            >
              {step > s.num ? (
                <CheckCircle2 className="h-4 w-4" />
              ) : (
                s.num
              )}
            </div>
            <span
              className={`text-sm ${
                step === s.num
                  ? "font-medium text-foreground"
                  : "text-muted-foreground"
              }`}
            >
              {s.label}
            </span>
            {i < steps.length - 1 && (
              <div className="mx-2 h-px w-8 bg-border" />
            )}
          </div>
        ))}
      </div>

      {/* Step 1: Choose campaign type */}
      {step === 1 && (
        <div className="space-y-4">
          <h2 className="text-lg font-semibold">Choose Campaign Type</h2>
          <div className="grid gap-4 sm:grid-cols-2">
            {campaignTypes.map((ct) => {
              const Icon = ct.icon;
              const isSelected = type === ct.id;
              return (
                <button
                  key={ct.id}
                  onClick={() => setType(ct.id)}
                  className={`rounded-xl border p-5 text-left transition-all ${
                    isSelected
                      ? "border-primary bg-primary/5 shadow-sm"
                      : "border-border hover:border-primary/30 hover:shadow-sm"
                  }`}
                >
                  <div
                    className={`flex h-10 w-10 items-center justify-center rounded-lg ${ct.color}`}
                  >
                    <Icon className="h-5 w-5" />
                  </div>
                  <h3 className="mt-3 font-medium">{ct.label}</h3>
                  <p className="mt-1 text-sm text-muted-foreground">
                    {ct.description}
                  </p>
                  {isSelected && (
                    <div className="mt-3">
                      <Badge variant="default">Selected</Badge>
                    </div>
                  )}
                </button>
              );
            })}
          </div>
          <div className="flex justify-end pt-4">
            <Button
              disabled={!type}
              onClick={() => setStep(2)}
            >
              Next: Choose Template
              <ArrowRight className="ml-1 h-4 w-4" />
            </Button>
          </div>
        </div>
      )}

      {/* Step 2: Choose template */}
      {step === 2 && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">Choose a Template</h2>
            <Button variant="ghost" size="sm" asChild>
              <Link href="/dashboard/campaigns/templates">
                Browse all templates
                <ArrowRight className="ml-1 h-3.5 w-3.5" />
              </Link>
            </Button>
          </div>
          <p className="text-sm text-muted-foreground">
            Pick a template to get started, or skip to create from scratch.
          </p>
          <div className="space-y-3">
            {mockTemplates
              .filter((t) => !type || t.type === type)
              .map((template) => {
                const isSelected = selectedTemplate?.id === template.id;
                return (
                  <button
                    key={template.id}
                    onClick={() => handleSelectTemplate(template)}
                    className={`w-full rounded-xl border p-4 text-left transition-all ${
                      isSelected
                        ? "border-primary bg-primary/5 shadow-sm"
                        : "border-border hover:border-primary/30"
                    }`}
                  >
                    <div className="flex items-start justify-between">
                      <div>
                        <h3 className="font-medium">{template.name}</h3>
                        <p className="mt-1 text-sm text-muted-foreground">
                          {template.description}
                        </p>
                      </div>
                      {isSelected && (
                        <CheckCircle2 className="h-5 w-5 text-primary shrink-0" />
                      )}
                    </div>
                    <div className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
                      <Badge variant="outline">
                        {template.type === "review_request"
                          ? "Review Request"
                          : template.type.charAt(0).toUpperCase() +
                            template.type.slice(1)}
                      </Badge>
                      {template.category && (
                        <Badge variant="secondary">
                          {template.category}
                        </Badge>
                      )}
                    </div>
                  </button>
                );
              })}
            {/* Skip template option */}
            <button
              onClick={() => {
                setSelectedTemplate(null);
                setCampaignName("");
                setSubject("");
                setBody("");
              }}
              className={`w-full rounded-xl border border-dashed p-4 text-center transition-all ${
                !selectedTemplate
                  ? "border-primary bg-primary/5"
                  : "border-border hover:border-primary/30"
              }`}
            >
              <Sparkles className="mx-auto h-5 w-5 text-muted-foreground" />
              <p className="mt-1 text-sm font-medium">Start from scratch</p>
              <p className="text-xs text-muted-foreground">
                Write your own message
              </p>
            </button>
          </div>
          <div className="flex justify-between pt-4">
            <Button variant="ghost" onClick={() => setStep(1)}>
              <ArrowLeft className="mr-1 h-4 w-4" />
              Back
            </Button>
            <Button onClick={() => setStep(3)}>
              Next: Customize
              <ArrowRight className="ml-1 h-4 w-4" />
            </Button>
          </div>
        </div>
      )}

      {/* Step 3: Customize */}
      {step === 3 && (
        <div className="space-y-4">
          <h2 className="text-lg font-semibold">Customize Your Message</h2>
          <p className="text-sm text-muted-foreground">
            Edit the campaign name and message content. Use{" "}
            <code className="rounded bg-muted px-1 py-0.5 text-xs">
              {"{{variable}}"}
            </code>{" "}
            placeholders for personalization.
          </p>
          <div className="space-y-4">
            <div className="space-y-2">
              <label htmlFor="campaign-name" className="text-sm font-medium">
                Campaign Name
              </label>
              <Input
                id="campaign-name"
                placeholder="e.g. Summer Promotion"
                value={campaignName}
                onChange={(e) => setCampaignName(e.target.value)}
              />
            </div>
            {type !== "sms" && type !== "social" && (
              <div className="space-y-2">
                <label htmlFor="subject" className="text-sm font-medium">
                  Subject Line
                </label>
                <Input
                  id="subject"
                  placeholder="Enter email subject..."
                  value={subject}
                  onChange={(e) => setSubject(e.target.value)}
                />
              </div>
            )}
            <div className="space-y-2">
              <label htmlFor="body" className="text-sm font-medium">
                Message Body
              </label>
              <Textarea
                id="body"
                placeholder="Write your message..."
                rows={8}
                value={body}
                onChange={(e) => setBody(e.target.value)}
              />
            </div>
          </div>
          <div className="flex justify-between pt-4">
            <Button variant="ghost" onClick={() => setStep(2)}>
              <ArrowLeft className="mr-1 h-4 w-4" />
              Back
            </Button>
            <Button
              disabled={!campaignName || !body}
              onClick={() => setStep(4)}
            >
              Next: Review
              <ArrowRight className="ml-1 h-4 w-4" />
            </Button>
          </div>
        </div>
      )}

      {/* Step 4: Review and launch */}
      {step === 4 && (
        <div className="space-y-4">
          <h2 className="text-lg font-semibold">Review &amp; Launch</h2>
          <p className="text-sm text-muted-foreground">
            Review your campaign before launching.
          </p>

          <Card>
            <CardContent className="p-5 space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium">Campaign Name</p>
                  <p className="text-sm text-muted-foreground">
                    {campaignName}
                  </p>
                </div>
                <Badge variant="outline">
                  {campaignTypes.find((t) => t.id === type)?.label ?? type}
                </Badge>
              </div>
              {subject && (
                <div>
                  <p className="text-sm font-medium">Subject</p>
                  <p className="text-sm text-muted-foreground">{subject}</p>
                </div>
              )}
              <div>
                <p className="text-sm font-medium">Message</p>
                <div className="mt-1 rounded-lg border border-border bg-muted/50 p-4 text-sm whitespace-pre-wrap">
                  {body}
                </div>
              </div>
            </CardContent>
          </Card>

          <div className="flex justify-between pt-4">
            <Button variant="ghost" onClick={() => setStep(3)}>
              <ArrowLeft className="mr-1 h-4 w-4" />
              Back
            </Button>
            <Button
              size="lg"
              onClick={handleLaunch}
              disabled={loading}
            >
              {loading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Launching...
                </>
              ) : (
                <>
                  <Sparkles className="h-4 w-4" />
                  Launch Campaign
                </>
              )}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}