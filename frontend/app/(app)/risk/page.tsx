"use client";

import { useCallback, useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Activity, BrainCircuit, Gauge, Info, Radar, RefreshCw, ShieldAlert, Sparkles, TriangleAlert, UserSearch } from "lucide-react";
import { api, type Paginated } from "@/lib/api";
import type { Driver, RiskAssessment } from "@/lib/types";
import { Avatar, Badge, Button, Card, DemoBanner, EmptyState, Field, Input, Modal, PageHeader, PageSkeleton, Select, toast } from "@/components/ui";
import { DataTable, type Column, Pagination } from "@/components/tables/DataTable";
import { Sparkline } from "@/components/charts";
import { cn, formatNumber, riskTone, timeAgo } from "@/lib/format";
import { confidenceLabel } from "@/lib/scoreDisplay";

type ModelInfo = {
  name: string;
  version: string;
  type: string;
  metrics: Record<string, number>;
  feature_importance: Record<string, number>;
  features: string[];
  training: Record<string, unknown>;
  limitations: string[];
  disclaimer: string;
};

type Overview = {
  generated_at: string;
  total_assessed: number;
  by_level: { level: string; count: number }[];
  high_risk_drivers: Record<string, unknown>[];
  fleet_risk_index: number;
  model_info: ModelInfo;
  disclaimer: string;
};

const LEVELS: ("low" | "moderate" | "high" | "critical")[] = ["low", "moderate", "high", "critical"];

