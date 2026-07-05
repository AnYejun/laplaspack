<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/mark-dark.svg">
  <img src="assets/mark-light.svg" width="92" alt="the LAPLAS mark — concentric diamonds">
</picture>

# `.laplaspack`

**The open format for portable AI memory.**<br>
One file that holds a mind — typed entities, causal links, human thoughts, and the provenance of how they got there.<br>
<sub>Verifiable two ways, both offline: <b>walk</b> the reasoning (<code>--why</code>, stdlib reader) · <b>check</b> the seal (Ed25519, seal tool).</sub>

<p>
  <img src="https://img.shields.io/badge/spec-v3_draft-111111?style=flat-square" alt="spec v3 draft">
  <img src="https://img.shields.io/badge/reader-stdlib_only-111111?style=flat-square" alt="zero dependencies">
  <img src="https://img.shields.io/badge/license-MIT-111111?style=flat-square" alt="MIT">
  <a href="https://discord.gg/utU3U7kb3"><img src="https://img.shields.io/badge/community-Discord-5865F2?style=flat-square&logo=discord&logoColor=white" alt="Discord"></a>
</p>

<sub>an <b>◈ ISOMORPH</b> project — the format under <a href="https://laplas-landing.vercel.app">LAPLAS</a> and <a href="https://laplas-manifesto.vercel.app">Manifesto</a></sub>

</div>

<br>

> Your memory should not live and die with someone else's server. A `.laplaspack`
> is designed to be **owned, verified, mounted, and moved** — independently of any
> model, app, or vendor.

## Try it in 30 seconds

No install, no network, no model. The reference reader is a single stdlib-only Python file:

```bash
git clone https://github.com/AnYejun/laplaspack && cd laplaspack

python3 laplaspack_reader.py examples/demo.laplaspack
```
```text
laplaspack: examples/demo.laplaspack
  format_version = 3
  entities=4  edges=3  thinks=2
  causal roles: derived-from×2, supports×1
```

Now ask the pack **why** it believes something:

```bash
python3 laplaspack_reader.py examples/demo.laplaspack --why "Subscription is the core offer"
```
```text
why «Subscription is the core offer» — 3 ancestor(s):
  1. (derived-from) Single-origin only                 [decision]
  2. (derived-from) Direct trade doubles farm income   [proof]
  3. (supports)     Own roastery in Mapo               [differentiator]
```

That ordered chain is not a search result — it is the pack's own recorded
reasoning, walked from the graph. There are also `--todos`, `--entity "…"`, and
`--json` for piping.

Seal it, and any edit becomes detectable (the one tool here that needs a
dependency — `pip install cryptography`; stdlib has no Ed25519):

```bash
python3 laplaspack_seal.py keygen --key me.key
python3 laplaspack_seal.py sign   examples/demo.laplaspack --key me.key
python3 laplaspack_seal.py verify examples/demo.laplaspack   # VALID — sealed by 1a2b…
```

