"use client";

import { useCallback, useEffect, useState } from "react";
import { Award, CalendarClock, Car, FileText, Plus, Search, ShieldCheck, TrendingDown, TrendingUp, UserPlus, Users } from "lucide-react";
import { api, type Paginated } from "@/lib/api";
import type { Driver, ScoreRow } from "@/lib/types";
import { Avatar, Badge, Button, Card, DemoBanner, EmptyState, Field, Input, Modal, PageHeader, PageSkeleton, Select, Textarea, toast } from "@/components/ui";
import { DataTable, type Column } from "@/components/tables/DataTable";
import { CategoryBars, Sparkline } from "@/components/charts";
import { cn, formatDate, formatKm, formatScore, scoreTone } from "@/lib/format";
import { confidenceLabel } from "@/lib/scoreDisplay";

const STATUS_OPTIONS = [
  { id: "all", label: "All statuses" },
  { id: "active", label: "Active" },
  { id: "inactive", label: "Inactive" },
  { id: "on_leave", label: "On leave" },
  { id: "suspended", label: "Suspended" },
];

const EMPTY_FORM = {
  first_name: "",
  last_name: "",
  email: "",
  phone: "",
  employee_id: "",
  licence_number: "",
  licence_class: "",
  licence_expiry: "",
  licence_issued: "",
  hire_date: "",
  status: "active",
  years_experience: 0,
  training_hours: 0,
  city: "",
  emergency_contact_name: "",
  emergency_contact_phone: "",
};

