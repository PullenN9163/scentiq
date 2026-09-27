import { expect, test } from "@playwright/test";

/**
 * The private-beta journey, end to end against a real Clerk test user and a
 * seeded database.
 *
 * It is skipped unless the environment supplies a test identity, because it
 * signs in for real rather than stubbing the provider. Set
 * E2E_CLERK_EMAIL and E2E_CLERK_CODE (Clerk's test-mode email-code identity) to
 * run it.
 */

const email = process.env.E2E_CLERK_EMAIL;
const code = process.env.E2E_CLERK_CODE;

test.describe("invited member journey", () => {
  test.skip(!email || !code, "Set E2E_CLERK_EMAIL and E2E_CLERK_CODE to run the signed-in journey");

  test("signs in, builds a collection, logs a wear and sees it reflected", async ({ page }) => {
    // --- sign in --------------------------------------------------------
    await page.goto("/sign-in");
    await page.getByLabel(/email/i).fill(email!);
    await page.getByRole("button", { name: /continue/i }).click();
    await page.getByLabel(/code/i).fill(code!);
    await expect(page).toHaveURL(/\/dashboard$/, { timeout: 30_000 });

    // --- create a custom fragrance --------------------------------------
    await page.goto("/collection");
    await page.getByRole("button", { name: /add fragrance/i }).click();
    await page.getByRole("button", { name: /create custom/i }).click();
    const unique = `E2E Blend ${Date.now()}`;
    await page.getByLabel("Brand").fill("E2E House");
    await page.getByLabel("Fragrance name").fill(unique);
    await page.getByLabel("Concentration").fill("eau_de_parfum");
    await page.getByRole("button", { name: /create fragrance/i }).click();
    await expect(page.getByText(/custom fragrance added/i)).toBeVisible();

    // --- add it to the collection ---------------------------------------
    await page.getByRole("button", { name: /from catalog/i }).click();
    await page.getByLabel("Catalog fragrance").selectOption({ label: `E2E House — ${unique}` });
    await page.getByLabel("Bottle size (ml)").fill("100");
    await page.getByLabel("Remaining (ml)").fill("100");
    await page.getByLabel("Purchase price").fill("120.00");
    await page.getByLabel("Your rating (1–5)").fill("5");
    await page.getByRole("button", { name: /add to collection/i }).click();
    await expect(page.getByRole("heading", { name: unique })).toBeVisible();

    // --- edit ownership --------------------------------------------------
    await page.getByRole("link", { name: `Open ${unique}` }).click();
    await page.getByRole("button", { name: /^edit$/i }).click();
    await page.getByLabel("Remaining (ml)").fill("80");
    await page.getByRole("button", { name: /save changes/i }).click();
    await expect(page.getByText("80ml remaining")).toBeVisible();

    // --- log a wear ------------------------------------------------------
    await page.getByRole("button", { name: /log wear/i }).click();
    await page.getByLabel("Sprays").fill("3");
    await page.getByLabel("Occasion").selectOption("work");
    await page.getByRole("button", { name: /^log wear$/i }).click();
    await expect(page.getByText(/wear logged/i)).toBeVisible();

    // --- dashboard and insights reflect it -------------------------------
    await page.goto("/dashboard");
    await expect(page.getByText(unique)).toBeVisible();

    await page.goto("/insights");
    await expect(page.getByRole("heading", { level: 1, name: "Insights" })).toBeVisible();
    // A custom entry has no classification data, which insights must disclose.
    await expect(page.getByText(/no classification data/i)).toBeVisible();

    // --- update preferences ----------------------------------------------
    await page.goto("/settings");
    await page.getByLabel("Location").fill("Manchester");
    await page.getByLabel("Maximum sprays").fill("4");
    await page.getByRole("button", { name: /save preferences/i }).click();
    await expect(page.getByText(/preferences saved/i)).toBeVisible();

    await page.reload();
    await expect(page.getByLabel("Location")).toHaveValue("Manchester");
  });
});

test("signed-out visitors are redirected away from the app shell", async ({ page }) => {
  await page.goto("/collection");

  // The proxy protects every app-shell route.
  await expect(page).toHaveURL(/sign-in/);
});

test("the landing page stays public", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { level: 1, name: "ScentIQ" })).toBeVisible();
  await expect(page.getByRole("link", { name: /sign in/i }).first()).toBeVisible();
});

/**
 * Preview screens still need coverage, but they now sit behind authentication,
 * so these run under the same credential gate as the journey above.
 */
test.describe("preview screens", () => {
  test.skip(!email || !code, "Set E2E_CLERK_EMAIL and E2E_CLERK_CODE to run the preview checks");

  test.beforeEach(async ({ page }) => {
    await page.goto("/sign-in");
    await page.getByLabel(/email/i).fill(email!);
    await page.getByRole("button", { name: /continue/i }).click();
    await page.getByLabel(/code/i).fill(code!);
    await expect(page).toHaveURL(/\/dashboard$/, { timeout: 30_000 });
  });

  const routes = [
    ["/week", "My Week"],
    ["/layering", "Layering Lab"],
    ["/discover", "Discover"],
    ["/agent", "Ask ScentIQ"],
  ] as const;

  for (const [route, heading] of routes) {
    test(`${heading} renders and declares itself a preview`, async ({ page }) => {
      await page.goto(route);
      await expect(page.getByRole("heading", { level: 1, name: heading })).toBeVisible();
      // Every preview surface must say it is not saving anything.
      await expect(page.getByRole("note").first()).toContainText(/preview/i);
    });
  }

  test("every primary route renders its product heading", async ({ page }) => {
    const primary = [
      ["/dashboard", "Hello"],
      ["/collection", "Collection"],
      ["/insights", "Insights"],
      ["/settings", "Settings"],
    ] as const;
    for (const [route, heading] of primary) {
      await page.goto(route);
      await expect(page.getByRole("heading", { level: 1 })).toContainText(heading);
    }
  });
});
