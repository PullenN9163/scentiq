import { expect, test, type Page } from "@playwright/test";

/** Every Atelier fixture view. Each one must render with the Atelier tokens and fit the viewport. */
const views = [
  "landing-atelier", "sign-in-atelier", "sign-up-atelier",
  "today-atelier", "today-loading", "week-atelier", "collection-atelier", "blends",
  "discover-atelier", "discover-atelier-error", "discover-loading", "insights-atelier", "settings-atelier",
  "fragrance", "sheet", "ask", "blend",
] as const;
const widths = [390, 820, 1180, 1440] as const;
const themes = ["dark", "light"] as const;

/** The views worth a baseline screenshot at the phone and desktop widths. */
const snapshotViews = ["landing-atelier", "sign-in-atelier", "today-atelier", "collection-atelier", "blend"] as const;

async function expectFits(page: Page) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
}

test.describe("Atelier views fit and use the Atelier tokens", () => {
  for (const view of views) {
    for (const theme of themes) {
      for (const width of widths) {
        test(`${view} fits ${width}px in ${theme}`, async ({ page }) => {
          const errors: string[] = [];
          page.on("pageerror", (error) => errors.push(error.message));
          await page.setViewportSize({ width, height: 900 });
          await page.emulateMedia({ reducedMotion: "reduce" });
          await page.goto(`/?view=${view}&theme=${theme}`);
          await expect(page.locator("html")).toHaveAttribute("data-atelier", "true");
          await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
          await expectFits(page);
          expect(errors).toEqual([]);
        });
      }
    }
  }
});

test.describe("Atelier baseline screenshots", () => {
  for (const view of snapshotViews) {
    for (const width of [390, 1440] as const) {
      test(`${view} at ${width}px matches its baseline`, async ({ page }) => {
        test.setTimeout(60000);
        await page.setViewportSize({ width, height: 900 });
        await page.emulateMedia({ reducedMotion: "reduce" });
        await page.clock.install({ time: new Date("2026-10-13T16:00:00Z") });
        await page.goto(`/?view=${view}&theme=dark`);
        await expect(page.locator("html")).toHaveAttribute("data-atelier", "true");
        await expect(page).toHaveScreenshot(`atelier-${view}-dark-${width}.png`, { fullPage: true, animations: "disabled", maxDiffPixelRatio: 0.005 });
      });
    }
  }
});
