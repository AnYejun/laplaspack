# The `.laplaspack` Format — Specification (v3 draft)

> **What this is.** A `.laplaspack` is a single, self-contained file that holds a
> unit of **structured, portable memory**: typed entities, their properties, the
> causal links between them, and the human thoughts attached to them — plus the
> canonical source they were compiled from, and the provenance of that build.
>
> It is designed to be **owned, verified, mounted, and moved** independently of
> any model or app. This document is the public contract for reading and writing
> one. A zero-dependency reference reader ships alongside it
> ([`laplaspack_reader.py`](./laplaspack_reader.py)); the canonical grammar of the
> source is [`LMD_GRAMMAR.ebnf`](./LMD_GRAMMAR.ebnf).
>
> Status: **draft**. `format_version` is **`3`**: the `thinks` table, populated
> `commits` provenance, and the **stable opaque-id** column (`entities.stable_id`,
> authored into the source as `>>id: lp_…`) are implemented. Packs built at 1/2
> rebuild automatically from source. License: the format is open; the reference
> implementation is provided for interoperability.

---

## 1. Design principles

1. **One file = one mind (or one lens of one).** A pack is portable by
   construction — copy it, sign it, send it, mount it. No server is required to
   read it.
2. **The source is canonical; the index is derived.** The human-authored
   **LMD** source (§4) is the source of truth and lives inside the pack
   (`lmd_source`). Every other table is a rebuildable projection of it. A reader
   that only trusts `lmd_source` can reconstruct everything else.
3. **Structure is captured at write-time, not guessed at read-time.** Entities,
   types, and causal links are authored (or compiled) when meaning is fresh —
   which is what makes provenance (§3.6) truthful rather than reconstructed.
4. **Atoms, not documents.** The unit of distribution is the property / link /
   think — not a blob of prose. This is what lets a pack be recomposed to a
   budget and cited at the claim level.

---

## 2. Container

A pack is a **SQLite database** (application_id/user_version optional). It MUST
be openable read-only by any SQLite client. All tables below are present in a
conformant pack; a reader MUST tolerate the absence of any *derived* table
(§2.2) and reconstruct from `lmd_source`.

### 2.1 Canonical tables (MUST)

```sql
manifest    (key TEXT PRIMARY KEY, value TEXT)         -- pack metadata (§2.3)
lmd_source  (shard_id TEXT PRIMARY KEY, content TEXT NOT NULL,
             commit_sha TEXT, time TEXT)               -- the canonical LMD (§4)
commits     (sha TEXT PRIMARY KEY, time TEXT, author TEXT, parents TEXT)  -- provenance (§3.6)
```

### 2.2 Derived tables (SHOULD; rebuildable from `lmd_source`)

```sql
entities    (id TEXT PRIMARY KEY, label TEXT NOT NULL, type TEXT, sigil TEXT,
             layer TEXT, refs INTEGER DEFAULT 0, fields_json TEXT,
             commit_sha TEXT, time TEXT)
edges       (src TEXT, dst TEXT, role TEXT, kind TEXT NOT NULL,
             commit_sha TEXT, time TEXT)               -- kind ∈ {knowing, subject}
thinks      (host TEXT, think_id TEXT, type TEXT, title TEXT, body TEXT,
             author TEXT, at TEXT, status TEXT, due TEXT,
             mentions_json TEXT, then_json TEXT, deleted INTEGER DEFAULT 0,
             commit_sha TEXT, time TEXT)               -- stored RAW; folded on read (§3.5)
schema_types(key TEXT PRIMARY KEY, label TEXT, sigil TEXT, color TEXT, layer TEXT)
```

### 2.3 Optional acceleration tables (MAY; never authoritative)

```sql
entities_fts     -- SQLite FTS5 over (label, fields); lexical recall
sparse_postings  (term, entity_id, weight)   -- learned-sparse index
embeddings       (entity_id, dim, vec BLOB)  -- float32 dense vectors (model in manifest.dense_model)
```

A pack with none of these is still fully valid — they are recall accelerators,
not content. A reader MUST NOT treat their absence as corruption.

### 2.4 `manifest` keys

