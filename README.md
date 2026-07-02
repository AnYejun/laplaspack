<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/mark-dark.svg">
  <img src="assets/mark-light.svg" width="92" alt="the LAPLAS mark — concentric diamonds">
</picture>

# `.laplaspack`

**The open format for portable AI memory.**<br>
One file that holds a mind — typed entities, causal links, human thoughts, and the provenance of how they got there.

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

## Why write-time structure

Every memory system answers *what*. Almost none can answer ***why*** — because
retrieval-time systems re-rank prose after the fact, and the reasoning was never
captured. A `.laplaspack` is compiled **at the moment of writing**: decisions,
evidence, and links land as a typed graph, so the receipt travels with the fact.

That property — memory that can **show its work, offline, to anyone** — is what
makes a mind verifiable, and therefore portable.

## Anatomy of a pack

```text
demo.lmd  ──(compile)──▶  demo.laplaspack        one SQLite file
─────────────────────────────────────────────────────────────────
[[Node]] + >>properties        entities           typed nodes
→(derived-from) links          edges              6 causal roles
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
| [`SPEC.md`](./SPEC.md) | the container spec, **v3 draft** — tables, stable identity, provenance, signing, redaction, conformance levels |
| [`LMD_GRAMMAR.ebnf`](./LMD_GRAMMAR.ebnf) | the grammar of the canonical source (nodes · properties · 6 causal roles · `@@think@@`) |
| [`laplaspack_reader.py`](./laplaspack_reader.py) | the **zero-dependency** reference reader (Python stdlib only) |
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
