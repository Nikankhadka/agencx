import { expect, test } from "@playwright/test";
import { DEMO_USERS, loginAsTenantAdmin } from "./auth-helpers";

/**
 * Regression for the 401 "missing bearer token" on the onboarding chat's
 * first message (T-042 / onboarding stream): the stream POST must carry the
 * Supabase session token, and a reply must stream in as SSE.
 */
test("onboarding first message streams a reply", async ({ page, request }) => {
  const nameInput = {
    kind: "text",
    placeholder: "What name would you like me to use?",
    chips: [],
    mask: null,
    cta_label: null,
    prefix: null,
    suggest_owner_email: false,
  };
  await page.route("**/api/onboarding/state", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        stage: "name",
        prompt: "Hi! I'm your Agencx setup assistant. What's your name?",
        draft: {},
        completed: false,
        history: [],
        input: nameInput,
        can_confirm: false,
        suggested_slug: null,
      }),
    }),
  );
  await page.route("**/api/onboarding/message/stream", (route) => {
    expect(route.request().headers().authorization).toMatch(/^Bearer \S+$/);
    return route.fulfill({
      contentType: "text/event-stream",
      body: [
        'data: {"type":"progress","stage":"processing"}',
        'data: {"type":"token","text":"Thanks. What does the business go by?"}',
        'data: {"type":"reply","text":"Thanks. What does the business go by?"}',
        `data: ${JSON.stringify({
          type: "state",
          stage: "business_name",
          draft: { name: "I run a phone repair shop." },
          completed: false,
          input: { ...nameInput, placeholder: "What does the business go by?" },
          can_confirm: false,
          suggested_slug: null,
        })}`,
        'data: {"type":"done"}',
        "",
      ].join("\n\n"),
    });
  });
  await loginAsTenantAdmin(page, request, DEMO_USERS[0]);

  // The onboarding thread IS the screen: no heading, and no console chrome
  // (agencx-prototype-v6.html shows no navigation until the business is live).
  await expect(
    page.getByRole("log", { name: "Onboarding conversation" }),
  ).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Console" })).toHaveCount(
    0,
  );
  await expect(page.getByRole("heading", { name: "Onboarding" })).toHaveCount(
    0,
  );

  const thread = page.getByTestId("onboarding-thread");
  await expect(thread).toContainText(/\S/);

  const composer = page.getByTestId("onboarding-composer");
  await composer.getByRole("textbox").fill("I run a phone repair shop.");
  await composer.getByRole("button", { name: "Send" }).click();

  // The customer message echoes into the thread...
  await expect(
    thread.getByText("I run a phone repair shop.", { exact: true }),
  ).toBeVisible();

  // ...and the stream resolves without an error line (a 401 surfaces there).
  await expect(page.getByTestId("onboarding-error")).toHaveCount(0);
});

test("team selection and the next question stay on the same server beat", async ({
  page,
  request,
}) => {
  const headcountInput = {
    kind: "text",
    placeholder: "or type…",
    chips: [
      { label: "Just me", value: "just me", dashed: false, widget: null },
      { label: "Got a team", value: "got a team", dashed: false, widget: null },
    ],
    mask: null,
    cta_label: null,
    prefix: null,
    suggest_owner_email: false,
  };
  const hoursInput = {
    kind: "text",
    placeholder:
      "What are your opening hours, and which days of the week are you open?",
    chips: [],
    mask: null,
    cta_label: null,
    prefix: null,
    suggest_owner_email: false,
  };

  await page.route("**/api/onboarding/state", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        stage: "headcount",
        prompt: "Is it just you, or do you work with a team?",
        draft: {
          name: "Ronin",
          business_name: "Test Repairs",
          business_type: "Phone repair shop",
        },
        completed: false,
        history: [
          {
            role: "assistant",
            content: "Is it just you, or do you work with a team?",
          },
        ],
        input: headcountInput,
        can_confirm: false,
        suggested_slug: "test-repairs",
      }),
    }),
  );

  // This is the old failure shape: the model says hours, but the server still
  // returns headcount, so the stale team chips remain beside the new question.
  await page.route("**/api/onboarding/message/stream", (route) =>
    route.fulfill({
      contentType: "text/event-stream",
      body: [
        'data: {"type":"progress","stage":"processing"}',
        'data: {"type":"token","text":"What are your opening hours, and which days of the week are you open?"}',
        'data: {"type":"reply","text":"What are your opening hours, and which days of the week are you open?"}',
        `data: ${JSON.stringify({
          type: "state",
          stage: "headcount",
          draft: {
            name: "Ronin",
            business_name: "Test Repairs",
            business_type: "Phone repair shop",
          },
          completed: false,
          input: headcountInput,
          can_confirm: false,
          suggested_slug: "test-repairs",
        })}`,
        'data: {"type":"done"}',
        "",
      ].join("\n\n"),
    }),
  );

  await page.route("**/api/onboarding/message", async (route) => {
    expect(route.request().postDataJSON()).toEqual({
      selection: { beat: "headcount", values: ["got a team"] },
    });
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        stage: "hours",
        prompt:
          "Got it. What are your opening hours, and which days of the week are you open?",
        draft: {
          name: "Ronin",
          business_name: "Test Repairs",
          business_type: "Phone repair shop",
          headcount: "got a team",
        },
        completed: false,
        history: [
          {
            role: "assistant",
            content: "Is it just you, or do you work with a team?",
          },
          { role: "user", content: "Got a team" },
          {
            role: "assistant",
            content:
              "Got it. What are your opening hours, and which days of the week are you open?",
          },
        ],
        input: hoursInput,
        can_confirm: false,
        suggested_slug: "test-repairs",
      }),
    });
  });

  await loginAsTenantAdmin(page, request, DEMO_USERS[0]);
  await page.getByRole("button", { name: "Got a team" }).click();

  await expect(
    page.getByText(
      "Got it. What are your opening hours, and which days of the week are you open?",
      { exact: true },
    ),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Got a team" })).toHaveCount(0);
});
