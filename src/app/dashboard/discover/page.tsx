"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  Search,
  MapPin,
  Building2,
  Phone,
  Mail,
  Star,
  Clock,
  Globe,
  Image,
  Loader2,
  CheckCircle2,
  ChevronRight,
  Save,
  AlertCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";

interface ScrapedBusiness {
  name: string;
  category: string;
  address: string;
  city: string;
  state: string;
  zip: string;
  phone: string;
  email: string;
  description: string;
  hours: Record<string, string>;
  rating: number;
  reviewsCount: number;
  website: string;
  photos: string[];
  services: string[];
}

// Mock scraper result
function mockScrape(name: string, address: string, phone: string): ScrapedBusiness {
  const slug = name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "");
  const city = "Austin";
  const state = "TX";

  return {
    name,
    category: "Plumber",
    address,
    city,
    state,
    zip: "78701",
    phone,
    email: `contact@${slug.replace(/-/g, "")}.com`,
    description: `${name} is a trusted local business serving the ${city}, ${state} area. We pride ourselves on quality service and customer satisfaction. Our team of experienced professionals is dedicated to providing reliable and affordable solutions for all your needs. Contact us today for a free estimate.`,
    hours: {
      Monday: "7:00 AM - 6:00 PM",
      Tuesday: "7:00 AM - 6:00 PM",
      Wednesday: "7:00 AM - 6:00 PM",
      Thursday: "7:00 AM - 6:00 PM",
      Friday: "7:00 AM - 6:00 PM",
      Saturday: "8:00 AM - 2:00 PM",
      Sunday: "Closed",
    },
    rating: 4.7,
    reviewsCount: Math.floor(Math.random() * 200) + 20,
    website: "",
    photos: [
      "https://images.unsplash.com/photo-1621905252507-b35492cc74b1?w=400",
      "https://images.unsplash.com/photo-1581578731548-c64695cc6952?w=400",
    ],
    services: [
      "General Service",
      "Emergency Service",
      "Installation",
      "Repair",
      "Maintenance",
      "Consultation",
    ],
  };
}

