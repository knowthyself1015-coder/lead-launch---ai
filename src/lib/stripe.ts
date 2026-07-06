import Stripe from "stripe";

if (!process.env.STRIPE_SECRET_KEY) {
  console.warn("STRIPE_SECRET_KEY is not set — Stripe API calls will fail.");
}

export const stripe = new Stripe(
  process.env.STRIPE_SECRET_KEY || "sk_missing",
  {
    typescript: true,
  }
);

export const PLANS = {
  basic: {
    name: "Basic",
    description: "Claim your site, edit content, view leads",
    price: 2900, // $29.00 in cents
    interval: "month" as const,
    features: [
      "Claim your generated website",
      "Edit business info & content",
      "View captured leads dashboard",
      "Remove platform branding",
      "Contact form & click-to-call",
    ],
  },
  pro: {
    name: "Pro",
    description: "AI content generation & advanced SEO",
    price: 5900, // $59.00 in cents
    interval: "month" as const,
    features: [
      "Everything in Basic",
      "AI-powered content generation",
      "Advanced SEO optimization",
      "Multiple service pages",
      "Google Maps integration",
      "Lead notifications via email",
    ],
  },
  premium: {
    name: "Premium",
    description: "Full suite — chatbot, SMS, priority support",
    price: 9900, // $99.00 in cents
    interval: "month" as const,
    features: [
      "Everything in Pro",
      "AI chatbot for your site",
      "SMS lead notifications",
      "SEO audit reports",
      "Priority support",
      "Custom domain support",
    ],
  },
} as const;

export type PlanId = keyof typeof PLANS;