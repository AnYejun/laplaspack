#!/usr/bin/env python3
"""
laplaspack_merge — ZERO-DEPENDENCY reference merge for .laplaspack files.

Merging two minds is mechanical when identity is DECLARED. This tool implements
the declared-identity merge (SPEC §MERGE, class 2): entities unify by authored
`stable_id`; field conflicts resolve last-writer-wins with the losing value
preserved losslessly; disagreement can be materialized as first-class
`contradicts` edges instead of being erased. No model, no service — merge is a
closed-schema operation precisely because identity was written down at
write-time.

    python3 laplaspack_merge.py a.laplaspack b.laplaspack -o merged.laplaspack
    python3 laplaspack_merge.py a.laplaspack b.laplaspack -o merged.laplaspack \\
        --conflicts materialize --report report.json

Semantics (deterministic; B is "theirs", A is "ours"):
  entities   same stable_id → ONE node. Fields merge per-key: later commit time
             wins; every losing value is preserved in fields_json under
             `_conflicts` with {value, from, time}. Newer label wins; the older
             label is kept as an `aka` field. Entities without a stable_id
             match by id (slug) — a label collision WITHOUT a shared stable_id
             is refused (identity must be declared, not guessed).
  edges      set-union on (src, dst, role, kind), label-space rewritten to the
             surviving labels.
  thinks     row-union — the think fold (LWW by (host,id), SPEC §3.5) already
             makes this safe; readers fold on read.
  lmd_source shards from both packs are kept (collisions namespaced), so the
             merged pack still carries its full canonical source.
  commits    union + ONE new merge commit whose `parents` lists both heads.
  seal       a merge produces NEW content → the output is intentionally
             UNSEALED; re-sign it with laplaspack_seal.py.

--conflicts record       (default) lossless `_conflicts` record + report
--conflicts materialize  ALSO create a sibling node per conflicting claim and a
                         `contradicts` edge — disagreement becomes queryable
                         graph structure ("A and B disagree about X").
Exit codes: 0 merged · 1 identity error (undeclared collision) · 2 usage.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone

ENT_COLS = "id, label, type, sigil, layer, refs, fields_json, commit_sha, time, stable_id"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS manifest (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS lmd_source (
  shard_id TEXT PRIMARY KEY, content TEXT NOT NULL, commit_sha TEXT, time TEXT
);
CREATE TABLE IF NOT EXISTS entities (
  id TEXT PRIMARY KEY, label TEXT NOT NULL, type TEXT, sigil TEXT,
  layer TEXT, refs INTEGER DEFAULT 0, fields_json TEXT, commit_sha TEXT, time TEXT,
  stable_id TEXT
);
CREATE INDEX IF NOT EXISTS idx_entities_stable ON entities(stable_id);
CREATE TABLE IF NOT EXISTS edges (
  src TEXT NOT NULL, dst TEXT NOT NULL, role TEXT, kind TEXT NOT NULL,
  commit_sha TEXT, time TEXT
);
CREATE INDEX IF NOT EXISTS idx_edges_src  ON edges(src);
CREATE INDEX IF NOT EXISTS idx_edges_dst  ON edges(dst);
CREATE INDEX IF NOT EXISTS idx_edges_role ON edges(role);
CREATE TABLE IF NOT EXISTS commits (
  sha TEXT PRIMARY KEY, time TEXT, author TEXT, parents TEXT
);
CREATE TABLE IF NOT EXISTS thinks (
  host TEXT NOT NULL, think_id TEXT, type TEXT, title TEXT, body TEXT,
  author TEXT, at TEXT, status TEXT, due TEXT,
  mentions_json TEXT, then_json TEXT, deleted INTEGER DEFAULT 0,
  commit_sha TEXT, time TEXT
);
CREATE INDEX IF NOT EXISTS idx_thinks_host ON thinks(host);
"""


def slug(label: str) -> str:
    return (label or "").strip().lower().replace(" ", "_")


def load(path: str) -> dict:
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    d = {
        "path": path,
        "name": os.path.basename(path),
        "manifest": {r["key"]: r["value"] for r in con.execute("SELECT key, value FROM manifest")},
        "entities": [dict(r) for r in con.execute(f"SELECT {ENT_COLS} FROM entities")],
        "edges": [dict(r) for r in con.execute("SELECT src, dst, role, kind, commit_sha, time FROM edges")],
        "thinks": [dict(r) for r in con.execute(
            "SELECT host, think_id, type, title, body, author, at, status, due,"
            " mentions_json, then_json, deleted, commit_sha, time FROM thinks")],
        "shards": [dict(r) for r in con.execute("SELECT shard_id, content, commit_sha, time FROM lmd_source")],
        "commits": [dict(r) for r in con.execute("SELECT sha, time, author, parents FROM commits")],
    }
    con.close()
    return d


