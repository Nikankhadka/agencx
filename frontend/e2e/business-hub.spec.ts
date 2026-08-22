/**
 * E2E for the Business hub and its Booking page (E-5 / D21).
 *
 * Surface: tenant-admin (http://app.localhost:3000)
 *
 * The hub's shape is the thing under test as much as its contents: Stage 2
 * grows it by adding rows, so "exactly the rows that open onto something" is
 * the invariant worth pinning (PRD, "never build dead surfaces").
 */

import { test, expect } from "@playwright/test";
import jsQR from "jsqr";
import { DEMO_USERS, loginAsTenantAdmin, tenantAdminHost } from "./auth-helpers";

const BYTEFIX = DEMO_USERS.find((u) => u.email === "owner@bytefix.dev")!;
const STAGE_2_ROWS = ["Schedule", "Money", "Plan"];

test.describe("Business hub", () => {
  test.use({ baseURL: `http://${tenantAdminHost()}` });

  test("holds only rows that open onto something", async ({ page, request }) => {
    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/business");

    const rows = page.getByRole("main").getByRole("link");
    await expect(rows).toHaveText([
      "Booking pageWhat customers see, and the link to it",
      "SettingsWhat your customers are told",
    ]);

    // Absent, not disabled - the prototype carries them, Stage 1 does not.
    for (const label of STAGE_2_ROWS) {
      await expect(page.getByText(label, { exact: true })).toHaveCount(0);
    }
  });

  test("the booking page shows the business and its public link", async ({ page, request }) => {
    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/business");
    await page.getByRole("link", { name: /Booking page/ }).click();
    await page.waitForURL("**/business/booking");

    await expect(page.getByRole("heading", { level: 2 })).toContainText("Bytefix");

    // Derived from the current host, so it is the address that actually works
    // from this browser - never a hardcoded domain.
    const link = page.getByTestId("booking-link");
    await expect(link).toContainText("bytefix.");
    await expect(link).not.toContainText("http");
    await expect(link).not.toContainText(/\/$/);
  });

  test("copying puts the full URL, scheme and all, on the clipboard", async ({
    page,
    request,
    context,
  }) => {
    await context.grantPermissions(["clipboard-read", "clipboard-write"]);
    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/business/booking");

    await page.getByTestId("booking-copy").click();
    await expect(page.getByTestId("booking-copy")).toContainText("Copied");

    const copied = await page.evaluate(() => navigator.clipboard.readText());
    // The pill hides the scheme; what a customer needs is the whole thing.
    expect(copied).toMatch(/^https?:\/\/bytefix\./);
    expect(copied.endsWith("/")).toBe(false);
  });

  test("the QR decodes to the same link the copy button gives", async ({ page, request }) => {
    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/business/booking");

    const qr = page.getByTestId("booking-qr");
    await expect(qr).toBeVisible();

    // A real decode, not a "it looks like a QR" check. The SVG is rasterised
    // in the page, then the pixels are decoded here in Node with jsQR. It
    // used to scan with Chromium's BarcodeDetector, but that API is absent
    // from Playwright's desktop Chromium builds (flag-gated upstream), so the
    // assertion could never run in CI or a fresh checkout. This is still the
    // assertion that catches an orientation slip in the SVG we build from the
    // module matrix - a transposed code still renders as a plausible-looking
    // QR and simply does not scan.
    const raster = await page.evaluate(async () => {
      const svg = document.querySelector("[data-testid='booking-qr']")!;
      const markup = new XMLSerializer().serializeToString(svg);

      // Rasterise through an <img> data URL: Chromium's createImageBitmap does
      // not accept SVG blobs. Drawn at 4x so every module is several pixels -
      // the detector wants pixels, not vectors.
      const SIZE = 528;
      const img = new Image(SIZE, SIZE);
      img.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(markup)}`;
      await img.decode();

      const canvas = document.createElement("canvas");
      canvas.width = SIZE;
      canvas.height = SIZE;
      const ctx = canvas.getContext("2d")!;
      // QR contrast needs an opaque light ground; the SVG itself is
      // transparent so it can sit on any themed surface.
      ctx.fillStyle = "#fff";
      ctx.fillRect(0, 0, SIZE, SIZE);
      ctx.drawImage(img, 0, 0, SIZE, SIZE);

      const { data, width, height } = ctx.getImageData(0, 0, SIZE, SIZE);
      return { data: Array.from(data), width, height };
    });

    const found = jsQR(new Uint8ClampedArray(raster.data), raster.width, raster.height);
    const decoded = found?.data ?? null;

    expect(decoded).toMatch(/^https?:\/\/bytefix\./);
    expect(decoded).toBe(await page.getByTestId("booking-link").textContent().then((t) => `http://${t}`));
  });

  test("back from the booking page returns to the hub", async ({ page, request }) => {
    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/business/booking");
    await page.getByRole("button", { name: "Back" }).click();
    await page.waitForURL("**/business");
  });
});
