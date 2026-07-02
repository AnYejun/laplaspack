---
name: laplaspack
description: Compile any source material (notes, a company story, a résumé, project docs) into a .laplaspack — structured, portable AI memory with causal receipts. Use when the user asks to "make a laplaspack", "turn this into memory", or wants a portable knowledge pack from their text.
---

# Build a .laplaspack from source material

You turn the user's raw material into a `.laplaspack`: a single SQLite file of
typed entities, causal links, and dated thoughts that any conformant reader can
open and interrogate offline. Two stdlib-only tools from
[github.com/AnYejun/laplaspack](https://github.com/AnYejun/laplaspack) do the
mechanical work; your job is the **compilation** — raw prose → LMD.

## Steps

1. **Get the tools** (skip if the repo is already present):
   ```bash
   git clone https://github.com/AnYejun/laplaspack /tmp/laplaspack 2>/dev/null || true
   ```

2. **Read the source material.** The user points you at text, files, or a
   directory. Read enough to extract the real claims, decisions, and evidence —
   not just headings.

3. **Compile to LMD** — write `<name>.lmd` following the grammar in
   `prompts/lmd-compiler.md` (same repo). The non-negotiables:
   - 6–16 nodes, short claim-like labels, one idea per node
   - `>>type:` on every node · `>>what:` = one dense sentence · facts ONLY from the source
   - causal links (`→(derived-from)` etc.) wherever the source implies WHY
   - source language preserved; non-English labels get an English gloss in parens
   - `@@decision/todo/question on="Full Label" by=<user> at=<today> … @@` for
     thoughts; ALWAYS quote `on=`
   - decisions link to their evidence: `[[Decision]] →(derived-from) [[Proof]]`

4. **Build the pack:**
   ```bash
   python3 /tmp/laplaspack/laplaspack_writer.py <name>.lmd --owner "<user>" --name "<Title>"
   ```

5. **Verify it carries its reasoning** — run all three and show the user:
   ```bash
   python3 /tmp/laplaspack/laplaspack_reader.py <name>.laplaspack
   python3 /tmp/laplaspack/laplaspack_reader.py <name>.laplaspack --why "<a decision label you created>"
   python3 /tmp/laplaspack/laplaspack_reader.py <name>.laplaspack --todos
   ```
   The `--why` chain must walk real ancestors. If it comes back empty, you
   under-linked — go back to step 3 and add the causal edges the source implies.

6. **Hand over** both files (`.lmd` = the editable source of truth,
   `.laplaspack` = the built artifact) and mention: the pack can be uploaded to
   [Laplas Manifesto](https://laplas-manifesto.vercel.app) to become a live,
   grounded Q&A page — or read by anyone with the zero-dependency reader.

## Quality bar

- A reader running `--why` on your pack should reconstruct the user's actual
  reasoning, not a summary of it.
- If the source contains numbers, dates, or names, they appear verbatim in
  `>>what:`/`>>why:` — never rounded or paraphrased into vagueness.
- When the source is thin on causality, say so to the user and ask one or two
  sharp questions ("why did you choose X over Y?") before compiling — captured
  WHY is the whole point of the format.
