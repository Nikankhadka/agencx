import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),

  // F-2: the frontend half of the deterministic boundary. The shared UI
  // library is presentational - a component that fetched its own data would
  // decide when a request happens from inside a render tree, and the page that
  // used it would have no say. Pages and route-local components own data; the
  // library takes props.
  //
  // This holds today (nothing under components/ui imports either module), so
  // the rule locks a property rather than announcing a migration.
  {
    files: ["src/components/ui/**/*.{ts,tsx}"],
    rules: {
      "no-restricted-imports": [
        "error",
        {
          paths: [
            {
              name: "@/lib/api",
              message:
                "components/ui is presentational. Fetch in the page or a route-local component and pass the result down.",
            },
            {
              name: "@/lib/useApiQuery",
              message:
                "components/ui is presentational. Query in the page or a route-local component and pass the result down.",
            },
          ],
        },
      ],
    },
  },
]);

export default eslintConfig;
