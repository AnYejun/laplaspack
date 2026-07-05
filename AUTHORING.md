# Make your own `.laplaspack`

Three ways, easiest first. All of them end at the same place: a single file
that answers `--why` offline.

## 1 · With any AI chatbot (2 minutes)

1. Open [`prompts/lmd-compiler.md`](./prompts/lmd-compiler.md) and copy the
   prompt block into Claude / ChatGPT / Gemini.
2. Paste your raw material as the next message — a company story, your résumé,
   project notes, meeting minutes. The model returns **LMD** (plain text).
3. Save it as `story.lmd`, then build and verify:

```bash
python3 laplaspack_writer.py story.lmd --owner you --name "My story"
python3 laplaspack_reader.py story.laplaspack --why "<one of your decision labels>"
```

If `--why` walks a real chain of reasoning, you have a pack.

## 2 · With Claude Code (one command)

Copy the skill into your project and ask for a pack:

```bash
mkdir -p .claude/skills && cp -r skills/laplaspack .claude/skills/
```

Then in Claude Code: *"make a laplaspack from ./docs/company.md"* — it reads
the source, compiles LMD, builds the pack with the writer, and verifies the
`--why` chain before handing it over. The skill lives at
[`skills/laplaspack/SKILL.md`](./skills/laplaspack/SKILL.md) and works as a
plain instruction file for any other agent runner too.

## 3 · With zero setup — Laplas Manifesto

Paste your story at [laplas-manifesto.vercel.app](https://laplas-manifesto.vercel.app):
it compiles the pack server-side and hands you a live, full-screen Q&A page for
it (free tier: 100 grounded answers/month). Packs built with the writer here
upload there too — same format, same receipts.

## Writing LMD by hand

LMD is designed to be written by humans as much as by models — it's markdown
with three extra moves. The full grammar is
[`LMD_GRAMMAR.ebnf`](./LMD_GRAMMAR.ebnf); the working subset:

```lmd
# Aurora Coffee — brand memory

## Single-origin only
[[Single-origin only]]
>>type: decision
>>what: We buy single-origin beans directly from two farms in Yirgacheffe.
>>why: Blends hide defects; direct trade doubles the farmer's take.

[[Single-origin only]] →(derived-from) [[Direct trade doubles farm income]]

@@todo on="Own roastery in Mapo" by=founder at=2026-07-03 status=open
Book the Q3 cupping session with both farms.
@@
```

Three rules that matter more than the rest:

1. **The three shapes.** A NODE is a noun phrase naming a thing you can point
   at; a scalar fact is a **`>>property:` on its node** (`>>born: 2011-03-02`);
   a relation is a **link** (`[[A]] →(child-of) [[B]]` — any kebab-case role,
   the causal six power `--why`). If a label reads as a sentence about another
   node ("height 166cm"), it's a property or a link, never a node. No orphans:
   every node connects; the writer warns when one doesn't.
2. **Link the WHY** — `→(derived-from)` from a decision to its evidence is what
   makes `--why` work. A pack without causal links is just notes.
3. **Quote multi-word hosts**: `on="Full node label"` (unquoted `on=` takes a
   single token).
4. **Give nodes an authored id** — `>>id: lp_a1c0ffee0001` — and renames survive
   rebuilds (the id, not the label, is the durable handle), and two packs that
   share ids can be **merged mechanically** (`laplaspack_merge.py`, SPEC §3.9) —
   this is how team packs become one organizational memory. The writer builds
   without them but will tell you what you're giving up; it also **fails the
   build** on dangling links, so a rename that misses a link line can't ship a
   silently broken graph.

See [`examples/demo.lmd`](./examples/demo.lmd) for the source that builds
[`examples/demo.laplaspack`](./examples/demo.laplaspack).
