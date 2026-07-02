#!/usr/bin/env python3
"""
laplaspack_reader — a ZERO-DEPENDENCY reference reader for the .laplaspack format.

Proof that the format is open: this file uses only the Python standard library
(sqlite3, json, argparse) and reads any conformant pack per LAPLASPACK_SPEC.md.
It reconstructs the two things that matter — the graph and the thoughts — and
applies the two semantics a naive SELECT would get wrong: think fold-on-read
(Last-Writer-Wins by (host, id), newest `at`, tombstones removed, §3.5) and the
recall_why causal walk over the six roles (§3.3).

    python3 laplaspack_reader.py mypack.laplaspack            # summary
    python3 laplaspack_reader.py mypack.laplaspack --entity "LAPLAS"
    python3 laplaspack_reader.py mypack.laplaspack --why "Structure at write-time, not read-time"
    python3 laplaspack_reader.py mypack.laplaspack --todos
    python3 laplaspack_reader.py mypack.laplaspack --json

No network, no service, no model. If this runs, the format is readable by anyone.
"""
from __future__ import annotations
import argparse
import json
import sqlite3
import sys

def _slug(name: str) -> str:
    # v2 identity derivation (SPEC §3.1): edges reference entities by name; the
    # entity id is the slugified label. v3 replaces this with opaque ids.
    return (name or "").strip().lower().replace(" ", "_")


DAG_ROLES = ("derived-from", "supports", "raises", "closes", "supersedes", "contradicts")
# For an X-sourced edge, the PARENT (cause) is the target for these roles:
PARENT_IS_TARGET = {"derived-from", "supersedes", "closes"}
# For an edge INTO X, the parent is the source for these:
PARENT_IS_SOURCE = {"supports", "raises"}


def _table_exists(con: sqlite3.Connection, name: str) -> bool:
    return con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def _manifest(con) -> dict:
    if not _table_exists(con, "manifest"):
        return {}
    return {k: v for k, v in con.execute("SELECT key, value FROM manifest")}


def _entities(con) -> dict:
    out = {}
    if not _table_exists(con, "entities"):
        return out
    # stable_id (v3) may be absent on older packs — select defensively
    cols = "id, label, type, layer, fields_json"
    has_sid = any(c[1] == "stable_id" for c in con.execute("PRAGMA table_info(entities)"))
    if has_sid:
        cols += ", stable_id"
    for r in con.execute(f"SELECT {cols} FROM entities"):
        try:
            fields = json.loads(r[4] or "{}")
        except Exception:
            fields = {}
        out[r[0]] = {"id": r[0], "label": r[1], "type": r[2], "layer": r[3],
                     "fields": fields, "stable_id": (r[5] if has_sid else None)}
    return out


def _edges(con) -> list:
    if not _table_exists(con, "edges"):
        return []
    return [{"src": s, "dst": d, "role": role, "kind": kind}
            for s, d, role, kind in con.execute("SELECT src, dst, role, kind FROM edges")]


def _folded_thinks(con) -> list:
    """Apply §3.5 fold-on-read: raw rows → current state, LWW by (host, id)."""
    if not _table_exists(con, "thinks"):
        return []
    rows = list(con.execute(
        "SELECT host, think_id, type, title, body, author, at, status, due, deleted "
        "FROM thinks"))
    latest: dict = {}
    for (host, tid, typ, title, body, author, at, status, due, deleted) in rows:
        key = (host, tid) if tid else (host, (body or "")[:60])
        prev = latest.get(key)
        if prev is None or (at or "") >= (prev["at"] or ""):   # newest at wins
            latest[key] = {"host": host, "id": tid, "type": typ, "title": title,
                           "body": body, "author": author, "at": at, "status": status,
                           "due": due, "deleted": bool(deleted)}
    return [t for t in latest.values() if not t["deleted"]]


