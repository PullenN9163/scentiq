import { expect, test, type Page } from "@playwright/test";

const shellCases = [
  { name: "phone", width: 393, height: 852, visible: "Mobile navigation" },
  { name: "tablet portrait", width: 834, height: 1194, visible: "Tablet navigation" },
  { name: "tablet landscape", width: 1194, height: 834, visible: "Tablet navigation" },
  { name: "desktop", width: 1440, height: 1000, visible: "Primary navigation" },
] as const;

async function expectNoDocumentOverflow(page: Page) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
}

test.describe("adaptive shell", () => {
  for (const viewport of shellCases) {
    test(`shell selects ${viewport.name} navigation`, async ({ page }) => {
      await page.setViewportSize(viewport);
      await page.goto("/?view=today&theme=dark");

      for (const name of ["Mobile navigation", "Tablet navigation", "Primary navigation"]) {
        const nav = page.getByRole("navigation", { name, exact: true });
        if (name === viewport.visible) await expect(nav).toBeVisible();
        else await expect(nav).toBeHidden();
      }

      await expectNoDocumentOverflow(page);
      const targets = page.getByRole("navigation", { name: viewport.visible, exact: true }).locator("a,button,select").filter({ visible: true });
      for (const target of await targets.all()) {
        const box = await target.boundingBox();
        expect(box?.width).toBeGreaterThanOrEqual(44);
        expect(box?.height).toBeGreaterThanOrEqual(44);
      }

      const footer = page.locator(".app-footer");
      await page.evaluate(() => {
        document.documentElement.style.scrollBehavior = "auto";
        window.scrollTo(0, document.documentElement.scrollHeight);
      });
      await expect(footer).toBeVisible();
      const footerBox = await footer.boundingBox();
      const bottomNavBox = viewport.visible === "Mobile navigation"
        ? await page.getByRole("navigation", { name: "Mobile navigation" }).boundingBox()
        : null;
      const visibleBottom = bottomNavBox?.y ?? viewport.height;
      expect(footerBox && footerBox.y + footerBox.height <= visibleBottom + 1).toBe(true);
    });
  }
});

const primaryViewports = [
  { name: "small phone", width: 320, height: 568 },
  { name: "modern phone", width: 393, height: 852 },
  { name: "tablet portrait", width: 834, height: 1194 },
  { name: "tablet landscape", width: 1194, height: 834 },
  { name: "200 percent reflow", width: 720, height: 900 },
] as const;

test.describe("primary screens", () => {
  for (const viewport of primaryViewports) {
    test(`primary screens reflow at ${viewport.name}`, async ({ page }) => {
      await page.setViewportSize(viewport);

      await page.goto("/?view=today&theme=light&long=1");
      await expectNoDocumentOverflow(page);
      const recommendation = page.locator(".recommendation-main");
      const recommendationLayout = await recommendation.evaluate((element) => {
        const children = Array.from(element.children) as HTMLElement[];
        const columns = getComputedStyle(element).gridTemplateColumns.split(" ").filter(Boolean).length;
        return { columns, total: element.clientWidth, copy: children[1]?.clientWidth ?? 0 };
      });
      if (viewport.width <= 430) expect(recommendationLayout.columns).toBe(1);
      else expect(recommendationLayout.columns === 1 || recommendationLayout.copy >= recommendationLayout.total * .55).toBe(true);

      await page.goto("/?view=week&theme=light&long=1");
      await expectNoDocumentOverflow(page);
      const firstDay = page.getByTestId("week-day").first();
      const dayHeading = await firstDay.getByRole("heading").first().boundingBox();
      const dayRecommendation = await firstDay.getByTestId("recommendation-card").boundingBox();
      expect(dayHeading && dayRecommendation && dayRecommendation.y >= dayHeading.y + dayHeading.height).toBe(true);
      const stickyTop = await page.locator(".week-day-nav").evaluate((element) => Number.parseFloat(getComputedStyle(element).top));
      if (viewport.width > 700) expect(stickyTop).toBe(16);
      else expect(stickyTop).toBeGreaterThan(64);

      await page.goto("/?view=collection&theme=light&long=1");
      await expectNoDocumentOverflow(page);
      await expect(page.getByRole("button", { name: "Filters and sort" })).toBeVisible();
      if (viewport.width <= 430) {
        const tools = await page.locator(".collection-tools").boundingBox();
        const search = await page.getByRole("searchbox", { name: "Search collection" }).locator("..").boundingBox();
        expect(tools && search && search.width >= tools.width - 2).toBe(true);
      }

      await page.goto("/?view=detail&theme=light&long=1");
      await expectNoDocumentOverflow(page);
      if (viewport.width <= 430) {
        const art = await page.locator(".detail-art").boundingBox();
        expect(art?.height).toBeLessThanOrEqual(viewport.height * .55);
      }
      await expect(page.getByRole("link", { name: "Layer it" })).toBeVisible();
    });
  }
});
