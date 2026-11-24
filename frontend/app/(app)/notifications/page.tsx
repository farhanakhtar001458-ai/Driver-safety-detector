"use client";

import { useCallback, useEffect, useState } from "react";
import { Bell, BellOff, CheckCheck, Clock, Mail, Save, Smartphone } from "lucide-react";
import { api, type Paginated } from "@/lib/api";
import type { Notification } from "@/lib/types";
import { Badge, Button, Card, DemoBanner, EmptyState, Field, Input, PageHeader, PageSkeleton, Select, Switch, toast } from "@/components/ui";
import { DataTable, type Column, Pagination } from "@/components/tables/DataTable";
import { cn, timeAgo } from "@/lib/format";

type Prefs = {
  in_app: boolean;
  email: boolean;
  sms: boolean;
  critical_only: boolean;
  quiet_hours_start: string | null;
  quiet_hours_end: string | null;
  user_id: number;
};

type Stats = {
  total: number;
  by_type: { type: string; count: number }[];
  by_priority: { priority: string; count: number }[];
};

const TYPES = [
  ["all", "All types"],
  ["speeding", "Speeding"],
  ["harsh_braking", "Harsh braking"],
  ["incident_update", "Incident updates"],
  ["maintenance_reminder", "Maintenance"],
  ["licence_expiry", "Licence expiry"],
  ["coaching", "Coaching"],
  ["route_deviation", "Route deviation"],
  ["possible_accident", "Possible accident"],
  ["system", "System"],
];

