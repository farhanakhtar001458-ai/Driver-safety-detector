/**
 * Presentation helpers for scores that must never imply more certainty than
 * the underlying data has.
 */

export type ScoreBand = "good" | "ok" | "warn" | "bad" | "muted";

export const SCORE_BAND_THRESHOLDS = { good: 85, ok: 70, warn: 55 } as const;

/**
 * Maps a 0-100 safety score to a display band. `null`/`undefined` means
 * "no data" and is deliberately distinct from a low score.
 */
export function scoreColour(score?: number | null): ScoreBand {
  if (score === null || score === undefined || Number.isNaN(Number(score))) return "muted";
  const value = Number(score);
  if (value >= SCORE_BAND_THRESHOLDS.good) return "good";
  if (value >= SCORE_BAND_THRESHOLDS.ok) return "ok";
  if (value >= SCORE_BAND_THRESHOLDS.warn) return "warn";
  return "bad";
}

/** Confidence under this level is rendered as "low confidence" in the UI. */
export const LOW_CONFIDENCE_THRESHOLD = 0.5;

export function confidenceLabel(confidence?: number | null): string {
  if (confidence === null || confidence === undefined) return "Unknown confidence";
  const pct = Math.round(confidence * 100);
  if (confidence < LOW_CONFIDENCE_THRESHOLD) return `Low confidence (${pct}%)`;
  return `${pct}% confidence`;
}
