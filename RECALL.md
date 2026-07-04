# Recall — the Query Surface of a `.laplaspack`

> **What this is.** The operator contract for *querying* a pack: the small,
> typed set of operations an agent (or a person) uses to navigate structured
> memory. The [format spec](./SPEC.md) defines what a pack **is**;
> this document defines how one is **asked**.
>
> The analogy is deliberate: SQLite is a file format *plus* SQL. A
> `.laplaspack` is a file format *plus* recall. An implementation that speaks
> these operators can serve any pack; an agent that emits them can run on any
> implementation.
>
> Status: **draft**, describes the reference implementation as shipped.

---

## 1. The model

Recall is **navigation, not generation**. A query never returns prose composed
by a model; it returns **Cards** — structured projections of nodes — which the
caller (usually an LLM inside a harness) reads and cites. Three consequences:

1. **Deterministic.** The same pack + the same operator call ⇒ the same cards.
   Rankers (BM25, learned-sparse, dense) affect *order*, never *content*.
2. **Budgeted.** Every operator returns a bounded set (`k`, `limit`, truncated
   field text). The whole-source dump is not an operator, by design: the LMD
   source is the *write* format, never the *read* path.
3. **Receipted.** Cards carry ids and provenance, so every downstream claim is
   attributable to the node it came from. "Cited / explored" counts fall out
   of the operator log for free.

## 2. The currency: `Card`

Every operator returns a `RetrievalResult` — an ordered list of Cards plus the
operator's name (for the receipt log).

```
Card {
  id:         str            # stable node id (SPEC §3, `>>id: lp_…`)
  label:      str
  type:       str            # schema type ("person", "decision", …)
  layer:      str            # "subject" (entity) | "knowing" (thought)
  fields:     {name: value}  # properties, values truncated to a per-call budget
  stubs:      [Stub]         # typed edges: {rel, target_id, target_label,
                             #   target_type, direction: parent|child|neighbor}
  provenance: {commit, author, time} | null
  flags:      ["open" | "contradicted" | "superseded"]
}
```

A Card is a *summary with handles*: enough to answer from, plus the ids needed
to go deeper (`expand`, `recall_why`). `to_text()` renders a result as a
compact, human-readable briefing — the only string that should ever reach a
model's context.

## 3. Core operators (conformance: every consumer)

These four are the minimum for a conforming **consumer** (an implementation
that can serve an existing pack — SPEC §6 level 1). All are derivable from the
pack's tables alone.

| Operator | Signature | Semantics |
|---|---|---|
| `find` | `(query, k=5)` | Hybrid candidate search over nodes: FTS5/BM25 ∪ learned-sparse ∪ dense (each layer optional, silently additive). Returns the top-k Cards. The entry point for "where is X?" |
| `expand` | `(entity_id)` | Open one node fully: all properties, all typed edges, attached thoughts. The "SELECT * on a row + its joins". |
| `recall_why` | `(entity_id, depth=6)` | Walk the **causal ancestry** — `because`/`then` edges — from a node, oldest-first, then the node's own thoughts in `then`-order. Answers "why is this so?" with lineage, not similarity. |
| `match` | `(type=, layer=, flags=, role=, target_type=, in_endeavor=, limit=200)` | Typed pattern query — the WHERE-clause of memory. All constraints AND-ed; `role`/`target_type` filter by edge shape ("everything that `owns` a `service`"). No free text involved. |

`find` locates; `match` filters; `expand` opens; `recall_why` explains.
An agent loop needs nothing else to be grounded.

## 4. Navigational operators (the thought layer & the working set)

Shipped by the reference implementation; recommended for any interactive
consumer.

| Operator | Signature | Semantics |
|---|---|---|
| `recall_thinks` | `(query, k=6, types=, open_only=)` | Search the **thought layer** (`thinks` table): todos, questions, decisions, insights — filterable by type and open/closed status. Entities answer *what*; thinks answer *why/what-next*. |
| `recall_open` | `()` | The open loops: unresolved todos & questions across the pack. "What's in motion?" |
| `recall_conflicts` | `(entity=None)` | Nodes whose properties are in active contradiction (flagged at merge or capture). Disagreement is surfaced, never silently resolved. |
| `anchors` | `(limit=300)` | A ranked directory of the graph (label + type only) — the map an agent scans before it queries. Deliberately tiny: labels, not content. |
| `recall_facts` | `(entity)` | The properties of one node, without edges — the cheap read. |

## 5. `route_recall` — the natural-language front door

`route_recall(query) → briefing` maps a natural-language question onto the
operators above (why-questions → `recall_why`, "stuck/what now" →
`recall_open` + open thinks, conflict words → `recall_conflicts`, everything
else → `find` + thinks) and renders the result with `to_text()`.

It exists so a *thin* client can be grounded with one call. A full agent
harness should prefer the typed operators directly — emitting them is how the
LLM "writes queries" instead of receiving dumps.

## 6. What is deliberately absent

- **`dump_all` / whole-source read.** Not an operator. Exporting the LMD
  source is a *file* operation (it's your file), not a *recall* operation; a
  model that wants everything must page through `anchors` + `expand` and leave
  a receipt trail while doing it.
- **Write operators.** Recall is read-only. Writes go through the capture/
  commit path (and in served settings, through a staged `propose_commit` that
  a human approves) — never through the query surface.

## 7. Conformance

- **Consumer, level 1** (SPEC §6): implements §3 over the pack tables.
- **Consumer, level 2**: adds §4 and `route_recall`.
- Rankings may differ between implementations (different sparse/dense models);
  **membership may not**: a node retrievable by `match`/`expand`/`recall_why`
  in one conforming implementation must be retrievable in all — those three
  are exact, not ranked.
