import { readdirSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * A tenant is served at `/{slug}` (D22), so any top-level route the app adds
 * takes that name out of the slug namespace. Next resolves static segments
 * before the dynamic one, so a tenant whose slug collides with a route is not
 * ambiguous - it is simply unreachable, silently, forever.
 *
 * This test is the tripwire: add a route directory without reserving its name
 * and it fails here, at the moment the route is added, rather than the day a
 * business signs up under that name.
 *
 * ponytail: the list below is a hand-kept mirror of RESERVED_SLUGS in
 * backend/app/features/tenants/slug.py - two languages, no shared file. The
 * ceiling is that the two can drift between this test running and the
 * backend's; the upgrade path, if that ever actually happens, is a checked-in
 * reserved-slugs.json that both read.
 */
const RESERVED_SLUGS = new Set([
  "admin",
  "api",
  "business",
  "chats",
  "conversations",
  "dashboards",
  "escalations",
  "home",
  "knowledge",
  "login",
  "onboarding",
  "pricing",
  "settings",
  "signup",
  "www",
]);

/** Top-level URL segments the app serves, flattening route groups. */
function topLevelRoutes(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .flatMap((entry) => {
      const name = entry.name;
      // Route groups do not segment URLs - their children are top-level.
      if (name.startsWith("(") && name.endsWith(")")) {
        return topLevelRoutes(join(dir, name));
      }
      // The dynamic segment is the tenant itself; private/internal folders
      // (`_foo`) are unroutable and the slug pattern rejects them anyway.
      if (name.startsWith("[") || name.startsWith("_")) return [];
      return [name];
    });
}

describe("reserved slugs", () => {
  it("covers every top-level route the app serves", () => {
    const routes = topLevelRoutes(join(import.meta.dirname, "..", "app"));
    expect(routes.length).toBeGreaterThan(0);
    const unreserved = routes.filter((route) => !RESERVED_SLUGS.has(route));
    expect(
      unreserved,
      `Route(s) ${unreserved.join(", ")} would shadow a tenant of the same name. ` +
        `Add them to RESERVED_SLUGS in backend/app/features/tenants/slug.py and to this test.`,
    ).toEqual([]);
  });
});
