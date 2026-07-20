"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const navItems = [
  { href: "/", label: "Dashboard", icon: "📊" },
  { href: "/portfolio", label: "Portfolio", icon: "💼" },
  { href: "/watchlist", label: "Watchlist", icon: "👁️" },
  { href: "/reports", label: "Reports", icon: "📋" },
  { href: "/settings", label: "Settings", icon: "⚙️" },
];

export default function Nav() {
  const pathname = usePathname();

  return (
    <nav className="w-56 bg-surface-800 border-r border-surface-700 flex flex-col shrink-0">
      {/* Brand */}
      <div className="px-5 py-4 border-b border-surface-700">
        <h1 className="text-lg font-bold tracking-tight">
          <span className="text-alpha-400">Alpha</span>Sight
        </h1>
        <p className="text-xs text-surface-200 mt-0.5">AI Trading Agent</p>
      </div>

      {/* Nav links */}
      <ul className="flex-1 px-3 py-4 space-y-1">
        {navItems.map((item) => {
          const isActive = pathname === item.href;
          return (
            <li key={item.href}>
              <Link
                href={item.href}
                className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                  isActive
                    ? "bg-alpha-900/30 text-alpha-400 font-medium"
                    : "text-surface-100 hover:bg-surface-700 hover:text-white"
                }`}
              >
                <span className="text-base">{item.icon}</span>
                {item.label}
              </Link>
            </li>
          );
        })}
      </ul>

      {/* Footer */}
      <div className="px-5 py-3 border-t border-surface-700 text-xs text-surface-200">
        v0.1.0 · Paper Trading
      </div>
    </nav>
  );
}
