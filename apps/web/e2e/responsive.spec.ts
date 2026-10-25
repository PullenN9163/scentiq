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

const layeringViewports = [
  { name: "iPhone", width: 393, height: 852 },
  { name: "iPad portrait", width: 834, height: 1194 },
  { name: "iPad landscape", width: 1194, height: 834 },
] as const;

function boxesIntersect(a: { x: number; y: number; width: number; height: number }, b: { x: number; y: number; width: number; height: number }) {
  return a.x < b.x + b.width && a.x + a.width > b.x && a.y < b.y + b.height && a.y + a.height > b.y;
}

test.describe("Layering Studio responsive canvas", () => {
  for (const viewport of layeringViewports) {
    test(`Layering Studio controls stay untangled on ${viewport.name}`, async ({ page }) => {
      await page.setViewportSize(viewport);
      await page.goto("/?view=layering&theme=dark&long=1");
      await expectNoDocumentOverflow(page);

      const canvas = page.getByRole("region", { name: "Interactive blend canvas" });
      const canvasBox = await canvas.boundingBox();
      const scoreBox = await page.getByTestId("score-orb").boundingBox();
      const bottles = canvas.getByTestId("canvas-bottle");
      for (const bottle of await bottles.all()) {
        await bottle.click();
        const labelBox = await bottle.locator(":scope > strong").boundingBox();
        const actions = canvas.getByRole("region", { name: /^Actions for/ });
        await expect(actions).toBeVisible();
        const actionsBox = await actions.boundingBox();
        expect(
          canvasBox && actionsBox && actionsBox.x >= canvasBox.x && actionsBox.x + actionsBox.width <= canvasBox.x + canvasBox.width,
          JSON.stringify({ canvasBox, actionsBox }),
        ).toBe(true);
        expect(canvasBox && actionsBox && actionsBox.y >= canvasBox.y && actionsBox.y + actionsBox.height <= canvasBox.y + canvasBox.height).toBe(true);
        expect(labelBox && scoreBox && boxesIntersect(labelBox, scoreBox)).toBe(false);
        expect(labelBox && actionsBox && boxesIntersect(labelBox, actionsBox)).toBe(false);
        for (const action of await actions.getByRole("button").all()) {
          const actionBox = await action.boundingBox();
          expect(actionBox?.height).toBeGreaterThanOrEqual(44);
        }
      }
    });
  }

  test("Layering Studio keeps its active composition across responsive tiers", async ({ page }) => {
    await page.setViewportSize({ width: 834, height: 1194 });
    await page.goto("/?view=layering&theme=dark&long=1");
    const canvas = page.getByRole("region", { name: "Interactive blend canvas" });
    const firstBottle = canvas.getByTestId("canvas-bottle").first();
    await firstBottle.click();
    const names = await canvas.getByTestId("canvas-bottle").allTextContents();
    const score = await page.getByRole("region", { name: "ScentIQ read" }).textContent();
    const sessions = await page.getByRole("region", { name: "Session blends" }).getByRole("button").count();

    for (const viewport of [{ width: 1194, height: 834 }, { width: 393, height: 852 }]) {
      await page.setViewportSize(viewport);
      await expect(canvas.getByTestId("canvas-bottle")).toHaveCount(names.length);
      expect(await canvas.getByTestId("canvas-bottle").allTextContents()).toEqual(names);
      await expect(firstBottle).toHaveAttribute("aria-pressed", "true");
      expect(await page.getByRole("region", { name: "ScentIQ read" }).textContent()).toBe(score);
      await expect(page.getByRole("region", { name: "Session blends" }).getByRole("button")).toHaveCount(sessions);
      await expectNoDocumentOverflow(page);
    }
  });
});

const secondaryViewports = [
  { name: "iPhone", width: 393, height: 852 },
  { name: "iPad portrait", width: 834, height: 1194 },
  { name: "iPad landscape", width: 1194, height: 834 },
  { name: "200 percent reflow", width: 720, height: 900 },
] as const;

async function expectWithinViewportWidth(page: Page, locator: ReturnType<Page["locator"]>) {
  const box = await locator.boundingBox();
  expect(box && box.x >= -1 && box.x + box.width <= page.viewportSize()!.width + 1).toBe(true);
}

test.describe("secondary screens", () => {
  for (const viewport of secondaryViewports) {
    test(`secondary screens adapt at ${viewport.name}`, async ({ page }) => {
      await page.setViewportSize(viewport);

      await page.goto("/?view=discover&theme=dark&long=1");
      await expectNoDocumentOverflow(page);
      await expectWithinViewportWidth(page, page.locator(".discovery-toolbar"));
      await expectWithinViewportWidth(page, page.locator(".discovery-featured"));
      const directionColumns = await page.locator(".discovery-directions").evaluate(element => getComputedStyle(element).gridTemplateColumns.split(" ").filter(Boolean).length);
      expect(directionColumns).toBe(viewport.width <= 430 ? 1 : 2);

      await page.goto("/?view=insights&theme=dark&long=1");
      await expectNoDocumentOverflow(page);
      await expect(page.locator(".fingerprint__visual")).toBeVisible();
      await expect(page.locator(".fingerprint__legend")).toBeVisible();
      await expectWithinViewportWidth(page, page.locator(".fingerprint__visual"));
      await expectWithinViewportWidth(page, page.locator(".fingerprint__legend"));
      await expect(page.locator(".note-bars > div").first()).toBeVisible();

      await page.goto("/?view=settings&theme=dark&long=1");
      await expectNoDocumentOverflow(page);
      const settingsColumns = await page.locator(".settings-grid").evaluate(element => getComputedStyle(element).gridTemplateColumns.split(" ").filter(Boolean).length);
      expect(settingsColumns).toBe(viewport.width <= 430 ? 1 : 2);

      await page.goto("/?view=agent&theme=dark&long=1");
      await page.setViewportSize({ width: viewport.width, height: 500 });
      await expectNoDocumentOverflow(page);
      const composer = page.locator(".agent-composer");
      await expect(composer).toBeVisible();
      const composerBox = await composer.boundingBox();
      const mobileNavigationBox = viewport.width <= 700
        ? await page.getByRole("navigation", { name: "Mobile navigation" }).boundingBox()
        : null;
      const visibleBottom = mobileNavigationBox?.y ?? 500;
      expect(composerBox && composerBox.y >= 0 && composerBox.y + composerBox.height <= visibleBottom + 1).toBe(true);
      const textareaBox = await composer.getByRole("textbox", { name: "Ask your fragrance advisor" }).boundingBox();
      expect(textareaBox?.height).toBeGreaterThanOrEqual(44);
    });
  }
});
