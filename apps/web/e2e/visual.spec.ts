import {expect,test} from "@playwright/test";

const widths=[{name:"mobile",width:375,height:812},{name:"tablet",width:820,height:1180},{name:"desktop",width:1440,height:1000}];
const views=["landing","sign-in","sign-up","today","week","collection","detail","discover","discover-error","insights","layering","agent","settings","states"];
for(const theme of ["light","dark"] as const) for(const viewport of widths) {
  test(`${theme} ${viewport.name}: product surfaces remain readable and contained`, async ({page}) => {
    test.setTimeout(120000);
    await page.setViewportSize(viewport);
    await page.emulateMedia({reducedMotion:"reduce"});
    await page.clock.install({time:new Date("2026-10-13T16:00:00Z")});
    for(const view of views) {
      await page.goto(`/?view=${view}&theme=${theme}`);
      await expect(page.locator("h1")).toBeVisible();
      await expect(page.locator("html")).toHaveAttribute("data-theme",theme);
      expect(await page.evaluate(()=>document.documentElement.scrollWidth <= innerWidth+1), `${view} must not overflow`).toBe(true);
      await expect(page).toHaveScreenshot(`${view}-${theme}-${viewport.name}.png`,{fullPage:true,animations:"disabled",maxDiffPixelRatio:.005});
    }
  });
}
test("recommendation layout, contrast, keyboard dialog and spray controls", async ({page}) => {
  for(const theme of ["light","dark"]) {
    await page.goto(`/?view=today&theme=${theme}&long=1`);
    const card=page.getByTestId("recommendation-card");
    await expect(card.getByRole("heading")).toContainText("An exceptionally long");
    const sizes=await card.locator(".recommendation-main").evaluate(element=>({content:element.clientWidth,text:element.children[1].clientWidth}));
    expect(sizes.text).toBeGreaterThan(sizes.content*.4);
    const contrast=await card.evaluate(element=>{
      const rgb=(value:string)=>value.match(/[\d.]+/g)!.slice(0,3).map(Number);
      const luminance=(color:number[])=>color.map(value=>{const channel=value/255;return channel<=.04045?channel/12.92:((channel+.055)/1.055)**2.4;}).reduce((sum,channel,index)=>sum+channel*[.2126,.7152,.0722][index],0);
      return Array.from(element.querySelectorAll("h2,.badge,.recommendation-main li,.button")).map(node=>{
        const style=getComputedStyle(node);let ancestor:Element|null=node;
        while(ancestor && getComputedStyle(ancestor).backgroundColor==="rgba(0, 0, 0, 0)") ancestor=ancestor.parentElement;
        const foreground=luminance(rgb(style.color));const background=luminance(rgb(getComputedStyle(ancestor??document.body).backgroundColor));
        return (Math.max(foreground,background)+.05)/(Math.min(foreground,background)+.05);
      });
    });
    expect(Math.min(...contrast)).toBeGreaterThanOrEqual(4.5);
    const wear=card.getByRole("button",{name:"Wear This"});
    await wear.focus();await page.keyboard.press("Enter");
    const dialog=page.getByRole("dialog");await expect(dialog).toBeVisible();
    const slider=dialog.getByRole("slider",{name:"Sprays slider"});
    await slider.focus();await page.keyboard.press("ArrowRight");
    await expect(dialog.getByRole("spinbutton",{name:"Sprays",exact:true})).toHaveValue("4");
    await page.keyboard.press("Tab");
    expect(await dialog.evaluate(element=>element.contains(document.activeElement))).toBe(true);
    await page.keyboard.press("Escape");await expect(dialog).not.toBeVisible();await expect(wear).toBeFocused();
  }
});
test("theme persists, respects system changes, and reduced motion stops ambient movement", async ({page}) => {
  await page.goto("/?view=settings&theme=light");
  await page.getByRole("radio",{name:"Dark",exact:true}).check();
  // Remove the fixture initializer to verify the persisted cookie.
  await page.goto("/?view=settings");await expect(page.locator("html")).toHaveAttribute("data-theme","dark");
  await page.reload();await expect(page.locator("html")).toHaveAttribute("data-theme","dark");
  await page.getByRole("radio",{name:"System",exact:true}).check();
  await page.emulateMedia({colorScheme:"dark",reducedMotion:"reduce"});
  await expect(page.locator("html")).toHaveAttribute("data-theme","dark");
  await page.emulateMedia({colorScheme:"light"});await expect(page.locator("html")).toHaveAttribute("data-theme","light");
  expect(await page.evaluate(()=>getComputedStyle(document.body,"::before").animationName)).toBe("none");
});
test("pagination failure preserves results and catalog search remains usable", async ({page}) => {
  await page.goto("/?view=catalog&theme=light");
  await expect(page.getByTestId("catalog-result-card")).toHaveCount(25);
  await page.getByRole("button",{name:"Load more",exact:true}).click();
  await expect(page.getByRole("alert")).toContainText("Could not load more");
  await expect(page.getByTestId("catalog-result-card")).toHaveCount(25);
  await expect(page.getByRole("button",{name:"Load more",exact:true})).toBeEnabled();
});
test("mobile navigation exposes all destinations and zoomed layouts reflow", async ({page}) => {
  await page.setViewportSize({width:375,height:812});await page.goto("/?view=today&theme=dark");
  await page.getByRole("button",{name:"More destinations",exact:true}).click();
  const dialog=page.getByRole("dialog");await expect(dialog).toBeVisible();
  for(const name of ["Layering Lab","Insights","Agent","Settings"]) await expect(dialog.getByRole("link",{name,exact:true})).toBeVisible();
  await page.keyboard.press("Escape");
  // 720 CSS pixels represent a 1440px viewport at 200% browser zoom.
  await page.setViewportSize({width:720,height:500});await page.goto("/?view=today&theme=light&long=1");
  expect(await page.evaluate(()=>document.documentElement.scrollWidth <= innerWidth+1)).toBe(true);
  await expect(page.getByRole("button",{name:"Wear This"})).toBeVisible();
});
test("long names and failed bottle images stay contained on mobile",async({page})=>{
  await page.setViewportSize({width:375,height:812});
  for(const theme of ["light","dark"]) {
    await page.goto(`/?view=today&theme=${theme}&long=1&broken=1`);
    await expect(page.getByTestId("recommendation-card").getByTestId("catalog-image-fallback")).toBeVisible();
    expect(await page.evaluate(()=>document.documentElement.scrollWidth <= innerWidth+1)).toBe(true);
  }
});
test("failed saves preserve slider and numeric input values",async({page})=>{
  await page.goto("/?view=settings&theme=dark");
  const value=page.getByRole("spinbutton",{name:"Maximum sprays",exact:true});
  await value.fill("7");await page.getByRole("button",{name:"Save preferences",exact:true}).click();
  await expect(page.getByRole("alert")).toContainText("Fixture save failed");
  await expect(value).toHaveValue("7");
  await expect(page.getByRole("slider",{name:"Maximum sprays slider"})).toHaveValue("7");
});