export default function RiskPage() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [model, setModel] = useState<ModelInfo | null>(null);
  const [drivers, setDrivers] = useState<Driver[]>([]);
  const [assessments, setAssessments] = useState<RiskAssessment[]>([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [assessOpen, setAssessOpen] = useState(false);
  const [driverId, setDriverId] = useState("");
  const [vehicleId, setVehicleId] = useState("");
  const [assessing, setAssessing] = useState(false);
  const [result, setResult] = useState<RiskAssessment | null>(null);
  const [detail, setDetail] = useState<RiskAssessment | null>(null);
  const [fleetRunning, setFleetRunning] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [overviewData, modelData, driverData, history] = await Promise.all([
        api.get<Overview>("/risk/overview"),
        api.get<ModelInfo>("/risk/model-info"),
        api.get<Paginated<Driver>>("/drivers", { page_size: 100 }),
        api.get<Paginated<RiskAssessment>>("/risk/assessments", { page, page_size: 15 }),
      ]);
      setOverview(overviewData);
      setModel(modelData);
      setDrivers(driverData.items ?? []);
      setAssessments(history.items ?? []);
      setTotal(history.total ?? 0);
      setPages(history.pages ?? 1);
    } catch (err) {
      toast(err instanceof Error ? err.message : "Could not load risk analysis.", "error");
    } finally {
      setLoading(false);
    }
  }, [page]);

  useEffect(() => {
    void load();
  }, [load]);

  const assess = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!driverId) return;
    setAssessing(true);
    setResult(null);
    try {
      const payload: Record<string, unknown> = { driver_id: Number(driverId) };
      if (vehicleId) payload.vehicle_id = Number(vehicleId);
      const created = await api.post<RiskAssessment>("/risk/assess", payload);
      setResult(created);
      toast("Assessment complete.");
      await load();
    } catch (err) {
      toast(err instanceof Error ? err.message : "Assessment failed.", "error");
    } finally {
      setAssessing(false);
    }
  };

  const runFleet = async () => {
    setFleetRunning(true);
    try {
      const created = await api.post<RiskAssessment[]>("/risk/assess-fleet", {});
      toast(`Assessed ${created.length} drivers.`);
      await load();
    } catch (err) {
      toast(err instanceof Error ? err.message : "Fleet assessment failed.", "error");
    } finally {
      setFleetRunning(false);
    }
  };

  const columns: Column<RiskAssessment>[] = [
    {
      key: "driver",
      header: "Driver",
      render: (row) => (
        <div className="flex items-center gap-2.5">
          <Avatar name={row.driver_name} color="#6366f1" size="sm" />
          <div>
            <p className="text-xs font-semibold text-ink-900 dark:text-white">{row.driver_name ?? "Unknown driver"}</p>
            <p className="text-[10px] text-ink-400">{row.registration_number ?? "No vehicle"} · {timeAgo(row.created_at)}</p>
          </div>
        </div>
      ),
    },
    {
      key: "level",
      header: "Risk level",
      render: (row) => <Badge tone={riskTone(row.risk_level)}>{row.risk_level}</Badge>,
    },
    {
      key: "score",
      header: "Score",
      align: "right",
      render: (row) => (
        <div className="flex items-center justify-end gap-2">
          <div className="h-1.5 w-16 overflow-hidden rounded-full bg-ink-100 dark:bg-white/10">
            <div
              className={cn("h-full rounded-full", row.risk_level === "critical" ? "bg-rose-500" : row.risk_level === "high" ? "bg-amber-500" : row.risk_level === "moderate" ? "bg-indigo-500" : "bg-emerald-500")}
              style={{ width: `${Math.min(100, row.risk_score * 100)}%` }}
            />
          </div>
          <span className="text-xs font-semibold tabular-nums">{row.risk_score.toFixed(2)}</span>
        </div>
      ),
    },
    {
      key: "confidence",
      header: "Confidence",
      render: (row) => (
        <span className="text-xs text-ink-600 dark:text-ink-300">{Math.round(row.confidence * 100)}%</span>
      ),
    },
    {
      key: "model",
      header: "Model",
      render: (row) => <span className="font-mono text-[10px] text-ink-400">{row.model_version}</span>,
    },
  ];

  if (loading && !overview) return <PageSkeleton cards={4} />;

  const highRisk = overview?.high_risk_drivers ?? [];
  const importance = Object.entries(model?.feature_importance ?? {})
    .map(([feature, value]) => ({ feature, importance: Number(value) }))
    .sort((a, b) => b.importance - a.importance)
    .slice(0, 8);

  return (
    <div>
      <PageHeader
        eyebrow="Safety intelligence · AI"
        title="AI risk analysis"
        description="A rule-assisted gradient-boosted model ranks drivers for review. It outputs triage priority, not accident predictions."
        actions={
          <>
            <Button variant="secondary" onClick={() => void load()}>
              <RefreshCw className="h-4 w-4" /> Refresh
            </Button>
            <Button variant="secondary" onClick={runFleet} loading={fleetRunning}>
              <Radar className="h-4 w-4" /> Assess fleet
            </Button>
            <Button onClick={() => setAssessOpen(true)}>
              <UserSearch className="h-4 w-4" /> Assess driver
            </Button>
          </>
        }
      />

      <DemoBanner message="Model inputs in this environment are largely simulated. Scores are illustrative of the method, not a measurement of any real driver." />

      <div className="page-grid">
        <Card className="p-5">
          <p className="text-[10px] font-semibold uppercase tracking-wide text-ink-500 dark:text-ink-400">Drivers assessed</p>
          <p className="mt-2 text-2xl font-semibold tracking-tight text-ink-950 dark:text-white">{formatNumber(overview?.total_assessed)}</p>
          <p className="mt-1 text-[11px] text-ink-400">Latest assessment per driver</p>
        </Card>
        <Card className="p-5">
          <p className="text-[10px] font-semibold uppercase tracking-wide text-ink-500 dark:text-ink-400">Fleet risk index</p>
          <p className="mt-2 text-2xl font-semibold tracking-tight text-ink-950 dark:text-white">{overview ? overview.fleet_risk_index.toFixed(2) : "—"}</p>
          <p className="mt-1 text-[11px] text-ink-400">Mean risk score, 0–1</p>
        </Card>
        <Card className="p-5">
          <p className="text-[10px] font-semibold uppercase tracking-wide text-ink-500 dark:text-ink-400">High + critical</p>
          <p className="mt-2 text-2xl font-semibold tracking-tight text-rose-600">{formatNumber(overview?.by_level.filter((row) => row.level === "high" || row.level === "critical").reduce((sum, row) => sum + row.count, 0))}</p>
          <p className="mt-1 text-[11px] text-ink-400">Recommended for review</p>
        </Card>
        <Card className="p-5">
          <p className="text-[10px] font-semibold uppercase tracking-wide text-ink-500 dark:text-ink-400">Model</p>
          <p className="mt-2 truncate text-sm font-semibold text-ink-950 dark:text-white">{model?.name ?? "—"}</p>
          <p className="mt-1 font-mono text-[10px] text-ink-400">{model?.version}</p>
        </Card>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <Card title="Risk distribution" subtitle="Latest assessment per driver" className="lg:col-span-1">
          <div className="space-y-3">
            {LEVELS.map((level) => {
              const count = overview?.by_level.find((row) => row.level === level)?.count ?? 0;
              const max = Math.max(1, ...(overview?.by_level.map((row) => row.count) ?? [1]));
              return (
                <div key={level}>
                  <div className="mb-1 flex items-center justify-between text-xs">
                    <span className="capitalize text-ink-600 dark:text-ink-300">{level}</span>
                    <span className="font-semibold text-ink-900 dark:text-white">{count}</span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-ink-100 dark:bg-white/10">
                    <div
                      className={cn("h-full rounded-full", level === "critical" ? "bg-rose-500" : level === "high" ? "bg-amber-500" : level === "moderate" ? "bg-indigo-500" : "bg-emerald-500")}
                      style={{ width: `${(count / max) * 100}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
          <div className="mt-5 flex items-start gap-2 rounded-xl bg-amber-50 p-3 text-[11px] leading-relaxed text-amber-800 dark:bg-amber-500/10 dark:text-amber-200">
            <TriangleAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            High or critical risk means "prioritise a human review", not "this driver will crash".
          </div>
        </Card>

        <Card
          title="Priority review list"
          subtitle="High and critical drivers"
          className="lg:col-span-2"
          padded={false}
          action={<Sparkles className="h-4 w-4 text-brand-500" />}
        >
          {highRisk.length === 0 ? (
            <div className="p-4">
              <EmptyState icon={<ShieldAlert className="h-5 w-5" />} title="No high-risk drivers" description="Run a fleet assessment to rank drivers." />
            </div>
          ) : (
            <div className="divide-y divide-ink-100 dark:divide-white/5">
              {highRisk.slice(0, 8).map((row) => {
                const name = String(row.driver_name ?? "Unknown");
                const level = String(row.risk_level ?? "moderate");
                const score = Number(row.risk_score ?? 0);
                return (
                  <div key={`${row.driver_id}-${score}`} className="flex flex-wrap items-center gap-3 px-4 py-3">
                    <Avatar name={name} color={level === "critical" ? "#e11d48" : "#f59e0b"} size="sm" />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-xs font-semibold text-ink-900 dark:text-white">{name}</p>
                      <p className="truncate text-[10px] text-ink-400">
                        {String(row.registration_number ?? "No vehicle")} · confidence {Math.round(Number(row.confidence ?? 0) * 100)}%
                      </p>
                    </div>
                    <Badge tone={riskTone(level)}>{level}</Badge>
                    <span className="w-10 text-right text-xs font-semibold tabular-nums">{score.toFixed(2)}</span>
                  </div>
                );
              })}
            </div>
          )}
        </Card>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <Card title="Model performance" subtitle="Holdout evaluation on synthetic historical data">
          {model ? (
            <>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                {[
                  ["AUC", model.metrics.auc, "Higher is better"],
                  ["Brier", model.metrics.brier, "Lower is better"],
                  ["Accuracy", model.metrics.accuracy, "Share correct"],
                  ["Precision", model.metrics.precision, "Of flagged, share true"],
                  ["Recall", model.metrics.recall, "Of true, share flagged"],
                  ["False positive", model.metrics.fpr, "Share wrongly flagged"],
                ].map(([label, value, hint]) => (
                  <div key={String(label)} className="rounded-xl bg-ink-50 p-3 dark:bg-white/5">
                    <p className="text-[10px] uppercase tracking-wide text-ink-400">{label}</p>
                    <p className="mt-1 text-lg font-semibold text-ink-950 dark:text-white">{typeof value === "number" ? value.toFixed(3) : "—"}</p>
                    <p className="text-[10px] text-ink-400">{hint}</p>
                  </div>
                ))}
              </div>
              <dl className="mt-4 grid grid-cols-2 gap-2 text-[11px]">
                <div className="text-ink-500">Type <span className="font-medium text-ink-800 dark:text-ink-100">{model.type.replace(/_/g, " ")}</span></div>
                <div className="text-ink-500">Holdout rows <span className="font-medium text-ink-800 dark:text-ink-100">{String(model.training?.holdout_rows ?? model.training?.holdout ?? "—")}</span></div>
                <div className="text-ink-500">Training rows <span className="font-medium text-ink-800 dark:text-ink-100">{String(model.training?.rows ?? model.training?.n_rows ?? "—")}</span></div>
                <div className="text-ink-500">Features <span className="font-medium text-ink-800 dark:text-ink-100">{model.features.length}</span></div>
              </dl>
            </>
          ) : (
            <div className="skeleton h-40 w-full" />
          )}
        </Card>

        <Card title="What drives the score" subtitle="Permutation importance on the holdout set">
          {importance.length ? (
            <div className="space-y-2.5">
              {importance.map(({ feature, importance: value }) => (
                <div key={feature} className="flex items-center gap-3">
                  <span className="w-40 truncate text-[11px] text-ink-600 dark:text-ink-300">{feature.replace(/_/g, " ")}</span>
                  <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-ink-100 dark:bg-white/10">
                    <div
                      className="h-full rounded-full bg-indigo-500"
                      style={{ width: `${Math.min(100, (value / (importance[0]?.importance || 1)) * 100)}%` }}
                    />
                  </div>
                  <span className="w-10 text-right text-[10px] font-semibold tabular-nums text-ink-700 dark:text-ink-200">
                    {value.toFixed(3)}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState title="No importance data" description="Feature importance is published with the model registry entry." />
          )}
        </Card>
      </div>

      <Card padded={false} className="mt-4" title="Assessment history" subtitle="Every risk score keeps its inputs, confidence and limitations">
        <DataTable
          columns={columns}
          rows={assessments}
          loading={loading}
          onRowClick={setDetail}
          emptyTitle="No assessments yet"
          emptyDescription="Assess a driver or run a fleet assessment."
        />
        <Pagination page={page} pages={pages} total={total} onPage={setPage} pageSize={15} />
      </Card>

      <Card title="Model limitations" subtitle="Read before acting on a score" className="mt-4">
        <ul className="grid gap-2 text-xs leading-relaxed text-ink-600 dark:text-ink-300 sm:grid-cols-2">
          {(model?.limitations ?? []).map((item) => (
            <li key={item} className="flex gap-2">
              <Info className="mt-0.5 h-3.5 w-3.5 shrink-0 text-ink-400" />
              {item}
            </li>
          ))}
          <li className="flex gap-2">
            <Info className="mt-0.5 h-3.5 w-3.5 shrink-0 text-ink-400" />
            Score inputs are drawn from event history, vehicle health and maintenance state — never from protected characteristics.
          </li>
        </ul>
        <p className="mt-4 rounded-xl bg-ink-50 p-3 text-[11px] leading-relaxed text-ink-500 dark:bg-white/5 dark:text-ink-400">
          {model?.disclaimer ?? overview?.disclaimer}
        </p>
      </Card>

      <Modal
        open={assessOpen}
        onClose={() => { setAssessOpen(false); setResult(null); }}
        title="Assess a driver"
        description="Produces a triage score from recent behaviour, vehicle health and incident history."
        footer={
          result ? (
            <Button onClick={() => { setAssessOpen(false); setResult(null); }}>Done</Button>
          ) : (
            <>
              <Button variant="secondary" onClick={() => setAssessOpen(false)}>Cancel</Button>
              <Button onClick={assess} loading={assessing}>Run assessment</Button>
            </>
          )
        }
      >
        {result ? (
          <div className="space-y-4">
            <div className="flex items-center gap-4 rounded-2xl bg-ink-50 p-4 dark:bg-white/5">
              <div>
                <p className="text-[10px] uppercase tracking-wide text-ink-400">Risk score</p>
                <p className="text-3xl font-semibold tracking-tight text-ink-950 dark:text-white">{result.risk_score.toFixed(2)}</p>
              </div>
              <div className="ml-auto text-right">
                <Badge tone={riskTone(result.risk_level)} className="text-sm">{result.risk_level}</Badge>
                <p className="mt-1 text-[10px] text-ink-400">confidence {Math.round(result.confidence * 100)}%</p>
              </div>
            </div>
            <p className="text-xs leading-relaxed text-ink-600 dark:text-ink-300">{result.explanation}</p>
            <div>
              <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-ink-400">Top indicators</p>
              <ul className="space-y-1 text-[11px] text-ink-600 dark:text-ink-300">
                {result.indicators.slice(0, 5).map((indicator) => (
                  <li key={indicator.key} className="flex gap-2">
                    <span className="text-ink-400">·</span>
                    <span>{indicator.label}: <span className="font-medium">{String(indicator.value)}</span></span>
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-ink-400">Recommended next step</p>
              <ul className="space-y-1 text-[11px] text-ink-600 dark:text-ink-300">
                {result.recommendations.slice(0, 3).map((item) => <li key={item}>· {item}</li>)}
              </ul>
            </div>
            <p className="text-[10px] leading-relaxed text-ink-400">{result.limitations.join(" ")}</p>
          </div>
        ) : (
          <form onSubmit={assess} className="space-y-4">
            <Field label="Driver" required>
              <Select value={driverId} onChange={(event) => setDriverId(event.target.value)} required>
                <option value="">Select a driver</option>
                {drivers.map((driver) => (
                  <option key={driver.id} value={driver.id}>{driver.full_name} — {driver.employee_id ?? `#${driver.id}`}</option>
                ))}
              </Select>
            </Field>
            <Field label="Vehicle (optional)" hint="Includes vehicle health and maintenance state in the score.">
              <Input
                type="number"
                min={1}
                value={vehicleId}
                onChange={(event) => setVehicleId(event.target.value)}
                placeholder="Vehicle ID, e.g. 1"
              />
            </Field>
            <div className="flex gap-2 rounded-xl bg-amber-50 p-3 text-[11px] leading-relaxed text-amber-800 dark:bg-amber-500/10 dark:text-amber-200">
              <TriangleAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              A high score is a review queue, not a verdict. Never use this score as the sole basis for discipline.
            </div>
            <button type="submit" className="hidden" aria-hidden="true" />
          </form>
        )}
      </Modal>

      <Modal
        open={detail !== null}
        onClose={() => setDetail(null)}
        title={detail?.driver_name ?? "Assessment"}
        description={detail ? `${detail.registration_number ?? "No vehicle"} · ${timeAgo(detail.created_at)} · ${detail.model_version}` : ""}
        size="lg"
      >
        {detail && (
          <div className="space-y-5">
            <div className="flex flex-wrap items-center gap-4 rounded-2xl bg-ink-50 p-4 dark:bg-white/5">
              <div>
                <p className="text-[10px] uppercase tracking-wide text-ink-400">Score</p>
                <p className="text-2xl font-semibold text-ink-950 dark:text-white">{detail.risk_score.toFixed(3)}</p>
              </div>
              <Badge tone={riskTone(detail.risk_level)} className="text-sm">{detail.risk_level}</Badge>
              <div className="ml-auto text-right">
                <p className="text-[10px] uppercase tracking-wide text-ink-400">Confidence</p>
                <p className="text-xs font-semibold text-ink-900 dark:text-white">{confidenceLabel(detail.confidence)}</p>
              </div>
            </div>

            <p className="text-xs leading-relaxed text-ink-700 dark:text-ink-200">{detail.explanation}</p>

            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <p className="mb-2 text-[10px] font-semibold uppercase tracking-wide text-ink-400">Indicators</p>
                <div className="space-y-1.5">
                  {detail.indicators.map((indicator) => (
                    <div key={indicator.key} className="rounded-lg bg-ink-50 px-2.5 py-2 dark:bg-white/5">
                      <div className="flex items-center justify-between gap-2 text-[11px]">
                        <span className="text-ink-600 dark:text-ink-300">{indicator.label}</span>
                        <span className="font-semibold text-ink-900 dark:text-white">{String(indicator.value)}</span>
                      </div>
                      <p className="mt-0.5 text-[10px] leading-relaxed text-ink-400">{indicator.detail}</p>
                    </div>
                  ))}
                </div>
              </div>
              <div>
                <p className="mb-2 text-[10px] font-semibold uppercase tracking-wide text-ink-400">Recommendations</p>
                <ul className="space-y-1.5 text-[11px] leading-relaxed text-ink-600 dark:text-ink-300">
                  {detail.recommendations.map((item) => <li key={item}>· {item}</li>)}
                </ul>
              </div>
            </div>

            <div>
              <p className="mb-2 text-[10px] font-semibold uppercase tracking-wide text-ink-400">Model inputs</p>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                {Object.entries(detail.inputs).map(([key, value]) => (
                  <div key={key} className="rounded-lg bg-ink-50 px-2.5 py-2 dark:bg-white/5">
                    <p className="truncate text-[9px] uppercase tracking-wide text-ink-400">{key.replace(/_/g, " ")}</p>
                    <p className="text-[11px] font-semibold text-ink-900 dark:text-white">{typeof value === "number" ? value.toFixed(2) : String(value)}</p>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 dark:border-amber-500/20 dark:bg-amber-500/5">
              <p className="mb-1 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wide text-amber-700 dark:text-amber-300">
                <TriangleAlert className="h-3 w-3" /> Limitations
              </p>
              <ul className="space-y-1 text-[11px] leading-relaxed text-amber-800 dark:text-amber-200">
                {detail.limitations.map((item) => <li key={item}>· {item}</li>)}
              </ul>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
