const PASSWORD_REQUIREMENTS =
  "Use at least 8 characters with an uppercase letter, a lowercase letter, and a number.";

export function passwordRequirementError(password: string): string | null {
  if (
    password.length < 8
    || !/[a-z]/.test(password)
    || !/[A-Z]/.test(password)
    || !/[0-9]/.test(password)
  ) {
    return PASSWORD_REQUIREMENTS;
  }
  return null;
}

export function friendlyAuthError(message: string, fallback: string): string {
  const normalized = message.toLowerCase();
  if (
    normalized.includes("password should contain")
    || normalized.includes("password must contain")
    || normalized.includes("password should be at least")
  ) {
    return PASSWORD_REQUIREMENTS;
  }
  if (normalized.includes("user already registered")) {
    return "An account already exists for this email. Sign in instead.";
  }
  if (normalized.includes("invalid login credentials")) {
    return "The email or password is incorrect.";
  }
  return fallback;
}

export { PASSWORD_REQUIREMENTS };