| key | meaning |
|---|---|
| `format_version` | integer; `2` today, `3` = stable-ID model (§3.1) |
| `head_sha` | content hash of the LMD source this pack was built from (freshness gate) |
| `entity_count`, `edge_count`, `thinks_count` | build stats |
| `dense_model` | id of the embedding model, if `embeddings` is populated |
| `owner`, `sig`, `sig_alg` | signing (§3.7); `owner` = public key, `sig` = detached signature over the canonical bytes |

---

## 3. Semantics

### 3.1 Entity identity (the v2→v3 change)

Every entity has an `id`, a display `label`, and a `type`.

- **v2 (as-built):** `id = label.lower().replace(" ", "_")` — a slug derived from
  the label. Simple, human-legible, but **renaming an entity forks its identity**
  and there is no stable handle for cross-pack references.
- **v3 (implemented):** each entity also carries a **stable opaque id**
  (`stable_id`, a `lp_`-prefixed ULID) **authored into the source** as an
  `>>id:` field, so it survives both rebuild (ids live in the source, not minted
  at build) and **rename** (the id sits beside, not derived from, the label).
  This is the durable handle for versioning, cross-pack links, and a registry.
  The slug (`id`) remains the internal join key **and a v2 alias** — so old
  references by slug still resolve while new references use the opaque id. A
  source is migrated once by `assign_stable_ids()` (idempotent); capture assigns
  ids to new entities. **Writers MUST persist `stable_id` in the source and MUST
  NOT re-mint it at build time.**

`layer ∈ {subject, knowing}`: `subject` = the things (person, project, …);
`knowing` = reasoning objects (decision, insight, question, …). `sigil` is a
display glyph; `fields_json` is the entity's properties (§3.2).

### 3.2 Properties

An entity's properties are `fields_json` — an object of `key → value` scalars
(authored as `>>key: value`, §4.2). Reserved keys: `type`, `aliases`/`alias`,
`id`. Properties are adjectival facts about the entity; they are NOT a prose
document. (A value MAY itself reference another entity as `[[Ref]]`, in which
case it is ALSO an edge — see §3.3.)

### 3.3 Edges

`edges(src, dst, role, kind)`. `kind` partitions the graph:

- **`knowing` edges** — the reasoning DAG. `role` is one of the **six canonical
  causal roles**:
  `derived-from` · `supports` · `raises` · `closes` · `supersedes` · `contradicts`.
  These are what `recall_why` walks to reconstruct the causal chain behind a
  claim. `contradicts` is symmetric; the others are directed.
- **`subject` edges** — associations and containment (`part_of`, `belongs_to`,
  `has_part`, `contains`, `targets`, …) plus plain mentions.

Authored either as a field reference `>>derived-from: [[X]]` or an arrow line
`[[A]] →(role) [[B]]` (§4.3). Directed spellings and inverses normalize to a
canonical role (e.g. `raised-by` → `raises`).

### 3.4 Thinks

A **think** is a typed, dated, human thought attached to a host entity —
`thinks(host, think_id, type, …)`. `type` ∈
`question · decision · todo · hypothesis · insight · note`. A think carries
`body`, `author`, `at` (ISO time), optional `status`/`due` (for `todo`),
`mentions_json` (soft `@[[refs]]`), and `then_json` (the human `then>` sequence
linking a thought to its predecessor).

### 3.5 Fold-on-read (thinks are stored raw)

`thinks` rows are stored **raw** — every authored version, including
tombstones (`deleted=1`). The current state of a think is computed at read time:
**Last-Writer-Wins by `(host, think_id)`, newest `at` wins, tombstones remove.**
This is intentional: the pack keeps the full history; the reader folds it. A
conformant reader that wants "current todos" MUST apply this fold, not read rows
verbatim. (Entities are likewise merged field-wise across shards before
materialization.)

### 3.6 Provenance

`commits(sha, time, author, parents)` records the build lineage; every
`entities`/`edges`/`thinks` row is stamped with the `commit_sha` that produced
it and the `time`. A pack built from source stamps one commit = its `head_sha`.
Incremental commit history (multiple rows, real `parents`) is the v3+ growth
path. Provenance is **not decorative**: it is what lets a consumer answer "when,
and from which source revision, did this fact enter the pack."

### 3.7 Signing & integrity (trust layer)

