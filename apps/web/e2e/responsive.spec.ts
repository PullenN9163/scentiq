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