def merge_entities(A: dict, B: dict, mode: str, report: dict):
    """Unify by stable_id; refuse undeclared label collisions; LWW fields with
    lossless loser preservation. Returns (entities, rename_map_per_pack, extra_nodes, extra_edges)."""
    out: dict[str, dict] = {}          # merged-id -> row
    by_sid: dict[str, str] = {}        # stable_id -> merged-id
    rename = {A["name"]: {}, B["name"]: {}}   # per-pack: old label -> surviving label
    extra_nodes: list[dict] = []
    extra_edges: list[tuple[str, str, str]] = []

    def key_time(row):  # merge order: later time wins ties deterministically
        return (row.get("time") or "", row.get("id") or "")

    for pack in (A, B):
        for row in sorted(pack["entities"], key=key_time):
            row = dict(row)
            try:
                row["fields"] = json.loads(row.pop("fields_json") or "{}")
            except Exception:
                row["fields"] = {}
            row["_from"] = pack["name"]
            sid = row.get("stable_id")
            hit = by_sid.get(sid) if sid else None
            if hit is None and row["id"] in out:
                # same slug from both packs — only mergeable when identity is DECLARED
                prev = out[row["id"]]
                if sid and prev.get("stable_id") == sid:
                    hit = row["id"]
                elif prev.get("stable_id") or sid:
                    hit = None if prev.get("stable_id") == sid else "__COLLIDE__"
                else:
                    hit = "__COLLIDE__"
            if hit == "__COLLIDE__":
                prev = out[row["id"]]
                report["errors"].append(
                    f"identity collision: [[{row['label']}]] ({pack['name']}) and "
                    f"[[{prev['label']}]] ({prev['_from']}) share id '{row['id']}' but declare no "
                    f"common stable_id — declare >>id: on both (same thing) or rename one (different things)")
                continue
            if hit is None:
                out[row["id"]] = row
                if sid:
                    by_sid[sid] = row["id"]
                continue
            # ── unify into out[hit] ──
            base = out[hit]
            newer, older = (row, base) if key_time(row) > key_time(base) else (base, row)
            merged = dict(newer)
            merged["fields"] = dict(newer["fields"])
            conflicts = dict(newer["fields"].get("_conflicts") or {})
            for k, v in older["fields"].items():
                if k.startswith("_"):
                    continue
                if k not in merged["fields"]:
                    merged["fields"][k] = v
                elif str(merged["fields"][k]) != str(v):
                    conflicts.setdefault(k, []).append(
                        {"value": v, "from": older["_from"], "time": older.get("time")})
                    report["field_conflicts"].append({
                        "entity": merged["label"], "stable_id": sid, "field": k,
                        "kept": merged["fields"][k], "kept_from": newer["_from"],
                        "lost": v, "lost_from": older["_from"]})
                    if mode == "materialize" and k in ("what", "why"):
                        alt_label = f"{older['label']} · per {older['_from']}"
                        extra_nodes.append({
                            "id": slug(alt_label), "label": alt_label, "type": older.get("type"),
                            "sigil": None, "layer": older.get("layer") or "",
                            "refs": 0, "fields": {k: v, "of": older["label"], "src_pack": older["_from"]},
                            "commit_sha": older.get("commit_sha"), "time": older.get("time"),
                            "stable_id": None, "_from": older["_from"]})
                        extra_edges.append((alt_label, merged["label"], "contradicts"))
            if conflicts:
                merged["fields"]["_conflicts"] = conflicts
            if older["label"] != newer["label"]:
                merged["fields"].setdefault("aka", older["label"])
                rename[older["_from"]][older["label"]] = newer["label"]
                report["label_unifications"].append(
                    {"kept": newer["label"], "aka": older["label"], "stable_id": sid})
            # surviving row keeps the NEWER slug id; map the older slug away
            if older["id"] != newer["id"] and older["id"] in out:
                out.pop(older["id"], None)
            out[newer["id"]] = merged
            if sid:
                by_sid[sid] = newer["id"]
            report["unified"] += 1
    return out, rename, extra_nodes, extra_edges


