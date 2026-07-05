# The LMD compiler prompt

Paste the block below into **any capable AI** — Claude, ChatGPT, Gemini — then
paste your raw material (company story, résumé, project notes, meeting minutes)
as the next message. The model returns valid LMD; save it as `story.lmd` and
build the pack:

```bash
python3 laplaspack_writer.py story.lmd        # → story.laplaspack
python3 laplaspack_reader.py story.laplaspack --why "<some decision label>"
```

---

## The prompt (copy from here)

```text
You convert raw source material (notes about a person or project, a company
story, a résumé, meeting minutes, decisions) into LAPLAS Markdown (LMD) — a
structured knowledge graph stored as plain text. Output ONLY LMD, nothing else.

FORMAT (follow EXACTLY):

# <Title of this memory>
<one or two plain sentences describing the pack>

## <Node label — a noun phrase>
[[<Node label — a noun phrase>]]
>>type: <lowercase noun the material calls for: person | org | team | project | decision | insight | value | goal | question | artifact | …>
>>what: <ONE sentence of essence — never a list of facts that belong in properties>
>><key>: <value>          ← any number of scalar properties: born, height, role, venue, date …

[[<label A>]] →(<role>) [[<label B>]]

@@<think-type> on="<host node label>" by=<author> at=<YYYY-MM-DD> [status=open] [id=<slug.t1>]
<an interpretation, decision, todo, or question — in full sentences>
@@

THE THREE SHAPES — every fact lands at exactly one level:
1. NODE — a thing you can point at: a person, org, artifact, concept, goal,
   decision, claim. Label = NOUN PHRASE, 2–6 words.
2. PROPERTY — a scalar fact about one node, written ON that node:
   >>born: 2011-03-02 · >>height: 166cm · >>position: midfielder
3. LINK — a relationship between two nodes:
   [[Hana Kim]] →(child-of) [[Minho Kim]]

THE TEST: if a candidate node's label reads as a sentence ABOUT another node
("height 166cm", "has a girlfriend", "favorite team is X"), it is NOT a node —
it is a property of that node or a link to another node. A node exists so that
other facts can attach to it.

WRONG (facts as nodes — a list wearing a graph's file extension):
  ## Height 166cm
  [[Height 166cm]]
  >>type: note
  >>what: Her height is 166cm as of 2026.

RIGHT (each fact at its level):
  ## 김하나 (Hana Kim)
  [[김하나 (Hana Kim)]]
  >>type: person
  >>what: 동산중 축구부 미드필더 — 프로를 꿈꾼다. (midfielder who wants to go pro)
  >>born: 2011-03-02
  >>height: 166cm (2026)

  [[김하나 (Hana Kim)]] →(plays-for) [[동산중 축구부 (Dongsan MS football team)]]
  [[김하나 (Hana Kim)]] →(child-of) [[김민호 (Minho Kim)]]
  [[김하나 (Hana Kim)]] →(admires) [[손흥민 (Son Heung-min)]]

LINKS — two channels:
- CAUSAL (exactly these six; they power the --why chain): derived-from ·
  supports · raises · closes · supersedes · contradicts. Whenever the source
  implies WHY, link it: [[Decision]] →(derived-from) [[Evidence]].
- DOMAIN (any kebab-case role you need): child-of · married-to · plays-for ·
  works-at · fan-of · admires · uses · tests · run-by · authored-by …
  Only edge-role field keys (part_of, belongs_to, has_part, has_goal, contains,
  targets + the six causal roles) also create links as >>fields:. Any OTHER
  >>key: [[Ref]] stays plain text — for father/team/friend relations you MUST
  use an arrow line.

RULES:
- 5 to 16 nodes. A claim MAY be a node when it stands alone as something you
  would cite ("Ships within 72 hours" as a differentiator, a hypothesis, an
  insight) — but a fact about another node never is.
- >>what: is the node's essence in ONE line. NEVER restate facts that already
  live in properties or links — zero duplication across what:/properties/links.
- NO ORPHANS: every node links to at least one other node. The subject of the
  pack is the hub; facts radiate from it. The writer warns on orphan nodes —
  treat that warning as a failed compile.
- Use ONLY facts present in the source. NEVER invent names, numbers, or claims.
- WRITE IN THE SOURCE LANGUAGE. Non-English labels get a short English gloss in
  parentheses, e.g. "주 단위 스프린트 협업 (weekly sprint collaboration)" — both
  must be searchable. Never nest parentheses.
- Link endpoints must match declared node labels verbatim.
- @@think@@ blocks carry interpretation, not raw facts: @@decision for decisions
  with reasoning, @@todo (status=open) for open items, @@question for open
  questions, @@insight for a reading of the facts. ALWAYS quote on="Full label".
- No prose outside the LMD. No code fences. Start with the # title line.
```

---

## Why this shape

Every `>>what:` becomes a **citable fact**. Every property makes its node
**dense** — properties are what an agent actually reads when it composes
context about the node. Every `→(role)` link makes the pack a **graph** — the
causal six power the `--why` chain, and domain roles are what lets a reader
walk from a person to their team, their family, their goals. Every `@@think@@`
becomes a dated, attributable thought that folds by last-writer-wins.

The failure mode this prompt exists to prevent: a model that turns each source
sentence into a "node" produces ten orphaned sentences and three links — a
bullet list, not a memory. Structure captured at write-time is the whole point
of the format; the three shapes are that structure.
