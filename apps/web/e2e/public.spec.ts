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
test("appearance initializes in server HTML and persists through hydration and navigation",async({page,context})=>{
  const errors:string[]=[];page.on("pageerror",error=>errors.push(error.message));
  await page.emulateMedia({colorScheme:"light"});
  const base=process.env.E2E_BASE_URL??"http://127.0.0.1:3000";
  await context.addCookies([{name:"scentiq-theme",value:"dark",url:base}]);
  await page.goto("/");
  await expect(page.locator("html")).toHaveAttribute("data-theme","dark");
  expect((await page.locator("script").allTextContents()).some(script=>script.startsWith("(function(){try{var m=document.cookie"))).toBe(true);
  await page.getByRole("combobox",{name:"Appearance"}).selectOption("light");
  await page.reload();await expect(page.locator("html")).toHaveAttribute("data-theme","light");
  expect(errors).toEqual([]);
});
