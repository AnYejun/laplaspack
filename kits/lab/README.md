# Lab Canon — starter kit

A research lab's memory, as files. The schema in motion: `hypothesis` ·
`experiment` · `result` · `protocol` · `dataset` · `paper` · `member` · `grant`,
wired with the six causal roles. **The lab's memory doesn't graduate.**

## What's here
| file | what |
|---|---|
| `lab-canon.lmd` | the canon, human-readable — edit this, it IS the memory |
| `lab-canon.laplaspack` | the same canon compiled (`laplaspack_writer.py`) |
| `harness-scout.yaml` | **Related-Work Scout** — "has the lab already tried this, and why did it end?" |
| `harness-protocol.yaml` | **Protocol Writer** — drafts plans grounded in YOUR protocols, stages changes for approval |

## 60 seconds, three ways

**In any MCP client (no account):**
```json
{ "mcpServers": { "lab": { "command": "python3",
  "args": ["laplaspack_mcp.py", "kits/lab/lab-canon.laplaspack"] } } }
```
Ask: *"why did we pivot to sparse replay?"* — the answer walks
`decision ← result ← experiment`, with the contradicted hypothesis named.

**In the AX console (laplas-ax.vercel.app):**
1. Memory → Add pack → `lab-canon.laplaspack`
2. Harnesses → Mount a harnesspack → paste `harness-scout.yaml` (then `harness-protocol.yaml`)
3. Agents → declare **Scout** (memory: lab-canon × harness: Related-Work Scout)
   and **Planner** (× Protocol Writer)
4. Loops → declare **Scout → Planner**: step 1 `{{input}}`, step 2
   `Draft the plan given what we know: {{prev}}` — one input, grounded plan out,
   protocol changes waiting in Approvals.

**Make it YOURS:** replace the contents of `lab-canon.lmd` with your lab's
hypotheses and results (keep the causal arrows — they are the why), then
`python3 laplaspack_writer.py your-lab.lmd`. Conventions: domain relations
(`>>tests:` `>>uses:` `>>run_by:`) are fields; **causality uses the six roles**
(`derived-from` · `supports` · `contradicts` · `raises` · `closes` · `supersedes`).
Types are yours to invent; causality is the standard.
