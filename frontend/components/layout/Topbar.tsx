"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Bell, ChevronDown, LogOut, Menu, Moon, Search, Sun, UserRound } from "lucide-react";
import { api, type Paginated } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useTheme } from "@/lib/theme";
import type { Notification } from "@/lib/types";
import { Avatar, Badge, Button } from "@/components/ui";
import { cn, ROLE_LABELS, timeAgo } from "@/lib/format";

const PAGE_TITLES: Record<string, string> = {
  "/overview": "Overview",
  "/tracking": "Live Tracking",
  "/vehicles": "Vehicles",
  "/drivers": "Drivers",
  "/behaviour": "Driving Behaviour",
  "/risk": "AI Risk Analysis",
  "/incidents": "Incidents",
  "/maintenance": "Maintenance",
  "/reports": "Reports",
  "/road-safety": "Road Safety",
  "/notifications": "Notifications",
  "/assistant": "AI Assistant",
  "/settings": "Settings",
  "/subscriptions": "Subscriptions",
};

function useClickOutside(onClose: () => void) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const handler = (event: MouseEvent) => {
      if (ref.current && !ref.current.contains(event.target as Node)) onClose();
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [onClose]);
  return ref;
}

function NotificationsMenu() {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<Notification[]>([]);
  const [unread, setUnread] = useState(0);
  const router = useRouter();
  const ref = useClickOutside(() => setOpen(false));

  const load = async () => {
    try {
      const [list, count] = await Promise.all([
        api.get<Paginated<Notification>>("/notifications", { page_size: 6 }),
        api.get<{ unread: number }>("/notifications/unread-count"),
      ]);
      setItems(list.items);
      setUnread(count.unread);
    } catch {
      /* silently ignore; topbar must never break the page */
    }
  };

  useEffect(() => {
    void load();
    const interval = setInterval(load, 30000);
    return () => clearInterval(interval);
  }, []);

  const openItem = async (notification: Notification) => {
    if (!notification.is_read) {
      try {
        await api.post(`/notifications/${notification.id}/read`);
      } catch {
        /* ignore */
      }
    }
    setOpen(false);
    if (notification.related_type === "incident") router.push("/incidents");
    else if (notification.type?.includes("maintenance")) router.push("/maintenance");
    else if (notification.type?.includes("speeding") || notification.type?.includes("braking")) router.push("/behaviour");
    else router.push("/notifications");
  };

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((value) => !value)}
        className="relative flex h-9 w-9 items-center justify-center rounded-xl text-ink-500 transition hover:bg-ink-100 hover:text-ink-900 dark:text-ink-400 dark:hover:bg-white/10 dark:hover:text-white"
        aria-label="Notifications"
      >
        <Bell className="h-4.5 w-4.5" />
        {unread > 0 && (
          <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-rose-500 px-1 text-[9px] font-bold text-white">
            {unread > 9 ? "9+" : unread}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 z-40 mt-2 w-80 overflow-hidden rounded-2xl border border-ink-200 bg-white shadow-pop dark:border-white/10 dark:bg-ink-900">
          <div className="flex items-center justify-between border-b border-ink-100 px-4 py-3 dark:border-white/5">
            <p className="text-sm font-semibold text-ink-900 dark:text-white">Notifications</p>
            <Link href="/notifications" className="text-xs font-medium text-brand-600 hover:underline dark:text-brand-300" onClick={() => setOpen(false)}>
              View all
            </Link>
          </div>
          <div className="max-h-80 overflow-y-auto">
            {items.length === 0 ? (
              <p className="px-4 py-8 text-center text-xs text-ink-400">You're all caught up.</p>
            ) : (
              items.map((item) => (
                <button
                  key={item.id}
                  onClick={() => openItem(item)}
                  className={cn(
                    "flex w-full gap-3 border-b border-ink-100 px-4 py-3 text-left transition last:border-0 hover:bg-ink-50 dark:border-white/5 dark:hover:bg-white/5",
                    !item.is_read && "bg-brand-50/40 dark:bg-brand-500/5",
                  )}
                >
                  <span className={cn("mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full", item.is_read ? "bg-ink-200 dark:bg-white/20" : "bg-brand-500")} />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-xs font-semibold text-ink-900 dark:text-white">{item.title}</span>
                    <span className="mt-0.5 line-clamp-2 block text-[11px] leading-relaxed text-ink-500 dark:text-ink-400">
                      {item.message}
                    </span>
                    <span className="mt-1 block text-[10px] text-ink-400">{timeAgo(item.created_at)}</span>
                  </span>
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function UserMenu() {
  const [open, setOpen] = useState(false);
  const { user, logout } = useAuth();
  const ref = useClickOutside(() => setOpen(false));

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((value) => !value)}
        className="flex items-center gap-2 rounded-xl px-1.5 py-1.5 transition hover:bg-ink-100 dark:hover:bg-white/5"
      >
        <Avatar name={user?.full_name} color={user?.role === "super_admin" ? "#4f46e5" : "#0dab99"} size="sm" />
        <span className="hidden text-left sm:block">
          <span className="block text-xs font-semibold text-ink-900 dark:text-white">{user?.full_name}</span>
          <span className="block text-[10px] text-ink-500 dark:text-ink-400">{user ? ROLE_LABELS[user.role] : ""}</span>
        </span>
        <ChevronDown className="h-3.5 w-3.5 text-ink-400" />
      </button>
      {open && (
        <div className="absolute right-0 z-40 mt-2 w-56 overflow-hidden rounded-2xl border border-ink-200 bg-white py-1.5 shadow-pop dark:border-white/10 dark:bg-ink-900">
          <div className="border-b border-ink-100 px-4 py-2.5 dark:border-white/5">
            <p className="truncate text-xs font-semibold text-ink-900 dark:text-white">{user?.full_name}</p>
            <p className="truncate text-[11px] text-ink-500 dark:text-ink-400">{user?.email}</p>
          </div>
          <Link href="/settings" onClick={() => setOpen(false)} className="flex items-center gap-2 px-4 py-2 text-xs text-ink-700 hover:bg-ink-50 dark:text-ink-200 dark:hover:bg-white/5">
            <UserRound className="h-3.5 w-3.5" /> Profile & settings
          </Link>
          <Link href="/subscriptions" onClick={() => setOpen(false)} className="flex items-center gap-2 px-4 py-2 text-xs text-ink-700 hover:bg-ink-50 dark:text-ink-200 dark:hover:bg-white/5">
            <Badge tone="bg-indigo-50 text-indigo-700 dark:bg-indigo-500/10 dark:text-indigo-300">Plan</Badge>
            Subscription
          </Link>
          <button onClick={logout} className="flex w-full items-center gap-2 px-4 py-2 text-xs text-rose-600 hover:bg-rose-50 dark:text-rose-300 dark:hover:bg-rose-500/10">
            <LogOut className="h-3.5 w-3.5" /> Sign out
          </button>
        </div>
      )}
    </div>
  );
}

export function Topbar({ onOpenSidebar }: { onOpenSidebar: () => void }) {
  const pathname = usePathname();
  const router = useRouter();
  const { theme, toggle } = useTheme();
  const [query, setQuery] = useState("");

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    const value = query.trim();
    if (!value) return;
    router.push(value.toLowerCase().startsWith("driver:") ? `/drivers?search=${encodeURIComponent(value.slice(7))}` : `/vehicles?search=${encodeURIComponent(value)}`);
    setQuery("");
  };

  return (
    <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b border-ink-200/70 bg-white/85 px-4 backdrop-blur-xl dark:border-white/10 dark:bg-ink-950/80 sm:px-6">
      <button
        onClick={onOpenSidebar}
        className="flex h-9 w-9 items-center justify-center rounded-xl text-ink-500 hover:bg-ink-100 dark:text-ink-400 dark:hover:bg-white/10 lg:hidden"
        aria-label="Open menu"
      >
        <Menu className="h-5 w-5" />
      </button>

      <div className="hidden min-w-0 md:block">
        <p className="text-[11px] font-medium text-ink-400 dark:text-ink-500">SafeWay AI / Workspace</p>
        <p className="truncate text-sm font-semibold text-ink-900 dark:text-white">
          {PAGE_TITLES[pathname] ?? "Dashboard"}
        </p>
      </div>

      <form onSubmit={submit} className="ml-auto hidden flex-1 max-w-md sm:block">
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-400" />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search vehicles… (driver:name for drivers)"
            className="w-full rounded-xl border border-ink-200 bg-ink-50/70 py-2 pl-9 pr-3 text-xs text-ink-900 outline-none transition placeholder:text-ink-400 focus:border-brand-500 focus:bg-white focus:ring-4 focus:ring-brand-500/10 dark:border-white/10 dark:bg-white/5 dark:text-white dark:focus:bg-white/10"
          />
        </div>
      </form>

      <div className="ml-auto flex items-center gap-1 sm:ml-0">
        <button
          onClick={toggle}
          className="flex h-9 w-9 items-center justify-center rounded-xl text-ink-500 transition hover:bg-ink-100 hover:text-ink-900 dark:text-ink-400 dark:hover:bg-white/10 dark:hover:text-white"
          aria-label="Toggle theme"
          title="Toggle theme"
        >
          {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </button>
        <NotificationsMenu />
        <UserMenu />
      </div>
    </header>
  );
}