And two minds **add**. Packs whose shared nodes declare an authored id
(`>>id: lp_…`) merge mechanically — no model in the loop; where they disagree,
the losing claim is kept losslessly and can even become a `contradicts` edge,
so *"where do our teams disagree?"* turns into a graph query
([SPEC §3.9](./SPEC.md#39-merge-declared-identity)):

```bash
python3 laplaspack_merge.py teamA.laplaspack teamB.laplaspack -o org.laplaspack \
    --conflicts materialize
python3 laplaspack_reader.py org.laplaspack --why "Deploy policy"   # walks BOTH teams' evidence
```

## Mount a pack into any MCP client

A pack someone handed you becomes a live, queryable memory inside Claude,
Cursor, or any other MCP client — one config line, zero dependencies, no
account, nothing leaves your machine
([`laplaspack_mcp.py`](./laplaspack_mcp.py)):

```json
{ "mcpServers": { "my-pack": {
    "command": "python3",
    "args": ["/path/to/laplaspack_mcp.py", "/path/to/mind.laplaspack"] } } }
```

The client gets five read-only tools: `find` (full-text over atoms), `open`
(one atom's properties + typed links + thoughts), `directory` (the map of the
mind), `why` (the recorded reasoning chain), and `blind_spots` — unclosed
loops in the typed graph (exact $H_1$): what this memory *doesn't know it's
missing*. Mount several packs at once by passing several paths.

## Make your own — with an AI, in minutes

Any capable model can compile raw material (your company story, your résumé,
project notes) into LMD; the stdlib writer turns that into a pack:

```bash
# 1 · paste prompts/lmd-compiler.md into Claude/ChatGPT/Gemini + your raw text
# 2 · save the returned LMD, then:
python3 laplaspack_writer.py story.lmd --owner you --name "My story"
python3 laplaspack_reader.py story.laplaspack --why "<one of your decisions>"
```

No raw material yet? Use the **interview**:
[`prompts/manifesto-interview.md`](./prompts/manifesto-interview.md) turns the
model into an interviewer that pulls your company's story out one question at
a time — specific claims, attached evidence — then compiles and builds the
pack for [Manifesto](https://laplas-manifesto.vercel.app).

Claude Code users: `cp -r skills/laplaspack .claude/skills/` and just ask —
*"make a laplaspack from ./docs"*. Full guide: [`AUTHORING.md`](./AUTHORING.md).
Packs built this way upload straight into
[Manifesto](https://laplas-manifesto.vercel.app) and become a live, grounded
Q&A page.

## Why write-time structure

Every memory system answers *what*. Almost none can answer ***why*** — because
retrieval-time systems re-rank prose after the fact, and the reasoning was never
captured. A `.laplaspack` is compiled **at the moment of writing**: decisions,
evidence, and links land as a typed graph, so the receipt travels with the fact.

That property — memory that can **show its work, offline, to anyone** — is what
makes a mind verifiable, and therefore portable. Concretely, "verifiable" here
means two checks anyone can run without a service: the **reasoning walk**
(`--why`: is this claim's recorded ancestry intact?) and the **seal**
(`laplaspack_seal.py verify`: has the content been touched since it was
signed?). What's implemented where is tracked honestly in
[SPEC §8](./SPEC.md#8-implementation-status-reference-tools-in-this-repo) —
redaction and hub addressing are still spec-ahead-of-tools.

## Anatomy of a pack

```text
demo.lmd  ──(compile)──▶  demo.laplaspack        one SQLite file
─────────────────────────────────────────────────────────────────
[[Node]] + >>properties        entities           typed nodes
→(role) links                  edges              6 causal roles + free relations
@@think … @@ documents         thinks             LWW-folded thoughts
                               commits            build provenance
                               lmd_source         the canonical text, embedded
```

The source format is **LMD** (LAPLAS Markdown) — human-readable, diffable,
git-friendly. The pack is its materialized, queryable form; either can always be
rebuilt from the other. See [`examples/demo.lmd`](./examples/demo.lmd) for the
exact source the demo pack was compiled from.

## What's in this repo

| File | What |
|---|---|
| [`METHOD.md`](./METHOD.md) | **start here** — the short technical report: compile edge → isomorph → recall, with the system figure |
| [`SPEC.md`](./SPEC.md) | the container spec, **v3 draft** — tables, stable identity, provenance, signing, redaction, conformance levels |
| [`VERSIONING.md`](./VERSIONING.md) | the **compatibility pledge** — every future reader reads every past pack; how the format may change; golden-corpus enforcement |
| [`RECALL.md`](./RECALL.md) | the **query surface** — the typed operator contract (`find` · `match` · `expand` · `recall_why` · thinks). A pack is a file *plus* recall, the way SQLite is a file *plus* SQL |
| [`LMD_GRAMMAR.ebnf`](./LMD_GRAMMAR.ebnf) | the grammar of the canonical source (nodes · properties · links: 6 causal roles + free relation roles · `@@think@@`) |
| [`laplaspack_reader.py`](./laplaspack_reader.py) | the **zero-dependency** reference reader (Python stdlib only) |
| [`laplaspack_writer.py`](./laplaspack_writer.py) | the **zero-dependency** reference writer — compiles LMD → pack, validates the build (dangling refs fail), honors authored `>>id:` |
| [`laplaspack_seal.py`](./laplaspack_seal.py) | Ed25519 seal — sign · verify · tamper-detect (`pip install cryptography`) |
| [`laplaspack_merge.py`](./laplaspack_merge.py) | **zero-dependency** declared-identity merge — union two packs, LWW + lossless conflict record, optional `contradicts` materialization |
| [`laplaspack_mcp.py`](./laplaspack_mcp.py) | **zero-dependency** MCP server — mount any pack into any MCP client (`find` · `open` · `directory` · `why` · `blind_spots`) |
| [`AUTHORING.md`](./AUTHORING.md) | **make your own** — with any AI chatbot, with Claude Code, or by hand |
| [`prompts/`](./prompts) · [`skills/`](./skills) | the copy-paste LMD compiler prompt + a drop-in Claude Code skill |
| [`HUB.md`](./HUB.md) | draft addressing + transfer semantics (`laplas://publisher/slug` — publish · fetch · grant · mount) |
| [`examples/`](./examples) | the demo pack + the LMD source it was compiled from |

## Status

**v3 draft.** The `thinks` table, populated `commits` provenance, and stable
opaque ids are implemented in the reference engine; packs built at earlier
versions rebuild automatically from their embedded source. Field names and
conformance levels may still move while the draft label is on.

Feedback, issues, and **independent implementations** are exactly what this repo
is for — if you build a reader or writer in another language, open an issue and
we'll link it here.

<br>

<div align="center">
  <sub>
    Built in Seoul by <b>◈ ISOMORPH</b> — the memory company.<br>
    <a href="https://laplas-landing.vercel.app">LAPLAS</a> ·
    <a href="https://laplas-manifesto.vercel.app">Manifesto</a> ·
    <a href="https://discord.gg/utU3U7kb3">Discord</a> ·
    MIT — see <a href="./LICENSE">LICENSE</a>
  </sub>
</div>
