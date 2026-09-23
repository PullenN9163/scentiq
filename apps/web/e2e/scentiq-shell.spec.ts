import { expect, test } from "@playwright/test";

const primaryRoutes = [
  ["/dashboard", "Today"],
  ["/week", "My Week"],
  ["/collection", "Collection"],
  ["/layering", "Layering Lab"],
  ["/discover", "Discover"],
  ["/insights", "Insights"],
  ["/agent", "Ask ScentIQ"],
  ["/settings", "Settings"],
] as const;

test("landing enters the demo dashboard", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("link", { name: /enter demo/i }).first().click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByRole("heading", { level: 1, name: "Today" })).toBeVisible();
});

test("every primary route renders its product heading", async ({ page }) => {
  await page.goto("/dashboard");
  for (const [route, heading] of primaryRoutes.slice(1)) {
    await page.locator("aside").getByRole("link", { name: heading === "Ask ScentIQ" ? "Agent" : heading }).click();
    await expect(page).toHaveURL(new RegExp(`${route}$`));
    await expect(page.getByRole("heading", { level: 1, name: heading })).toBeVisible();
  }
});

test("dashboard opens a fragrance detail", async ({ page }) => {
  await page.goto("/dashboard");
  await page.getByRole("link", { name: /view details/i }).click();
  await expect(page).toHaveURL(/\/collection\//);
  await expect(page.getByRole("link", { name: /back to collection/i })).toBeVisible();
});

test("week recommendation can be replaced", async ({ page }) => {
  await page.goto("/week");
  await page.getByRole("button", { name: /replace recommendation/i }).first().click();
  const dialog = page.getByRole("dialog", { name: /choose another direction/i });
  await expect(dialog).toBeVisible();
  await expect(dialog.locator(":focus")).toHaveCount(1);
  const replacement = dialog.getByRole("button", { name: /^choose /i }).first();
  const name = (await replacement.getAttribute("aria-label"))!.replace("Choose ", "");
  await replacement.click();
  await expect(dialog).toBeHidden();
  await expect(page.getByTestId("week-day").first().getByRole("heading", { name })).toBeVisible();
});

test("collection search leads to a detail page", async ({ page }) => {
  await page.goto("/collection");
  await page.getByRole("searchbox", { name: /search collection/i }).fill("Cedar");
  await page.getByLabel("Ownership").selectOption("Bottle");
  await expect(page.getByTestId("fragrance-card")).toHaveCount(1);
  await page.getByRole("link", { name: /cedar after rain/i }).click();
  await expect(page).toHaveURL(/cedar-after-rain/);
});

test("collection add form reports required fields", async ({ page }) => {
  await page.goto("/collection");
  await page.getByRole("button", { name: /add fragrance/i }).click();
  const dialog = page.getByRole("dialog", { name: /add fragrance/i });
  await dialog.getByRole("button", { name: /add to collection/i }).click();
  await expect(dialog.locator("#add-fragrance-error")).toHaveText(/choose a fragrance/i);
});

test("layering selections update the result", async ({ page }) => {
  await page.goto("/layering");
  await page.getByLabel("Fragrance B").selectOption("amber-index");
  await expect(page.getByText(/no curated safe pairing/i)).toBeVisible();
  await page.getByRole("button", { name: /show a curated pair/i }).click();
  await expect(page.getByRole("progressbar", { name: /compatibility score/i })).toBeVisible();
});

test("discover mode filters recommendations", async ({ page }) => {
  await page.goto("/discover");
  const before = await page.getByTestId("discovery-card").count();
  await page.getByRole("button", { name: "Office" }).click();
  await page.getByLabel("Redundancy tolerance").selectOption("High");
  const after = await page.getByTestId("discovery-card").count();
  expect(after).toBeLessThan(before);
});

test("agent quick action produces a response", async ({ page }) => {
  await page.goto("/agent");
  await page.locator(".quick-prompts button").first().click();
  await expect(page.getByText("Demo response")).toBeVisible();
});

test("mobile navigation exposes secondary destinations", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto("/dashboard");
  await page.getByRole("button", { name: /more destinations/i }).click();
  const dialog = page.getByRole("dialog", { name: /more destinations/i });
  await expect(dialog).toBeVisible();
  await dialog.getByRole("link", { name: "Settings" }).click();
  await expect(page).toHaveURL(/\/settings$/);
  await expect(dialog).toBeHidden();
});

for (const width of [375, 430, 768, 1024, 1440]) {
  test(`shell has no horizontal overflow at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    for (const route of ["/", ...primaryRoutes.map(([path]) => path), "/collection/cedar-after-rain"]) {
      await page.goto(route);
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      expect(overflow, `${route} overflow at ${width}px`).toBeLessThanOrEqual(1);
    }
  });
}
