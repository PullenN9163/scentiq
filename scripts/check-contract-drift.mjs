#!/usr/bin/env node
/**
 * Fails when the committed API contract no longer matches the FastAPI app.
 *
 * Regenerating in CI and comparing is what stops the web app's typed client
 * drifting away from the service it calls. Run `pnpm contracts` to refresh.
 */

import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const repositoryRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const committedOpenApiPath = resolve(repositoryRoot, "apps/api/openapi.json");
const committedTypesPath = resolve(repositoryRoot, "apps/web/types/api.generated.ts");

function fail(message, detail) {
  process.stderr.write(`\n${message}\n`);
  if (detail) {
    process.stderr.write(`${detail}\n`);
  }
  process.stderr.write("\nRun `pnpm contracts` and commit the result.\n");
  process.exit(1);
}

function read(path, label) {
  try {
    return readFileSync(path, "utf8");
  } catch {
    fail(`${label} is missing at ${path}.`);
  }
}

function regenerateOpenApi() {
  try {
    return execFileSync(
      "uv",
      ["run", "--directory", "apps/api", "python", "-m", "scentiq_api.export_openapi"],
      { cwd: repositoryRoot, encoding: "utf8", maxBuffer: 64 * 1024 * 1024 },
    );
  } catch (error) {
    fail("Could not regenerate the OpenAPI document.", error.stderr || error.message);
  }
}

function openapiTypescriptCli() {
  // openapi-typescript is a dependency of apps/web, not the workspace root,
  // and pnpm keeps package trees isolated. Resolve its package.json from there
  // and read its own `bin` entry rather than guessing the file name.
  const requireFromWeb = createRequire(resolve(repositoryRoot, "apps/web/package.json"));
  let manifestPath;
  try {
    manifestPath = requireFromWeb.resolve("openapi-typescript/package.json");
  } catch {
    fail("openapi-typescript is not installed. Run `pnpm install`.");
  }
  const manifest = JSON.parse(readFileSync(manifestPath, "utf8"));
  const binEntry =
    typeof manifest.bin === "string" ? manifest.bin : manifest.bin["openapi-typescript"];
  return resolve(dirname(manifestPath), binEntry);
}

function regenerateTypes() {
  const openapiTypescript = openapiTypescriptCli();
  try {
    return execFileSync(
      process.execPath,
      [openapiTypescript, committedOpenApiPath],
      { cwd: repositoryRoot, encoding: "utf8", maxBuffer: 64 * 1024 * 1024 },
    );
  } catch (error) {
    fail("Could not regenerate the TypeScript contracts.", error.stderr || error.message);
  }
}

// Compare parsed JSON so incidental whitespace is not reported as drift.
const committedOpenApi = read(committedOpenApiPath, "The committed OpenAPI document");
const freshOpenApi = regenerateOpenApi();
if (JSON.stringify(JSON.parse(committedOpenApi)) !== JSON.stringify(JSON.parse(freshOpenApi))) {
  fail("apps/api/openapi.json is out of date with the FastAPI application.");
}

const committedTypes = read(committedTypesPath, "The generated TypeScript contracts");
const freshTypes = regenerateTypes();
if (committedTypes.trim() !== freshTypes.trim()) {
  fail("apps/web/types/api.generated.ts is out of date with apps/api/openapi.json.");
}

process.stdout.write("API contracts are in sync.\n");
