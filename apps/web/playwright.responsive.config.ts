import { defineConfig, devices } from "@playwright/test";
import path from "node:path";

const artifactRoot = process.env.SCENTIQ_VISUAL_ARTIFACTS
  ?? path.resolve(import.meta.dirname, "../../../artifacts/responsive-apple-devices");

export default defineConfig({
  testDir: "./e2e",
  testMatch: "responsive.spec.ts",
  fullyParallel: true,
  workers: 2,
  outputDir: path.join(artifactRoot, "results"),
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:3100",
    trace: "retain-on-failure",
  },
  webServer: {
    command: "node e2e/fixtures/server.mjs",
    url: "http://127.0.0.1:3100",
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"], hasTouch: true } },
    { name: "webkit", use: { ...devices["Desktop Safari"], hasTouch: true } },
  ],
});