def main() -> int:
    ap = argparse.ArgumentParser(description="Merge two .laplaspack files (declared-identity, SPEC §MERGE).")
    ap.add_argument("a"); ap.add_argument("b")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--name", help="merged pack name")
    ap.add_argument("--owner", default="", help="owner recorded in the merged manifest")
    ap.add_argument("--conflicts", choices=["record", "materialize"], default="record",
                    help="record: lossless _conflicts field (default) · materialize: + contradicts edges")
    ap.add_argument("--report", help="write the merge report as JSON to this path")
    a = ap.parse_args()

    A, B = load(a.a), load(a.b)
    report = {"a": a.a, "b": a.b, "unified": 0, "field_conflicts": [],
              "label_unifications": [], "errors": []}

    ents, rename, extra_nodes, extra_edges = merge_entities(A, B, a.conflicts, report)
    if report["errors"]:
        for e in report["errors"]:
            print(f"error: {e}", file=sys.stderr)
        print(f"\n{len(report['errors'])} identity error(s) — nothing written. "
              f"Declared identity is the contract that makes merge mechanical.", file=sys.stderr)
        return 1
    for n in extra_nodes:
        ents.setdefault(n["id"], n)

    # edges: rewrite renamed labels, then set-union
    edge_set: dict[tuple, dict] = {}
    for pack in (A, B):
        rmap = rename[pack["name"]]
        for e in pack["edges"]:
            src = rmap.get(e["src"], e["src"]); dst = rmap.get(e["dst"], e["dst"])
            edge_set.setdefault((src, dst, e["role"], e["kind"]),
                                {**e, "src": src, "dst": dst})
    for (src, dst, role) in extra_edges:
        edge_set.setdefault((src, dst, role, "knowing"),
                            {"src": src, "dst": dst, "role": role, "kind": "knowing",
                             "commit_sha": None, "time": None})

    # thinks: row union (fold is read-time); rewrite renamed hosts
    think_rows: list[dict] = []
    seen_t = set()
    for pack in (A, B):
        rmap = {slug(k): slug(v) for k, v in rename[pack["name"]].items()}
        for t in pack["thinks"]:
            t = dict(t); t["host"] = rmap.get(t["host"], t["host"])
            sig = (t["host"], t.get("think_id"), t.get("at"), (t.get("body") or "")[:80])
            if sig in seen_t:
                continue
            seen_t.add(sig); think_rows.append(t)

    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    heads = [p["manifest"].get("head_sha") or (p["commits"][-1]["sha"] if p["commits"] else "")
             for p in (A, B)]
    msha = hashlib.sha256(("merge|" + "|".join(sorted(filter(None, heads))) + "|" +
                           str(sorted(ents))).encode()).hexdigest()[:16]

    if os.path.exists(a.out):
        os.remove(a.out)
    con = sqlite3.connect(a.out)
    con.executescript(_SCHEMA)
    name = a.name or f"{A['manifest'].get('name', 'A')} + {B['manifest'].get('name', 'B')}"
    for k, v in [("format_version", "3"), ("created_at", now),
                 ("writer_version", "laplaspack_merge/0.1"), ("namespace", ""),
                 ("owner", a.owner), ("name", name),
                 ("merged_from", json.dumps([A["manifest"].get("name"), B["manifest"].get("name")])),
                 ("entity_count", str(len(ents))), ("edge_count", str(len(edge_set))),
                 ("thinks_count", str(len(think_rows)))]:
        con.execute("INSERT OR REPLACE INTO manifest(key, value) VALUES(?,?)", (k, v))
    for pack in (A, B):
        for sh in pack["shards"]:
            sid = sh["shard_id"]
            if con.execute("SELECT 1 FROM lmd_source WHERE shard_id=?", (sid,)).fetchone():
                sid = f"{pack['name']}::{sid}"
            con.execute("INSERT INTO lmd_source(shard_id, content, commit_sha, time) VALUES(?,?,?,?)",
                        (sid, sh["content"], sh["commit_sha"], sh["time"]))
        for c in pack["commits"]:
            con.execute("INSERT OR IGNORE INTO commits(sha, time, author, parents) VALUES(?,?,?,?)",
                        (c["sha"], c["time"], c["author"], c["parents"]))
    con.execute("INSERT OR REPLACE INTO commits(sha, time, author, parents) VALUES(?,?,?,?)",
                (msha, now, a.owner or "merge", json.dumps([h for h in heads if h])))
    for eid in sorted(ents):
        e = ents[eid]
        con.execute(f"INSERT OR REPLACE INTO entities({ENT_COLS}) VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (eid, e["label"], e.get("type"), e.get("sigil"), e.get("layer") or "",
                     e.get("refs") or 0, json.dumps(e["fields"], ensure_ascii=False),
                     e.get("commit_sha"), e.get("time"), e.get("stable_id")))
    for k in sorted(edge_set):
        e = edge_set[k]
        con.execute("INSERT INTO edges(src, dst, role, kind, commit_sha, time) VALUES(?,?,?,?,?,?)",
                    (e["src"], e["dst"], e["role"], e["kind"], e.get("commit_sha"), e.get("time")))
    for t in think_rows:
        con.execute("INSERT INTO thinks(host, think_id, type, title, body, author, at, status, due,"
                    " mentions_json, then_json, deleted, commit_sha, time) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (t["host"], t.get("think_id"), t.get("type"), t.get("title"), t.get("body"),
                     t.get("author"), t.get("at"), t.get("status"), t.get("due"),
                     t.get("mentions_json"), t.get("then_json"), t.get("deleted") or 0,
                     t.get("commit_sha"), t.get("time")))
    con.commit(); con.close()

    nconf = len(report["field_conflicts"])
    print(f"merged → {a.out}: {len(ents)} entities · {len(edge_set)} edges · {len(think_rows)} thinks")
    print(f"  unified {report['unified']} shared identit{'y' if report['unified'] == 1 else 'ies'} · "
          f"{nconf} field conflict(s) {'materialized as contradicts' if a.conflicts == 'materialize' and nconf else 'recorded losslessly' if nconf else ''}")
    print("  note: the merge is new content — the output is unsealed (re-sign with laplaspack_seal.py)")
    if a.report:
        with open(a.report, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"  report → {a.report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
