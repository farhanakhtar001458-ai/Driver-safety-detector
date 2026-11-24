import { describe, expect, it } from "vitest";
import {
  cn,
  formatKm,
  formatNumber,
  formatScore,
  percent,
  riskTone,
  scoreTone,
  severityTone,
  statusTone,
  timeAgo,
  VEHICLE_STATUS_LABELS,
} from "@/lib/format";

describe("format helpers", () => {
  it("joins class names and drops falsy values", () => {
    expect(cn("a", false, undefined, "b")).toBe("a b");
  });

  it("formats numbers with a maximum fraction", () => {
    expect(formatNumber(1234.567)).toBe("1,235");
    expect(formatNumber(null)).toBe("—");
  });

  it("formats distance in kilometres", () => {
    expect(formatKm(1200)).toContain("km");
    expect(formatKm(null)).toBe("—");
  });

  it("formats scores to one decimal and handles missing data", () => {
    expect(formatScore(71.44)).toBe("71.4");
    expect(formatScore(null)).toBe("—");
  });

  it("computes a percentage share safely", () => {
    expect(percent(1, 4)).toBe(25);
    expect(percent(1, 0)).toBe(0);
    expect(percent(null, 10)).toBe(0);
  });

  it("maps severity to a tone class", () => {
    expect(severityTone("critical")).toContain("rose");
    expect(severityTone("low")).toContain("emerald");
    expect(severityTone("unknown")).toContain("ink");
  });

  it("maps risk levels without implying certainty", () => {
    expect(riskTone("critical")).toContain("rose");
    expect(riskTone("moderate")).toContain("indigo");
    expect(riskTone("low")).toContain("emerald");
  });

  it("maps vehicle status to a tone class", () => {
    expect(statusTone("active")).toContain("emerald");
    expect(statusTone("offline")).toContain("rose");
  });

  it("keeps score bands monotonic", () => {
    expect(scoreTone(95)).toContain("emerald");
    expect(scoreTone(75)).toContain("brand");
    expect(scoreTone(40)).toContain("rose");
  });

  it("renders human readable relative times", () => {
    const now = new Date().toISOString();
    expect(timeAgo(now)).toMatch(/just now|second/);
    expect(timeAgo(null)).toBe("—");
  });

  it("labels every vehicle status without leaking snake_case", () => {
    for (const label of Object.values(VEHICLE_STATUS_LABELS)) {
      expect(label).not.toContain("_");
    }
  });
});
