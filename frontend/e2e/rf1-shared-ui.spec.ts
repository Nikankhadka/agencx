/**
 * E2E for RF-1: the shared list-row grammar, always-visible keyboard focus,
 * focus restoration after a sheet or modal closes, and list scroll
 * restoration on return.
 *
 * Surface: tenant-admin (http://localhost:3000)
 *
 * The unit test (src/components/ui/ListRow.test.tsx) pins the slot order and
 * the element each row becomes. What only a browser can prove is here: that
 * the slots line up at both widths, that `:focus-visible` actually paints a
 * ring on real controls, that closing an overlay hands focus back to its
 * opener, and that an inner scroll container - which Next does not restore -
 * comes back where the owner left it.
 */

import { expect, test, type Page } from "@playwright/test";
import { DEMO_USERS, loginAsTenantAdmin } from "./auth-helpers";

const BYTEFIX = DEMO_USERS.find((u) => u.email === "owner@bytefix.dev")!;

function conversationRows(count: number) {
  return Array.from({ length: count }, (_, index) => ({
    id: `00000000-0000-4000-8000-${String(index + 1).padStart(12, "0")}`,
    // The attention row keeps the founder's real name, so the "not truncated
    // at 360px" assertion tests the exact case the compact badge fixes.
    customer_ref: index === 0 ? "morgan.chen" : `Customer ${index + 1}`,
    status: "open",
    created_at: "2026-01-01T00:00:00Z",
    message_count: 1,
    // The first row carries the attention pill and a long preview, so the
    // single-line truncation is tested under the same squeeze the phone sees.
    needs_attention: index === 0,
    last_message: `Message ${index + 1} with a deliberately long preview that would wrap onto several lines at phone width if the row did not truncate it to one`,
    // The attention row carries the long "Yesterday" stamp the founder's
    // morgan.chen row had, so the title squeeze is reproduced under the pill.
    last_activity_at:
      index === 0
        ? new Date(Date.now() - 25 * 60 * 60 * 1000).toISOString()
        : "2026-01-01T00:00:00Z",
  }));
}

async function focusInfo(page: Page) {
  return page.evaluate(() => {
    const element = document.activeElement as HTMLElement | null;
    if (!element) return null;
    const style = getComputedStyle(element);
    return {
      tag: element.tagName,
      label: (element.textContent ?? "").trim().slice(0, 40),
      ariaLabel: element.getAttribute("aria-label") ?? "",
      outlineStyle: style.outlineStyle,
      outlineWidth: style.outlineWidth,
    };
  });
}

