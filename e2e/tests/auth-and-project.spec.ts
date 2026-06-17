import { test, expect } from "@playwright/test";

/**
 * End-to-end auth + project flow:
 *  1. Register a brand-new user
 *  2. Auto-redirect to /projects
 *  3. Create a project with a deadline
 *  4. Open the project & verify tabs render
 */
test("register, create project, open Kanban", async ({ page }) => {
  const email = `e2e_${Date.now()}@example.com`;
  const password = "password123";
  const name = "E2E User";
  const projectTitle = `E2E Project ${Date.now()}`;

  // 1. Register
  await page.goto("/register");
  await page.getByLabel(/Họ và tên/i).fill(name);
  await page.getByLabel(/Email/i).fill(email);
  await page.getByLabel(/Mật khẩu/i).fill(password);
  await page.getByRole("button", { name: /Đăng ký|Tạo tài khoản/i }).click();
  await page.waitForURL(/\/projects/);
  await expect(page.getByRole("heading", { name: /Dự án của tôi/i })).toBeVisible();

  // 2. Create project
  await page.getByRole("button", { name: /Dự án mới/i }).click();
  await page.getByLabel(/Tiêu đề/).fill(projectTitle);
  await page.getByLabel(/Deadline/i).fill("2099-12-31");
  await page.getByRole("button", { name: /Tạo dự án/i }).click();
  await expect(page.getByText(projectTitle)).toBeVisible();

  // 3. Open project, then Kanban tab
  await page.getByText(projectTitle).click();
  await page.waitForURL(/\/projects\/[a-f0-9-]+/);
  await expect(page.getByRole("link", { name: /Kanban/i })).toBeVisible();
  await page.getByRole("link", { name: /Kanban/i }).click();
  await expect(page.getByText(/Tính CPM/i)).toBeVisible();
});
