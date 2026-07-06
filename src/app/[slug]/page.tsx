import { notFound } from "next/navigation";
import { prisma } from "@/lib/prisma";
import Link from "next/link";
import type { Metadata } from "next";

interface Props {
  params: { slug: string };
}

interface WebsiteContent {
  about?: string;
  services?: { title: string; description: string }[];
  faq?: { question: string; answer: string }[];
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const business = await prisma.business.findUnique({
    where: { slug: params.slug },
    include: { websites: true },
  });

  if (!business) return { title: "Not Found" };

  const website = business.websites[0];
  return {
    title: website?.seoTitle || business.name,
    description:
      website?.seoDescription ||
      `Contact ${business.name} — ${business.city || "local"} business`,
    openGraph: {
      title: website?.seoTitle || business.name,
      description: website?.seoDescription || undefined,
      type: "website",
    },
  };
}

export default async function BusinessWebsitePage({ params }: Props) {
  const business = await prisma.business.findUnique({
    where: { slug: params.slug },
    include: { websites: true },
  });

  if (!business) notFound();

  const website = business.websites[0];
  const content = (website?.content as WebsiteContent) ?? {};
  const theme = (website?.theme as Record<string, string>) ?? {};
  const accentColor = theme.accentColor || "#2563eb";
  const services = content.services ?? [];
  const faq = content.faq ?? [];

  return (
    <div className="min-h-screen">
      {/* Hero Section */}
      <section
        className="px-4 py-24 text-center"
        style={{ background: `oklch(0.97 0.02 ${theme.hue || "240"})` }}
      >
        <div className="mx-auto max-w-3xl">
          <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">
            {website?.heroHeadline || business.name}
          </h1>
          {website?.heroSubheadline && (
            <p className="mt-4 text-lg text-muted-foreground">
              {website.heroSubheadline}
            </p>
          )}
          <div className="mt-8 flex flex-wrap items-center justify-center gap-4">
            {business.phone && (
              <a
                href={`tel:${business.phone}`}
                className="inline-flex items-center gap-2 rounded-lg px-6 py-3 text-sm font-medium text-white"
                style={{ background: accentColor }}
              >
                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z"
                  />
                </svg>
                {business.phone}
              </a>
            )}
            <a
              href="#contact"
              className="rounded-lg border border-border px-6 py-3 text-sm font-medium hover:bg-muted"
            >
              Get a Quote
            </a>
          </div>
        </div>
      </section>

      {/* About Section */}
      <section className="mx-auto max-w-4xl px-4 py-16">
        <div className="text-center">
          <h2 className="text-3xl font-bold">About {business.name}</h2>
          <div className="mx-auto mt-6 max-w-2xl text-lg text-muted-foreground leading-relaxed">
            <p>{content.about || business.description || "Professional service dedicated to quality and customer satisfaction."}</p>
          </div>
        </div>

        <div className="mt-12 grid gap-8 sm:grid-cols-2">
          {business.address && (
            <div className="rounded-xl border border-border p-6">
              <h3 className="flex items-center gap-2 font-semibold">
                <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"
                  />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"
                  />
                </svg>
                Location
              </h3>
              <p className="mt-2 text-muted-foreground">{business.address}</p>
              {business.city && business.state && (
                <p className="text-muted-foreground">{business.city}, {business.state} {business.zip}</p>
              )}
            </div>
          )}

          {business.hours && typeof business.hours === "object" && Object.keys(business.hours as object).length > 0 && (
            <div className="rounded-xl border border-border p-6">
              <h3 className="flex items-center gap-2 font-semibold">
                <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
                  />
                </svg>
                Business Hours
              </h3>
              <div className="mt-2 space-y-1">
                {Object.entries(business.hours as Record<string, string>).map(
                  ([day, hours]) => (
                    <div key={day} className="flex justify-between text-sm">
                      <span className="font-medium capitalize">{day}</span>
                      <span className="text-muted-foreground">{hours}</span>
                    </div>
                  )
                )}
              </div>
            </div>
          )}
        </div>
      </section>

      {/* Services Section - AI generated */}
      {services.length > 0 && (
        <section className="border-t border-border px-4 py-16">
          <div className="mx-auto max-w-6xl">
            <h2 className="text-center text-3xl font-bold">Our Services</h2>
            <div className="mt-10 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
              {services.map((service, i) => (
                <div key={i} className="group rounded-xl border border-border p-6 transition hover:shadow-md">
                  <div
                    className="flex h-10 w-10 items-center justify-center rounded-lg text-sm font-bold text-white"
                    style={{ background: accentColor }}
                  >
                    {i + 1}
                  </div>
                  <h3 className="mt-4 font-semibold">{service.title}</h3>
                  <p className="mt-2 text-sm text-muted-foreground">{service.description}</p>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* FAQ Section - AI generated */}
      {faq.length > 0 && (
        <section className="border-t border-border px-4 py-16">
          <div className="mx-auto max-w-3xl">
            <h2 className="text-center text-3xl font-bold">Frequently Asked Questions</h2>
            <div className="mt-10 space-y-4">
              {faq.map((item, i) => (
                <details key={i} className="group rounded-xl border border-border">
                  <summary className="flex cursor-pointer items-center justify-between px-6 py-4 font-medium">
                    {item.question}
                    <svg className="h-5 w-5 transition group-open:rotate-180" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                    </svg>
                  </summary>
                  <div className="border-t border-border px-6 py-4 text-sm text-muted-foreground">
                    {item.answer}
                  </div>
                </details>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* Contact Form Section */}
      <section id="contact" className="border-t border-border px-4 py-16">
        <div className="mx-auto max-w-lg">
          <h2 className="text-center text-3xl font-bold">Get in Touch</h2>
          <p className="mt-2 text-center text-muted-foreground">
            Ready to get started? Contact us today for a free consultation.
          </p>
          <form className="mt-8 space-y-4" action={`/api/leads`} method="POST">
            <input type="hidden" name="businessId" value={business.id} />
            <div>
              <label htmlFor="name" className="block text-sm font-medium text-muted-foreground">
                Name <span className="text-red-500">*</span>
              </label>
              <input id="name" name="customerName" required
                className="mt-1 block w-full rounded-lg border border-border bg-background px-4 py-2 text-sm focus:outline-none focus:ring-2"
                style={{ "--tw-ring-color": accentColor } as React.CSSProperties}
              />
            </div>
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-muted-foreground">
                Email <span className="text-red-500">*</span>
              </label>
              <input id="email" name="email" type="email" required
                className="mt-1 block w-full rounded-lg border border-border bg-background px-4 py-2 text-sm focus:outline-none focus:ring-2"
                style={{ "--tw-ring-color": accentColor } as React.CSSProperties}
              />
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label htmlFor="phone" className="block text-sm font-medium text-muted-foreground">Phone</label>
                <input id="phone" name="phone" type="tel"
                  className="mt-1 block w-full rounded-lg border border-border bg-background px-4 py-2 text-sm focus:outline-none focus:ring-2"
                  style={{ "--tw-ring-color": accentColor } as React.CSSProperties}
                />
              </div>
              <div>
                <label htmlFor="service" className="block text-sm font-medium text-muted-foreground">Service Needed</label>
                <input id="service" name="serviceType"
                  className="mt-1 block w-full rounded-lg border border-border bg-background px-4 py-2 text-sm focus:outline-none focus:ring-2"
                  style={{ "--tw-ring-color": accentColor } as React.CSSProperties}
                />
              </div>
            </div>
            <div>
              <label htmlFor="message" className="block text-sm font-medium text-muted-foreground">Message</label>
              <textarea id="message" name="message" rows={4}
                className="mt-1 block w-full rounded-lg border border-border bg-background px-4 py-2 text-sm focus:outline-none focus:ring-2"
                style={{ "--tw-ring-color": accentColor } as React.CSSProperties}
              />
            </div>
            <button type="submit"
              className="w-full rounded-lg px-6 py-3 text-sm font-medium text-white"
              style={{ background: accentColor }}
            >
              Send Message
            </button>
          </form>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-border px-4 py-6 text-center text-sm text-muted-foreground">
        <p>
          &copy; {new Date().getFullYear()} {business.name}. All rights reserved.
          Powered by{" "}
          <Link href="/" className="underline hover:text-foreground">LeadLaunch AI</Link>
        </p>
      </footer>
    </div>
  );
}