def why(con, label: str) -> list:
    """recall_why (§3.3): walk the causal DAG upstream from an entity, following
    the six roles in their parent direction. Returns the ordered ancestry."""
    ents = _entities(con)
    # resolve label → id (exact, then case-insensitive)
    anchor = next((e["id"] for e in ents.values() if e["label"] == label), None)
    if anchor is None:
        anchor = next((e["id"] for e in ents.values()
                       if e["label"].lower() == label.lower()), None)
    if anchor is None:
        return []
    edges = _edges(con)
    chain, seen, frontier = [], {anchor}, [anchor]
    while frontier:
        cur = frontier.pop(0)
        parents = []
        for e in edges:
            if e["role"] not in DAG_ROLES:
                continue
            esrc, edst = _slug(e["src"]), _slug(e["dst"])   # edges store names; join by slug
            if esrc == cur and e["role"] in PARENT_IS_TARGET:
                parents.append((e["role"], edst))
            elif edst == cur and e["role"] in PARENT_IS_SOURCE:
                parents.append((e["role"], esrc))
        for role, pid in parents:
            if pid in seen:
                continue
            seen.add(pid)
            p = ents.get(pid, {"label": pid, "type": "?"})
            chain.append({"role": role, "id": pid, "label": p["label"], "type": p.get("type")})
            frontier.append(pid)
    return chain


def summarize(path: str) -> dict:
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        man = _manifest(con)
        ents = _entities(con)
        edges = _edges(con)
        thinks = _folded_thinks(con)
        by_role: dict = {}
        for e in edges:
            by_role[e["role"]] = by_role.get(e["role"], 0) + 1
        return {"manifest": man, "counts": {
            "entities": len(ents), "edges": len(edges), "thinks": len(thinks)},
            "edge_roles": by_role, "entities": ents, "edges": edges, "thinks": thinks}
    finally:
        con.close()


def main() -> int:
    ap = argparse.ArgumentParser(description="Reference reader for .laplaspack (zero deps).")
    ap.add_argument("pack")
    ap.add_argument("--entity", help="show one entity's properties + links")
    ap.add_argument("--why", help="show the causal ancestry of an entity (recall_why)")
    ap.add_argument("--todos", action="store_true", help="list open todos (folded)")
    ap.add_argument("--json", action="store_true", help="dump the whole reconstruction as JSON")
    a = ap.parse_args()

    s = summarize(a.pack)
    if a.json:
        print(json.dumps(s, ensure_ascii=False, indent=2)); return 0

    if a.why:
        chain = why(sqlite3.connect(f"file:{a.pack}?mode=ro", uri=True), a.why)
        print(f"why «{a.why}» — {len(chain)} ancestor(s):")
        for i, n in enumerate(chain, 1):
            print(f"  {i}. ({n['role']}) {n['label']}  [{n['type']}]")
        return 0

    if a.entity:
        e = next((v for v in s["entities"].values()
                  if v["label"].lower() == a.entity.lower()), None)
        if not e:
            print(f"no entity: {a.entity}"); return 1
        sid = f"  id={e['stable_id']}" if e.get("stable_id") else ""
        print(f"◈ {e['label']}  ({e['type']}, layer={e['layer']}){sid}")
        for k, v in e["fields"].items():
            print(f"  »{k}: {v}")
        links = [x for x in s["edges"] if _slug(x["src"]) == e["id"] or _slug(x["dst"]) == e["id"]]
        for x in links:
            out_edge = _slug(x["src"]) == e["id"]
            arrow, other = ("→", x["dst"]) if out_edge else ("←", x["src"])
            print(f"  {arrow}({x['role']}) {other}")
        return 0

    if a.todos:
        todos = [t for t in s["thinks"] if t["type"] == "todo" and t.get("status") != "done"]
        print(f"{len(todos)} open todo(s):")
        for t in todos:
            due = f"  (due {t['due']})" if t.get("due") else ""
            print(f"  ☐ {t['title'] or (t['body'] or '')[:60]}  @{t['host']}{due}")
        return 0

    # default: summary
    m = s["manifest"]
    print(f"laplaspack: {a.pack}")
    print(f"  format_version = {m.get('format_version', '?')}   head_sha = {(m.get('head_sha') or '')[:12]}")
    if m.get("owner"):
        print(f"  owner = {m['owner'][:24]}")
    if m.get("sig"):
        # presence only — checking it is laplaspack_seal.py's job (needs Ed25519,
        # which the stdlib doesn't have; this reader stays zero-dependency)
        print(f"  seal  = {m.get('sig_alg', '?')} key {m.get('sig_pubkey', '')[:16]}…  "
              f"(check: laplaspack_seal.py verify)")
    else:
        print("  seal  = none (unsigned)")
    c = s["counts"]
    print(f"  entities={c['entities']}  edges={c['edges']}  thinks={c['thinks']}")
    print(f"  causal roles: " + ", ".join(f"{k}×{v}" for k, v in s["edge_roles"].items()
                                          if k in DAG_ROLES) or "  (none)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
