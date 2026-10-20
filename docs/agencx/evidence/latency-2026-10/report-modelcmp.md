# Model comparison - DeepSeek, Gemini, Groq

Two back-to-back passes, same window; three tenants x three turns in one reused conversation; single leg. 18 turn-slots per model (small n).

**Measured.** Gemini 3.5 Flash Lite completed 11/18; DeepSeek V4 Flash 3/18; Groq gpt-oss-120b 0/18. Completed Gemini fast-path turns ran 2.8-4.3 s (one 8.8 s seven-call turn) and hybrid 3.2-5.4 s. DeepSeek's three completions were 4,992 ms, 7,965 ms and 8,173 ms, with 15/18 turns hitting the 10 s cap. Run-2 cumulatives: Gemini 11.7 s / 10.6 s / 25.3 s (bytefix / sababa2 / sababa); DeepSeek 25.0 s / 30.0 s / 30.0 s; Groq 30.0 s / 0.4 s / 30.0 s, where the 0.4 s is an immediate HTTP 413 refusal, not an answer.

**Why they differ.** DeepSeek V4 Flash is a reasoning model on a paid OpenRouter route; hidden thinking inflates every serial call, and the app makes two calls per fast turn. It produced no 429/5xx, so its 15 budget misses are model/provider speed. List cost: $0.0009-0.0013 per pass, $0.0002-0.0006 per three-question tenant. Its cache-read price equals its prompt price, so caching saves no money.

Gemini Flash Lite is a small non-reasoning model on a free tier. When quota allows, it is fastest. The window logged 13 x 429 and 2 x 503, causing four provider refusals and three budget misses; free-tier quota is the binding constraint.

Groq is free-tier with an 8,000 TPM ceiling; the app's prompts reach 11-22k tokens. `sababa2` is rejected with HTTP 413 before any call, and the other tenants spend the 10 s budget in 429 retries. Not viable at this prompt size.

**Recommendation.** Free: Gemini first. Cheap paid: DeepSeek, accepting that it does not fix latency. Groq only with a paid tier or a prompt cut below roughly 8k tokens.
