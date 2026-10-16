# Slice-2 per-turn tool rounds (the multi-round evidence)

Built from the two slice-2 run logs, which were ephemeral
(`/tmp/slice2-run1.log`, `/tmp/slice2-run2.log`). The distilled filtered lines
are committed beside this file (`slice2-run1-lines.jsonl`,
`slice2-run2-lines.jsonl`), so the numbers below are reproducible without the
`/tmp` logs; this artifact is now the record.

## Extraction recipe

- Rounds: logger `app.agents.agent_node`, message `agent model call`, field
  `iteration`; its sibling field `tool_calls` is that round's requested tool
  count. Tool names: logger `app.agents.agent_node`, message `agent tool`,
  field `tool`.
- Join: `request_id` on those lines to the `latency turn` payload (logger
  `app.latency`), which carries `tenant_id` and the per-turn record
  (`llm_call_count`, `first_prose_ms`, `total_ms`).
- Turn order: the runner drives one tenant at a time, five turns in order, so a
  tenant's `latency turn` lines appear in turn order; turn N's message is
  `latency_config.json`'s `corpus[].messages[(N-1) % 5]`.
- Tenant id: bytefix's slice-2 `tenant_id` (`620844f6-…`) predates the later
  `make seed-tenant1` reseed and is no longer in `tenants`; it is mapped back to
  `bytefix` here.

## Filter commands

```
grep -E '"message": "agent model call"|"message": "agent tool"|"logger": "app.latency"' \
  /tmp/slice2-run1.log > slice2-run1-lines.jsonl
grep -E '"message": "agent model call"|"message": "agent tool"|"logger": "app.latency"' \
  /tmp/slice2-run2.log > slice2-run2-lines.jsonl
```

(The reviewer asked for the `agent model call` + `latency turn` lines; the
`agent tool` message is included because the tool-name column needs it.)

## Per-turn table

`agent rounds` is the list of `iteration` values seen; `tool calls/round` is the
`tool_calls` count of each; `tool rounds` counts rounds that executed at least
one tool. `completed` is `first_prose_ms != None`; a `no` row timed out, so its
rounds and `llm_call_count` are truncated (a lower bound).

| run | tenant | turn | message | agent rounds | tool calls/round | tool rounds | tools | llm_call_count | completed | total_ms |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | bytefix | 1 | What repairs do you offer? | [0] | [1] | 1 | show_catalog x1 | 1 | yes | 2385.6 |
| 1 | bytefix | 2 | How long do repairs usually take? | [0] | [0] | 0 | - | 2 | yes | 9228.4 |
| 1 | bytefix | 3 | Do you fix water-damaged phones? | [0] | [0] | 0 | - | 1 | no | 10009.5 |
| 1 | bytefix | 4 | Do you offer a warranty on your repairs? | [0] | [0] | 0 | - | 2 | yes | 5825.7 |
| 1 | bytefix | 5 | Can you replace a charging port? | [0] | [0] | 0 | - | 1 | no | 10008.4 |
| 1 | sababa2 | 1 | Which dishes are vegan or gluten free? | [0] | [0] | 0 | - | 2 | yes | 7733.3 |
| 1 | sababa2 | 2 | What are your most popular items? | [0] | [0] | 0 | - | 2 | yes | 3788.2 |
| 1 | sababa2 | 3 | What time do you open? | [0] | [0] | 0 | - | 2 | yes | 4605.7 |
| 1 | sababa2 | 4 | Do you have anything without nuts? | [0] | [0] | 0 | - | 1 | no | 10007.2 |
| 1 | sababa2 | 5 | What is the Super Plate? | [0] | [0] | 0 | - | 1 | no | 10007.6 |
| 1 | sababa | 1 | Which dishes are vegan or gluten free? | [0, 1, 2] | [2, 2, 0] | 2 | search_knowledge x2, recommend_items x2 | 3 | no | 10005.0 |
| 1 | sababa | 2 | What are your most popular items? | [0, 1, 2, 3] | [2, 1, 1, 1] | 4 | search_knowledge x4, recommend_items x1 | 4 | no | 10011.8 |
| 1 | sababa | 3 | What time do you open? | [0] | [0] | 0 | - | 4 | yes | 9120.2 |
| 1 | sababa | 4 | Do you have anything without nuts? | [0, 1, 2] | [2, 2, 0] | 2 | search_knowledge x2, recommend_items x2 | 4 | no | 10009.8 |
| 1 | sababa | 5 | What is the Super Plate? | [0, 1] | [1, 0] | 1 | recommend_items x1 | 3 | no | 10007.8 |
| 2 | bytefix | 1 | What repairs do you offer? | [0] | [1] | 1 | show_catalog x1 | 1 | yes | 5261.6 |
| 2 | bytefix | 2 | How long do repairs usually take? | [0] | [0] | 0 | - | 2 | yes | 8406.6 |
| 2 | bytefix | 3 | Do you fix water-damaged phones? | [0] | [0] | 0 | - | 1 | no | 10006.4 |
| 2 | bytefix | 4 | Do you offer a warranty on your repairs? | [0] | [0] | 0 | - | 2 | yes | 5449.7 |
| 2 | bytefix | 5 | Can you replace a charging port? | [0] | [0] | 0 | - | 2 | yes | 9544.6 |
| 2 | sababa2 | 1 | Which dishes are vegan or gluten free? | [0] | [0] | 0 | - | 1 | no | 10014.0 |
| 2 | sababa2 | 2 | What are your most popular items? | [0] | [0] | 0 | - | 2 | yes | 7687.2 |
| 2 | sababa2 | 3 | What time do you open? | [0] | [0] | 0 | - | 2 | yes | 4304.2 |
| 2 | sababa2 | 4 | Do you have anything without nuts? | [0] | [0] | 0 | - | 2 | yes | 7179.2 |
| 2 | sababa2 | 5 | What is the Super Plate? | [0] | [0] | 0 | - | 2 | yes | 4588.7 |
| 2 | sababa | 1 | Which dishes are vegan or gluten free? | [0, 1, 2] | [2, 2, 0] | 2 | search_knowledge x2, recommend_items x2 | 3 | no | 10006.8 |
| 2 | sababa | 2 | What are your most popular items? | [0, 1, 2] | [1, 2, 2] | 3 | search_knowledge x4, recommend_items x1 | 3 | no | 10007.3 |
| 2 | sababa | 3 | What time do you open? | [0] | [0] | 0 | - | 3 | no | 10006.2 |
| 2 | sababa | 4 | Do you have anything without nuts? | [0, 1, 2] | [1, 1, 0] | 2 | search_knowledge x1, recommend_items x1 | 4 | no | 10011.1 |
| 2 | sababa | 5 | What is the Super Plate? | [0, 1] | [1, 0] | 1 | recommend_items x1 | 3 | no | 10008.5 |

## Correction to the design note

The earlier recon listed run 1's third sababa row as "search_knowledge,
recommend_items x2". The extracted lines show it is **2x search_knowledge + 2x
recommend_items** (`search_knowledge, recommend_items, search_knowledge,
recommend_items` across the round's 4 tool calls). The table above is
authoritative.

## What it shows

- Fast tenants (bytefix, sababa2) answered in one P-3 round; bytefix's only tool
  turn was a single `show_catalog` round.
- sababa (hybrid): 4 of 5 turns per run called tools, and 3 of those 4 were
  multi-round (2-4 rounds, `search_knowledge` and `recommend_items` across
  rounds). Multi-round tool use is the norm on the hybrid path.
