import { expect, test } from "@playwright/test";
import { DEMO_USERS, loginAsTenantAdmin } from "./auth-helpers";

const ABN = "51 824 753 556";

/**
 * O-9 Settings > ABN & Tax: the interview asks for an ABN, so the owner can
 * read it back and fix it. The summary line is the assertion that matters -
 * before this ticket the field was captured and rendered nowhere.
 */
test("the ABN row reads back what is saved, and edits it", async ({
  page,
  request,
}) => {
  await loginAsTenantAdmin(page, request, DEMO_USERS[0]);

  // Relative, like every other spec: since D22 there is one origin, so the
  // session the login helper established is simply still here.
  await page.goto("/business/details");
  const row = page.getByRole("button", { name: /ABN & Tax/ });
  await row.click();

  const sheet = page.getByRole("dialog", { name: "Edit ABN & Tax" });
  await expect(sheet).toBeVisible();

  // Typed as digits, grouped as the prototype groups them.
  await page.getByTestId("abn-input").fill("51824753556");
  await expect(page.getByTestId("abn-input")).toHaveValue(ABN);
  await page.getByTestId("gst-yes").click();
  await page.getByTestId("abn-save").click();

  // The sheet stays mounted (it animates), so "closed" is its editor going
  // away - that is what unmounts when `open` turns false.
  await expect(page.getByTestId("abn-input")).toHaveCount(0, { timeout: 15_000 });
  await expect(row).toContainText(`${ABN} · GST registered`);

  // The correction survives a reload - it is saved, not just on screen.
  await page.reload();
  await expect(page.getByRole("button", { name: /ABN & Tax/ })).toContainText(
    `${ABN} · GST registered`,
  );

  // And the GST half is the owner's to change.
  await page.getByRole("button", { name: /ABN & Tax/ }).click();
  await page.getByTestId("gst-no").click();
  await page.getByTestId("abn-save").click();
  await expect(page.getByRole("button", { name: /ABN & Tax/ })).toContainText(
    `${ABN} · Not GST registered`,
  );
});

test("an ABN that is not eleven digits is refused, in the owner's words", async ({
  page,
  request,
}) => {
  await loginAsTenantAdmin(page, request, DEMO_USERS[0]);
  await page.goto("/business/details");
  await page.getByRole("button", { name: /ABN & Tax/ }).click();

  await page.getByTestId("abn-input").fill("5182475");
  await page.getByTestId("abn-save").click();

  // Scoped to the sheet: Next mounts its own empty role="alert" announcer.
  const sheet = page.getByRole("dialog", { name: "Edit ABN & Tax" });
  await expect(sheet.getByRole("alert")).toHaveText("An ABN is 11 digits.");
  await expect(sheet).toBeVisible();
});
