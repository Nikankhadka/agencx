# Cheap and best right now: model choice

Window A = prior `modelcmp.md` (`78685fc`); B = this run (`9ea418c`). Each: two back-to-back passes, 3 tenants x 3 turns, one reused conversation, single leg. n = 9/model/pass, 36 turn-slots across both (gpt-oss-20b: 18, B only).

|model (tier)|done, A / B|p50 done, s (A, B)|3Q cumulative, s bf/s2/sa|cache (B)|cost/pass, then per 3Q|blocker|
|---|---|---|---|---|---|---|
|Gemini 3.5 Flash Lite (free)|25/36 (4,7 + 7,7)|3.5, 4.0 / 4.2, 3.8|B 18.0/10.7/22.2; 12.1/9.7/28.4|18.5% / 20.0%|n/a|7 x 429/pass, 3 refusals|
|DeepSeek V4 Flash (paid)|8/36 (2,1 + 3,2)|8.1, 5.0 / 5.0, 8.0|B 27.8/19.6/30.0; 29.8/26.3/30.0|27.8% / 7.6%|B $0.00245, $0.00068; $0.00008-0.00092/3Q. A $0.00133, $0.00094; $0.00021-0.00063/3Q|13/18 budget; cache read = prompt|
|Groq gpt-oss-120b (free)|0/36 (0,0 + 0,0)|n/a|A 30.0/0.5/30.0; B 30.0/0.4/30.0|0%|B $0.00258, $0.00275; $0-0.00193/3Q. A $0.00218, $0.00239; $0-0.00195/3Q|413 at 11-12k; 10-11 x 429/pass|
|gpt-oss-20b (paid)|0/18 (0,0)|n/a|B 30.0/30.0/30.0 both|0% / 23.2%|B $0.00026, $0.00032; $0-0.00021/3Q. A n/a|18/18 budget; tools pass|

Only Gemini clears 10 s. DeepSeek is the only other model to complete any turn, but it is paid, reasoning-slow (13/18 budget here, 15/18 prior), and cache read equals prompt. Free Groq is not a working fallback: 8k TPM 413s the 11-12k-token tenant and burns the budget on 429s; gpt-oss-120b never completed. gpt-oss-20b passes tools and structured outputs but never completed a turn, so it is not viable.

Cost caveat: Groq and gpt-oss-20b price only tokens billed before the clamp. DeepSeek's prompt price halved between windows; Gemini publishes none.

**Recommendation: keep free Gemini primary; replace free Groq with paid DeepSeek V4 Flash.** It is the only measured fallback that answers and never rate-limited. Do not adopt gpt-oss-20b. This does not fix the 10 s miss on hybrid/large prompts; the next lever is turn policy. n is small; quota moved between passes.
