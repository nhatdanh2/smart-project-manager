import { test, expect } from "@playwright/test";

/**
 * Verify theme toggle flips dark mode on.
 */
test("dark mode toggle works", async ({ page }) => {
  await page.goto("/");
  const html = page.locator("html");
  await expect(html).not.toHaveClass(/dark/);
  // Open the dashboard to find the theme toggle
  await page.getByRole("link", { name: /Đăng nhập/i }).click();
  await page.getByLabel(/Email/i).fill("leader@example.com");
  await page.getByLabel(/Mật khẩu/i).fill("password123");
  await page.getByRole("button", { name: /Đăng nhập/i }).click();
  await page.waitForURL(/\/projects/);
  const toggle = page.getByRole("button", { name: /Toggle theme|Chuyển theme/i });
  await toggle.click();
  await expect(html).toHaveClass(/dark/);
  await toggle.click();
  await expect(html).not.toHaveClass(/dark/);
});
