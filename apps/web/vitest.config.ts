import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": import.meta.dirname,
      // Next supplies this server-only marker internally. Unit tests exercise
      // server modules in Node without Next's module graph.
      "server-only": `${import.meta.dirname}/node_modules/next/dist/compiled/server-only/empty.js`,
    },
  },
  test: {
    environment: "jsdom",
    exclude: ["e2e/**", "node_modules/**", ".next/**"],
    setupFiles: ["./vitest.setup.ts"],
  },
});
