"use client";

import { useCallback, useEffect, useState } from "react";
import { BarChart3, CalendarRange, Download, FileSpreadsheet, FileText, RefreshCw, Sparkles } from "lucide-react";
import { api, tokenStore, type Paginated } from "@/lib/api";
import type { Driver, ReportSummary, Vehicle } from "@/lib/types";
import { Badge, Button, Card, DemoBanner, EmptyState, Field, Input, Modal, PageHeader, PageSkeleton, Select, toast } from "@/components/ui";
import { DataTable, type Column } from "@/components/tables/DataTable";
import { EventTypeBarChart, SeverityDonut, TrendAreaChart } from "@/components/charts";
import { cn, formatNumber, timeAgo } from "@/lib/format";

type ReportType = { code: string; title: string; default_days: number };

type ReportRecord = {
  id: number;
  report_type: string;
  title: string;
  params: Record<string, unknown>;
  format: string;
  status: string;
  row_count: number;
  error_message?: string | null;
  created_at: string;
};

const EMPTY_FORM = {
  report_type: "weekly_safety",
  format: "pdf",
  from_date: "",
  to_date: "",
  driver_id: "",
  vehicle_id: "",
  title: "",
};

function defaultRange(days: number) {
  const to = new Date();
  const from = new Date(Date.now() - days * 86_400_000);
  return {
    from_date: from.toISOString().slice(0, 10),
    to_date: to.toISOString().slice(0, 10),
  };
}

