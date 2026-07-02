# `.laplaspack` — an open format for portable AI memory

A `.laplaspack` is a **single file that holds a mind**: typed entities, their
properties, the causal links between them, and the dated human thoughts attached
to them — plus the canonical source it was compiled from and the provenance of
that build. It is designed to be **owned, verified, mounted, and moved**
independently of any model, app, or vendor.

Your memory should not live and die with someone else's server.

## Try it in 30 seconds

No install, no network, no model — the reference reader is a single
stdlib-only Python file:

```bash
git clone https://github.com/AnYejun/laplaspack && cd laplaspack

python3 laplaspack_reader.py examples/demo.laplaspack
#   entities=4  edges=3  thinks=2
#   causal roles: derived-from×2, supports×1

python3 laplaspack_reader.py examples/demo.laplaspack --why "Subscription is the core offer"
#   1. (derived-from) Single-origin only          [decision]
#   2. (derived-from) Direct trade doubles farm income  [proof]
#   3. (supports)     Own roastery in Mapo        [differentiator]

python3 laplaspack_reader.py examples/demo.laplaspack --todos
python3 laplaspack_reader.py examples/demo.laplaspack --json
```

If this runs, the format is readable by anyone — which is the point: memory you
own is memory you can leave with.

## What's in this repo

| File | What |
|---|---|
| [`SPEC.md`](./SPEC.md) | the container spec, v3 draft — SQLite tables, stable identity, provenance, signing, redaction, conformance levels |
| [`LMD_GRAMMAR.ebnf`](./LMD_GRAMMAR.ebnf) | the grammar of the canonical source (nodes · properties · 6 causal roles · `@@think@@` documents) |
| [`laplaspack_reader.py`](./laplaspack_reader.py) | the **zero-dependency** reference reader (Python stdlib only) |
| [`HUB.md`](./HUB.md) | draft addressing + transfer semantics (`laplas://publisher/slug` — publish · fetch · grant · mount) |
| [`examples/`](./examples) | a tiny demo pack + the LMD source it was compiled from |

## The one thing that makes it different

Structure is captured **at write-time**, so a pack carries its own *reasoning*.
`--why` above reconstructs the ordered causal ancestry of a claim from the
graph — it is not a re-ranking of prose, and a retriever cannot fabricate it
after the fact. That property is what makes a memory **verifiable, and
therefore portable**: the receipt travels with the fact.

The format is the contract; apps are just clients. [LAPLAS](https://laplas-landing.vercel.app)
builds a wallet (desktop), a showroom ([Manifesto](https://laplas-manifesto.vercel.app) —
a grounded concierge served from a pack), and a serving rail on top of it — all
reading and writing this same file.

## Status

**v3 draft.** The `thinks` table, populated `commits` provenance, and stable
opaque ids are implemented in the reference engine; packs built at earlier
versions rebuild automatically from their embedded source. Field names and
conformance levels may still change while the draft label is on. Feedback,
issues, and independent implementations are very welcome — that is what this
repo is for.

Community: [Discord](https://discord.gg/utU3U7kb3) · an [ISOMORPH](https://laplas-landing.vercel.app) project.

## License

MIT — see [LICENSE](./LICENSE). The spec text and the reference reader are both
yours to implement, fork, and ship against.
