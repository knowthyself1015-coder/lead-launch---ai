import { cn } from "@/lib/utils";

function StatsCard({
  title,
  value,
  description,
  icon,
  trend,
  className,
}: {
  title: string;
  value: string | number;
  description?: string;
  icon?: React.ReactNode;
  trend?: { value: string; positive: boolean };
  className?: string;
}) {
  return (
    <div
      className={cn(
        "rounded-xl border border-border bg-card p-6 shadow-sm transition-all hover:shadow-md",
        className
      )}
    >
      <div className="flex items-start justify-between">
        <div className="space-y-1">
          <p className="text-sm text-muted-foreground">{title}</p>
          <p className="text-2xl font-bold tracking-tight">{value}</p>
        </div>
        {icon && (
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
            {icon}
          </div>
        )}
      </div>
      {(description || trend) && (
        <div className="mt-3 flex items-center gap-2">
          {trend && (
            <span
              className={`text-xs font-medium ${
                trend.positive ? "text-emerald-600" : "text-red-600"
              }`}
            >
              {trend.positive ? "↑" : "↓"} {trend.value}
            </span>
          )}
          {description && (
            <p className="text-xs text-muted-foreground">{description}</p>
          )}
        </div>
      )}
    </div>
  );
}

export { StatsCard };