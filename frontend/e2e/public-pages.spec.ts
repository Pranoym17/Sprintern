import { expect, test } from "@playwright/test";

test("landing page communicates the live product and stays within the viewport", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Stop finding internships");
  await expect(page.getByRole("link", { name: /create your alert/i })).toBeVisible();
  await expect(page.getByText("Continuously updated jobs").first()).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
  expect(overflow).toBe(false);
});

for (const [path, heading] of [["/privacy", "Privacy at Sprintern"], ["/terms", "Terms of use"], ["/data-sources", "How Sprintern handles postings"], ["/contact", "Contact Sprintern"]] as const) {
  test(`${path} is public and linked back to the product`, async ({ page }) => {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1, name: heading })).toBeVisible();
    await expect(page.getByRole("link", { name: "Back to home" })).toHaveAttribute("href", "/");
  });
}

test("sign-in form has accessible labels and links", async ({ page }) => {
  await page.goto("/sign-in");
  await expect(page.getByRole("heading", { name: "Sign in to your alerts" })).toBeVisible();
  await expect(page.getByLabel("Email address")).toBeVisible();
  await expect(page.getByLabel("Password")).toBeVisible();
  await expect(page.getByRole("link", { name: "Create an account" })).toHaveAttribute("href", "/sign-up");
  await expect(page.getByRole("link", { name: "Forgot password?" })).toHaveAttribute("href", "/forgot-password");
});

test("protected routes redirect signed-out users and preserve a safe destination", async ({ page }) => {
  await page.goto("/matches");
  await expect(page).toHaveURL(/\/sign-in\?next=%2Fmatches$/);
  await expect(page.getByText("Sign in to your alerts")).toBeVisible();
});

test("password recovery is available", async ({ page }) => {
  await page.goto("/forgot-password");
  await expect(page.getByRole("heading", { name: "Reset your password" })).toBeVisible();
  await expect(page.getByRole("button", { name: /send reset link/i })).toBeVisible();
});

test("security headers are present", async ({ request }) => {
  const response = await request.get("/");
  expect(response.headers()["content-security-policy"]).toContain("frame-ancestors 'none'");
  expect(response.headers()["x-content-type-options"]).toBe("nosniff");
  expect(response.headers()["referrer-policy"]).toBe("strict-origin-when-cross-origin");
});

test("reduced motion removes continuous animations", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  const duration = await page.locator(".orbit--outer").evaluate((element) => getComputedStyle(element).animationDuration);
  expect(Number.parseFloat(duration)).toBeLessThanOrEqual(0.00001);
});
