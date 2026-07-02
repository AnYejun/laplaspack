#!/usr/bin/env python3
"""
laplaspack_writer — a ZERO-DEPENDENCY reference writer for the .laplaspack format.

The other half of the proof that the format is open: this file uses only the
Python standard library and compiles LMD source (the subset below) into a pack
that any conformant reader — including `laplaspack_reader.py` in this repo —
can open, walk (`--why`), and fold (`--todos`).

    python3 laplaspack_writer.py story.lmd                      # → story.laplaspack
    python3 laplaspack_writer.py story.lmd -o mind.laplaspack --name "Aurora" --owner you

LMD subset understood (see LMD_GRAMMAR.ebnf for the full grammar):

    ## Any heading                      (prose — ignored)
    [[Node label]]                      entity declaration
    >>type: decision                    typed property (type is special)
    >>what: one dense sentence          any other >>key: value → fields
    [[A]] →(derived-from) [[B]]         causal link (6 roles)
    @@todo on="Node label" by=me at=2026-07-03 status=open id=t1
    body of the thought …               think document (until @@)
    @@

No network, no service, no model. Write structure at the moment of writing —
the pack carries its own reasoning.
"""
from __future__ import annotations
import argparse
import hashlib
import os
import json
import re
import sqlite3
import sys
from datetime import datetime, timezone

ROLES = ("derived-from", "supports", "raises", "closes", "supersedes", "contradicts")

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

DECL = re.compile(r"^\[\[([*!]?)([^\]\n]+)\]\]\s*$")
PROP = re.compile(r"^>>\s*([A-Za-z0-9_-]+)\s*:\s*(.+?)\s*$")
LINK = re.compile(r"^\[\[([^\]\n]+)\]\]\s*(?:→|->)\((" + "|".join(ROLES) + r")\)\s*\[\[([^\]\n]+)\]\]\s*$")
THINK_OPEN = re.compile(r"^@@([A-Za-z]+)\s+(.*)$")
ATTR = re.compile(r'([A-Za-z_]+)=(?:"([^"]*)"|(\S+))')


def slug(label: str) -> str:
    return (label or "").strip().lower().replace(" ", "_")


def parse(src: str):
    entities: dict[str, dict] = {}
    edges: list[dict] = []
    thinks: list[dict] = []
    cur: dict | None = None
    lines = src.replace("\r\n", "\n").split("\n")
    i = 0
    while i < len(lines):
        ln = lines[i]
        m = THINK_OPEN.match(ln.strip())
        if m and m.group(1).lower() not in ("end",):
            ttype = m.group(1).lower()
            attrs = {k: (a if a is not None else b) for k, a, b in ATTR.findall(m.group(2))}
            body_lines: list[str] = []
            i += 1
            while i < len(lines) and lines[i].strip() != "@@":
                body_lines.append(lines[i])
                i += 1
            body = "\n".join(body_lines).strip()
            title = next((l.strip() for l in body_lines
                          if l.strip() and not l.strip().startswith(("then>", "@[["))), "")[:200]
            thens = [l.strip()[5:].strip() for l in body_lines if l.strip().startswith("then>")]
            mentions = re.findall(r"@\[\[([^\]]+)\]\]", body)
            thinks.append({
                "host": attrs.get("on", ""), "think_id": attrs.get("id"),
                "type": ttype, "title": title, "body": body,
                "author": attrs.get("by", "").lstrip("@"), "at": attrs.get("at"),
                "status": attrs.get("status") if ttype == "todo" else None,
                "due": attrs.get("due"), "mentions": mentions, "thens": thens,
                "deleted": 1 if attrs.get("deleted") in ("1", "true") else 0,
            })
            i += 1
            continue
        s = ln.strip()
        m = LINK.match(s)
        if m:
            edges.append({"src": m.group(1).strip(), "dst": m.group(3).strip(), "role": m.group(2)})
            i += 1
            continue
        m = DECL.match(s)
        if m:
            label = m.group(2).strip()
            cur = entities.setdefault(slug(label), {"label": label, "type": None, "fields": {}})
            i += 1
            continue
        m = PROP.match(s)
        if m and cur is not None:
            k, v = m.group(1), m.group(2)
            cur["fields"][k] = v
            if k == "type":
                cur["type"] = v
            i += 1
            continue
        i += 1
    return entities, edges, thinks


