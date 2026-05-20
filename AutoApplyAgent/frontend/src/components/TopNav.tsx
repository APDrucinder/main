"use client";

import { UserButton } from "@clerk/nextjs";
import {
  Bell,
  LayoutDashboard,
  Rocket,
  Briefcase,
  Settings
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const navItems = [
  { icon: LayoutDashboard, href: "/dashboard", label: "Dashboard" },
  { icon: Rocket, href: "/onboarding", label: "Onboarding" },
  { icon: Briefcase, href: "/applications", label: "Applications" },
  { icon: Settings, href: "/settings", label: "Settings" },
];

export function TopNav() {
  const pathname = usePathname();
  const landingHref =
    process.env.NEXT_PUBLIC_LANDING_URL ??
    (process.env.NODE_ENV === "development" ? "http://localhost:3000/" : "/");

  if (pathname.startsWith("/login")) {
    return (
      <header className="absolute top-0 left-0 w-full h-24 flex items-center z-40 bg-transparent px-8 py-4">
        <Link href={landingHref} className="flex items-center gap-2 text-foreground hover:opacity-80 transition-opacity">
          <img src="/celerix-hex-mark.png" alt="Celerix Logo" className="w-6 h-6 object-contain invert" />
          <span className="font-bold text-xl tracking-wide uppercase text-white">CelerixAi</span>
        </Link>
      </header>
    );
  }

  return (
    <header className="h-24 flex items-center justify-between z-40 bg-transparent py-4 relative">

      {/* Left: Logo */}
      <div className="flex items-center gap-8">
        <Link href="/" className="flex items-center gap-2 text-foreground hover:opacity-80 transition-opacity">
          <img src="/celerix-hex-mark.png" alt="Celerix Logo" className="w-6 h-6 object-contain invert" />
          <span className="font-bold text-xl tracking-wide uppercase text-white">CelerixAi</span>
        </Link>
      </div>

      {/* Center: Navigation Pills */}
      <div className="hidden lg:flex absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2">
        <nav className="flex items-center gap-1 nav-pill-container">
          {navItems.map((item) => {
            const isActive =
              pathname === item.href ||
              (item.href !== "/dashboard" && pathname.startsWith(item.href));

            return (
              <Link key={item.href} href={item.href}>
                <button
                  className={cn(
                    "flex items-center gap-2 px-4 py-2.5 rounded-full text-xs font-semibold transition-all duration-300",
                    isActive ? "glass-pill-active" : "glass-pill"
                  )}
                >
                  <item.icon className="w-4 h-4" strokeWidth={isActive ? 2.5 : 2} />
                  <span>{item.label}</span>
                </button>
              </Link>
            );
          })}
        </nav>
      </div>


      {/* Right Actions */}
      <div className="flex items-center gap-4">
        <button className="relative w-10 h-10 rounded-full bg-[#27272A]/40 backdrop-blur-md flex items-center justify-center text-muted-foreground hover:text-foreground transition-all duration-200 border border-white/10 shadow-sm">
          <Bell className="w-4 h-4" strokeWidth={2} />
          <span className="absolute top-2.5 right-2.5 w-1.5 h-1.5 bg-primary rounded-full shadow-sm"></span>
        </button>

        <UserButton />
      </div>
    </header>
  );
}
