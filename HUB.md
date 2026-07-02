# Laplas Hub — `laplas://` addressing & registry (v0)

The Hub is the rail on which a `.laplaspack` **moves between parties**: publish →
fetch → mount, addressed by a `laplas://` URI, verified by a content hash. v0 is
the minimum that makes ONE stranger-to-stranger transaction real — the inflection
the whole distribution thesis turns on: a pack produced by one person, fetched
and mounted by a stranger, with `recall_why` receipts working on the other side.

It is built on the existing rails, not greenfield: it salvages ACP-v0.1's
`<type>/<name>` object addressing + `{read/write/denied}` permission shape, the
current AX auth (unguessable `workspace_id`, token, `_require_pack`), and the
engine's stable ids + provenance.

## Addressing

```
laplas://<publisher>/<slug>[@<version>][#<stable_id>]
```

- **publisher** — a workspace's unique handle (e.g. `alice-co`).
- **slug** — the pack name, slugified (`founder-soul`).
- **version** — an integer, incremented on every publish; **immutable** once
  written. Omit to mean "latest".
- **#stable_id** — optionally address one entity inside the pack by its opaque
  `lp_…` id (SPEC §3.1) — the durable, rename-proof handle.

Example: `laplas://alice-co/founder-soul@1`.

## Lifecycle

1. **Publish** — `POST /hub/publish {token, pack, name, slug?, description?, visibility}`.
   The caller's workspace pack (resolved via `_require_pack`, so LFI-safe) is
   snapshotted into an **immutable version file**; its `sha256` is stored as the
   integrity hash; the registry entry is created/updated. Returns the
   `laplas://` address + version + integrity.
2. **Discover** — `GET /hub/pack/{publisher}/{slug}` returns metadata (name,
   description, latest version, integrity, fetch count) if the caller may read it.
3. **Fetch** — `GET /hub/fetch/{publisher}/{slug}[?version=]` returns the pack
   bytes with `X-Laplas-Integrity` + `X-Laplas-Address` headers, iff public or
   granted. This is the move.
4. **Mount** — `POST /hub/mount {token, address}` (consumer side): fetch a
   readable pack, **verify integrity**, and add it to the caller's workspace
   **read-only** (as an `up_…` pack, labeled with its provenance
   `name · from <publisher>`). It then appears in the memory picker and can be
   recalled / asked — `recall_why` works on the fetched graph.
5. **Grant / revoke** — `POST /hub/grant|revoke {token, address, grantee}` — the
   owner opens/closes read access to a **private** pack for another handle (ACP
   `read` set). Public packs skip this.
6. **List** — `GET /hub/list` — your published packs + versions + fetch counts,
   and your publisher handle.

## Trust model (v0)

- **Integrity** — `sha256:` over the pack bytes, computed on publish (after any
  v2→v3 settle) and re-verified on mount. Detects tampering/corruption in transit.
- **Identity** — publish is workspace-authenticated; the address namespace
  (`publisher/`) is owned by one workspace (name-squatting rejected). **Ed25519
  signing** of the pack (`manifest.owner`/`sig`, SPEC §3.7) is the next step —
  deferred to when engine-path sealing lands; v0 relies on integrity + authed
  publish.
- **Access** — `public` (read: everyone) or `private` (read: owner + explicit
  grantees), the ACP-v0.1 permission shape.
- **Untrusted-pack safety** — a mounted pack's contents enter the consumer's
  recall/LLM context. v0 mounts **read-only** (never merged into the consumer's
  own pack), labels the source + publisher, and carries the integrity hash.
  Prompt-injection from a hostile pack's fields is a known, tracked risk;
  quarantine/label hardening is the next trust increment before packs are traded
  at scale.

## Explicitly out of scope for v0

Payments/royalties, delta/subscribe (pull another pack's updates), public
discovery/search, ratings, CDN/large-scale storage. v0 = one transaction working
on the Fly volume; the marketplace narrative stays off until these rails have
paying use.

*Endpoints live in `LAPLAS_AX/laplas_ax/server.py`; storage in `store.py`
(`hub_packs` / `hub_versions` / `hub_grants`). This file is the public contract.*
