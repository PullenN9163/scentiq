import {defineConfig} from "@playwright/test";
import path from "node:path";
const artifactRoot=process.env.SCENTIQ_VISUAL_ARTIFACTS ?? path.resolve(import.meta.dirname,"../../../artifacts/frontend-redesign/browser");
export default defineConfig({
  testDir:"./e2e",testMatch:"visual.spec.ts",workers:2,fullyParallel:true,
  outputDir:path.join(artifactRoot,"results"),
  snapshotPathTemplate:path.join(artifactRoot,"snapshots","{arg}{ext}"),
  reporter:"list",use:{baseURL:"http://127.0.0.1:3100",browserName:"chromium",trace:"retain-on-failure"},
  webServer:{command:"node e2e/fixtures/server.mjs",url:"http://127.0.0.1:3100",reuseExistingServer:!process.env.CI,timeout:60000},
});
