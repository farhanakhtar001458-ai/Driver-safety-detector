export type Role = "super_admin" | "org_admin" | "fleet_manager" | "safety_officer" | "driver";

export interface User {
  id: number;
  email: string;
  full_name: string;
  role: Role;
  job_title?: string | null;
  organisation_id?: number | null;
  is_active: boolean;
  is_verified: boolean;
  last_login_at?: string | null;
  created_at: string;
  phone_masked?: string | null;
  permissions: string[];
}

export interface Organisation {
  id: number;
  name: string;
  slug: string;
  billing_email?: string | null;
  phone?: string | null;
  address?: string | null;
  city?: string | null;
  country?: string | null;
  timezone: string;
  monitoring_policy_accepted_at?: string | null;
  is_active: boolean;
  created_at: string;
}

export interface Plan {
  id: number;
  code: string;
  name: string;
  description?: string | null;
  price_monthly: number;
  currency: string;
  max_vehicles: number;
  max_drivers: number;
  features: string[];
  trial_days: number;
  is_active: boolean;
  is_custom: boolean;
  sort_order: number;
}

export interface Subscription {
  id: number;
  organisation_id: number;
  plan_id: number;
  status: string;
  seats: number;
  trial_start?: string | null;
  trial_end?: string | null;
  current_period_start?: string | null;
  current_period_end?: string | null;
  cancel_at_period_end: boolean;
  plan?: Plan;
}

export interface Usage {
  vehicles: number;
  vehicle_limit: number | null;
  drivers: number;
  driver_limit: number | null;
  events_this_month: number;
  reports_this_month: number;
  plan_code: string;
  plan_name: string;
  subscription_status: string;
  trial_days_left?: number | null;
}

export interface AuthMe {
  user: User;
  organisation?: Organisation | null;
  subscription?: Subscription | null;
  usage?: Usage | null;
}

export interface Vehicle {
  id: number;
  registration_number: string;
  vehicle_type: string;
  manufacturer: string;
  model: string;
  manufacturing_year: number;
  fuel_type: string;
  vin_masked?: string | null;
  assigned_driver_id?: number | null;
  assigned_driver_name?: string | null;
  gps_device_id?: number | null;
  gps_device_serial?: string | null;
  status: "active" | "inactive" | "under_maintenance" | "offline";
  insurance_expiry?: string | null;
  mileage_km: number;
  depot?: string | null;
  notes?: string | null;
  last_service_at?: string | null;
  next_service_km?: number | null;
  is_archived: boolean;
  created_at: string;
  updated_at: string;
}

export interface Driver {
  id: number;
  organisation_id: number;
  user_id?: number | null;
  employee_id?: string | null;
  first_name: string;
  last_name: string;
  full_name: string;
  email?: string | null;
  phone_masked?: string | null;
  licence_number_masked?: string | null;
  licence_class?: string | null;
  licence_expiry?: string | null;
  status: string;
  years_experience: number;
  training_hours: number;
  hire_date?: string | null;
  city?: string | null;
  avatar_color: string;
  assigned_vehicle_ids: number[];
  created_at: string;
}

export interface LiveVehicle {
  vehicle_id: number;
  registration_number: string;
  vehicle_type: string;
  status: string;
  driver_name?: string | null;
  latitude: number;
  longitude: number;
  speed_kph: number;
  heading: number;
  ignition_on: boolean;
  last_seen: string;
  is_simulated: boolean;
  today_distance_km?: number;
}

export interface LocationPoint {
  latitude: number;
  longitude: number;
  speed_kph: number;
  heading?: number;
  recorded_at: string;
  is_simulated?: boolean;
  source?: string;
}

export interface DrivingEvent {
  id: number;
  vehicle_id: number;
  registration_number?: string | null;
  driver_id?: number | null;
  driver_name?: string | null;
  event_type: string;
  severity: "low" | "medium" | "high" | "critical";
  latitude?: number | null;
  longitude?: number | null;
  speed_kph?: number | null;
  speed_limit_kph?: number | null;
  sensor_data: Record<string, unknown>;
  recommended_action?: string | null;
  is_simulated: boolean;
  source: string;
  occurred_at: string;
}

export interface ScoreRow {
  id: number;
  driver_id: number;
  driver_name?: string | null;
  period: string;
  period_start: string;
  period_end: string;
  overall_score: number;
  speed_score: number;
  braking_score: number;
  acceleration_score: number;
  cornering_score: number;
  seatbelt_score?: number | null;
  consistency_score: number;
  events_count: number;
  distance_km: number;
  confidence: number;
  breakdown?: Record<string, unknown>;
  model_version: string;
  created_at: string;
}

