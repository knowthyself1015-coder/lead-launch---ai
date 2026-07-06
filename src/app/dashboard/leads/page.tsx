"use client";

import { useEffect, useState } from "react";
import { Loader2, Users, Mail, Phone, MessageSquare } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";

interface Lead {
  id: string;
  customerName: string;
  email: string | null;
  phone: string | null;
  message: string | null;
  serviceType: string | null;
  status: string;
  createdAt: string;
  business: { name: string; slug: string };
}

export default function LeadsPage() {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");

  useEffect(() => {
    fetch("/api/leads")
      .then((res) => res.json())
      .then((data) => {
        setLeads(data.leads ?? []);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  const filtered = leads.filter((l) => {
    const matchesSearch =
      l.customerName.toLowerCase().includes(search.toLowerCase()) ||
      (l.email ?? "").toLowerCase().includes(search.toLowerCase()) ||
      l.business.name.toLowerCase().includes(search.toLowerCase());
    const matchesStatus = !statusFilter || l.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Leads</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          All captured leads ({leads.length})
        </p>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <div className="relative max-w-xs flex-1">
          <Input
            placeholder="Search leads..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <Select
          options={[
            { value: "", label: "All Statuses" },
            { value: "NEW", label: "New" },
            { value: "CONTACTED", label: "Contacted" },
            { value: "CONVERTED", label: "Converted" },
            { value: "ARCHIVED", label: "Archived" },
          ]}
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          placeholder="All Statuses"
          className="w-40"
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
            {filtered.map((lead) => (
              <div
                key={lead.id}
                className="px-6 py-4 transition-colors hover:bg-muted/50"
              >
                <div className="flex items-start justify-between">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <Users className="h-4 w-4 text-muted-foreground shrink-0" />
                      <span className="text-sm font-medium">
                        {lead.customerName}
                      </span>
                      <Badge
                        variant={
                          lead.status === "NEW"
                            ? "default"
                            : lead.status === "CONTACTED"
                              ? "warning"
                              : lead.status === "CONVERTED"
                                ? "success"
                                : "secondary"
                        }
                      >
                        {lead.status}
                      </Badge>
                    </div>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {lead.business.name}
                    </p>
                    <div className="mt-2 flex flex-wrap gap-3 text-xs text-muted-foreground">
                      {lead.email && (
                        <span className="flex items-center gap-1">
                          <Mail className="h-3 w-3" />
                          {lead.email}
                        </span>
                      )}
                      {lead.phone && (
                        <span className="flex items-center gap-1">
                          <Phone className="h-3 w-3" />
                          {lead.phone}
                        </span>
                      )}
                      {lead.serviceType && (
                        <span className="flex items-center gap-1">
                          <MessageSquare className="h-3 w-3" />
                          {lead.serviceType}
                        </span>
                      )}
                    </div>
                    {lead.message && (
                      <p className="mt-2 text-sm text-muted-foreground line-clamp-2">
                        &ldquo;{lead.message}&rdquo;
                      </p>
                    )}
                  </div>
                  <span className="text-xs text-muted-foreground shrink-0 ml-4">
                    {new Date(lead.createdAt).toLocaleDateString()}
                  </span>
                </div>
              </div>
            ))}
            {filtered.length === 0 && (
              <div className="px-6 py-12 text-center text-sm text-muted-foreground">
                {search || statusFilter
                  ? "No leads match your filters."
                  : "No leads captured yet."}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}