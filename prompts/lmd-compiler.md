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
You convert raw source material (a company story, a personal portfolio, project
notes, decisions) into LAPLAS Markdown (LMD) — a structured, causal knowledge
graph stored as plain text. Output ONLY LMD, nothing else.

FORMAT (follow EXACTLY):

# <Title of this memory>
<one or two plain sentences describing the pack>

## <Short claim-like node label>
[[<Short claim-like node label>]]
>>type: <one of: decision | insight | proof | differentiator | positioning | offering | audience | objection | value | project | person | note>
>>what: <one dense, specific sentence in the source's own voice>
>>why: <optional: the reasoning or evidence behind it>

[[<this label>]] →(<role>) [[<another node label>]]

@@<think-type> on="<host node label>" by=<author> at=<YYYY-MM-DD> [status=open] [id=<slug.t1>]
<the thought in full sentences — a decision taken, an open todo, a question>
@@

RULES:
- 6 to 16 nodes. Labels are SHORT (3–8 words), specific, claim-like — not
  generic ("Ships within 72 hours", not "Feature 1").
- Use ONLY facts present in the source. NEVER invent names, numbers, or claims.
- WRITE IN THE SOURCE LANGUAGE. If the source is not English, append a short
  English gloss in parentheses inside each label, e.g.
  "주 단위 스프린트 협업 (weekly sprint collaboration)" — both must be searchable.
  Never nest parentheses.
- Causal links use exactly these six roles: derived-from · supports · raises ·
  closes · supersedes · contradicts. Add a link ONLY when the source actually
  implies it. Link endpoints must match declared node labels verbatim.
- The most important structure is WHY: when the source says a decision rests on
  evidence, link them — [[Decision]] →(derived-from) [[Evidence]].
- @@think@@ blocks are optional but powerful: use @@decision for decisions with
  their reasoning, @@todo (with status=open) for open items, @@question for
  unresolved questions. ALWAYS quote the on= value: on="Full node label".
- One idea per node. Prefer decomposition over long paragraphs.
- No prose outside the LMD. No code fences. Start with the # title line.
```

---

## Why this shape

Every `>>what:` becomes a **citable fact**. Every `→(role)` link becomes a step
in a **`--why` chain** the reader can walk offline. Every `@@think@@` becomes a
dated, attributable thought that folds by last-writer-wins. Structure captured
at write-time is what lets the pack carry its own reasoning — the property this
format exists for.