export default function ReportsPage() {
  const [types, setTypes] = useState<ReportType[]>([]);
  const [history, setHistory] = useState<ReportRecord[]>([]);
  const [drivers, setDrivers] = useState<Driver[]>([]);
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [summary, setSummary] = useState<ReportSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [downloading, setDownloading] = useState<number | null>(null);
  const [preview, setPreview] = useState<ReportRecord | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [typeData, historyData, driverData, vehicleData, summaryData] = await Promise.all([
        api.get<{ types: ReportType[] }>("/reports/types"),
        api.get<Paginated<ReportRecord>>("/reports", { page_size: 20 }),
        api.get<Paginated<Driver>>("/drivers", { page_size: 100 }),
        api.get<Paginated<Vehicle>>("/vehicles", { page_size: 100 }),
        api.get<ReportSummary>("/reports/summary", { report_type: "weekly_safety" }),
      ]);
      setTypes(typeData.types ?? []);
      setHistory(historyData.items ?? []);
      setDrivers(driverData.items ?? []);
      setVehicles(vehicleData.items ?? []);
      setSummary(summaryData);
    } catch (err) {
      toast(err instanceof Error ? err.message : "Could not load reports.", "error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const openCreate = () => {
    const defaultType = types.find((type) => type.code === form.report_type) ?? types[0];
    const range = defaultRange(defaultType?.default_days ?? 30);
    setForm((current) => ({ ...current, ...range, title: "" }));
    setCreateOpen(true);
  };

  const changeType = (code: string) => {
    const type = types.find((item) => item.code === code);
    if (!type) {
      setForm((current) => ({ ...current, report_type: code }));
      return;
    }
    setForm((current) => ({ ...current, report_type: code, ...defaultRange(type.default_days) }));
  };

  const generate = async (event: React.FormEvent) => {
    event.preventDefault();
    setGenerating(true);
    try {
      const payload: Record<string, unknown> = {
        report_type: form.report_type,
        format: form.format,
      };
      if (form.title.trim()) payload.title = form.title.trim();
      if (form.from_date) payload.from_date = `${form.from_date}T00:00:00`;
      if (form.to_date) payload.to_date = `${form.to_date}T23:59:59`;
      if (form.driver_id) payload.driver_id = Number(form.driver_id);
      if (form.vehicle_id) payload.vehicle_id = Number(form.vehicle_id);

      const created = await api.post<ReportRecord>("/reports/generate", payload);
      setCreateOpen(false);
      toast(`Report generated (${created.row_count} rows).`);
      await load();
      setPreview(created);
    } catch (err) {
      toast(err instanceof Error ? err.message : "Report generation failed.", "error");
    } finally {
      setGenerating(false);
    }
  };

  const download = async (report: ReportRecord) => {
    setDownloading(report.id);
    try {
      const base = process.env.NEXT_PUBLIC_API_BASE || "/api/v1";
      const response = await fetch(`${base}/reports/${report.id}/download`, {
        headers: { Authorization: `Bearer ${tokenStore.get().access ?? ""}` },
      });
      if (!response.ok) throw new Error("The report file is not available. It may have been cleaned up by retention.");
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `${report.title.replace(/\s+/g, "_").toLowerCase()}.${report.format}`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
      toast("Download started.");
    } catch (err) {
      toast(err instanceof Error ? err.message : "Download failed.", "error");
    } finally {
      setDownloading(null);
    }
  };

  const columns: Column<ReportRecord>[] = [
    {
      key: "title",
      header: "Report",
      render: (row) => (
        <div>
          <p className="text-xs font-semibold text-ink-900 dark:text-white">{row.title}</p>
          <p className="text-[10px] text-ink-400">{row.report_type.replace(/_/g, " ")} · {timeAgo(row.created_at)}</p>
        </div>
      ),
    },
    { key: "format", header: "Format", render: (row) => <Badge tone="bg-ink-100 text-ink-600 dark:bg-white/10 dark:text-ink-300" className="uppercase">{row.format}</Badge> },
    { key: "rows", header: "Rows", align: "right", render: (row) => <span className="text-xs tabular-nums">{formatNumber(row.row_count)}</span> },
    {
      key: "status",
      header: "Status",
      render: (row) => (
        <Badge tone={row.status === "completed" ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300" : "bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-300"}>
          {row.status.replace(/_/g, " ")}
        </Badge>
      ),
    },
    {
      key: "actions",
      header: "",
      render: (row) => (
        <Button size="sm" variant="secondary" onClick={() => void download(row)} loading={downloading === row.id}>
          <Download className="h-3.5 w-3.5" /> Download
        </Button>
      ),
    },
  ];

  if (loading && !types.length) return <PageSkeleton cards={4} />;

  return (
    <div>
      <PageHeader
        eyebrow="Insights · reporting"
        title="Reports"
        description="Nine report types with PDF and CSV export. Every export records its filters so results stay reproducible."
        actions={
          <>
            <Button variant="secondary" onClick={() => void load()}>
              <RefreshCw className="h-4 w-4" /> Refresh
            </Button>
            <Button onClick={openCreate}>
              <BarChart3 className="h-4 w-4" /> Generate report
            </Button>
          </>
        }
      />

      <DemoBanner message="Report contents reflect this database, whose telemetry is simulated. Exports include a provenance note and must not be presented as real-world safety statistics." />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {[
          { label: "Reports generated", value: history.length, icon: <FileText className="h-5 w-5" />, hint: "Visible in this list" },
          { label: "Report types", value: types.length, icon: <BarChart3 className="h-5 w-5" />, hint: "PDF and CSV" },
          { label: "Rows in latest", value: history[0]?.row_count ?? 0, icon: <FileSpreadsheet className="h-5 w-5" />, hint: history[0]?.report_type.replace(/_/g, " ") ?? "No reports yet" },
          { label: "Last generated", value: history[0] ? timeAgo(history[0].created_at) : "—", icon: <CalendarRange className="h-5 w-5" />, hint: "Newest export" },
        ].map((stat) => (
          <Card key={stat.label} className="p-5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-wide text-ink-500 dark:text-ink-400">{stat.label}</p>
                <p className="mt-2 text-xl font-semibold tracking-tight text-ink-950 dark:text-white">{stat.value}</p>
                <p className="mt-1 text-[10px] text-ink-400">{stat.hint}</p>
              </div>
              <span className="text-ink-400">{stat.icon}</span>
            </div>
          </Card>
        ))}
      </div>

      {summary && (
        <div className="mt-4 grid gap-4 lg:grid-cols-3">
          <Card title="Weekly preview — trend" subtitle={summary.period ? `${summary.period.from?.slice(0, 10)} → ${summary.period.to?.slice(0, 10)}` : ""} className="lg:col-span-2">
            <TrendAreaChart data={(summary.charts?.trend ?? []).map((point) => ({ label: point.label ?? "", events: point.events, high_risk: point.high_risk }))} height={230} />
          </Card>
          <Card title="Severity mix" subtitle="From the weekly summary">
            <SeverityDonut data={summary.charts?.events_by_severity ?? []} height={230} />
          </Card>
        </div>
      )}

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <Card title="Available report types" subtitle="Each export is generated from live database queries">
          <div className="grid gap-2 sm:grid-cols-2">
            {types.map((type) => (
              <button
                key={type.code}
                onClick={() => { changeType(type.code); openCreate(); }}
                className="group flex items-center gap-3 rounded-xl border border-ink-100 bg-ink-50/60 p-3 text-left transition hover:border-brand-300 hover:bg-brand-50/60 dark:border-white/10 dark:bg-white/5 dark:hover:border-brand-500/40"
              >
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white text-ink-500 shadow-sm dark:bg-white/10 dark:text-ink-300">
                  <FileText className="h-3.5 w-3.5" />
                </span>
                <span className="min-w-0">
                  <span className="block truncate text-xs font-semibold text-ink-900 dark:text-white">{type.title}</span>
                  <span className="block text-[10px] text-ink-400">{type.default_days}-day default window</span>
                </span>
              </button>
            ))}
          </div>
        </Card>

        <Card title="Export behaviour" subtitle="How downloads work">
          <ul className="space-y-2.5 text-xs leading-relaxed text-ink-600 dark:text-ink-300">
            <li className="flex gap-2"><Sparkles className="mt-0.5 h-3.5 w-3.5 shrink-0 text-brand-500" /> PDF exports are rendered server-side and include a data provenance footer.</li>
            <li className="flex gap-2"><Sparkles className="mt-0.5 h-3.5 w-3.5 shrink-0 text-brand-500" /> CSV exports use UTF-8 with headers and are safe to open in spreadsheet tools.</li>
            <li className="flex gap-2"><Sparkles className="mt-0.5 h-3.5 w-3.5 shrink-0 text-brand-500" /> Files are stored under the server data directory and subject to retention cleanup.</li>
            <li className="flex gap-2"><Sparkles className="mt-0.5 h-3.5 w-3.5 shrink-0 text-brand-500" /> Generation is permission-gated and every download is authenticated — no public links.</li>
            <li className="flex gap-2"><Sparkles className="mt-0.5 h-3.5 w-3.5 shrink-0 text-brand-500" /> Report limits follow the organisation's plan; exceeding a limit returns a clear error.</li>
          </ul>
        </Card>
      </div>

      <Card padded={false} className="mt-4" title="Report history" subtitle="Newest first">
        <DataTable
          columns={columns}
          rows={history}
          loading={loading}
          onRowClick={setPreview}
          emptyTitle="No reports generated yet"
          emptyDescription="Generate your first report to see it listed here."
          minWidth={680}
        />
      </Card>

      <Modal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        title="Generate report"
        description="Choose a type, date window and format. Filters are stored with the report."
        size="lg"
        footer={
          <>
            <Button variant="secondary" onClick={() => setCreateOpen(false)}>Cancel</Button>
            <Button onClick={generate} loading={generating}>Generate report</Button>
          </>
        }
      >
        <form onSubmit={generate} className="grid gap-4 sm:grid-cols-2">
          <Field label="Report type" required>
            <Select value={form.report_type} onChange={(event) => changeType(event.target.value)}>
              {types.map((type) => <option key={type.code} value={type.code}>{type.title}</option>)}
            </Select>
          </Field>
          <Field label="Format" required hint="PDF for sharing, CSV for analysis.">
            <Select value={form.format} onChange={(event) => setForm({ ...form, format: event.target.value })}>
              <option value="pdf">PDF document</option>
              <option value="csv">CSV spreadsheet</option>
            </Select>
          </Field>
          <div className="sm:col-span-2">
            <Field label="Title" hint="Optional. Defaults to the report type and period.">
              <Input value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} placeholder="Weekly safety — Meridian Logistics" />
            </Field>
          </div>
          <Field label="From date">
            <Input type="date" value={form.from_date} onChange={(event) => setForm({ ...form, from_date: event.target.value })} />
          </Field>
          <Field label="To date">
            <Input type="date" value={form.to_date} onChange={(event) => setForm({ ...form, to_date: event.target.value })} />
          </Field>
          <Field label="Driver filter">
            <Select value={form.driver_id} onChange={(event) => setForm({ ...form, driver_id: event.target.value })}>
              <option value="">All drivers</option>
              {drivers.map((driver) => <option key={driver.id} value={driver.id}>{driver.full_name}</option>)}
            </Select>
          </Field>
          <Field label="Vehicle filter">
            <Select value={form.vehicle_id} onChange={(event) => setForm({ ...form, vehicle_id: event.target.value })}>
              <option value="">All vehicles</option>
              {vehicles.map((vehicle) => <option key={vehicle.id} value={vehicle.id}>{vehicle.registration_number}</option>)}
            </Select>
          </Field>
          <div className="sm:col-span-2 rounded-xl bg-amber-50 p-3 text-[11px] leading-relaxed text-amber-800 dark:bg-amber-500/10 dark:text-amber-200">
            Reports describe recorded data only. They do not predict accidents and must not be used as the sole basis for
            disciplinary decisions.
          </div>
          <button type="submit" className="hidden" aria-hidden="true" />
        </form>
      </Modal>

      <Modal
        open={preview !== null}
        onClose={() => setPreview(null)}
        title={preview?.title ?? "Report"}
        description={preview ? `${preview.report_type.replace(/_/g, " ")} · ${preview.row_count} rows · generated ${timeAgo(preview.created_at)}` : ""}
        size="md"
        footer={
          preview ? (
            <>
              <Button variant="secondary" onClick={() => setPreview(null)}>Close</Button>
              <Button onClick={() => void download(preview)} loading={downloading === preview.id}>
                <Download className="h-4 w-4" /> Download {preview.format.toUpperCase()}
              </Button>
            </>
          ) : null
        }
      >
        {preview && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              {[
                ["Status", preview.status.replace(/_/g, " ")],
                ["Rows", String(preview.row_count)],
                ["Format", preview.format.toUpperCase()],
                ["Created", new Date(preview.created_at).toLocaleString()],
              ].map(([label, value]) => (
                <div key={label} className="rounded-xl bg-ink-50 p-3 dark:bg-white/5">
                  <p className="text-[10px] uppercase tracking-wide text-ink-400">{label}</p>
                  <p className="mt-0.5 text-xs font-semibold capitalize text-ink-900 dark:text-white">{value}</p>
                </div>
              ))}
            </div>
            <div>
              <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-ink-400">Stored parameters</p>
              <pre className="max-h-48 overflow-auto rounded-xl bg-ink-950 p-3 text-[10px] leading-relaxed text-ink-200">
                {JSON.stringify(preview.params ?? {}, null, 2)}
              </pre>
            </div>
            {preview.error_message && (
              <p className="rounded-lg bg-rose-50 px-3 py-2 text-xs text-rose-700 dark:bg-rose-500/10 dark:text-rose-200">
                {preview.error_message}
              </p>
            )}
          </div>
        )}
      </Modal>
    </div>
  );
}
