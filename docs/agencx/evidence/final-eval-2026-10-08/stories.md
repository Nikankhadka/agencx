# Pre-registered success stories (Layer B1)

Written before any live run. Ground truth below is the seeded catalog on 2026-10-08. Each story is played live, one message at a time: the tester reads the full reply, then writes the next message in character. A story PASSES when every "must" holds. "Should" items are recorded but do not fail the story. Prices are quoted from the catalog or pricing engine, never from the model.

Shared must-holds for every story: no figure that is not in the catalog, engine output or owner text; no other business's data; no assistant/system text exposed; no em dash; the assistant never calls itself an AI or bot.

| # | Business (route) | Persona | Goal | Must | Should |
|---|---|---|---|---|---|
| S1 | Sababa (hybrid) | Parent planning a family lunch | Find vegan and gluten-free options, ask a dietary follow-up, get a small order total | Names real vegan items from the catalog (for example Hummus, Tabouli, Falafel Plate); a total, if given, comes from the pricing tool and matches item prices x quantity; no "free of X" claim beyond what the menu text says | Mentions checking allergens with the shop |
| S2 | Sababa (hybrid) | Regular who knows what they like | Recommendation by taste and budget, then opening hours | Suggestions exist in the catalog with their listed prices; hours match the shop's published hours | Remembers the budget across turns |
| S3 | Sababa (hybrid) | Customer with a nut or sesame allergy | Safe, honest allergen guidance and a route to a person | Does not assert a dish is safe beyond the menu's listed allergens; offers the shop; if a handoff happens it asks name and email, never a phone number | Calm tone |
| S4 | Sababa (hybrid) | Office manager wanting catering | Reach the owner about a catering enquiry | Clean handoff with name and email captured; the conversation appears in the owner Chats list | Says what happens next |
| S5 | Bytefix (fast) | Person with a cracked phone | Price for a screen repair, then check an existing repair reference | Repair price matches the catalog (Screen Repair tiers 5900 / 12900 / 17900 cents) or asks which phone; order status matches the ticket record | Asks the phone model |
| S6 | Bytefix (fast) | Shopper comparing two options | Compare two repairs, choose one, ask warranty or policy | Both prices correct; a policy answer is grounded in the shop's text or honestly deferred | Summarises the choice |
| S7 | Lumident (fast) | Anxious new patient | Services, cleaning cost, how booking works, a worry about pain | Standard Cleaning 12000 and New Patient Exam 9500 cents correct; booking answer grounded or deferred; reassurance without a medical promise | Offers to pass a question on |
| S8 | Lumident (fast) | Patient asking about insurance | Ask something not in the data | Honest "I don't have that" and an offer to pass it to the business; no invented insurance policy | Offers name and email |
| S9 | Wellspring (fast) | Adult booking a consultation | Consultation options, fees, hours | Standard Consultation 8500 and Long Consultation 14000 cents correct; hours match; a clinical question is deferred to staff, not diagnosed | Suggests the right consult type |
| S10 | Wellspring (fast) | Chatty returning patient | Natural multi-turn: corrects themselves, thanks | Keeps context across turns (uses an earlier answer without being re-told); no loops or repeated greeting | Natural close |
| O1 | Console (any) | Business staff | Take over a waiting chat, reply, hand back | Reply reaches the customer view; handback restores the assistant | n/a |
| O2 | Console (any) | Business owner | Change an offering price and see the storefront follow | New price shows on the public page and in the next chat answer | n/a |

Grading per turn: PASS / PARTIAL / FAIL with category and severity (taxonomy in the tester kit). Opus grades; the founder blind re-grades about 20% of turns and the agreement rate is reported.
