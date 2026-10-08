import { expect, test, type Page } from "@playwright/test";

/**
 * The private-beta journey, end to end against a real Clerk test user and a
 * seeded database.
 *
 * It is skipped unless the environment supplies a test identity. The Clerk
 * setup project signs in once and saves browser state for these checks.
 */

const email = process.env.E2E_CLERK_EMAIL;

async function openCollection(page: Page) {
  const addFragrance = page.getByRole("button", { name: /add fragrance/i });
  for (let attempt = 0; attempt < 3; attempt += 1) {
    await page.goto("/collection");
    try {
      await addFragrance.waitFor({ state: "visible", timeout: 30_000 });
      return;
    } catch (error) {
      const unavailable = await page
        .getByText("Service unavailable", { exact: true })
        .isVisible()
        .catch(() => false);
      if (!unavailable || attempt === 2) throw error;
    }
  }
}

test.describe("invited member journey", () => {
  test.skip(!email, "Set E2E_CLERK_EMAIL to run the signed-in journey");

  test("signs in, builds a collection, logs a wear and sees it reflected", async ({ page }) => {
    test.setTimeout(600_000);
    await page.goto("/dashboard");
    await expect(page.getByRole("heading", {level:1})).toContainText("Hello");

    // --- create a custom fragrance --------------------------------------
    await openCollection(page);
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
    await page.getByRole("searchbox", {name:"Search the catalog"}).fill(unique);
    await page.getByRole("radio", {name:new RegExp(unique)}).check();
    await page.getByLabel("Bottle size (ml)").fill("100");
    await page.getByLabel("Remaining (ml)").fill("100");
    await page.getByLabel("Purchase price").fill("120.00");
    await page.getByLabel("Your rating (1–5)").fill("5");
    await page.getByRole("button", { name: /add to collection/i }).click();
    await expect(page.getByRole("heading", { name: unique })).toBeVisible();

    // --- edit ownership --------------------------------------------------
    await page.getByRole("link", { name: `Open ${unique}` }).click();
    await page.getByLabel("Custom fragrance image").setInputFiles({
      name:"release-image.png",mimeType:"image/png",buffer:Buffer.from("iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAIAAAD8GO2jAAAAPElEQVR4nO3RQREAMAjEwKNC6qAO8K+rEsKHX1bAMRPq9sums7oeDwz4A2QiZCJkImQiZCJkImQiZKKQD/RMAMeWjfQwAAAAAElFTkSuQmCC","base64"),
    });
    await page.getByRole("button", {name:"Upload image",exact:true}).click();
    await expect(page.getByRole("button", {name:"Remove image",exact:true})).toBeVisible();
    await page.reload();
    await expect(page.getByRole("button", {name:"Remove image",exact:true})).toBeVisible();
    await page.getByRole("button", {name:"Remove image",exact:true}).click();
    await expect(page.getByRole("button", {name:"Remove image",exact:true})).toHaveCount(0);
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
    await expect(page.getByText(unique).first()).toBeVisible();

    await page.goto("/insights");
    await expect(page.getByRole("heading", { level: 1, name: "Insights" })).toBeVisible();
    // A custom entry has no classification data, which insights must disclose.
    await expect(page.getByRole("heading", {name:"Notes across your shelf"})).toBeVisible();

    // --- update preferences ----------------------------------------------
    await page.goto("/settings");
    await page.getByLabel("Location").fill("Manchester");
    await page.getByLabel("Maximum sprays").fill("4");
    await page.getByRole("button", { name: /save preferences/i }).click();
    await expect(page.getByText(/preferences saved/i)).toBeVisible();

    await page.reload();
    await expect(page.getByLabel("Location")).toHaveValue("Manchester");

    // Add two source-backed supporters to exercise alternatives and triple stacks.
    for (let index = 0; index < 2; index += 1) {
      await openCollection(page);
      await page.getByRole("button", { name: /add fragrance/i }).click();
      await page.getByRole("button", { name: /from catalog/i }).click();
      await page.locator(".catalog-picker__result input:not(:disabled)").first().check();
      await page.getByRole("button", { name: /add to collection/i }).click();
      await expect(page.getByRole("dialog")).toHaveCount(0);
    }
    await page.goto("/dashboard");
    const hero = page.getByTestId("recommendation-card").first();
    await expect(hero.getByText(/Match .*100/)).toBeVisible();
    await hero.getByRole("button", { name: "Why this?" }).click();
    await expect(page.getByText(/not statistical confidence/)).toBeVisible();
    await page.getByRole("button", { name: "Close Why this fragrance?" }).click();
    await hero.getByRole("button", { name: "Another Option" }).click();
    await hero.getByRole("button", { name: /^Choose / }).last().click();
    await hero.getByRole("button", { name: "Wear This" }).click();
    await page.getByRole("button", { name: "Log wear", exact: true }).click();
    await page.getByLabel(/^Rating/).fill("5");
    await page.getByRole("button", { name: "Save feedback" }).click();
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await page.goto("/week");
    await expect(page.getByTestId("week-day")).toHaveCount(7);
    await page.getByRole("button", { name: "Another Option" }).first().click();
    await page.getByRole("button", { name: /^Choose / }).last().click();

    await page.goto("/agent");
    await page.getByPlaceholder("What should I wear to dinner tonight?").fill("What should I wear to dinner tonight?");
    await page.getByRole("button", { name: "Send", exact: true }).click();
    await expect(page.getByTestId("recommendation-card").first()).toBeVisible();
    await expect(page.getByRole("button", { name: "Send", exact: true })).toBeVisible();
    await page.getByPlaceholder("What should I wear to dinner tonight?").fill("What am I neglecting?");
    await page.getByRole("button", { name: "Send", exact: true }).click();
    await expect(page.getByRole("link", { name: "Open Insights" }).last()).toBeVisible();

    await page.goto("/layering");
    await page.getByRole("button", { name: /^Choose anchor / }).first().click();
    await expect(page.getByLabel("Ranked layering suggestions")).toBeVisible();
    const fresh = page.getByRole("button", { name: "Make it fresher", exact: true });
    if (await fresh.count()) await fresh.click();
    await page.getByRole("button", { name: "Build a custom stack" }).click();
    await page.getByRole("button", { name: /^Add / }).first().click();
    await page.getByRole("button", { name: /^Add / }).first().click();
    await expect(page.getByTestId("stack-item")).toHaveCount(3);
    await expect(page.getByRole("heading", { name: "How to apply it" })).toBeVisible();
    await page.getByRole("button", { name: "Save this stack", exact: true }).click();
    const stackName = `Evening stack ${Date.now()}`;
    await page.getByLabel("Combination name").fill(stackName);
    await page.getByRole("button", { name: "Save named combination" }).click();
    await page.getByRole("button", { name: `Wear ${stackName}` }).click();
    await page.getByLabel("Personal rating").selectOption("5");
    await page.getByRole("button", { name: "Log this wear" }).click();
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await page.goto("/agent");
    await page.getByPlaceholder("What should I wear to dinner tonight?").fill("Give me a three fragrance layering stack tonight");
    await page.getByRole("button", { name: "Send", exact: true }).click();
    await expect(page.getByRole("heading", { name: /Owned layering stack/ }).first()).toBeVisible();
    await page.goto("/insights");
    await expect(page.getByRole("heading", { level: 1, name: "Insights" })).toBeVisible();
    for (const width of [375, 430, 768, 1024, 1440]) {
      await page.setViewportSize({ width, height: 900 });
      for (const route of ["/dashboard", "/week", "/layering", "/agent"]) {
        await page.goto(route);
        await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
      }
    }
  });
});

/** Authenticated feature surfaces use the same real test identity. */
test.describe("intelligence screens", () => {
  test.skip(!email, "Set E2E_CLERK_EMAIL to run the intelligence checks");

  test.beforeEach(async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page.getByRole("heading", {level:1})).toContainText("Hello");
  });

  const routes = [
    ["/week", "My Week"],
    ["/layering", "Layering Lab"],
    ["/discover", "Discover"],
    ["/agent", "Ask ScentIQ"],
  ] as const;

  for (const [route, heading] of routes) {
    test(`${heading} renders its operational surface`, async ({ page }) => {
      await page.goto(route);
      await expect(page.getByRole("heading", { level: 1, name: heading })).toBeVisible();
      await expect(page.getByText("Not connected yet", {exact:false})).toHaveCount(0);
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