export interface RiskAssessment {
  id: number;
  driver_id?: number | null;
  driver_name?: string | null;
  vehicle_id?: number | null;
  registration_number?: string | null;
  risk_level: "low" | "moderate" | "high" | "critical";
  risk_score: number;
  indicators: { key: string; label: string; value: unknown; detail: string; weight: number }[];
  explanation: string;
  recommendations: string[];
  confidence: number;
  model_version: string;
  inputs: Record<string, number>;
  limitations: string[];
  created_at: string;
}

export interface Incident {
  id: number;
  vehicle_id?: number | null;
  registration_number?: string | null;
  driver_id?: number | null;
  driver_name?: string | null;
  reporter_name?: string | null;
  incident_type: string;
  title: string;
  description?: string | null;
  severity: "minor" | "moderate" | "severe" | "critical";
  status: "new" | "under_investigation" | "verified" | "resolved" | "false_alert";
  latitude?: number | null;
  longitude?: number | null;
  occurred_at: string;
  evidence: Record<string, unknown>[];
  investigation_notes?: string | null;
  resolution_notes?: string | null;
  emergency_contact?: Record<string, unknown>;
  verified_at?: string | null;
  resolved_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface MaintenanceAlert {
  id: number;
  vehicle_id: number;
  registration_number?: string | null;
  alert_type: string;
  severity: string;
  title: string;
  description?: string | null;
  status: string;
  estimated_cost?: number | null;
  created_at: string;
  resolved_at?: string | null;
}

export interface MaintenanceRecord {
  id: number;
  vehicle_id: number;
  record_type: string;
  title: string;
  description?: string | null;
  status: string;
  odometer_km: number;
  cost: number;
  currency: string;
  performed_at: string;
  next_due_km?: number | null;
  next_due_date?: string | null;
  vendor?: string | null;
  created_at: string;
}

export interface VehicleHealth {
  vehicle_id: number;
  registration_number: string;
  status: string;
  health_score: number;
  engine_temperature_c?: number | null;
  battery_voltage?: number | null;
  fuel_level_pct?: number | null;
  fuel_consumption_l_per_100km?: number | null;
  fault_codes: string[];
  mileage_km: number;
  is_simulated: boolean;
  recorded_at?: string | null;
  next_service_km?: number | null;
  days_to_service?: number | null;
}

export interface Notification {
  id: number;
  type: string;
  title: string;
  message: string;
  priority: "low" | "medium" | "high" | "urgent";
  is_read: boolean;
  read_at?: string | null;
  channel: string;
  related_type?: string | null;
  related_id?: number | null;
  created_at: string;
}

export interface DashboardData {
  generated_at: string;
  period_days: number;
  kpis: Record<string, number>;
  trend: { label: string; events: number; high_risk: number; simulated: number }[];
  events_by_type: { type: string; count: number }[];
  events_by_severity: { severity: string; count: number }[];
  vehicle_activity: { date: string; distance_km: number; trips: number; events: number }[];
  leaderboard: {
    driver_id: number;
    driver_name: string;
    score: number;
    events: number;
    distance_km: number;
    avatar_color: string;
  }[];
  vehicle_health: {
    vehicle_id: number;
    registration_number: string;
    status: string;
    health_score: number | null;
    fault_codes: string[];
    is_simulated: boolean;
    mileage_km: number;
  }[];
  recent_incidents: Record<string, unknown>[];
  recent_notifications: Record<string, unknown>[];
  disclaimer: string;
}

export interface BehaviourSummary {
  period_days: number;
  total_events: number;
  high_risk_events: number;
  critical_events: number;
  events_per_100km: number;
  distance_km: number;
  by_type: { event_type: string; count: number }[];
  by_severity: { severity: string; count: number }[];
  trend: { label?: string; events: number; high_risk: number }[];
  top_drivers: { driver_id: number; driver_name: string; events: number; high_risk: number }[];
  safest_drivers: { driver_id: number; driver_name: string; score: number }[];
  simulation_share_pct: number;
}

export interface Pattern {
  key: string;
  title: string;
  description: string;
  severity: string;
  affected_drivers: number;
  evidence: Record<string, unknown>;
  recommended_action: string;
  confidence: number;
}

export interface ReportSummary {
  report_type: string;
  title: string;
  period: { from: string; to: string; days: number };
  kpis: Record<string, number>;
  charts: {
    trend: { label: string; events: number; high_risk: number }[];
    events_by_type: { type: string; count: number }[];
    events_by_severity: { severity: string; count: number }[];
  };
  tables: Record<string, Record<string, unknown>[]>;
  generated_at: string;
  disclaimer: string;
}

export interface AuditLog {
  id: number;
  user_name?: string | null;
  action: string;
  resource_type?: string | null;
  resource_id?: string | null;
  detail: Record<string, unknown>;
  ip_address?: string | null;
  created_at: string;
}

export interface ChatResponse {
  reply: string;
  mode: "llm" | "local";
  suggestions: string[];
  grounding: Record<string, unknown>;
  disclaimer: string;
  model?: string | null;
  latency_ms?: number | null;
}
