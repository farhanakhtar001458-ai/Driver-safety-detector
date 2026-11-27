import { describe, expect, it } from "vitest";
import { validCoordinates } from "@/lib/map";

describe("map coordinate validation", () => {
  it("accepts coordinates on the equator and prime meridian", () => {
    expect(validCoordinates(0, 0)).toBe(true);
    expect(validCoordinates(0, 77)).toBe(true);
  });
  it("rejects missing, non-finite or out-of-range coordinates", () => {
    for (const [lat, lng] of [[null, 5], [NaN, 0], [91, 0], [0, 181], [0, Infinity]]) {
      expect(validCoordinates(lat, lng)).toBe(false);
    }
  });
});
