# `.laplaspack` Versioning & Compatibility Pledge

> **What this is.** The rules under which the `.laplaspack` format is allowed to
> change — and the guarantees a pack holder gets in return. A memory you can
> *own* is a memory that still opens in ten years; this document is that promise,
> stated precisely enough to be falsifiable.
>
> Companion to the [format specification](./SPEC.md). Status: applies
> from `format_version: 3`.

---

## 0. The pledge

1. **Every future reader reads every past pack.** An engine at any future
   version opens any pack written at `format_version ≥ 1`, without data loss.
2. **A pack written today stays readable at least through 2035** — and
   structurally, forever (see §1: the guarantee does not depend on us existing).
3. **No release may break this.** A frozen corpus of packs from every released
   format version is part of the engine's test suite (§4); a change that fails
   to open one of them does not ship.

## 1. Why this pledge is cheap to keep (the structural guarantee)

The spec's second design principle does the heavy lifting:
**the source is canonical; the index is derived** ([SPEC §1](./SPEC.md#1-design-principles),
[§5 Rebuild contract](./SPEC.md#5-rebuild-contract)).

A pack carries its own human-readable LMD source (`lmd_source`). Every other
table — entities, edges, thinks, FTS, sparse/dense postings — is a rebuildable
projection of that text. Therefore:

- **The universal migration is `rebuild`.** A newer engine that meets an older
  pack does not need bespoke per-version converters: it re-parses `lmd_source`
  with the current parser and materializes the current tables. This is not
  aspirational — it is how versions 1 and 2 open today (the engine's
  `open_or_build_index` gate rebuilds on any `format_version` mismatch).
- **Even a dead reader leaves readable memory.** The grammar
  ([LMD_GRAMMAR.ebnf](./LMD_GRAMMAR.ebnf)) and a zero-dependency reference
  reader ([laplaspack_reader.py](./laplaspack_reader.py)) are public. If every
  implementation vanished, the pack still opens with SQLite and reads as text.
  The pledge in §0 is a promise about *convenience*; the floor is physics.

## 2. What each kind of change is allowed to do

Version changes are classified by what they demand of readers.

**Minor (additive) — no `format_version` bump required.**
- New tables, new columns with defaults, new manifest keys, new LMD constructs
  that older parsers may safely skip.
- Rules: writers write the newest shape; **readers must ignore what they do not
  understand and must preserve it on rewrite** (protobuf's unknown-field rule).
  Never reuse or repurpose an existing name.

**Format bump (`format_version: N → N+1`).**
- Changes to the meaning or shape of existing tables/columns, new required
  invariants (e.g. v3's stable ids).
- Rules: the bump ships **in the same release** as (a) automatic rebuild-on-open
  for all prior versions, and (b) where semantics moved, a compatibility bridge
  in the reader (v3 keeps v2 slug ids resolvable as aliases). A pack is
  *upgraded on write, never on read*: opening an old pack must not mutate it.

**Forbidden, at any version.**
- Deleting or rewriting `lmd_source` content during migration.
- Any change that makes a previously-valid pack unreadable, or that alters
  provenance (`commits`) retroactively.

## 3. Version history

| `format_version` | Shipped | What changed | How older packs open |
|---|---|---|---|
| 1 | 2026-06 | Base container: manifest · entities · edges · fields · FTS · sparse | — |
| 2 | 2026-07 | `thinks` table (the thought layer); freshness gate learns `format_version` | rebuild from source |
| 3 | 2026-07 | Stable opaque ids (`entities.stable_id`, authored as `>>id: lp_…`); populated `commits` provenance; `lmd_source` round-trip guarantee ([SPEC §5](./SPEC.md#5-rebuild-contract)) | rebuild from source; v2 slugs remain resolvable as aliases |

## 4. The golden corpus (how the pledge is enforced)

The engine repository keeps `tests/golden/` — a directory of **frozen pack
files, one or more per released format version, that are never edited after
being added**. CI opens every one of them and asserts the conformance-level-1
operations ([SPEC §6](./SPEC.md#6-conformance-levels)) still work:
open, hydrate, `find`, `expand`, `recall_why`.

Releasing a format change therefore has exactly one honest path: make the new
engine pass the old packs, then add the new version's pack to the corpus.

## 5. What `format_version` means operationally

- It lives in the `manifest` table (`format_version` key), written at build time.
- Readers compare it (together with the content head and semantic-model ids) in
  the freshness gate; **any mismatch means "rebuild from `lmd_source`", never
  "refuse to open"**. Refusal is reserved for packs whose `lmd_source` is
  missing *and* whose tables are unreadable — i.e. corruption, not age.
