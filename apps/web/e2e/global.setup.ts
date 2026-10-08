import { clerk, clerkSetup } from "@clerk/testing/playwright";
import { expect, test as setup } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const authFile = path.join(path.dirname(fileURLToPath(import.meta.url)), "../playwright/.clerk/user.json");
const email = process.env.E2E_CLERK_EMAIL;

setup.describe.configure({ mode: "serial" });

setup("configure Clerk testing", async () => {
  await clerkSetup();
});

setup("authenticate the deployment test user", async ({ page }) => {
  if (!email) throw new Error("E2E_CLERK_EMAIL is required for authenticated browser checks");

  await page.goto("/");
  await clerk.signIn({ page, emailAddress: email });
  await page.goto("/dashboard");
  await expect(page.getByRole("button", { name: "Open user menu" })).toBeVisible();
  await page.context().storageState({ path: authFile });
});
