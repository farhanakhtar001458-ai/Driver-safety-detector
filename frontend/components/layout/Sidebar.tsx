"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  Bell,
  BrainCircuit,
  LayoutDashboard,
  Map,
  MessageSquare,
  Radar,
  Settings,
  ShieldCheck,
  Truck,
  Users,
  Wrench,
  X,
} from "lucide-react";
import { cn } from "@/lib/format";
import { useAuth } from "@/lib/auth";

interface NavItem {
  href: string;
  label: string;
  icon: React.ElementType;
  permission: string;
}

const SECTIONS: { title: string; items: NavItem[] }[] = [
  {
    title: "Operations",
    items: [
      { href: "/overview", label: "Overview", icon: LayoutDashboard, permission: "dashboard:read" },
      { href: "/tracking", label: "Live Tracking", icon: Radar, permission: "tracking:read" },
      { href: "/vehicles", label: "Vehicles", icon: Truck, permission: "vehicles:read" },
      { href: "/drivers", label: "Drivers", icon: Users, permission: "drivers:read" },
    ],
  },
  {
    title: "Safety intelligence",
    items: [
      { href: "/behaviour", label: "Driving Behaviour", icon: Activity, permission: "behaviour:read" },
      { href: "/risk", label: "AI Risk Analysis", icon: BrainCircuit, permission: "risk:read" },
      { href: "/incidents", label: "Incidents", icon: AlertTriangle, permission: "incidents:read" },
      { href: "/maintenance", label: "Maintenance", icon: Wrench, permission: "maintenance:read" },
    ],
  },
  {
    title: "Insights",
    items: [
      { href: "/reports", label: "Reports", icon: BarChart3, permission: "reports:read" },
      { href: "/road-safety", label: "Road Safety", icon: Map, permission: "road_safety:read" },
    ],
  },
  {
    title: "Workspace",
    items: [
      { href: "/notifications", label: "Notifications", icon: Bell, permission: "notifications:read" },
      { href: "/assistant", label: "AI Assistant", icon: MessageSquare, permission: "assistant:use" },
      { href: "/settings", label: "Settings", icon: Settings, permission: "settings:read" },
    ],
  },
];

export function Sidebar({ open, onClose }: { open: boolean; onClose: () => void }) {
  const pathname = usePathname();
  const { user, hasPermission } = useAuth();

  return (
    <>
      {open && <div className="fixed inset-0 z-40 bg-ink-950/50 backdrop-blur-sm lg:hidden" onClick={onClose} />}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex w-72 flex-col bg-ink-950 text-ink-100 transition-transform duration-300 lg:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <div className="flex items-center justify-between gap-3 px-5 py-5">
          <Link href="/overview" className="flex items-center gap-3">
            <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-brand-400 to-brand-600 shadow-lg shadow-brand-500/25">
              <ShieldCheck className="h-5 w-5 text-white" />
            </span>
            <span>
              <span className="block text-sm font-semibold tracking-tight text-white">SafeWay AI</span>
              <span className="block text-[10px] font-medium uppercase tracking-[0.18em] text-brand-300/80">
                Safety intelligence
              </span>
            </span>
          </Link>
          <button onClick={onClose} className="rounded-lg p-1.5 text-ink-400 hover:bg-white/10 lg:hidden" aria-label="Close menu">
            <X className="h-4 w-4" />
          </button>
        </div>

        <nav className="flex-1 space-y-5 overflow-y-auto px-3 py-2">
          {SECTIONS.map((section) => {
            const items = section.items.filter((item) => hasPermission(item.permission));
            if (!items.length) return null;
            return (
              <div key={section.title}>
                <p className="mb-1.5 px-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-ink-500">{section.title}</p>
                <div className="space-y-0.5">
                  {items.map((item) => {
                    const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
                    return (
                      <Link
                        key={item.href}
                        href={item.href}
                        onClick={onClose}
                        className={cn(
                          "group relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-[13px] font-medium transition",
                          active ? "bg-white/10 text-white" : "text-ink-400 hover:bg-white/5 hover:text-ink-100",
                        )}
                      >
                        {active && (
                          <motion.span
                            layoutId="sidebar-active"
                            className="absolute left-0 top-1/2 h-5 w-1 -translate-y-1/2 rounded-r-full bg-brand-400"
                            transition={{ type: "spring", stiffness: 380, damping: 32 }}
                          />
                        )}
                        <item.icon className={cn("h-4 w-4 shrink-0", active ? "text-brand-300" : "text-ink-500 group-hover:text-ink-300")} />
                        {item.label}
                      </Link>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </nav>

        <div className="border-t border-white/10 p-4">
          <div className="rounded-2xl bg-gradient-to-br from-brand-500/15 to-indigo-500/10 p-3.5 ring-1 ring-white/10">
            <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-brand-300">Demo workspace</p>
            <p className="mt-1 text-xs leading-relaxed text-ink-300">
              Telemetry is simulated and labelled. No real vehicles are tracked in this environment.
            </p>
          </div>
          <p className="mt-3 px-1 text-[10px] text-ink-600">SafeWay AI · v1.0.0 · {user?.role.replace("_", " ")}</p>
        </div>
      </aside>
    </>
  );
}
