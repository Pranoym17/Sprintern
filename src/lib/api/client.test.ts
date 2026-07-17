import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiClient, ApiError } from "./client";

const token = vi.fn(async () => "access-token");
const api = new ApiClient(token);

afterEach(() => vi.unstubAllGlobals());

describe("ApiClient", () => {
  it("attaches the bearer token and parses JSON", async () => {
    const fetchMock = vi.fn<typeof fetch>(async () => new Response(JSON.stringify({ matched_count: 4 }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    await expect(api.analytics()).resolves.toEqual({ matched_count: 4 });
    expect(fetchMock).toHaveBeenCalledWith("http://127.0.0.1:8010/analytics/summary", expect.objectContaining({ cache: "no-store", headers: expect.objectContaining({ Authorization: "Bearer access-token" }) }));
  });

  it("normalizes application error envelopes", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ error: { code: "invalid_cursor", message: "Pagination cursor is invalid" } }), { status: 400 })));
    await expect(api.matches("bad cursor")).rejects.toMatchObject({ status: 400, code: "invalid_cursor", message: "Pagination cursor is invalid" } satisfies Partial<ApiError>);
  });

  it("normalizes authentication detail responses", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ detail: "Invalid authentication credentials" }), { status: 401 })));
    await expect(api.profile()).rejects.toMatchObject({ status: 401, message: "Invalid authentication credentials" } satisfies Partial<ApiError>);
  });

  it("handles successful empty responses", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(null, { status: 204 })));
    await expect(api.deleteFilter("filter-id")).resolves.toBeUndefined();
  });

  it("reports missing sessions before calling fetch", async () => {
    const fetchMock = vi.fn(); vi.stubGlobal("fetch", fetchMock);
    const signedOut = new ApiClient(async () => null);
    await expect(signedOut.profile()).rejects.toMatchObject({ status: 401, code: "not_authenticated" } satisfies Partial<ApiError>);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("reports network failures without leaking implementation details", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("connection refused"); }));
    await expect(api.profile()).rejects.toMatchObject({ status: 0, code: "network_error" } satisfies Partial<ApiError>);
  });

  it("times out stalled requests", async () => {
    vi.stubGlobal("fetch", vi.fn<typeof fetch>(async (_input, init) => new Promise((_resolve, reject) => {
      init?.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")));
    })));
    const impatient = new ApiClient(async () => "token", undefined, 1);
    await expect(impatient.profile()).rejects.toMatchObject({ code: "request_timeout" } satisfies Partial<ApiError>);
  });

  it("invokes centralized session recovery once on 401", async () => {
    const recover = vi.fn();
    vi.stubGlobal("fetch", vi.fn<typeof fetch>(async () => new Response(JSON.stringify({ detail: "expired" }), { status: 401 })));
    const expiring = new ApiClient(async () => "token", recover);
    await expect(expiring.profile()).rejects.toMatchObject({ status: 401 });
    expect(recover).toHaveBeenCalledOnce();
  });

  it("encodes opaque cursors and sends match status mutations", async () => {
    const fetchMock = vi.fn<typeof fetch>(async () => new Response(JSON.stringify({ id: "match-id", status: "applied" }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    await api.matches("opaque+/=");
    expect(fetchMock.mock.calls[0][0]).toContain("cursor=opaque%2B%2F%3D");
    await api.updateMatch("match-id", "applied");
    expect(fetchMock.mock.calls[1][1]).toEqual(expect.objectContaining({ method: "PATCH", body: JSON.stringify({ status: "applied" }) }));
  });
});
