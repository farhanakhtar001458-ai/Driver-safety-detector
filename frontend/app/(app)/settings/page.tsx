"use client";

import { useCallback, useEffect, useState } from "react";
import { KeyRound, Search, ShieldCheck, Trash2, Users } from "lucide-react";
import { api, type Paginated } from "@/lib/api";
import type { AuditLog, Organisation, Subscription, Usage, User } from "@/lib/types";
import { Avatar, Badge, Button, Card, ConfirmDialog, Field, Input, Modal, PageHeader, PageSkeleton, Select, Switch, Tabs, toast } from "@/components/ui";
import { DataTable, type Column, Pagination } from "@/components/tables/DataTable";
import { ProgressBar } from "@/components/ui";
import { cn, formatDate, ROLE_LABELS, timeAgo } from "@/lib/format";

const ROLES = ["org_admin", "fleet_manager", "safety_officer", "driver"];

const EMPTY_MEMBER = { full_name: "", email: "", role: "driver", job_title: "", phone: "", password: "" };

export default function SettingsPage() {
  const [tab, setTab] = useState("organisation");
  const [organisation, setOrganisation] = useState<Organisation | null>(null);
  const [orgForm, setOrgForm] = useState<Partial<Organisation>>({});
  const [members, setMembers] = useState<User[]>([]);
  const [memberSearch, setMemberSearch] = useState("");
  const [usage, setUsage] = useState<Usage | null>(null);
  const [subscription, setSubscription] = useState<Subscription | null>(null);
  const [audit, setAudit] = useState<AuditLog[]>([]);
  const [auditPage, setAuditPage] = useState(1);
  const [auditTotal, setAuditTotal] = useState(0);
  const [auditPages, setAuditPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [savingOrg, setSavingOrg] = useState(false);
  const [memberOpen, setMemberOpen] = useState(false);
  const [memberForm, setMemberForm] = useState(EMPTY_MEMBER);
  const [savingMember, setSavingMember] = useState(false);
  const [deactivating, setDeactivating] = useState<User | null>(null);
  const [passwordForm, setPasswordForm] = useState({ current_password: "", new_password: "", confirm: "" });
  const [savingPassword, setSavingPassword] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [orgData, memberData, usageData, subData, auditData] = await Promise.all([
        api.get<Organisation>("/organisations/me"),
        api.get<Paginated<User>>("/organisations/me/team", { page_size: 100, search: memberSearch || undefined }),
        api.get<Usage>("/organisations/me/usage"),
        api.get<Subscription>("/subscriptions/me"),
        api.get<Paginated<AuditLog>>("/audit-logs", { page: auditPage, page_size: 20 }),
      ]);
      setOrganisation(orgData);
      setOrgForm({
        name: orgData.name,
        billing_email: orgData.billing_email ?? "",
        phone: orgData.phone ?? "",
        address: orgData.address ?? "",
        city: orgData.city ?? "",
        country: orgData.country ?? "",
        timezone: orgData.timezone,
      });
      setMembers(memberData.items ?? []);
      setUsage(usageData);
      setSubscription(subData);
      setAudit(auditData.items ?? []);
      setAuditTotal(auditData.total ?? 0);
      setAuditPages(auditData.pages ?? 1);
    } catch (err) {
      toast(err instanceof Error ? err.message : "Could not load settings.", "error");
    } finally {
      setLoading(false);
    }
  }, [memberSearch, auditPage]);

  useEffect(() => {
    void load();
  }, [load]);

  const saveOrganisation = async (event: React.FormEvent) => {
    event.preventDefault();
    setSavingOrg(true);
    try {
      const updated = await api.patch<Organisation>("/organisations/me", {
        name: orgForm.name,
        billing_email: orgForm.billing_email || null,
        phone: orgForm.phone || null,
        address: orgForm.address || null,
        city: orgForm.city || null,
        country: orgForm.country || null,
        timezone: orgForm.timezone,
      });
      setOrganisation(updated);
      toast("Organisation details saved.");
    } catch (err) {
      toast(err instanceof Error ? err.message : "Could not save the organisation.", "error");
    } finally {
      setSavingOrg(false);
    }
  };

  const createMember = async (event: React.FormEvent) => {
    event.preventDefault();
    setSavingMember(true);
    try {
      const payload: Record<string, unknown> = {
        email: memberForm.email.trim().toLowerCase(),
        password: memberForm.password,
        full_name: memberForm.full_name.trim(),
        role: memberForm.role,
      };
      if (memberForm.job_title.trim()) payload.job_title = memberForm.job_title.trim();
      if (memberForm.phone.trim()) payload.phone = memberForm.phone.trim();
      await api.post("/organisations/me/team", payload);
      setMemberOpen(false);
      setMemberForm(EMPTY_MEMBER);
      toast("Team member invited. They can sign in with the password you set.");
      await load();
    } catch (err) {
      toast(err instanceof Error ? err.message : "Could not create the team member.", "error");
    } finally {
      setSavingMember(false);
    }
  };

  const toggleActive = async (member: User) => {
    try {
      await api.patch(`/organisations/me/team/${member.id}`, { is_active: !member.is_active });
      setMembers((current) => current.map((item) => (item.id === member.id ? { ...item, is_active: !item.is_active } : item)));
      toast(member.is_active ? "Member deactivated." : "Member reactivated.");
    } catch (err) {
      toast(err instanceof Error ? err.message : "Could not update the member.", "error");
    }
  };

  const deactivate = async () => {
    if (!deactivating) return;
    setSavingMember(true);
    try {
      await api.delete(`/organisations/me/team/${deactivating.id}`);
      setDeactivating(null);
      toast("Team member deactivated.");
      await load();
    } catch (err) {
      toast(err instanceof Error ? err.message : "Could not deactivate the member.", "error");
    } finally {
      setSavingMember(false);
    }
  };

  const changePassword = async (event: React.FormEvent) => {
    event.preventDefault();
    if (passwordForm.new_password !== passwordForm.confirm) {
      toast("The new passwords do not match.", "error");
      return;
    }
    setSavingPassword(true);
    try {
      await api.post("/auth/change-password", {
        current_password: passwordForm.current_password,
        new_password: passwordForm.new_password,
      });
      setPasswordForm({ current_password: "", new_password: "", confirm: "" });
      toast("Password updated.");
    } catch (err) {
      toast(err instanceof Error ? err.message : "Could not change the password.", "error");
    } finally {
      setSavingPassword(false);
    }
  };

  const auditColumns: Column<AuditLog>[] = [
    {
      key: "action",
      header: "Action",
      render: (row) => (
        <div>
          <p className="font-mono text-[11px] font-medium text-ink-900 dark:text-white">{row.action}</p>
          <p className="text-[10px] text-ink-400">{row.resource_type ?? "—"} {row.resource_id ? `#${row.resource_id}` : ""}</p>
        </div>
      ),
    },
    { key: "user", header: "Actor", render: (row) => <span className="text-xs text-ink-600 dark:text-ink-300">{row.user_name ?? "System"}</span> },
    { key: "ip", header: "IP", render: (row) => <span className="font-mono text-[10px] text-ink-400">{row.ip_address ?? "—"}</span> },
    { key: "when", header: "When", render: (row) => <span className="text-xs text-ink-500">{timeAgo(row.created_at)}</span> },
  ];

  if (loading && !organisation) return <PageSkeleton cards={3} />;

  const plan = subscription?.plan;
  const vehiclePct = usage?.vehicle_limit ? (usage.vehicles / usage.vehicle_limit) * 100 : null;
  const driverPct = usage?.driver_limit ? (usage.drivers / usage.driver_limit) * 100 : null;

  return (
    <div>
      <PageHeader
        eyebrow="Workspace · administration"
        title="Settings"
        description="Organisation profile, team access, security and the audit trail. Only organisation admins can change most of this."
      />

      <Tabs
        value={tab}
        onChange={setTab}
        tabs={[
          { id: "organisation", label: "Organisation" },
          { id: "team", label: "Team", count: members.length },
          { id: "plan", label: "Plan & usage" },
          { id: "security", label: "Security" },
          { id: "audit", label: "Audit log", count: auditTotal },
        ]}
      />

      {tab === "organisation" && (
        <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1fr)_340px]">
          <Card title="Organisation profile" subtitle="Shown on reports and invoices">
            <form onSubmit={saveOrganisation} className="grid gap-4 sm:grid-cols-2">
              <Field label="Organisation name" required>
                <Input value={orgForm.name ?? ""} onChange={(event) => setOrgForm({ ...orgForm, name: event.target.value })} required minLength={2} />
              </Field>
              <Field label="Billing email">
                <Input type="email" value={orgForm.billing_email ?? ""} onChange={(event) => setOrgForm({ ...orgForm, billing_email: event.target.value })} />
              </Field>
              <Field label="Phone">
                <Input value={orgForm.phone ?? ""} onChange={(event) => setOrgForm({ ...orgForm, phone: event.target.value })} />
              </Field>
              <Field label="Timezone">
                <Input value={orgForm.timezone ?? ""} onChange={(event) => setOrgForm({ ...orgForm, timezone: event.target.value })} placeholder="Asia/Kolkata" />
              </Field>
              <Field label="Address">
                <Input value={orgForm.address ?? ""} onChange={(event) => setOrgForm({ ...orgForm, address: event.target.value })} />
              </Field>
              <Field label="City">
                <Input value={orgForm.city ?? ""} onChange={(event) => setOrgForm({ ...orgForm, city: event.target.value })} />
              </Field>
              <Field label="Country">
                <Input value={orgForm.country ?? ""} onChange={(event) => setOrgForm({ ...orgForm, country: event.target.value })} />
              </Field>
              <div className="sm:col-span-2">
                <Button type="submit" loading={savingOrg}>Save changes</Button>
              </div>
            </form>
          </Card>

          <div className="space-y-4">
            <Card title="Monitoring policy" subtitle="Driver consent record">
              <div className="flex items-start gap-3">
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-300">
                  <ShieldCheck className="h-4 w-4" />
                </span>
                <div>
                  <p className="text-xs font-semibold text-ink-900 dark:text-white">Policy accepted</p>
                  <p className="mt-1 text-[11px] leading-relaxed text-ink-500 dark:text-ink-400">
                    {organisation?.monitoring_policy_accepted_at
                      ? `Accepted ${formatDate(organisation.monitoring_policy_accepted_at)}.`
                      : "Not yet accepted."}{" "}
                    Drivers must be informed that vehicle monitoring is active and how data is used.
                  </p>
                </div>
              </div>
            </Card>
            <Card title="Data residency" subtitle="Where this deployment stores data">
              <p className="text-[11px] leading-relaxed text-ink-500 dark:text-ink-400">
                This build runs on a single server with an embedded database. PII fields (phone, licence number,
                emergency contact) are encrypted at rest with a server-held key. Production deployments should use
                PostgreSQL with encryption at rest and a managed secret store.
              </p>
            </Card>
          </div>
        </div>
      )}

      {tab === "team" && (
        <Card
          padded={false}
          className="mt-4"
          title="Team members"
          subtitle="Role changes are permission-checked and audit-logged"
          action={
            <Button size="sm" onClick={() => setMemberOpen(true)}>
              <Users className="h-4 w-4" /> Add member
            </Button>
          }
        >
          <div className="border-b border-ink-100 p-4 dark:border-white/5">
            <div className="relative max-w-xs">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-400" />
              <Input value={memberSearch} onChange={(event) => setMemberSearch(event.target.value)} placeholder="Search name or email…" className="pl-9" aria-label="Search team" />
            </div>
          </div>
          <DataTable
            columns={[
              {
                key: "member",
                header: "Member",
                render: (row) => (
                  <div className="flex items-center gap-3">
                    <Avatar name={row.full_name} color={row.role === "org_admin" ? "#0dab99" : "#6366f1"} size="sm" />
                    <div>
                      <p className="text-xs font-semibold text-ink-900 dark:text-white">{row.full_name}</p>
                      <p className="text-[10px] text-ink-400">{row.email}</p>
                    </div>
                  </div>
                ),
              },
              {
                key: "role",
                header: "Role",
                render: (row) => <Badge tone="bg-indigo-50 text-indigo-700 dark:bg-indigo-500/10 dark:text-indigo-300">{ROLE_LABELS[row.role] ?? row.role}</Badge>,
              },
              { key: "title", header: "Job title", render: (row) => <span className="text-xs text-ink-600 dark:text-ink-300">{row.job_title ?? "—"}</span> },
              {
                key: "active",
                header: "Active",
                render: (row) => (
                  <Switch checked={row.is_active} onChange={() => void toggleActive(row)} label={`Active status for ${row.full_name}`} />
                ),
              },
              {
                key: "last",
                header: "Last sign-in",
                render: (row) => <span className="text-xs text-ink-500">{row.last_login_at ? timeAgo(row.last_login_at) : "Never"}</span>,
              },
              {
                key: "actions",
                header: "",
                render: (row) => (
                  <Button size="sm" variant="ghost" onClick={() => setDeactivating(row)} aria-label={`Remove ${row.full_name}`}>
                    <Trash2 className="h-3.5 w-3.5 text-rose-500" />
                  </Button>
                ),
              },
            ]}
            rows={members}
            loading={loading}
            minWidth={720}
            emptyTitle="No team members"
            emptyDescription="Add your first team member."
          />
        </Card>
      )}

      {tab === "plan" && (
        <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1fr)_360px]">
          <Card title="Current plan" subtitle={plan?.description ?? "Your organisation's subscription"}>
            <div className="flex flex-wrap items-end justify-between gap-4">
              <div>
                <p className="text-2xl font-semibold tracking-tight text-ink-950 dark:text-white">{plan?.name ?? "No plan"}</p>
                <p className="mt-1 text-xs text-ink-500 dark:text-ink-400">
                  {plan?.price_monthly ? `₹${plan.price_monthly.toLocaleString("en-IN")} / month` : "Custom pricing"} ·{" "}
                  {subscription?.status.replace(/_/g, " ")}
                  {usage?.trial_days_left != null && usage.trial_days_left >= 0 ? ` · ${usage.trial_days_left} trial days left` : ""}
                </p>
              </div>
              <Button variant="secondary" href="/subscriptions">Compare plans</Button>
            </div>

            <div className="mt-6 space-y-4">
              {[
                { label: "Vehicles", value: usage?.vehicles ?? 0, limit: usage?.vehicle_limit, pct: vehiclePct },
                { label: "Drivers", value: usage?.drivers ?? 0, limit: usage?.driver_limit, pct: driverPct },
              ].map((row) => (
                <div key={row.label}>
                  <div className="mb-1 flex items-center justify-between text-xs">
                    <span className="text-ink-600 dark:text-ink-300">{row.label}</span>
                    <span className="font-semibold text-ink-900 dark:text-white">
                      {row.value} / {row.limit ?? "unlimited"}
                    </span>
                  </div>
                  <ProgressBar value={row.pct ?? 0} tone={(row.pct ?? 0) > 90 ? "rose" : "teal"} />
                </div>
              ))}
            </div>

            <dl className="mt-5 grid grid-cols-2 gap-3 text-xs sm:grid-cols-3">
              <div className="rounded-xl bg-ink-50 p-3 dark:bg-white/5">
                <dt className="text-[10px] uppercase tracking-wide text-ink-400">Events this month</dt>
                <dd className="mt-0.5 text-sm font-semibold text-ink-900 dark:text-white">{usage?.events_this_month ?? 0}</dd>
              </div>
              <div className="rounded-xl bg-ink-50 p-3 dark:bg-white/5">
                <dt className="text-[10px] uppercase tracking-wide text-ink-400">Reports this month</dt>
                <dd className="mt-0.5 text-sm font-semibold text-ink-900 dark:text-white">{usage?.reports_this_month ?? 0}</dd>
              </div>
              <div className="rounded-xl bg-ink-50 p-3 dark:bg-white/5">
                <dt className="text-[10px] uppercase tracking-wide text-ink-400">Period ends</dt>
                <dd className="mt-0.5 text-sm font-semibold text-ink-900 dark:text-white">
                  {subscription?.current_period_end ? formatDate(subscription.current_period_end) : "—"}
                </dd>
              </div>
            </dl>
          </Card>

          <Card title="Plan features" subtitle={plan?.code ? `Included in ${plan.code}` : ""}>
            <ul className="space-y-2 text-[11px] leading-relaxed text-ink-600 dark:text-ink-300">
              {(plan?.features ?? []).map((feature) => (
                <li key={feature} className="flex gap-2">
                  <ShieldCheck className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-500" />
                  {feature}
                </li>
              ))}
            </ul>
            <p className="mt-4 rounded-lg bg-amber-50 px-3 py-2 text-[10px] leading-relaxed text-amber-800 dark:bg-amber-500/10 dark:text-amber-200">
              Payments are not processed in this build. Upgrades are recorded but no charge is taken until a payment
              provider is configured.
            </p>
          </Card>
        </div>
      )}

      {tab === "security" && (
        <div className="mt-4 grid gap-4 lg:grid-cols-2">
          <Card title="Change password" subtitle="Minimum 8 characters">
            <form onSubmit={changePassword} className="space-y-4">
              <Field label="Current password" required>
                <Input type="password" value={passwordForm.current_password} onChange={(event) => setPasswordForm({ ...passwordForm, current_password: event.target.value })} required autoComplete="current-password" />
              </Field>
              <Field label="New password" required hint="Use a long, unique passphrase.">
                <Input type="password" value={passwordForm.new_password} onChange={(event) => setPasswordForm({ ...passwordForm, new_password: event.target.value })} required minLength={8} autoComplete="new-password" />
              </Field>
              <Field label="Confirm new password" required>
                <Input type="password" value={passwordForm.confirm} onChange={(event) => setPasswordForm({ ...passwordForm, confirm: event.target.value })} required minLength={8} autoComplete="new-password" />
              </Field>
              <Button type="submit" loading={savingPassword}>
                <KeyRound className="h-4 w-4" /> Update password
              </Button>
            </form>
          </Card>

          <Card title="Security posture" subtitle="How this deployment protects accounts">
            <ul className="space-y-3 text-[11px] leading-relaxed text-ink-600 dark:text-ink-300">
              <li className="flex gap-2"><ShieldCheck className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-500" /> JWT access tokens expire after 30 minutes; refresh tokens rotate and are revocable.</li>
              <li className="flex gap-2"><ShieldCheck className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-500" /> Passwords stored with bcrypt. Device ingest keys are SHA-256 hashed server-side.</li>
              <li className="flex gap-2"><ShieldCheck className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-500" /> Every organisation query is tenant-scoped; cross-tenant IDs return 403/404.</li>
              <li className="flex gap-2"><ShieldCheck className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-500" /> Rate limits apply per identity on auth and ingest endpoints.</li>
              <li className="flex gap-2"><ShieldCheck className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-500" /> PII fields are encrypted at rest; list responses return masked values.</li>
            </ul>
            <p className="mt-4 text-[10px] leading-relaxed text-ink-400">
              Not included in this build: SSO/SAML, hardware MFA, IP allow-lists and session device listing. Treat these
              as production-hardening work before handling real driver data at scale.
            </p>
          </Card>
        </div>
      )}

      {tab === "audit" && (
        <Card padded={false} className="mt-4" title="Audit trail" subtitle="Write actions across the organisation">
          <DataTable
            columns={auditColumns}
            rows={audit}
            loading={loading}
            minWidth={640}
            emptyTitle="No audit entries"
            emptyDescription="Actions appear here as they are performed."
          />
          <Pagination page={auditPage} pages={auditPages} total={auditTotal} onPage={setAuditPage} pageSize={20} />
        </Card>
      )}

      <Modal
        open={memberOpen}
        onClose={() => setMemberOpen(false)}
        title="Add team member"
        description="Creates a user in your organisation. You cannot assign the super administrator role here."
        size="lg"
        footer={
          <>
            <Button variant="secondary" onClick={() => setMemberOpen(false)}>Cancel</Button>
            <Button onClick={createMember} loading={savingMember}>Create member</Button>
          </>
        }
      >
        <form onSubmit={createMember} className="grid gap-4 sm:grid-cols-2">
          <Field label="Full name" required>
            <Input value={memberForm.full_name} onChange={(event) => setMemberForm({ ...memberForm, full_name: event.target.value })} required minLength={2} />
          </Field>
          <Field label="Email" required>
            <Input type="email" value={memberForm.email} onChange={(event) => setMemberForm({ ...memberForm, email: event.target.value })} required />
          </Field>
          <Field label="Role" required hint="You cannot grant a role above your own.">
            <Select value={memberForm.role} onChange={(event) => setMemberForm({ ...memberForm, role: event.target.value })}>
              {ROLES.map((role) => <option key={role} value={role}>{ROLE_LABELS[role] ?? role}</option>)}
            </Select>
          </Field>
          <Field label="Job title">
            <Input value={memberForm.job_title} onChange={(event) => setMemberForm({ ...memberForm, job_title: event.target.value })} />
          </Field>
          <Field label="Phone">
            <Input value={memberForm.phone} onChange={(event) => setMemberForm({ ...memberForm, phone: event.target.value })} placeholder="+91 98765 43210" />
          </Field>
          <Field label="Temporary password" required hint="Share this securely. They can change it in Settings.">
            <Input type="password" value={memberForm.password} onChange={(event) => setMemberForm({ ...memberForm, password: event.target.value })} required minLength={8} />
          </Field>
          <button type="submit" className="hidden" aria-hidden="true" />
        </form>
      </Modal>

      <ConfirmDialog
        open={deactivating !== null}
        onCancel={() => setDeactivating(null)}
        onConfirm={deactivate}
        title="Deactivate team member"
        message={deactivating ? `Deactivate ${deactivating.full_name}? They will lose access immediately. Their historical audit entries are retained.` : ""}
        confirmLabel="Deactivate"
        danger
        loading={savingMember}
      />
    </div>
  );
}