test.describe("RF-1 shared row grammar", () => {
  test("a list row renders leading, title, meta and trailing slots at both widths", async ({
    page,
    request,
  }) => {
    await page.route("**/api/conversations", async (route) => {
      await route.fulfill({ json: conversationRows(3) });
    });
    await loginAsTenantAdmin(page, request, BYTEFIX);

    for (const width of [360, 1024]) {
      await page.setViewportSize({ width, height: 900 });
      await page.goto("/chats");

      const row = page.getByTestId("chat-row").first();
      await expect(row.locator('[data-slot="leading"]')).toBeVisible();
      await expect(row.locator('[data-slot="title"]')).toHaveText("morgan.chen");
      await expect(row.locator('[data-slot="meta"]')).toContainText("Message 1");
      await expect(row.locator('[data-slot="trailing"]')).toBeVisible();

      // The preview is exactly one line: the meta slot's box is no taller than
      // its line-height. A long preview that wrapped would be a multiple of it.
      const meta = await row.locator('[data-slot="meta"]').evaluate((element) => {
        const style = getComputedStyle(element);
        return { height: element.clientHeight, lineHeight: parseFloat(style.lineHeight) };
      });
      expect(meta.height, `meta is one line at ${width}px`).toBeLessThanOrEqual(
        meta.lineHeight + 1,
      );

      // The name is not needlessly squeezed by the trailing time + attention
      // badge: the founder's own `morgan.chen` fits without ellipsis at 360px.
      const title = await row.locator('[data-slot="title"]').evaluate((element) => ({
        scrollWidth: element.scrollWidth,
        clientWidth: element.clientWidth,
      }));
      expect(title.scrollWidth, `title not squeezed at ${width}px`).toBeLessThanOrEqual(
        title.clientWidth + 1,
      );

      const boxes = await row.evaluate((element) => {
        const pick = (slot: string) => {
          const node = element.querySelector<HTMLElement>(`[data-slot="${slot}"]`)!;
          const rect = node.getBoundingClientRect();
          return { left: rect.left, right: rect.right, top: rect.top };
        };
        return {
          leading: pick("leading"),
          title: pick("title"),
          meta: pick("meta"),
          trailing: pick("trailing"),
        };
      });
      expect(boxes.leading.right, `leading at ${width}px`).toBeLessThanOrEqual(boxes.title.left + 1);
      expect(boxes.trailing.left, `trailing at ${width}px`).toBeGreaterThanOrEqual(
        boxes.title.right - 1,
      );
      expect(boxes.meta.top, `meta under title at ${width}px`).toBeGreaterThan(boxes.title.top);

      // The attention indicator is a compact labelled icon badge, not a text
      // pill; the words "Action needed" are not rendered in the row at all.
      const badge = row.getByTestId("row-attention");
      await expect(badge).toBeVisible();
      await expect(badge).toHaveAttribute("aria-label", "Action needed");
      await expect(row).not.toContainText("Action needed");
    }
  });

  test("keyboard focus always shows a visible ring", async ({ page, request }) => {
    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/business");

    for (let index = 0; index < 5; index++) {
      await page.keyboard.press("Tab");
      const info = await focusInfo(page);
      expect(info, `tab ${index}`).not.toBeNull();
      expect(info!.tag, `tab ${index} landed on the body`).not.toBe("BODY");
      expect(info!.outlineStyle, `tab ${index}: ${info!.tag} ${info!.label}`).toBe("solid");
      expect(info!.outlineWidth, `tab ${index}: ${info!.tag} ${info!.label}`).not.toBe("0px");
    }
  });

  test("closing a sheet returns focus to the row that opened it", async ({ page, request }) => {
    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/business/details");

    await page.getByRole("button", { name: /ABN & Tax/ }).click();
    await expect(page.getByTestId("abn-input")).toBeVisible();

    await page.keyboard.press("Escape");
    // The sheet never unmounts, so "closed" is its body going away.
    await expect(page.getByTestId("abn-input")).toHaveCount(0);
    await expect
      .poll(async () => (await focusInfo(page))?.label ?? "")
      .toContain("ABN & Tax");
  });

  test("closing a modal returns focus to the control that opened it", async ({ page, request }) => {
    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/business/offerings");
    await expect(
      page.getByTestId("offerings-list").or(page.getByText("Nothing added yet.")),
    ).toBeVisible();

    // The ConfirmDialog's opener stays mounted, so "the control that opened
    // it" is still a real node to return to.
    const opener = page.getByTestId("offering-remove").first();
    await expect(opener).toHaveAttribute("aria-label", /^Remove /);
    await opener.click();
    await expect(page.getByTestId("confirm-accept")).toBeVisible();

    await page.keyboard.press("Escape");
    await expect(page.getByTestId("confirm-accept")).toHaveCount(0);
    await expect.poll(async () => (await focusInfo(page))?.ariaLabel ?? "").toMatch(/^Remove /);
  });

  test("returning to a list restores its scroll position", async ({ page, request }) => {
    await page.route("**/api/conversations", async (route) => {
      await route.fulfill({ json: conversationRows(40) });
    });
    await page.route("**/api/conversations/**", async (route) => {
      await route.fulfill({
        json: {
          id: "00000000-0000-4000-8000-000000000001",
          customer_ref: "Customer 1",
          status: "open",
          messages: [],
        },
      });
    });
    await loginAsTenantAdmin(page, request, BYTEFIX);
    await page.goto("/chats");

    const list = page.getByTestId("chats-list");
    await expect(page.getByTestId("chat-row")).toHaveCount(40);
    await list.evaluate((element) => {
      element.scrollTop = 700;
    });
    await expect.poll(() => list.evaluate((element) => element.scrollTop)).toBeGreaterThan(500);

    await page.getByTestId("chat-row").nth(10).click();
    await page.waitForURL(/\/chats\/[0-9a-f-]{36}$/);
    await page.goBack();

    await expect(page.getByTestId("chats-list")).toBeVisible();
    await expect.poll(() => list.evaluate((element) => element.scrollTop)).toBeGreaterThan(500);
  });
});
