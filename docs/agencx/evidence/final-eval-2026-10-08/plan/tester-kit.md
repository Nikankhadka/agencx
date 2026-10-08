# Tester kit - PRT691 final evaluation (2026-10-08)

One shared log for every human tester: `human-findings.csv` (columns: id, tester, role, tenant, surface, steps, expected, actual, severity, category, screenshot). Add a row for everything you notice, good or bad - a short "worked well" note is also useful evidence. Severity: critical (wrong money, leaked data, unsafe claim, broken chat), major (wrong or missing answer, dead end), minor (wording, layout, polish). Category: grounding, money, isolation, escalation, tone, latency, ui, other.

Where to test: customer chat at `/{slug}` (sababa, bytefix, lumident, wellspring). Owner console login uses an emailed code; on the local stack read it in Mailpit (http://localhost:8025). Demo owners are `owner@{slug}.dev`. Timing note for everyone: replies can take 10-30 seconds on the free model tier. Wait for the full reply before sending the next message, like a real chat.

## QA teammates (30 minutes each)

Each tester takes one business and talks to it like a real customer would, in their own words. Do not copy the examples; the point is natural, varied input.

| Tester | Business | Customer charter | Owner/console charter |
|---|---|---|---|
| Pramisha | lumident (dental) | Find out what a new patient needs to know: services, rough costs, how to book, one worried question. | Open Chats, read a conversation you started, check the handoff details look right. |
| Rahul | bytefix (repair shop) | Ask about a repair you actually have in mind, compare two options, ask about warranty, check an order reference from the queue. | Take over a chat, reply as the business, hand it back. |
| Sanil | wellspring (clinic) | Ask about a consultation, fees and hours; ask something clinical and see what happens. | Check the business hub shows the right name, hours and services. |
| Each | any other business (cross-over, 10 min) | Same chat on a phone-sized screen. Try one thing that should NOT be answerable. | n/a |

Also each tester: ask for a human once, give a name and email when asked, and confirm the owner side shows it.

## Business manager (Sababa) - acceptance session (30-40 minutes)

Part 1, your real customers' questions (15-20). Type the questions your customers actually ask you. For each answer rate it: Correct / Acceptable (right but you would word it differently) / Wrong / Unsafe to send. Write one line for anything Wrong or Unsafe.

Part 2, owner tasks (4-6, on a shared screen if login is not available for you): see a customer conversation, take it over and reply, hand it back, change a dish price and see the page update, read what the assistant knows about the shop.

Part 3, in your own words: Would you put this in front of your customers today? What would you need fixed first? What did it get right that surprised you? Any answer you would not want a customer to see?

Consent: confirm you are happy for the shop name, menu and your comments to appear in the project presentation (yes/no, and whether to use your name or "the shop owner").

## Rules for all testers

- Do not try to break it in the first pass; do the realistic task first, then the edge cases.
- Do not paste real personal data. Use made-up names and emails (for example test.name@example.com).
- Screenshot anything surprising and put the file name in the log.