def write_pack(out: str, src: str, entities, edges, thinks, *, name: str, owner: str, shard: str):
    if os.path.exists(out):  # a pack is a build artifact — always rebuilt whole
        os.remove(out)
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    sha = hashlib.sha256(src.encode("utf-8")).hexdigest()[:16]
    con = sqlite3.connect(out)
    con.executescript(_SCHEMA)
    con.execute("DELETE FROM manifest")
    for k, v in [("format_version", "3"), ("created_at", now), ("writer_version", "laplaspack_writer/0.1"),
                 ("namespace", ""), ("owner", owner), ("name", name),
                 ("entity_count", str(len(entities))), ("edge_count", str(len(edges))),
                 ("thinks_count", str(len(thinks)))]:
        con.execute("INSERT INTO manifest(key, value) VALUES(?, ?)", (k, v))
    con.execute("INSERT OR REPLACE INTO lmd_source(shard_id, content, commit_sha, time) VALUES(?,?,?,?)",
                (shard, src, sha, now))
    con.execute("INSERT OR REPLACE INTO commits(sha, time, author, parents) VALUES(?,?,?,?)",
                (sha, now, owner, "[]"))
    for eid, e in entities.items():
        con.execute(
            "INSERT OR REPLACE INTO entities(id, label, type, sigil, layer, refs, fields_json, commit_sha, time, stable_id)"
            " VALUES(?,?,?,?,?,?,?,?,?,?)",
            (eid, e["label"], e["type"], None, "", 0,
             json.dumps(e["fields"], ensure_ascii=False), sha, now,
             "lp_" + hashlib.sha256((shard + "|" + e["label"]).encode()).hexdigest()[:12]))
    for ed in edges:  # edges reference entities by LABEL (v2 identity, SPEC §3.1)
        con.execute("INSERT INTO edges(src, dst, role, kind, commit_sha, time) VALUES(?,?,?,?,?,?)",
                    (ed["src"], ed["dst"], ed["role"], "knowing", sha, now))
    for t in thinks:
        con.execute(
            "INSERT INTO thinks(host, think_id, type, title, body, author, at, status, due,"
            " mentions_json, then_json, deleted, commit_sha, time) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (slug(t["host"]), t["think_id"], t["type"], t["title"], t["body"], t["author"], t["at"],
             t["status"], t["due"], json.dumps(t["mentions"], ensure_ascii=False),
             json.dumps(t["thens"], ensure_ascii=False), t["deleted"], sha, now))
    con.commit()
    con.close()


def main() -> int:
    ap = argparse.ArgumentParser(description="Compile LMD source into a .laplaspack (stdlib only).")
    ap.add_argument("lmd", help="path to the LMD source file")
    ap.add_argument("-o", "--out", help="output pack path (default: <lmd>.laplaspack)")
    ap.add_argument("--name", help="pack name (default: first # heading or the file name)")
    ap.add_argument("--owner", default="", help="owner string recorded in the manifest")
    a = ap.parse_args()
    src = open(a.lmd, encoding="utf-8").read()
    entities, edges, thinks = parse(src)
    if not entities:
        print("no [[entities]] found — is this LMD? (see LMD_GRAMMAR.ebnf)", file=sys.stderr)
        return 1
    # sanity: links must point at declared labels
    known = {e["label"] for e in entities.values()}
    for ed in edges:
        for end in (ed["src"], ed["dst"]):
            if end not in known:
                print(f"warning: link references undeclared node [[{end}]]", file=sys.stderr)
    m = re.search(r"^#\s+(.+)$", src, re.M)
    name = a.name or (m.group(1).strip() if m else a.lmd.rsplit("/", 1)[-1])
    out = a.out or (a.lmd.rsplit(".", 1)[0] + ".laplaspack")
    write_pack(out, src, entities, edges, thinks, name=name, owner=a.owner,
               shard=a.lmd.rsplit("/", 1)[-1])
    print(f"wrote {out}: {len(entities)} entities · {len(edges)} edges · {len(thinks)} thinks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
