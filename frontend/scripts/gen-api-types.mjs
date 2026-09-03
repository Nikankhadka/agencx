// Generate src/lib/api-types.ts from the backend's FastAPI OpenAPI schema, so
// the frontend's request/response types are derived from the backend contract
// instead of hand-redeclared per file (which silently drifts). No running
// server is needed - the schema is dumped straight from the app object.
//
// Regenerate with:  npm run gen:types
import { execFileSync } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";
import openapiTS, { astToString } from "openapi-typescript";

const schemaJson = execFileSync(
  "uv",
  [
    "run",
    "python",
    "-c",
    "import json,sys; from app.main import app; sys.stdout.write(json.dumps(app.openapi()))",
  ],
  { cwd: new URL("../../backend", import.meta.url), encoding: "utf8", maxBuffer: 16 * 1024 * 1024 },
);

const ast = await openapiTS(JSON.parse(schemaJson));
const header =
  "// AUTO-GENERATED from the backend OpenAPI schema by scripts/gen-api-types.mjs.\n" +
  "// Do not edit by hand; run `npm run gen:types` to refresh.\n\n";
const generated = header + astToString(ast);
const output = new URL("../src/lib/api-types.ts", import.meta.url);
if (process.argv.includes("--check")) {
  const current = readFileSync(output, "utf8");
  if (current !== generated) {
    console.error("api-types.ts is out of date; run npm run gen:types");
    process.exitCode = 1;
  } else {
    console.log("api-types.ts is up to date");
  }
} else {
  writeFileSync(output, generated);
  console.log("wrote src/lib/api-types.ts");
}
