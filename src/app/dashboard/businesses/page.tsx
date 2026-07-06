"use client";

import { useEffect, useState } from "react";
import { Search, Loader2, Building2, MapPin, Star } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

interface Business {
  id: string;
  name: string;
  category: string | null;
  city: string | null;
  state: string | null;
  phone: string | null;
  claimed: boolean;
  slug: string;
  rating: number | null;
  createdAt: string;
}

export default function BusinessesPage() {
  const [businesses, setBusinesses] = useState<Business[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");

  useEffect(() => {
    fetch("/api/businesses")
      .then((res) => res.json())
      .then((data) => {
        setBusinesses(data.businesses ?? []);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  const filtered = businesses.filter(
    (b) =>
      b.name.toLowerCase().includes(search.toLowerCase()) ||
      (b.city?.toLowerCase() ?? "").includes(search.toLowerCase()) ||
      (b.category?.toLowerCase() ?? "").includes(search.toLowerCase())
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Businesses</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            All discovered businesses ({businesses.length})
          </p>
        </div>
        <Button>Generate Site</Button>
      </div>

      {/* Search */}
      <div className="relative max-w-sm">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          placeholder="Search by name, city, category..."
          className="pl-9"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      {/* Table */}
      {loading ? (
        <div className="flex items-center justify-center py-24">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
        </div>
      ) : (
        <div className="rounded-xl border border-border bg-card">
          <div className="divide-y divide-border">
            {filtered.map((business) => (
              <div
                key={business.id}
                className="flex items-center justify-between px-6 py-4 transition-colors hover:bg-muted/50"
              >
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <Building2 className="h-4 w-4 text-muted-foreground shrink-0" />
                    <span className="text-sm font-medium truncate">
                      {business.name}
                    </span>
                    {business.claimed ? (
                      <Badge variant="success">Claimed</Badge>
                    ) : (
                      <Badge variant="secondary">Unclaimed</Badge>
                    )}
                  </div>
                  <div className="mt-1 flex items-center gap-3 text-xs text-muted-foreground">
                    {business.category && <span>{business.category}</span>}
                    {(business.city || business.state) && (
                      <span className="flex items-center gap-1">
                        <MapPin className="h-3 w-3" />
                        {[business.city, business.state]
                          .filter(Boolean)
                          .join(", ")}
                      </span>
                    )}
                    {business.rating && (
                      <span className="flex items-center gap-1">
                        <Star className="h-3 w-3 fill-amber-400 text-amber-400" />
                        {business.rating.toFixed(1)}
                      </span>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-3 shrink-0 ml-4">
                  <span className="text-xs text-muted-foreground">
                    {new Date(business.createdAt).toLocaleDateString()}
                  </span>
                  <Button variant="ghost" size="sm">
                    View
                  </Button>
                </div>
              </div>
            ))}
            {filtered.length === 0 && (
              <div className="px-6 py-12 text-center text-sm text-muted-foreground">
                {search
                  ? "No businesses match your search."
                  : "No businesses discovered yet."}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}