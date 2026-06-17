import { test, expect } from "@playwright/test";

/**
 * Smoke test: landing page renders.
 */
test("landing page loads", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    /Smart Student Project Manager/i
  );
  await expect(page.getByRole("link", { name: /Đăng nhập/i })).toBeVisible();
  await expect(page.getByRole("link", { name: /Tạo tài khoản/i })).toBeVisible();
});
