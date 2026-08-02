import { describe, expect, it } from "vitest";
import { friendlyAuthError, passwordRequirementError } from "./messages";

describe("authentication messages", () => {
  it("requires mixed-case letters and a number for new passwords", () => {
    expect(passwordRequirementError("lowercase1")).toContain("uppercase");
    expect(passwordRequirementError("ValidPass1")).toBeNull();
  });

  it("does not expose Supabase's raw password policy message", () => {
    expect(friendlyAuthError("Password should contain at least one character of each: abcXYZ, 0123456789.", "Sign-up failed."))
      .toBe("Use at least 8 characters with an uppercase letter, a lowercase letter, and a number.");
  });
});
