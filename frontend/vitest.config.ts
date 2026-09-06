import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

export default defineConfig({
  // Mirror tsconfig's `@/*` path alias. Without it a unit test can only import
  // from modules that happen to use relative paths, which quietly decided which
  // components were testable.
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  test: {
    exclude: ["e2e/**", "node_modules/**"],
  },
});