A pack MAY be signed: `manifest.owner` = an Ed25519 public key, `manifest.sig` =
a detached signature (`sig_alg` names the scheme) over the canonical byte stream
(the ordered `lmd_source` shards + manifest identity fields). Verification is
**offline** and requires no service. An unsigned pack is valid but
unattributed; a signed pack lets a mounter verify *who* authored the memory
before trusting its contents. (Reference sealing lives in the desktop client;
promoting it into the engine export path is tracked separately.)

### 3.8 Redaction / partial views

Fields carry a visibility tier — `open` (default) · `masked` · `secret`. An
**export** MAY omit or mask non-`open` fields (and think bodies) to produce a
shareable partial view of a pack without leaking private reasoning. A reader
sees only what the exporter chose to include; there is no hidden channel. (Full
think-body redaction on export is a required trust fix, tracked for the desktop
export path.)

---

## 4. The source format: LMD (Laplas Markdown)

`lmd_source.content` is **LMD** — a small, human-writable, Markdown-compatible
grammar. The normative grammar is [`LMD_GRAMMAR.ebnf`](./LMD_GRAMMAR.ebnf); this
section is the readable summary. A `.md` file of LMD and the pack built from it
are two views of the same memory.

### 4.1 Node

```
## Structure at write-time, not read-time
[[Structure at write-time, not read-time]]
>>type: decision
>>rule: decompose context into typed nodes at capture, not query time.
```

A `## Heading` names a node; the `[[Heading]]` line declares it as an entity;
`>>key: value` lines are its properties. `>>type:` sets the entity type.

### 4.2 Property

`>>key: value` — one property. Value is free text; `>>key: [[Ref]]` makes the
value an edge to `Ref` (with `key` as the role if `key` is an edge role, §3.3).

### 4.3 Link (edge)

- Field form: `>>derived-from: [[LLMs are amnesiac]]`
- Arrow form: `[[A]] →(supersedes) [[B]]`

Roles: the six causal roles (§3.3) + containment forms. Unknown roles are
retained as `subject`-kind associations.

### 4.4 Think

```
@@decision on="LAPLAS" by=@yejun at=2026-06-20T10:00:00Z status=done id=d-42
The product is the memory, not the assistant.
then> d-17
@[[ISOMORPH]]
@@
```

A column-0 `@@<type> <attrs>` line opens a think; a line that is exactly `@@`
closes it. Attributes: `on=` (host, `"quoted"` if it has spaces), `by=@author`,
`at=` (ISO), `status=` / `due=` (todo), `id=`. Body lines: prose, plus
`then> <id>` (human sequence) and `@[[Ref]]` (soft mention). Types: the six
think types (§3.4).

---

## 5. Rebuild contract

Given only `lmd_source`, a conformant implementation MUST reproduce
`entities`, `edges`, `thinks`, and `schema_types` such that recall over the
rebuilt tables is equivalent to recall over the originals. This is the
**round-trip invariant** and the basis of the freshness gate: a pack is stale
iff `manifest.head_sha` ≠ the content hash of its current `lmd_source`. This is
why every derived table is disposable and why a third party can adopt the format
with only the source + this spec + the grammar.

---

## 6. Conformance levels

- **L0 — Reader.** Opens the SQLite file, reads `manifest` + `lmd_source`, lists
  entities/edges/thinks (from derived tables if present, else by parsing
  `lmd_source`). The reference reader is L0.
- **L1 — Recall.** Adds lexical + structural retrieval and the `recall_why`
  causal walk over the six roles.
- **L2 — Writer.** Parses LMD → materializes a pack (v3 stable IDs), stamps
  provenance, applies fold-on-read semantics.
- **L3 — Trust.** Verifies signatures, honors redaction tiers, refuses to
  surface `secret` fields on export.

---

## 7. Open questions (tracked)

- Stable-ID migration (v2 slugs → v3 opaque) + the alias-map format.
- Canonical byte-stream definition for signing (shard order, manifest subset).
- Delta/patch packs (subscribe to another pack's updates) vs full rebuild.
- Untrusted-pack safety: a mounted pack's contents enter an LLM context; the
  spec must define an isolation / provenance-labeling contract before packs are
  traded between strangers.

*This spec is generated from the reference engine (`laplas_engine`) and kept in
lockstep with it. Discrepancies between this document and the code are bugs in
this document.*
