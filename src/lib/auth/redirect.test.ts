import { describe, expect, it } from "vitest";
import { safeInternalPath } from "./redirect";

describe("safeInternalPath", () => {
  it("keeps allowlisted app destinations", () => { expect(safeInternalPath("/matches?cursor=abc#job")).toBe("/matches?cursor=abc#job"); });
  it.each(["//evil.com", "/\\evil.com", "/%5Cevil.com", "https://evil.com", "/unknown", "/dashboard%00evil"])("rejects unsafe destination %s", (value) => { expect(safeInternalPath(value)).toBe("/dashboard"); });
});