export default function DiscoverPage() {
  const router = useRouter();

  const [businessName, setBusinessName] = useState("");
  const [address, setAddress] = useState("");
  const [phone, setPhone] = useState("");
  const [mapsUrl, setMapsUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [result, setResult] = useState<ScrapedBusiness | null>(null);
  const [error, setError] = useState("");
  const [saveResult, setSaveResult] = useState<{
    type: "saved" | "generated" | "error";
    message: string;
    businessId?: string;
  } | null>(null);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setResult(null);
    setSaveResult(null);

    if (!businessName.trim()) {
      setError("Business name is required.");
      return;
    }
    if (!address.trim()) {
      setError("Address is required.");
      return;
    }
    if (!phone.trim()) {
      setError("Phone number is required.");
      return;
    }

    setLoading(true);

    // Mock scraping delay
    await new Promise((resolve) => setTimeout(resolve, 2000));

    const data = mockScrape(businessName.trim(), address.trim(), phone.trim());
    setResult(data);
    setLoading(false);
  };

  const saveBusiness = async (alsoGenerateWebsite: boolean) => {
    if (!result) return;

    setSaving(true);
    setSaveResult(null);

    try {
      const slug = result.name
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/(^-|-$)/g, "");

      const businessPayload = {
        name: result.name,
        category: result.category,
        phone: result.phone,
        email: result.email,
        address: result.address,
        city: result.city,
        state: result.state,
        zip: result.zip,
        description: result.description,
        hours: result.hours,
        website: result.website,
        slug,
        source: mapsUrl || "manual",
        rating: result.rating,
        reviewsCount: result.reviewsCount,
        photos: result.photos,
      };

      const bizRes = await fetch("/api/businesses", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(businessPayload),
      });

      if (!bizRes.ok) {
        const errData = await bizRes.json();
        throw new Error(errData.error || "Failed to save business");
      }

      const { business } = await bizRes.json();

      if (alsoGenerateWebsite) {
        const websitePayload = {
          businessId: business.id,
          seoTitle: `${result.name} | ${result.city} ${result.state}`,
          seoDescription: result.description.slice(0, 160),
          heroHeadline: `Trusted ${result.category} in ${result.city}`,
          heroSubheadline: `Serving ${result.city} and surrounding areas with quality service.`,
          content: {
            about: result.description,
            services: result.services,
            hours: result.hours,
          },
          theme: {},
        };

        const siteRes = await fetch("/api/websites", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(websitePayload),
        });

        if (!siteRes.ok) {
          const errData = await siteRes.json();
          throw new Error(errData.error || "Failed to generate website");
        }

        setSaveResult({
          type: "generated",
          message: `Business saved and website generated for ${result.name}!`,
          businessId: business.id,
        });
      } else {
        setSaveResult({
          type: "saved",
          message: `${result.name} has been saved to your businesses.`,
          businessId: business.id,
        });
      }
    } catch (err) {
      setSaveResult({
        type: "error",
        message:
          err instanceof Error ? err.message : "An unexpected error occurred.",
      });
    } finally {
      setSaving(false);
    }
  };

  const resetForm = () => {
    setResult(null);
    setSaveResult(null);
    setError("");
  };

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">
          Discover Businesses
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Find local businesses without a website and generate a microsite for
          them.
        </p>
      </div>

      {/* Search Form */}
      <Card>
        <CardContent className="p-6">
          <form onSubmit={handleSearch} className="space-y-5">
            <div className="grid gap-5 sm:grid-cols-2">
              <div className="space-y-2">
                <label
                  htmlFor="businessName"
                  className="text-sm font-medium"
                >
                  Business Name <span className="text-red-500">*</span>
                </label>
                <div className="relative">
                  <Building2 className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    id="businessName"
                    placeholder="e.g. Johnson's Plumbing"
                    className="pl-9"
                    value={businessName}
                    onChange={(e) => setBusinessName(e.target.value)}
                  />
                </div>
              </div>
              <div className="space-y-2">
                <label htmlFor="phone" className="text-sm font-medium">
                  Phone <span className="text-red-500">*</span>
                </label>
                <div className="relative">
                  <Phone className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    id="phone"
                    placeholder="e.g. (512) 555-0142"
                    className="pl-9"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                  />
                </div>
              </div>
            </div>

            <div className="space-y-2">
              <label htmlFor="address" className="text-sm font-medium">
                Address <span className="text-red-500">*</span>
              </label>
              <div className="relative">
                <MapPin className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  id="address"
                  placeholder="e.g. 123 Main St, Austin, TX 78701"
                  className="pl-9"
                  value={address}
                  onChange={(e) => setAddress(e.target.value)}
                />
              </div>
            </div>

            <div className="space-y-2">
              <label htmlFor="mapsUrl" className="text-sm font-medium">
                Google Maps URL{" "}
                <span className="text-xs text-muted-foreground">
                  (optional)
                </span>
              </label>
              <Input
                id="mapsUrl"
                placeholder="https://maps.google.com/?cid=..."
                value={mapsUrl}
                onChange={(e) => setMapsUrl(e.target.value)}
              />
              <p className="text-xs text-muted-foreground">
                Paste a Google Maps listing URL for more accurate results.
              </p>
            </div>

            {error && (
              <div className="flex items-center gap-2 text-sm text-red-500">
                <AlertCircle className="h-4 w-4" />
                {error}
              </div>
            )}

            <Button type="submit" size="lg" disabled={loading}>
              {loading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Searching & Generating...
                </>
              ) : (
                <>
                  <Search className="h-4 w-4" />
                  Search &amp; Generate
                </>
              )}
            </Button>
          </form>
        </CardContent>
      </Card>

      {/* Loading State */}
      {loading && (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-16">
            <div className="relative">
              <Loader2 className="h-12 w-12 animate-spin text-primary" />
              <div className="absolute inset-0 flex items-center justify-center">
                <div className="h-3 w-3 rounded-full bg-primary" />
              </div>
            </div>
            <h3 className="mt-6 text-lg font-semibold">
              Searching &amp; Generating Preview...
            </h3>
            <p className="mt-2 text-sm text-muted-foreground">
              Scanning Google Business Profile and directories.
            </p>
            <div className="mt-6 flex items-center gap-2 text-xs text-muted-foreground">
              <div className="flex items-center gap-1">
                <div className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                Scanning directories
              </div>
              <div className="flex items-center gap-1">
                <div className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                Extracting data
              </div>
              <div className="flex items-center gap-1">
                <div className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                Generating preview
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Save Result Banner */}
      {saveResult && (
        <div
          className={`flex items-start gap-3 rounded-xl border px-6 py-4 ${
            saveResult.type === "error"
              ? "border-red-200 bg-red-50 text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-200"
              : "border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-900 dark:bg-emerald-950 dark:text-emerald-200"
          }`}
        >
          {saveResult.type === "error" ? (
            <AlertCircle className="h-5 w-5 shrink-0 mt-0.5" />
          ) : (
            <CheckCircle2 className="h-5 w-5 shrink-0 mt-0.5" />
          )}
          <div className="flex-1">
            <p className="font-medium">{saveResult.message}</p>
            {saveResult.type !== "error" && (
              <div className="mt-3 flex gap-3">
                <Button size="sm" variant="outline" asChild>
                  <a href="/dashboard/businesses">
                    <Building2 className="h-3.5 w-3.5" />
                    View Businesses
                  </a>
                </Button>
                <Button size="sm" variant="ghost" onClick={resetForm}>
                  <Search className="h-3.5 w-3.5" />
                  Search Another
                </Button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Results */}
      {result && !loading && !saveResult && (
        <div className="space-y-6">
          {/* Success Banner */}
          <div className="flex items-center gap-3 rounded-xl border border-emerald-200 bg-emerald-50 px-6 py-4 text-emerald-800 dark:border-emerald-900 dark:bg-emerald-950 dark:text-emerald-200">
            <CheckCircle2 className="h-5 w-5 shrink-0" />
            <div>
              <p className="font-medium">Business found!</p>
              <p className="text-sm opacity-80">
                We discovered &ldquo;{result.name}&rdquo;. Review the data below
                and save it to your businesses.
              </p>
            </div>
          </div>

          {/* Business Details */}
          <Card>
            <CardContent className="p-6">
              <div className="flex flex-col gap-6 sm:flex-row sm:items-start sm:justify-between">
                <div className="space-y-4 flex-1">
                  <div>
                    <div className="flex items-center gap-2">
                      <h2 className="text-xl font-bold">{result.name}</h2>
                      <Badge>{result.category}</Badge>
                    </div>
                    <p className="mt-1 text-sm text-muted-foreground">
                      {result.address}, {result.city}, {result.state}{" "}
                      {result.zip}
                    </p>
                  </div>

                  <div className="flex flex-wrap gap-4 text-sm">
                    <span className="flex items-center gap-1.5 text-muted-foreground">
                      <Phone className="h-3.5 w-3.5" />
                      {result.phone}
                    </span>
                    <span className="flex items-center gap-1.5 text-muted-foreground">
                      <Mail className="h-3.5 w-3.5" />
                      {result.email}
                    </span>
                    <span className="flex items-center gap-1.5">
                      <Star className="h-3.5 w-3.5 fill-amber-400 text-amber-400" />
                      <span className="font-medium">{result.rating}</span>
                      <span className="text-muted-foreground">
                        ({result.reviewsCount} reviews)
                      </span>
                    </span>
                  </div>

                  <p className="text-sm text-muted-foreground leading-relaxed">
                    {result.description}
                  </p>
                </div>
              </div>

              {/* Hours & Services */}
              <div className="mt-6 grid gap-6 sm:grid-cols-2">
                <div>
                  <h4 className="mb-2 flex items-center gap-1.5 text-sm font-medium">
                    <Clock className="h-3.5 w-3.5" />
                    Business Hours
                  </h4>
                  <div className="space-y-1 text-xs text-muted-foreground">
                    {Object.entries(result.hours).map(([day, hours]) => (
                      <div key={day} className="flex justify-between gap-4">
                        <span className="font-medium">{day}</span>
                        <span>{hours}</span>
                      </div>
                    ))}
                  </div>
                </div>

                <div>
                  <h4 className="mb-2 flex items-center gap-1.5 text-sm font-medium">
                    <Globe className="h-3.5 w-3.5" />
                    Services
                  </h4>
                  <div className="flex flex-wrap gap-1.5">
                    {result.services.map((service) => (
                      <Badge key={service} variant="secondary">
                        {service}
                      </Badge>
                    ))}
                  </div>
                </div>
              </div>

              {/* Photos */}
              {result.photos.length > 0 && (
                <div className="mt-6">
                  <h4 className="mb-3 flex items-center gap-1.5 text-sm font-medium">
                    <Image className="h-3.5 w-3.5" />
                    Photos
                  </h4>
                  <div className="flex gap-3 overflow-x-auto pb-2">
                    {result.photos.map((photo, i) => (
                      <div
                        key={i}
                        className="h-24 w-36 shrink-0 overflow-hidden rounded-lg bg-muted"
                      >
                        <img
                          src={photo}
                          alt={`${result.name} photo ${i + 1}`}
                          className="h-full w-full object-cover"
                        />
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Action Buttons */}
          <div className="flex flex-wrap gap-3">
            <Button
              size="lg"
              onClick={() => saveBusiness(true)}
              disabled={saving}
            >
              {saving ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Globe className="h-4 w-4" />
              )}
              {saving ? "Saving & Generating..." : "Save & Generate Website"}
              {!saving && <ChevronRight className="h-4 w-4" />}
            </Button>
            <Button
              variant="outline"
              size="lg"
              onClick={() => saveBusiness(false)}
              disabled={saving}
            >
              {saving ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Save className="h-4 w-4" />
              )}
              {saving ? "Saving..." : "Save Business Only"}
            </Button>
            <Button
              variant="ghost"
              size="lg"
              onClick={resetForm}
              disabled={saving}
            >
              <Search className="h-4 w-4" />
              Search Again
            </Button>
          </div>
        </div>
      )}

      {/* Empty State */}
      {!result && !loading && !saveResult && (
        <Card>
          <CardContent className="py-16 text-center">
            <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/10">
              <Search className="h-8 w-8 text-primary" />
            </div>
            <h3 className="mt-6 text-lg font-semibold">
              Discover a Business
            </h3>
            <p className="mt-2 max-w-md mx-auto text-sm text-muted-foreground">
              Enter a business name, address, and phone number above, or paste a
              Google Maps URL to automatically extract business information and
              generate a microsite.
            </p>
            <div className="mt-8 flex justify-center gap-8 text-xs text-muted-foreground">
              <div className="text-center">
                <p className="text-lg font-bold text-foreground">10M+</p>
                <p>Businesses without a site</p>
              </div>
              <div className="text-center">
                <p className="text-lg font-bold text-foreground">60%</p>
                <p>Leads unclaimed</p>
              </div>
              <div className="text-center">
                <p className="text-lg font-bold text-foreground">5 min</p>
                <p>To generate a site</p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}