export default function DriversPage() {
  const [drivers, setDrivers] = useState<Driver[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(1);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("all");
  const [createOpen, setCreateOpen] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [detail, setDetail] = useState<Driver | null>(null);
  const [scores, setScores] = useState<ScoreRow[]>([]);
  const [latestScore, setLatestScore] = useState<ScoreRow | null>(null);
  const [scoreLoading, setScoreLoading] = useState(false);
  const [coaching, setCoaching] = useState<{ summary: string; strengths: string[]; recommendations: string[]; disclaimer: string } | null>(null);
  const [coachingLoading, setCoachingLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const result = await api.get<Paginated<Driver>>("/drivers", {
        page,
        page_size: 20,
        search: search || undefined,
        status: status === "all" ? undefined : status,
      });
      setDrivers(result.items ?? []);
      setTotal(result.total ?? 0);
      setPages(result.pages ?? 1);
    } catch {
      setDrivers([]);
    } finally {
      setLoading(false);
    }
  }, [page, search, status]);

  useEffect(() => setPage(1), [search, status]);
  useEffect(() => {
    void load();
  }, [load]);

  const openDetail = async (driver: Driver) => {
    setDetail(driver);
    setCoaching(null);
    setLatestScore(null);
    setScoreLoading(true);
    try {
      const result = await api.get<{ history: ScoreRow[]; latest?: ScoreRow }>(`/drivers/${driver.id}/scores`);
      setScores(result.history ?? []);
      setLatestScore(result.latest ?? result.history?.[0] ?? null);
    } catch {
      setScores([]);
    } finally {
      setScoreLoading(false);
    }
  };

  const generateCoaching = async () => {
    if (!detail) return;
    setCoachingLoading(true);
    try {
      const result = await api.post<{ summary: string; strengths: string[]; recommendations: string[]; disclaimer: string }>(
        `/drivers/${detail.id}/coaching-report`,
        {},
      );
      setCoaching(result);
    } catch (err) {
      toast(err instanceof Error ? err.message : "Could not generate the coaching report.", "error");
    } finally {
      setCoachingLoading(false);
    }
  };

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setSaving(true);
    try {
      const payload: Record<string, unknown> = {
        first_name: form.first_name.trim(),
        last_name: form.last_name.trim(),
        status: form.status,
        years_experience: Number(form.years_experience) || 0,
        training_hours: Number(form.training_hours) || 0,
      };
      if (form.email.trim()) payload.email = form.email.trim();
      if (form.phone.trim()) payload.phone = form.phone.trim();
      if (form.employee_id.trim()) payload.employee_id = form.employee_id.trim();
      if (form.licence_number.trim()) payload.licence_number = form.licence_number.trim();
      if (form.licence_class.trim()) payload.licence_class = form.licence_class.trim();
      if (form.licence_expiry) payload.licence_expiry = form.licence_expiry;
      if (form.licence_issued) payload.licence_issued = form.licence_issued;
      if (form.hire_date) payload.hire_date = form.hire_date;
      if (form.city.trim()) payload.city = form.city.trim();
      if (form.emergency_contact_name.trim()) payload.emergency_contact_name = form.emergency_contact_name.trim();
      if (form.emergency_contact_phone.trim()) payload.emergency_contact_phone = form.emergency_contact_phone.trim();

      await api.post("/drivers", payload);
      setCreateOpen(false);
      setForm(EMPTY_FORM);
      toast("Driver profile created.");
      await load();
    } catch (err) {
      toast(err instanceof Error ? err.message : "Could not create the driver.", "error");
    } finally {
      setSaving(false);
    }
  };

  const licenceExpiring = (driver: Driver) => {
    if (!driver.licence_expiry) return false;
    const days = (new Date(driver.licence_expiry).getTime() - Date.now()) / 86_400_000;
    return days >= 0 && days <= 45;
  };

  const columns: Column<Driver>[] = [
    {
      key: "driver",
      header: "Driver",
      render: (row) => (
        <div className="flex items-center gap-3">
          <Avatar name={row.full_name} color={row.avatar_color} size="sm" />
          <div>
            <p className="text-xs font-semibold text-ink-900 dark:text-white">{row.full_name}</p>
            <p className="text-[10px] text-ink-400">
              {row.employee_id ?? "No employee ID"} · {row.years_experience} yrs experience
            </p>
          </div>
        </div>
      ),
    },
    {
      key: "contact",
      header: "Contact",
      render: (row) => (
        <div className="text-xs">
          <p className="text-ink-700 dark:text-ink-200">{row.email ?? "—"}</p>
          <p className="text-[10px] text-ink-400">{row.phone_masked ?? "No phone"}</p>
        </div>
      ),
    },
    {
      key: "licence",
      header: "Licence",
      render: (row) => (
        <div className="text-xs">
          <p className="font-mono text-[11px] text-ink-600 dark:text-ink-300">{row.licence_number_masked ?? "—"}</p>
          <p className={cn("text-[10px]", licenceExpiring(row) ? "font-semibold text-amber-600" : "text-ink-400")}>
            {row.licence_expiry ? `${row.licence_class ?? ""} · ${formatDate(row.licence_expiry)}` : "No expiry"}
          </p>
        </div>
      ),
    },
    {
      key: "status",
      header: "Status",
      render: (row) => (
        <Badge tone={row.status === "active" ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300" : "bg-ink-100 text-ink-600 dark:bg-white/10 dark:text-ink-300"}>
          {row.status.replace("_", " ")}
        </Badge>
      ),
    },
    {
      key: "vehicles",
      header: "Vehicles",
      render: (row) => <span className="text-xs text-ink-600 dark:text-ink-300">{row.assigned_vehicle_ids?.length ?? 0}</span>,
    },
  ];

  if (loading && !drivers.length) return <PageSkeleton cards={4} />;

  return (
    <div>
      <PageHeader
        eyebrow="People · safety"
        title="Drivers"
        description="Driver profiles, licence compliance and per-driver safety scoring. Personal data is masked in list views."
        actions={
          <Button onClick={() => setCreateOpen(true)}>
            <UserPlus className="h-4 w-4" /> Add driver
          </Button>
        }
      />

      <DemoBanner message="Driver records are stored in this database. Their trips, events and scores come from simulated telemetry and are labelled as such." />

      <div className="page-grid">
        {[
          { label: "Drivers on record", value: total, icon: <Users className="h-5 w-5" /> },
          { label: "Active", value: drivers.filter((driver) => driver.status === "active").length, icon: <ShieldCheck className="h-5 w-5" /> },
          { label: "Licence expiring ≤45 days", value: drivers.filter(licenceExpiring).length, icon: <CalendarClock className="h-5 w-5" /> },
          { label: "Assigned to a vehicle", value: drivers.filter((driver) => (driver.assigned_vehicle_ids?.length ?? 0) > 0).length, icon: <Car className="h-5 w-5" /> },
        ].map((stat) => (
          <Card key={stat.label} className="p-5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-wide text-ink-500 dark:text-ink-400">{stat.label}</p>
                <p className="mt-2 text-2xl font-semibold tracking-tight text-ink-950 dark:text-white">{stat.value}</p>
              </div>
              <span className="text-ink-400">{stat.icon}</span>
            </div>
          </Card>
        ))}
      </div>

      <Card padded={false} className="mt-4">
        <div className="flex flex-col justify-between gap-3 border-b border-ink-100 p-4 dark:border-white/5 sm:flex-row sm:items-center">
          <div className="relative w-full max-w-xs">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-400" />
            <Input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search name, email, licence…" className="pl-9" aria-label="Search drivers" />
          </div>
          <Select value={status} onChange={(event) => setStatus(event.target.value)} className="w-[170px]" aria-label="Filter by status">
            {STATUS_OPTIONS.map((option) => (
              <option key={option.id} value={option.id}>{option.label}</option>
            ))}
          </Select>
        </div>
        <DataTable
          columns={columns}
          rows={drivers}
          loading={loading}
          onRowClick={(row) => void openDetail(row)}
          emptyTitle="No drivers match"
          emptyDescription="Try clearing filters or add a driver profile."
        />
        <div className="border-t border-ink-100 px-4 py-3 text-xs text-ink-500 dark:border-white/5 dark:text-ink-400">
          Page {page} of {Math.max(1, pages)} · {total} drivers
          <div className="mt-2 flex gap-2">
            <Button size="sm" variant="secondary" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</Button>
            <Button size="sm" variant="secondary" disabled={page >= pages} onClick={() => setPage(page + 1)}>Next</Button>
          </div>
        </div>
      </Card>

      <Modal
        open={detail !== null}
        onClose={() => setDetail(null)}
        title={detail?.full_name ?? "Driver"}
        description={detail ? `${detail.employee_id ?? "No employee ID"} · ${detail.status.replace("_", " ")}` : ""}
        size="lg"
        footer={
          <>
            <Button variant="secondary" onClick={generateCoaching} loading={coachingLoading}>
              <FileText className="h-4 w-4" /> Generate coaching report
            </Button>
            <Button variant="primary" onClick={() => setDetail(null)}>Close</Button>
          </>
        }
      >
        {detail && (
          <div className="space-y-5">
            <div className="flex items-start gap-4">
              <Avatar name={detail.full_name} color={detail.avatar_color} size="lg" />
              <div className="min-w-0 flex-1">
                <h3 className="text-base font-semibold text-ink-950 dark:text-white">{detail.full_name}</h3>
                <p className="text-xs text-ink-500 dark:text-ink-400">{detail.email ?? "No email on file"}</p>
                <p className="text-[11px] text-ink-400">{detail.phone_masked ?? "No phone on file"} · {detail.city ?? "No city"}</p>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  <Badge tone="bg-brand-50 text-brand-700 dark:bg-brand-500/10 dark:text-brand-300">{detail.licence_class ?? "No class"}</Badge>
                  <Badge tone="bg-ink-100 text-ink-600 dark:bg-white/10 dark:text-ink-300">
                    Licence {detail.licence_number_masked ?? "not recorded"}
                  </Badge>
                  <Badge tone={licenceExpiring(detail) ? "bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-300" : "bg-ink-100 text-ink-600 dark:bg-white/10 dark:text-ink-300"}>
                    Expires {detail.licence_expiry ? formatDate(detail.licence_expiry) : "—"}
                  </Badge>
                </div>
              </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-3">
              <div className="rounded-xl bg-ink-50 p-3 dark:bg-white/5">
                <p className="text-[10px] uppercase tracking-wide text-ink-400">Latest score</p>
                <p className={cn("mt-1 text-lg font-semibold", latestScore ? "" : "text-ink-400")}>
                  {latestScore ? formatScore(latestScore.overall_score) : "No data"}
                </p>
              </div>
              <div className="rounded-xl bg-ink-50 p-3 dark:bg-white/5">
                <p className="text-[10px] uppercase tracking-wide text-ink-400">Events</p>
                <p className="mt-1 text-lg font-semibold text-ink-900 dark:text-white">{latestScore?.events_count ?? "—"}</p>
              </div>
              <div className="rounded-xl bg-ink-50 p-3 dark:bg-white/5">
                <p className="text-[10px] uppercase tracking-wide text-ink-400">Distance</p>
                <p className="mt-1 text-lg font-semibold text-ink-900 dark:text-white">{latestScore ? formatKm(latestScore.distance_km) : "—"}</p>
              </div>
            </div>

            {scoreLoading ? (
              <div className="skeleton h-40 w-full" />
            ) : latestScore ? (
              <div className="grid gap-5 sm:grid-cols-2">
                <div>
                  <h4 className="mb-3 text-xs font-semibold text-ink-900 dark:text-white">Score breakdown</h4>
                  <CategoryBars
                    categories={[
                      { key: "speed", label: "Speed compliance", value: latestScore.speed_score },
                      { key: "braking", label: "Smooth braking", value: latestScore.braking_score },
                      { key: "acceleration", label: "Acceleration", value: latestScore.acceleration_score },
                      { key: "cornering", label: "Cornering", value: latestScore.cornering_score },
                      { key: "consistency", label: "Consistency", value: latestScore.consistency_score },
                    ]}
                  />
                </div>
                <div>
                  <h4 className="mb-3 text-xs font-semibold text-ink-900 dark:text-white">Score trend</h4>
                  <Sparkline values={scores.map((score) => score.overall_score).reverse()} width={220} height={56} />
                  <div className="mt-2 flex items-center gap-1.5 text-xs">
                    {scores.length > 1 && scores[0].overall_score > scores[1].overall_score ? (
                      <>
                        <TrendingUp className="h-3.5 w-3.5 text-emerald-500" />
                        <span className="text-emerald-600">+{(scores[0].overall_score - scores[1].overall_score).toFixed(1)} vs previous</span>
                      </>
                    ) : scores.length > 1 ? (
                      <>
                        <TrendingDown className="h-3.5 w-3.5 text-rose-500" />
                        <span className="text-rose-600">{(scores[0].overall_score - scores[1].overall_score).toFixed(1)} vs previous</span>
                      </>
                    ) : (
                      <span className="text-ink-400">Only one scored period</span>
                    )}
                  </div>
                  <p className="mt-3 text-[10px] leading-relaxed text-ink-400">
                    {confidenceLabel(latestScore.confidence)} · model {latestScore.model_version}. Scores are coaching aids, not
                    evidence for disciplinary action on their own.
                  </p>
                </div>
              </div>
            ) : (
              <EmptyState
                icon={<Award className="h-5 w-5" />}
                title="No scored periods yet"
                description="Scores are computed from recorded trips. With only simulated trips, coverage may be low."
              />
            )}

            {coaching && (
              <div className="rounded-2xl border border-brand-200 bg-brand-50/50 p-4 dark:border-brand-500/20 dark:bg-brand-500/5">
                <div className="mb-2 flex items-center gap-2">
                  <Award className="h-4 w-4 text-brand-600 dark:text-brand-300" />
                  <h4 className="text-xs font-semibold text-ink-900 dark:text-white">AI coaching summary</h4>
                </div>
                <p className="text-xs leading-relaxed text-ink-700 dark:text-ink-200">{coaching.summary}</p>
                <div className="mt-3 grid gap-3 sm:grid-cols-2">
                  <div>
                    <p className="text-[10px] font-semibold uppercase tracking-wide text-emerald-600">Strengths</p>
                    <ul className="mt-1 space-y-1 text-[11px] text-ink-600 dark:text-ink-300">
                      {coaching.strengths.map((item) => <li key={item}>· {item}</li>)}
                    </ul>
                  </div>
                  <div>
                    <p className="text-[10px] font-semibold uppercase tracking-wide text-amber-600">Focus areas</p>
                    <ul className="mt-1 space-y-1 text-[11px] text-ink-600 dark:text-ink-300">
                      {coaching.recommendations.map((item) => <li key={item}>· {item}</li>)}
                    </ul>
                  </div>
                </div>
                <p className="mt-3 text-[10px] leading-relaxed text-ink-400">{coaching.disclaimer}</p>
              </div>
            )}
          </div>
        )}
      </Modal>

      <Modal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        title="Add driver"
        description="Create a driver profile. Sensitive fields are encrypted at rest and masked in responses."
        size="lg"
        footer={
          <>
            <Button variant="secondary" onClick={() => setCreateOpen(false)}>Cancel</Button>
            <Button onClick={submit} loading={saving}>Add driver</Button>
          </>
        }
      >
        <form onSubmit={submit} className="grid gap-4 sm:grid-cols-2">
          <Field label="First name" required>
            <Input value={form.first_name} onChange={(event) => setForm({ ...form, first_name: event.target.value })} required maxLength={60} />
          </Field>
          <Field label="Last name" required>
            <Input value={form.last_name} onChange={(event) => setForm({ ...form, last_name: event.target.value })} required maxLength={60} />
          </Field>
          <Field label="Email">
            <Input type="email" value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} placeholder="driver@company.com" />
          </Field>
          <Field label="Phone">
            <Input value={form.phone} onChange={(event) => setForm({ ...form, phone: event.target.value })} placeholder="+91 98765 43210" />
          </Field>
          <Field label="Employee ID">
            <Input value={form.employee_id} onChange={(event) => setForm({ ...form, employee_id: event.target.value })} placeholder="DRV-0042" />
          </Field>
          <Field label="Licence class">
            <Select value={form.licence_class} onChange={(event) => setForm({ ...form, licence_class: event.target.value })}>
              <option value="">Not recorded</option>
              {["LMV", "MCWG", "HMV", "TRANSPORT", "PSV"].map((item) => <option key={item} value={item}>{item}</option>)}
            </Select>
          </Field>
          <Field label="Licence number" hint="Stored encrypted and returned masked.">
            <Input value={form.licence_number} onChange={(event) => setForm({ ...form, licence_number: event.target.value })} maxLength={40} />
          </Field>
          <Field label="Licence expiry">
            <Input type="date" value={form.licence_expiry} onChange={(event) => setForm({ ...form, licence_expiry: event.target.value })} />
          </Field>
          <Field label="Licence issued">
            <Input type="date" value={form.licence_issued} onChange={(event) => setForm({ ...form, licence_issued: event.target.value })} />
          </Field>
          <Field label="Hire date">
            <Input type="date" value={form.hire_date} onChange={(event) => setForm({ ...form, hire_date: event.target.value })} />
          </Field>
          <Field label="Status">
            <Select value={form.status} onChange={(event) => setForm({ ...form, status: event.target.value })}>
              {STATUS_OPTIONS.filter((option) => option.id !== "all").map((option) => <option key={option.id} value={option.id}>{option.label}</option>)}
            </Select>
          </Field>
          <Field label="Years of experience">
            <Input type="number" min={0} max={60} value={form.years_experience} onChange={(event) => setForm({ ...form, years_experience: Number(event.target.value) })} />
          </Field>
          <Field label="Training hours">
            <Input type="number" min={0} step={0.5} value={form.training_hours} onChange={(event) => setForm({ ...form, training_hours: Number(event.target.value) })} />
          </Field>
          <Field label="City">
            <Input value={form.city} onChange={(event) => setForm({ ...form, city: event.target.value })} />
          </Field>
          <Field label="Emergency contact name">
            <Input value={form.emergency_contact_name} onChange={(event) => setForm({ ...form, emergency_contact_name: event.target.value })} />
          </Field>
          <Field label="Emergency contact phone">
            <Input value={form.emergency_contact_phone} onChange={(event) => setForm({ ...form, emergency_contact_phone: event.target.value })} />
          </Field>
          <button type="submit" className="hidden" aria-hidden="true" />
        </form>
      </Modal>
    </div>
  );
}
