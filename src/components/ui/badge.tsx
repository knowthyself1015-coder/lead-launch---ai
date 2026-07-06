import * as React from "react";
import { cn } from "@/lib/utils";

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "default" | "secondary" | "destructive" | "outline" | "success" | "warning";
}

function Badge({ className, variant = "default", ...props }: BadgeProps) {
  return (
    <div
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors",
        {
          "border-transparent bg-primary text-primary-foreground": variant === "default",
          "border-transparent bg-muted text-foreground": variant === "secondary",
          "border-transparent bg-red-600 text-white": variant === "destructive",
          "border-border text-foreground": variant === "outline",
          "border-transparent bg-emerald-600 text-white": variant === "success",
          "border-transparent bg-amber-600 text-white": variant === "warning",
        },
        className
      )}
      {...props}
    />
  );
}

export { Badge };