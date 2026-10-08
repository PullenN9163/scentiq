import { expect, test } from "@playwright/test";

test.use({ storageState: { cookies: [], origins: [] } });

test("signed-out visitors are redirected away from the app shell", async ({ page }) => {
  await page.goto("/collection");
  await expect(page).toHaveURL(/sign-in/);
});

test("the landing page stays public", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1, name: "ScentIQ" })).toBeVisible();
  await expect(page.getByRole("link", { name: /sign in/i }).first()).toBeVisible();
});