export default function NotificationsPage() {
  const [items, setItems] = useState<Notification[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [prefs, setPrefs] = useState<Prefs | null>(null);
  const [draft, setDraft] = useState<Prefs | null>(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(1);
  const [typeFilter, setTypeFilter] = useState("all");
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [list, statsData, prefsData] = await Promise.all([
        api.get<Paginated<Notification>>("/notifications", {
          page,
          page_size: 20,
          type: typeFilter === "all" ? undefined : typeFilter,
          unread: unreadOnly ? "true" : undefined,
        }),
        api.get<Stats>("/notifications/stats"),
        api.get<Prefs>("/notifications/preferences"),
      ]);
      setItems(list.items ?? []);
      setTotal(list.total ?? 0);
      setPages(list.pages ?? 1);
      setStats(statsData);
      setPrefs(prefsData);
      setDraft(prefsData);
    } catch (err) {
      toast(err instanceof Error ? err.message : "Could not load notifications.", "error");
    } finally {
      setLoading(false);
    }
  }, [page, typeFilter, unreadOnly]);

  useEffect(() => setPage(1), [typeFilter, unreadOnly]);
  useEffect(() => {
    void load();
  }, [load]);

  const markRead = async (notification: Notification) => {
    try {
      await api.post(`/notifications/${notification.id}/read`);
      setItems((current) => current.map((item) => (item.id === notification.id ? { ...item, is_read: true } : item)));
    } catch {
      /* non-fatal */
    }
  };

  const markAll = async () => {
    setSaving(true);
    try {
      await api.post("/notifications/read-all");
      setItems((current) => current.map((item) => ({ ...item, is_read: true })));
      toast("All notifications marked as read.");
    } catch (err) {
      toast(err instanceof Error ? err.message : "Could not update notifications.", "error");
    } finally {
      setSaving(false);
    }
  };

  const savePrefs = async () => {
    if (!draft) return;
    setSaving(true);
    try {
      const saved = await api.put<Prefs>("/notifications/preferences", {
        in_app: draft.in_app,
        email: draft.email,
        sms: draft.sms,
        critical_only: draft.critical_only,
        quiet_hours_start: draft.quiet_hours_start || null,
        quiet_hours_end: draft.quiet_hours_end || null,
      });
      setPrefs(saved);
      setDraft(saved);
      toast("Notification preferences saved.");
    } catch (err) {
      toast(err instanceof Error ? err.message : "Could not save preferences.", "error");
    } finally {
      setSaving(false);
    }
  };

  const columns: Column<Notification>[] = [
    {
      key: "notification",
      header: "Notification",
      render: (row) => (
        <button
          onClick={() => void markRead(row)}
          className={cn("flex w-full items-start gap-3 text-left", !row.is_read && "font-medium")}
        >
          <span className={cn("mt-1.5 h-2 w-2 shrink-0 rounded-full", row.is_read ? "bg-ink-200 dark:bg-white/20" : "bg-brand-500")} />
          <span className="min-w-0">
            <span className="flex flex-wrap items-center gap-2">
              <span className={cn("text-xs", row.is_read ? "text-ink-600 dark:text-ink-300" : "text-ink-900 dark:text-white")}>{row.title}</span>
              <Badge
                tone={
                  row.priority === "urgent"
                    ? "bg-rose-50 text-rose-700 dark:bg-rose-500/10 dark:text-rose-300"
                    : row.priority === "high"
                      ? "bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-300"
                      : "bg-ink-100 text-ink-600 dark:bg-white/10 dark:text-ink-300"
                }
              >
                {row.priority}
              </Badge>
            </span>
            <span className="mt-0.5 block text-[11px] leading-relaxed text-ink-500 dark:text-ink-400">{row.message}</span>
            <span className="mt-1 flex items-center gap-2 text-[10px] text-ink-400">
              {row.type.replace(/_/g, " ")} · {timeAgo(row.created_at)}
              <span className="inline-flex items-center gap-1">
                {row.channel === "email" ? <Mail className="h-2.5 w-2.5" /> : row.channel === "sms" ? <Smartphone className="h-2.5 w-2.5" /> : <Bell className="h-2.5 w-2.5" />}
                {row.channel}
              </span>
            </span>
          </span>
        </button>
      ),
    },
  ];

  if (loading && !items.length) return <PageSkeleton cards={4} />;

  const unread = items.filter((item) => !item.is_read).length;

  return (
    <div>
      <PageHeader
        eyebrow="Workspace · inbox"
        title="Notifications"
        description="Safety, maintenance and coaching alerts delivered in-app, by email or SMS depending on your preferences."
        actions={
          <Button variant="secondary" onClick={markAll} loading={saving}>
            <CheckCheck className="h-4 w-4" /> Mark all read
          </Button>
        }
      />

      <DemoBanner message="Notification payloads reference this database's simulated telemetry. Email and SMS delivery are stubbed in this environment unless SMTP and SMS provider credentials are configured server-side." />

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_360px]">
        <Card padded={false} title="Notification centre" subtitle={`${total} notifications · ${unread} unread on this page`}>
          <div className="flex flex-col justify-between gap-3 border-b border-ink-100 p-4 dark:border-white/5 sm:flex-row sm:items-center">
            <Select value={typeFilter} onChange={(event) => setTypeFilter(event.target.value)} className="w-full sm:w-[220px]" aria-label="Notification type">
              {TYPES.map(([id, label]) => <option key={id} value={id}>{label}</option>)}
            </Select>
            <label className="flex cursor-pointer items-center gap-2 text-xs text-ink-600 dark:text-ink-300">
              <input
                type="checkbox"
                checked={unreadOnly}
                onChange={(event) => setUnreadOnly(event.target.checked)}
                className="h-4 w-4 rounded border-ink-300 text-brand-600 focus:ring-brand-500"
              />
              Unread only
            </label>
          </div>
          <DataTable
            columns={columns}
            rows={items}
            loading={loading}
            emptyTitle="No notifications"
            emptyDescription={unreadOnly ? "Everything is read. Uncheck the unread filter to see history." : "Alerts will appear here as they are generated."}
            minWidth={520}
          />
          <Pagination page={page} pages={pages} total={total} onPage={setPage} pageSize={20} />
        </Card>

        <div className="space-y-4">
          <Card title="Delivery preferences" subtitle="Applies to your user account">
            {draft ? (
              <div className="space-y-4">
                <div className="space-y-3">
                  {[
                    { key: "in_app" as const, label: "In-app", icon: <Bell className="h-4 w-4" />, hint: "Notification centre and topbar badge" },
                    { key: "email" as const, label: "Email", icon: <Mail className="h-4 w-4" />, hint: "Requires SMTP configuration" },
                    { key: "sms" as const, label: "SMS", icon: <Smartphone className="h-4 w-4" />, hint: "Requires an SMS provider key" },
                  ].map((channel) => (
                    <div key={channel.key} className="flex items-start justify-between gap-3 rounded-xl border border-ink-100 p-3 dark:border-white/10">
                      <div className="flex gap-2.5">
                        <span className="mt-0.5 text-ink-400">{channel.icon}</span>
                        <div>
                          <p className="text-xs font-semibold text-ink-900 dark:text-white">{channel.label}</p>
                          <p className="text-[10px] text-ink-400">{channel.hint}</p>
                        </div>
                      </div>
                      <Switch
                        checked={Boolean(draft[channel.key])}
                        onChange={(value) => setDraft({ ...draft, [channel.key]: value })}
                      />
                    </div>
                  ))}
                </div>

                <div className="flex items-start justify-between gap-3 rounded-xl border border-ink-100 p-3 dark:border-white/10">
                  <div>
                    <p className="text-xs font-semibold text-ink-900 dark:text-white">Critical only</p>
                    <p className="text-[10px] text-ink-400">Suppress low and medium priority alerts</p>
                  </div>
                  <Switch checked={draft.critical_only} onChange={(value) => setDraft({ ...draft, critical_only: value })} />
                </div>

                <div className="rounded-xl border border-ink-100 p-3 dark:border-white/10">
                  <p className="mb-2 flex items-center gap-1.5 text-xs font-semibold text-ink-900 dark:text-white">
                    <Clock className="h-3.5 w-3.5" /> Quiet hours
                  </p>
                  <div className="grid grid-cols-2 gap-2">
                    <Field label="Start">
                      <Input type="time" value={draft.quiet_hours_start ?? ""} onChange={(event) => setDraft({ ...draft, quiet_hours_start: event.target.value })} />
                    </Field>
                    <Field label="End">
                      <Input type="time" value={draft.quiet_hours_end ?? ""} onChange={(event) => setDraft({ ...draft, quiet_hours_end: event.target.value })} />
                    </Field>
                  </div>
                  <p className="mt-1 text-[10px] text-ink-400">Urgent alerts bypass quiet hours.</p>
                </div>

                <Button onClick={savePrefs} loading={saving} className="w-full">
                  <Save className="h-4 w-4" /> Save preferences
                </Button>
              </div>
            ) : (
              <div className="skeleton h-40 w-full" />
            )}
          </Card>

          <Card title="Breakdown" subtitle="By type and priority">
            <div className="space-y-2.5">
              {(stats?.by_type ?? []).map((row) => (
                <div key={row.type} className="flex items-center justify-between text-xs">
                  <span className="capitalize text-ink-600 dark:text-ink-300">{row.type.replace(/_/g, " ")}</span>
                  <Badge tone="bg-ink-100 text-ink-600 dark:bg-white/10 dark:text-ink-300">{row.count}</Badge>
                </div>
              ))}
            </div>
            <div className="mt-4 border-t border-ink-100 pt-3 dark:border-white/5">
              <p className="mb-2 text-[10px] font-semibold uppercase tracking-wide text-ink-400">By priority</p>
              <div className="flex flex-wrap gap-1.5">
                {(stats?.by_priority ?? []).map((row) => (
                  <Badge
                    key={row.priority}
                    tone={
                      row.priority === "urgent"
                        ? "bg-rose-50 text-rose-700 dark:bg-rose-500/10 dark:text-rose-300"
                        : row.priority === "high"
                          ? "bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-300"
                          : "bg-ink-100 text-ink-600 dark:bg-white/10 dark:text-ink-300"
                    }
                  >
                    {row.priority} · {row.count}
                  </Badge>
                ))}
              </div>
            </div>
          </Card>

          <Card>
            <div className="flex gap-3">
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-amber-50 text-amber-600 dark:bg-amber-500/10 dark:text-amber-300">
                <BellOff className="h-4 w-4" />
              </span>
              <div>
                <h4 className="text-xs font-semibold text-ink-900 dark:text-white">Emergency escalation is manual</h4>
                <p className="mt-1 text-[11px] leading-relaxed text-ink-500 dark:text-ink-400">
                  Possible-accident alerts notify people only. This platform never automatically contacts emergency
                  services, and no notification is a confirmed emergency.
                </p>
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
