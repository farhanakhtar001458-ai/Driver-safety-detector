"use client";

import { useCallback, useEffect, useState } from "react";
import { BadgeCheck, CreditCard, ShieldCheck, X } from "lucide-react";
import { api } from "@/lib/api";
import type { Plan, Subscription, Usage } from "@/lib/types";
import { Badge, Button, Card, ConfirmDialog, DemoBanner, PageHeader, PageSkeleton, Select, toast } from "@/components/ui";
import { cn, formatDate } from "@/lib/format";

type Payment = {
  id: number;
  invoice_number: string;
  amount: number;
  currency: string;
  status: string;
  created_at: string;
  plan_code?: string | null;
};

export default function SubscriptionsPage() {
  const [plans, setPlans] = useState<Plan[]>([]);
  const [subscription, setSubscription] = useState<Subscription | null>(null);
  const [usage, setUsage] = useState<Usage | null>(null);
  const [payments, setPayments] = useState<Payment[]>([]);
  const [loading, setLoading] = useState(true);
  const [seats, setSeats] = useState(3);
  const [upgrading, setUpgrading] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState(false);
  const [cancelOpen, setCancelOpen] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [planData, subData, usageData, paymentData] = await Promise.all([
        api.get<Plan[]>("/subscriptions/plans"),
        api.get<Subscription>("/subscriptions/me"),
        api.get<Usage>("/subscriptions/me/usage"),
        api.get<Payment[]>("/subscriptions/payments"),
      ]);
      setPlans(planData ?? []);
      setSubscription(subData);
      setUsage(usageData);
      setPayments(paymentData ?? []);
      setSeats(subData?.seats ?? 3);
    } catch (err) {
      toast(err instanceof Error ? err.message : "Could not load billing information.", "error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const upgrade = async (code: string) => {
    setUpgrading(code);
    try {
      const result = await api.post<{ message: string }>("/subscriptions/upgrade", { plan_code: code, seats });
      toast(result.message);
      await load();
    } catch (err) {
      toast(err instanceof Error ? err.message : "Plan change failed.", "error");
    } finally {
      setUpgrading(null);
    }
  };

  const cancel = async () => {
    setCancelling(true);
    try {
      await api.post("/subscriptions/cancel");
      setCancelOpen(false);
      toast("Subscription set to cancel at the end of the current period.");
      await load();
    } catch (err) {
      toast(err instanceof Error ? err.message : "Could not cancel the subscription.", "error");
    } finally {
      setCancelling(false);
    }
  };

  if (loading && !plans.length) return <PageSkeleton cards={3} />;

  const currentCode = subscription?.plan?.code;
  const isCustom = (plan: Plan) => plan.is_custom || plan.price_monthly === 0;

  return (
    <div>
      <PageHeader
        eyebrow="Workspace · billing"
        title="Plans & billing"
        description="Published pricing with clear limits. No quote-only tiers, no hidden hardware costs."
        actions={<Button variant="secondary" href="/settings">Back to settings</Button>}
      />

      <DemoBanner message="Payments are not processed in this build: no payment provider is configured. Plan changes are recorded and invoices stay pending until billing is enabled." />

      <div className="grid gap-4 lg:grid-cols-3">
        <Card title="Current subscription" subtitle={subscription?.plan?.name}>
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-2xl font-semibold tracking-tight text-ink-950 dark:text-white">{subscription?.plan?.name ?? "No plan"}</p>
              <p className="mt-1 text-xs text-ink-500 dark:text-ink-400">
                {subscription?.status.replace(/_/g, " ")}
                {subscription?.cancel_at_period_end ? " · cancels at period end" : ""}
              </p>
            </div>
            {subscription?.plan && <Badge tone="bg-brand-50 text-brand-700 dark:bg-brand-500/10 dark:text-brand-300">{subscription.plan.code}</Badge>}
          </div>
          <dl className="mt-4 grid grid-cols-2 gap-2 text-[11px]">
            <div className="text-ink-500">Seats <span className="font-medium text-ink-900 dark:text-white">{subscription?.seats}</span></div>
            <div className="text-ink-500">Period ends <span className="font-medium text-ink-900 dark:text-white">{subscription?.current_period_end ? formatDate(subscription.current_period_end) : "—"}</span></div>
            <div className="text-ink-500">Trial ends <span className="font-medium text-ink-900 dark:text-white">{subscription?.trial_end ? formatDate(subscription.trial_end) : "—"}</span></div>
            <div className="text-ink-500">Vehicles <span className="font-medium text-ink-900 dark:text-white">{usage?.vehicles}/{usage?.vehicle_limit ?? "∞"}</span></div>
            <div className="text-ink-500">Drivers <span className="font-medium text-ink-900 dark:text-white">{usage?.drivers}/{usage?.driver_limit ?? "∞"}</span></div>
            <div className="text-ink-500">Reports <span className="font-medium text-ink-900 dark:text-white">{usage?.reports_this_month ?? 0}</span></div>
          </dl>
          {subscription?.status !== "cancelled" && !subscription?.cancel_at_period_end && (
            <Button variant="ghost" className="mt-4 text-rose-600" onClick={() => setCancelOpen(true)}>
              Cancel subscription
            </Button>
          )}
        </Card>

        <Card title="Billing contact" subtitle="Invoices and receipts" className="lg:col-span-2">
          <div className="flex items-start gap-3">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-brand-50 text-brand-600 dark:bg-brand-500/10 dark:text-brand-300">
              <CreditCard className="h-5 w-5" />
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-xs font-semibold text-ink-900 dark:text-white">Invoice history</p>
              <p className="text-[11px] text-ink-500 dark:text-ink-400">
                Invoices are generated for every plan change. Until a payment provider is connected they remain pending.
              </p>
              <div className="mt-3 space-y-1.5">
                {payments.length === 0 ? (
                  <p className="rounded-lg bg-ink-50 px-3 py-2 text-[11px] text-ink-400 dark:bg-white/5">No invoices yet.</p>
                ) : (
                  payments.slice(0, 4).map((payment) => (
                    <div key={payment.id} className="flex items-center gap-3 rounded-lg bg-ink-50 px-3 py-2 dark:bg-white/5">
                      <span className="font-mono text-[10px] text-ink-600 dark:text-ink-300">{payment.invoice_number}</span>
                      <Badge tone={payment.status === "paid" ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300" : "bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-300"}>
                        {payment.status}
                      </Badge>
                      <span className="ml-auto text-[11px] font-semibold text-ink-900 dark:text-white">
                        ₹{Math.round(payment.amount).toLocaleString("en-IN")} {payment.currency}
                      </span>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        </Card>
      </div>

      <div className="mt-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold tracking-tight text-ink-950 dark:text-white">Available plans</h2>
          <p className="mt-1 text-xs text-ink-500 dark:text-ink-400">Published monthly prices in INR. Prices exclude taxes.</p>
        </div>
        <label className="flex items-center gap-2 text-xs text-ink-600 dark:text-ink-300">
          Seats
          <Select value={String(seats)} onChange={(event) => setSeats(Number(event.target.value))} className="w-[90px] py-1.5">
            {[1, 2, 3, 5, 10, 25, 50].map((value) => <option key={value} value={value}>{value}</option>)}
          </Select>
        </label>
      </div>

      <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {plans.map((plan) => {
          const current = plan.code === currentCode;
          const popular = plan.code === "professional";
          return (
            <div
              key={plan.id}
              className={cn(
                "relative flex flex-col rounded-3xl border bg-white p-5 shadow-card dark:bg-ink-900",
                current
                  ? "border-brand-500 ring-2 ring-brand-500/20"
                  : "border-ink-200 dark:border-white/10",
              )}
            >
              {popular && !current && (
                <span className="absolute -top-2.5 left-5 rounded-full bg-brand-600 px-2.5 py-0.5 text-[9px] font-bold uppercase tracking-wide text-white">
                  Most popular
                </span>
              )}
              {current && (
                <span className="absolute -top-2.5 left-5 rounded-full bg-ink-900 px-2.5 py-0.5 text-[9px] font-bold uppercase tracking-wide text-white dark:bg-white dark:text-ink-900">
                  Current plan
                </span>
              )}
              <p className="text-sm font-semibold text-ink-950 dark:text-white">{plan.name}</p>
              <div className="mt-3 flex items-baseline gap-1">
                <span className="text-2xl font-semibold tracking-tight text-ink-950 dark:text-white">
                  {isCustom(plan) ? "Custom" : `₹${plan.price_monthly.toLocaleString("en-IN")}`}
                </span>
                {!isCustom(plan) && <span className="text-[11px] text-ink-400">/ month</span>}
              </div>
              <p className="mt-1 text-[11px] leading-relaxed text-ink-500 dark:text-ink-400">{plan.description}</p>

              <div className="mt-4 grid grid-cols-2 gap-2 text-[11px]">
                <div className="rounded-lg bg-ink-50 px-2.5 py-2 dark:bg-white/5">
                  <p className="text-[9px] uppercase tracking-wide text-ink-400">Vehicles</p>
                  <p className="font-semibold text-ink-900 dark:text-white">{plan.max_vehicles || "Unlimited"}</p>
                </div>
                <div className="rounded-lg bg-ink-50 px-2.5 py-2 dark:bg-white/5">
                  <p className="text-[9px] uppercase tracking-wide text-ink-400">Drivers</p>
                  <p className="font-semibold text-ink-900 dark:text-white">{plan.max_drivers || "Unlimited"}</p>
                </div>
              </div>

              <ul className="mt-4 flex-1 space-y-1.5">
                {(plan.features ?? []).slice(0, 6).map((feature) => (
                  <li key={feature} className="flex items-start gap-1.5 text-[11px] leading-relaxed text-ink-600 dark:text-ink-300">
                    <BadgeCheck className="mt-0.5 h-3 w-3 shrink-0 text-brand-500" />
                    {feature}
                  </li>
                ))}
              </ul>

              {plan.trial_days > 0 && (
                <p className="mt-3 rounded-lg bg-brand-50 px-2.5 py-1.5 text-[10px] font-medium text-brand-700 dark:bg-brand-500/10 dark:text-brand-300">
                  {plan.trial_days}-day free trial
                </p>
              )}

              <div className="mt-4">
                {current ? (
                  <Button variant="secondary" className="w-full" disabled>
                    Current plan
                  </Button>
                ) : plan.is_custom ? (
                  <Button variant="secondary" className="w-full" disabled>
                    Contact sales
                  </Button>
                ) : (
                  <Button className="w-full" onClick={() => void upgrade(plan.code)} loading={upgrading === plan.code}>
                    {plan.trial_days > 0 ? "Start trial" : "Choose plan"}
                  </Button>
                )}
              </div>
            </div>
          );
        })}
      </div>

      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <Card>
          <div className="flex gap-3">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-amber-50 text-amber-600 dark:bg-amber-500/10 dark:text-amber-300">
              <X className="h-4 w-4" />
            </span>
            <div>
              <h4 className="text-xs font-semibold text-ink-900 dark:text-white">No payment processing in this build</h4>
              <p className="mt-1 text-[11px] leading-relaxed text-ink-500 dark:text-ink-400">
                Plan changes and invoices are recorded, but no card is charged. Connect a payment provider server-side
                before using this page for real billing.
              </p>
            </div>
          </div>
        </Card>
        <Card>
          <div className="flex gap-3">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-300">
              <ShieldCheck className="h-4 w-4" />
            </span>
            <div>
              <h4 className="text-xs font-semibold text-ink-900 dark:text-white">Limits are enforced server-side</h4>
              <p className="mt-1 text-[11px] leading-relaxed text-ink-500 dark:text-ink-400">
                Vehicle and driver limits are checked on write, not just displayed here. Exceeding a limit returns a
                clear 409 error instead of silently accepting the record.
              </p>
            </div>
          </div>
        </Card>
      </div>

      <ConfirmDialog
        open={cancelOpen}
        onCancel={() => setCancelOpen(false)}
        onConfirm={cancel}
        title="Cancel subscription"
        message="Your plan stays active until the end of the current billing period, then the organisation moves to the Free plan limits. Data is retained."
        confirmLabel="Cancel at period end"
        danger
        loading={cancelling}
      />
    </div>
  );
}