test("expressive workspaces preserve controls and respect reduced motion", async ({page}) => {
  for (const theme of ["light", "dark"]) {
    await page.emulateMedia({reducedMotion:"reduce"});
    await page.goto(`/?view=discover&theme=${theme}`);
    await expect(page.getByRole("link", {name:"Explore something new", exact:true})).toHaveAttribute("href", "/discover?mode=explore&family=Woody&gender=unisex&minimum_value=4");
    await page.getByRole("button", {name:"Compact view"}).click();
    await expect(page.getByRole("button", {name:"Compact view"})).toHaveAttribute("aria-pressed","true");
    await page.getByLabel("Family", {exact:true}).fill("Amber");
    await page.getByRole("button", {name:"More filters"}).click();
    await expect(page.getByLabel("Family", {exact:true})).not.toBeVisible();
    await page.getByRole("button", {name:"More filters"}).click();
    await expect(page.getByLabel("Family", {exact:true})).toHaveValue("Amber");
    await page.goto(`/?view=insights&theme=${theme}`);
    const fresh=page.getByRole("button", {name:"Inspect Fresh accord"});
    await fresh.focus(); await page.keyboard.press("Enter");
    await expect(page.getByTestId("selected-profile")).toContainText("Fresh");
    await expect(page.getByTestId("selected-profile")).toContainText("25%");
    const seasonWidth = await page.getByRole("progressbar", {name:"Spring coverage"}).evaluate(element=>element.getBoundingClientRect().width);
    expect(seasonWidth).toBeGreaterThan(40);
    await page.goto(`/?view=layering&theme=${theme}`);
    await page.getByRole("region",{name:"Fragrance composition"}).getByRole("button",{name:"Refine this blend"}).click();
    await expect(page.getByRole("region",{name:"Stack builder"})).toBeVisible();
    const animations=await page.locator(".experience-page").evaluate(element=>Array.from(element.querySelectorAll("*")).map(node=>getComputedStyle(node).animationName));
    expect(animations.every(name=>name==="none")).toBe(true);
  }
  await page.emulateMedia({reducedMotion:"no-preference"});
  await page.goto("/?view=layering&theme=dark");
  expect(await page.locator(".experience-backdrop i").first().evaluate(element=>getComputedStyle(element).animationName)).not.toBe("none");
});

test("redesigned workspaces contain long names and missing images at 200% reflow", async ({page}) => {
  await page.emulateMedia({reducedMotion:"reduce"});
  for (const width of [375,720]) {
    await page.setViewportSize({width,height:900});
    for (const theme of ["light","dark"]) for (const view of ["discover","layering","insights"]) {
      await page.goto(`/?view=${view}&theme=${theme}&long=1&broken=1`);
      expect(await page.evaluate(()=>document.documentElement.scrollWidth <= innerWidth+1),`${view} ${theme} ${width}`).toBe(true);
      await expect(page.locator("h1")).toBeVisible();
    }
  }
});
