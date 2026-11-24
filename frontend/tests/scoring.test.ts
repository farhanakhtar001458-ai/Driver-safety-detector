import { describe, expect, it } from "vitest";
import { scoreColour } from "@/lib/scoreDisplay";

describe("score presentation", () => {
  it("treats a missing score as unknown rather than zero", () => {
    expect(scoreColour(null)).toBe("muted");
    expect(scoreColour(undefined)).toBe("muted");
  });

  it("uses distinct bands for good, fair and poor scores", () => {
    expect(scoreColour(92)).toBe("good");
    expect(scoreColour(78)).toBe("ok");
    expect(scoreColour(61)).toBe("warn");
    expect(scoreColour(30)).toBe("bad");
  });

  it("clamps out-of-range values instead of throwing", () => {
    expect(scoreColour(140)).toBe("good");
    expect(scoreColour(-10)).toBe("bad");
  });
});
