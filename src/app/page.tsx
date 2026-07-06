import Link from "next/link";
import {
  Globe,
  Zap,
  Search,
  Users,
  BarChart3,
  Shield,
  ArrowRight,
  CheckCircle2,
  Building2,
  TrendingUp,
  MousePointerClick,
  Sparkles,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

export default function HomePage() {
  return (
    <div className="flex min-h-screen flex-col">
      {/* Header */}
      <header className="sticky top-0 z-50 border-b border-border bg-background/80 backdrop-blur-xl">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
              <Sparkles className="h-4 w-4" />
            </div>
            <span className="text-lg font-bold">LeadLaunch AI</span>
          </div>
          <nav className="hidden items-center gap-6 sm:flex">
            <Link
              href="#features"
              className="text-sm text-muted-foreground transition-colors hover:text-foreground"
            >
              Features
            </Link>
            <Link
              href="#how-it-works"
              className="text-sm text-muted-foreground transition-colors hover:text-foreground"
            >
              How It Works
            </Link>
            <Link
              href="/api/auth/signin"
              className="text-sm text-muted-foreground transition-colors hover:text-foreground"
            >
              Sign In
            </Link>
            <Button asChild>
              <Link href="/api/auth/signin">Get Started</Link>
            </Button>
          </nav>
        </div>
      </header>

      {/* Hero Section */}
      <section className="relative overflow-hidden px-6 py-24 sm:py-32">
        <div className="absolute inset-0 -z-10 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-primary/20 via-transparent to-transparent" />
        <div className="mx-auto max-w-5xl text-center">
          <div className="inline-flex items-center gap-2 rounded-full border border-border bg-muted/50 px-4 py-1.5 text-sm text-muted-foreground mb-6">
            <Zap className="h-3.5 w-3.5 text-primary" />
            AI-powered lead generation
          </div>
          <h1 className="text-4xl font-bold tracking-tight sm:text-5xl md:text-6xl lg:text-7xl">
            Turn Businesses Without Websites
            <br />
            <span className="bg-gradient-to-r from-primary to-blue-400 bg-clip-text text-transparent">
              Into New Customers
            </span>
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-lg text-muted-foreground sm:text-xl">
            Millions of local businesses have Google and Yelp listings but no
            website. LeadLaunch AI automatically discovers them, generates a
            unique SEO-optimized microsite, and captures leads — all in minutes.
          </p>
          <div className="mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row">
            <Button size="xl" asChild>
              <Link href="/api/auth/signin">
                Start Generating Sites
                <ArrowRight className="ml-1 h-4 w-4" />
              </Link>
            </Button>
            <Button variant="outline" size="xl" asChild>
              <Link href="#how-it-works">See How It Works</Link>
            </Button>
          </div>
          <div className="mt-12 flex items-center justify-center gap-8 text-sm text-muted-foreground">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-emerald-500" />
              No credit card
            </div>
            <div className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-emerald-500" />
              5-minute setup
            </div>
            <div className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-emerald-500" />
              Cancel anytime
            </div>
          </div>
        </div>
      </section>

      {/* Stats Section */}
      <section className="border-y border-border bg-muted/30 px-6 py-16">
        <div className="mx-auto max-w-6xl">
          <div className="grid gap-8 sm:grid-cols-3">
            <div className="text-center">
              <p className="text-3xl font-bold sm:text-4xl">10M+</p>
              <p className="mt-1 text-sm text-muted-foreground">
                Local businesses without a website
              </p>
            </div>
            <div className="text-center">
              <p className="text-3xl font-bold sm:text-4xl">60%</p>
              <p className="mt-1 text-sm text-muted-foreground">
                Leads go unclaimed without a site
              </p>
            </div>
            <div className="text-center">
              <p className="text-3xl font-bold sm:text-4xl">$29/mo</p>
              <p className="mt-1 text-sm text-muted-foreground">
                Starting price to claim &amp; upgrade
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section id="features" className="px-6 py-24">
        <div className="mx-auto max-w-6xl">
          <div className="text-center">
            <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
              Everything you need to capture leads
            </h2>
            <p className="mt-4 text-lg text-muted-foreground">
              From automated discovery to lead management — all in one platform.
            </p>
          </div>
          <div className="mt-16 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {features.map((feature) => (
              <Card
                key={feature.title}
                className="group transition-all hover:shadow-md hover:border-primary/30"
              >
                <CardContent className="p-6">
                  <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-primary/10 text-primary transition-colors group-hover:bg-primary/20">
                    {feature.icon}
                  </div>
                  <h3 className="mt-4 font-semibold">{feature.title}</h3>
                  <p className="mt-2 text-sm text-muted-foreground">
                    {feature.description}
                  </p>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* How It Works Section */}
      <section
        id="how-it-works"
        className="border-t border-border bg-muted/30 px-6 py-24"
      >
        <div className="mx-auto max-w-6xl">
          <div className="text-center">
            <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
              How It Works
            </h2>
            <p className="mt-4 text-lg text-muted-foreground">
              Three simple steps to start generating leads.
            </p>
          </div>
          <div className="mt-16 grid gap-8 sm:grid-cols-3">
            {steps.map((step, i) => (
              <div key={step.title} className="relative text-center">
                <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-primary text-xl font-bold text-primary-foreground shadow-lg">
                  {step.icon}
                </div>
                <div className="mt-2 hidden sm:block">
                  {i < steps.length - 1 && (
                    <div className="absolute left-[60%] top-8 hidden h-0.5 w-[40%] bg-gradient-to-r from-primary/50 to-transparent lg:block" />
                  )}
                </div>
                <h3 className="mt-6 text-xl font-semibold">{step.title}</h3>
                <p className="mt-3 text-sm text-muted-foreground">
                  {step.description}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="px-6 py-24">
        <div className="mx-auto max-w-4xl rounded-2xl border border-border bg-gradient-to-br from-primary/5 via-background to-background p-12 text-center shadow-lg sm:p-16">
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
            Ready to start generating leads?
          </h2>
          <p className="mx-auto mt-4 max-w-2xl text-lg text-muted-foreground">
            Join thousands of businesses using LeadLaunch AI to capture
            customers who are searching for local services right now.
          </p>
          <div className="mt-8 flex flex-col items-center justify-center gap-4 sm:flex-row">
            <Button size="xl" asChild>
              <Link href="/api/auth/signin">
                Get Started Free
                <ArrowRight className="ml-1 h-4 w-4" />
              </Link>
            </Button>
            <Button variant="outline" size="xl" asChild>
              <Link href="#features">Learn More</Link>
            </Button>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-border px-6 py-12">
        <div className="mx-auto max-w-6xl">
          <div className="flex flex-col items-center justify-between gap-6 sm:flex-row">
            <div className="flex items-center gap-2">
              <div className="flex h-7 w-7 items-center justify-center rounded-md bg-primary text-primary-foreground">
                <Sparkles className="h-3.5 w-3.5" />
              </div>
              <span className="text-sm font-semibold">LeadLaunch AI</span>
            </div>
            <div className="flex items-center gap-6 text-sm text-muted-foreground">
              <Link href="#" className="hover:text-foreground">
                Privacy
              </Link>
              <Link href="#" className="hover:text-foreground">
                Terms
              </Link>
              <Link href="#" className="hover:text-foreground">
                Contact
              </Link>
            </div>
            <p className="text-sm text-muted-foreground">
              &copy; {new Date().getFullYear()} LeadLaunch AI. All rights
              reserved.
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}

const features = [
  {
    title: "Auto-Discovery",
    description:
      "We scan Google Business Profiles and directories to find local businesses with no website, so you never miss an opportunity.",
    icon: <Search className="h-6 w-6" />,
  },
  {
    title: "AI-Generated Sites",
    description:
      "Our AI generates a unique, professional microsite with contact form, maps, call button, and SEO-optimized copy in minutes.",
    icon: <Globe className="h-6 w-6" />,
  },
  {
    title: "Lead Capture",
    description:
      "Every generated site includes a contact form and click-to-call. Leads are captured and stored in your dashboard automatically.",
    icon: <MousePointerClick className="h-6 w-6" />,
  },
  {
    title: "Claim Management",
    description:
      "Business owners can claim their site with simple verification. You process claims and convert them to paying subscribers.",
    icon: <Shield className="h-6 w-6" />,
  },
  {
    title: "Business Dashboard",
    description:
      "Track total businesses, generated sites, leads captured, claims, and revenue — all in one real-time dashboard.",
    icon: <BarChart3 className="h-6 w-6" />,
  },
  {
    title: "Monetization Ready",
    description:
      "Free tier captures leads for you. Business owners upgrade to paid plans starting at $29/mo to take control of their site.",
    icon: <TrendingUp className="h-6 w-6" />,
  },
];

const steps = [
  {
    title: "Discover",
    description:
      "We automatically find local businesses across Google Business Profiles and directories that don't have a website yet.",
    icon: <Search className="h-6 w-6" />,
  },
  {
    title: "Generate",
    description:
      "AI creates a unique, SEO-optimized microsite with contact form, maps embed, click-to-call, and compelling copy — published in minutes.",
    icon: <Zap className="h-6 w-6" />,
  },
  {
    title: "Claim & Upgrade",
    description:
      "Business owners verify ownership, claim the site, and unlock lead dashboards, editing, and custom domains starting at $29/mo.",
    icon: <Users className="h-6 w-6" />,
  },
];