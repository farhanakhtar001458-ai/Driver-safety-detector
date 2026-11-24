import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { Badge, DemoBanner, SimulatedBadge, StatCard, severityToneLocalForTest } from "@/components/ui";

describe("simulated-data labelling", () => {
  it("renders an explicit simulated badge", () => {
    render(<SimulatedBadge />);
    expect(screen.getByText(/simulated/i)).toBeInTheDocument();
  });

  it("allows a custom label for telemetry provenance", () => {
    render(<SimulatedBadge label="Simulated telemetry" />);
    expect(screen.getByText(/simulated telemetry/i)).toBeInTheDocument();
  });

  it("warns clearly in the demo banner", () => {
    render(<DemoBanner />);
    expect(screen.getByText(/does not represent real vehicles/i)).toBeInTheDocument();
  });

  it("keeps the disclaimer when a custom message is supplied", () => {
    render(<DemoBanner message="All positions are simulator-generated." />);
    expect(screen.getByText(/simulator-generated/i)).toBeInTheDocument();
    expect(screen.getByText(/Demo environment/i)).toBeInTheDocument();
  });
});

describe("presentation components", () => {
  it("renders stat values and hints", () => {
    render(<StatCard label="Total vehicles" value={12} hint="9 active" />);
    expect(screen.getByText("Total vehicles")).toBeInTheDocument();
    expect(screen.getByText("12")).toBeInTheDocument();
    expect(screen.getByText("9 active")).toBeInTheDocument();
  });

  it("falls back to a dash for unknown values", () => {
    render(<StatCard label="Average score" value="—" />);
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("applies severity tones consistently", () => {
    expect(severityToneLocalForTest("critical")).toContain("rose");
    expect(severityToneLocalForTest("high")).toContain("amber");
    expect(severityToneLocalForTest("low")).toContain("emerald");
    expect(severityToneLocalForTest(undefined)).toContain("ink");
  });

  it("renders badges with a tone class", () => {
    render(<Badge tone="bg-emerald-50 text-emerald-700">Active</Badge>);
    expect(screen.getByText("Active")).toHaveClass("badge");
  });
});
