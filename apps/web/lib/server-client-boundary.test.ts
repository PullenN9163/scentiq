import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * A module marked "use client" exports client references. A server component may render a
 * client *component* (an uppercase export), but calling any other export, such as a helper
 * function, fails at request time with "Attempted to call X() from the server". Unit tests
 * and the fixture server cannot see that, so this walks every module reachable from the app
 * routes without crossing a client boundary and rejects imports of lowercase client exports.
 */

const root = resolve(__dirname, "..");
const ROUTE_FILE = /^(page|layout|loading|template|default|not-found|route)\.(tsx|ts)$/;
const EXTENSIONS = [".tsx", ".ts", "/index.tsx", "/index.ts"];

function walk(directory: string, found: string[] = []): string[] {
  for (const name of readdirSync(directory)) {
    if (name === "node_modules" || name.startsWith(".")) continue;
    const path = join(directory, name);
    if (statSync(path).isDirectory()) walk(path, found);
    else found.push(path);
  }
  return found;
}

function isClient(source: string): boolean {
  const head = source.replace(/^(\s|\/\/[^\n]*\n|\/\*[\s\S]*?\*\/)*/, "");
  return /^["']use client["']/.test(head);
}

function resolveImport(from: string, specifier: string): string | null {
  const base = specifier.startsWith("@/") ? join(root, specifier.slice(2)) : specifier.startsWith(".") ? resolve(dirname(from), specifier) : null;
  if (!base) return null;
  if (existsSync(base) && statSync(base).isFile()) return base;
  for (const extension of EXTENSIONS) if (existsSync(base + extension)) return base + extension;
  return null;
}

const IMPORT = /import\s+(?!type\s)([^;'"]*?)\s+from\s+["']([^"']+)["']/g;

function namedValueImports(clause: string): string[] {
  const names: string[] = [];
  const braces = clause.match(/\{([^}]*)\}/);
  if (braces) {
    for (const part of braces[1].split(",")) {
      const entry = part.trim();
      if (!entry || entry.startsWith("type ")) continue;
      names.push(entry.split(/\s+as\s+/)[0].trim());
    }
  }
  return names;
}

describe("server and client module boundary", () => {
  it("never calls a client module's non-component export from a server module", () => {
    const cache = new Map<string, string>();
    const read = (path: string) => cache.get(path) ?? (cache.set(path, readFileSync(path, "utf8")), cache.get(path) as string);
    const entries = walk(join(root, "app")).filter((path) => ROUTE_FILE.test(path.split(/[\\/]/).pop() ?? ""));
    const visited = new Set<string>();
    const violations: string[] = [];
    const queue = entries.filter((path) => !isClient(read(path)));
    while (queue.length) {
      const file = queue.pop() as string;
      if (visited.has(file)) continue;
      visited.add(file);
      const source = read(file);
      for (const match of source.matchAll(IMPORT)) {
        const target = resolveImport(file, match[2]);
        if (!target || !/\.(tsx|ts)$/.test(target)) continue;
        const targetSource = read(target);
        if (isClient(targetSource)) {
          for (const name of namedValueImports(match[1])) {
            if (/^[a-z]/.test(name)) violations.push(`${file.replace(root, "")} imports "${name}" from client module ${target.replace(root, "")}`);
          }
        } else {
          queue.push(target);
        }
      }
    }
    expect(violations).toEqual([]);
  });
});
