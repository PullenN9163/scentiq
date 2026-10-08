import { defineConfig, devices } from "@playwright/test";

const hasClerkTestIdentity = Boolean(
  process.env.E2E_CLERK_EMAIL &&
  process.env.CLERK_PUBLISHABLE_KEY &&
  process.env.CLERK_SECRET_KEY,
);

const browserProject = {
  name: "chromium",
  testIgnore: /global\.setup\.ts/,
  use: {
    ...devices["Desktop Chrome"],
    ...(hasClerkTestIdentity
      ? { storageState: "playwright/.clerk/user.json" }
      : {}),
  },
  ...(hasClerkTestIdentity ? { dependencies: ["setup"] } : {}),
};

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: !process.env.E2E_BASE_URL,
  workers: process.env.E2E_BASE_URL ? 1 : undefined,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: process.env.E2E_BASE_URL || "http://127.0.0.1:3000",
    trace: "retain-on-failure",
  },
  webServer: process.env.E2E_BASE_URL ? undefined : {
    command: "pnpm dev --hostname 127.0.0.1",
    url: "http://127.0.0.1:3000",
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
  projects: hasClerkTestIdentity
    ? [
        {
          name: "setup",
          testMatch: /global\.setup\.ts/,
          use: { ...devices["Desktop Chrome"] },
        },
        browserProject,
      ]
    : [browserProject],
});
