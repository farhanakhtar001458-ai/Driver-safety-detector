import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, api, tokenStore } from "@/lib/api";

describe("api client", () => {
  beforeEach(() => {
    tokenStore.clear();
    vi.restoreAllMocks();
  });

  afterEach(() => {
    tokenStore.clear();
  });

  it("normalises a backend error envelope into a readable message", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "Vehicle limit reached for this plan" }), {
        status: 409,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await expect(api.get("/vehicles")).rejects.toMatchObject({
      message: "Vehicle limit reached for this plan",
      status: 409,
    });
  });

  it("reports an unreachable backend without throwing a raw TypeError", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("Failed to fetch"));

    await expect(api.get("/dashboard")).rejects.toMatchObject({
      message: expect.stringContaining("Cannot reach the SafeWay API"),
    });
  });

  it("attaches the bearer token when one is stored", async () => {
    tokenStore.set("access-token", "refresh-token");
    const spy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ items: [] }), { status: 200, headers: { "Content-Type": "application/json" } }),
    );

    await api.get("/vehicles");
    const request = spy.mock.calls[0][1] as RequestInit;
    expect((request.headers as Record<string, string>).Authorization).toBe("Bearer access-token");
  });

  it("encodes query parameters and skips empty values", async () => {
    const spy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ items: [] }), { status: 200, headers: { "Content-Type": "application/json" } }),
    );

    await api.get("/vehicles", { page: 2, search: undefined, status: "" });
    const url = String(spy.mock.calls[0][0]);
    expect(url).toContain("page=2");
    expect(url).not.toContain("search");
    expect(url).not.toContain("status");
  });

  it("exposes the status code for role-aware UI handling", () => {
    const error = new ApiError("Forbidden", 403, "forbidden");
    expect(error.status).toBe(403);
    expect(error).toBeInstanceOf(Error);
  });
});
