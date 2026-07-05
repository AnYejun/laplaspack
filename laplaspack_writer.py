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
    >>part_of: [[Whole]]                edge-role fields become edges (§3.3 whitelist)
    [[A]] →(derived-from) [[B]]         causal link (6 roles — these power --why)
    [[A]] →(plays-for) [[B]]            association link (any kebab-case role)
    @@todo on="Node label" by=me at=2026-07-03 status=open id=t1
    body of the thought …               think document (until @@)
    @@

No network, no service, no model. Write structure at the moment of writing —
the pack carries its own reasoning.
"""
from __future__ import annotations
import argparse
import difflib
import hashlib
import os
import json
import re
import sqlite3
import sys
from datetime import datetime, timezone

ROLES = ("derived-from", "supports", "raises", "closes", "supersedes", "contradicts")

# Mirror of the engine's edge-field whitelist (laplas_engine/lmd/parser.py):
# a `>>key: [[Ref]]` property whose key is below compiles into an edge
# (SPEC §4.2/§3.3). Any OTHER key keeps its refs as plain text — the writer
# warns, because that silent demotion is exactly how graphs go missing.
DAG_FIELDS = {
    "derived-from": "derived-from", "derived_from": "derived-from", "derivedfrom": "derived-from",
    "supports": "supports",
    "raises": "raises", "raised-by": "raises", "raised_by": "raises",
    "closes": "closes", "supersedes": "supersedes", "contradicts": "contradicts",
}
CONTAINMENT_FIELDS = {
    "part-of": "part_of", "part_of": "part_of",
    "belongs-to": "belongs_to", "belongs_to": "belongs_to",
    "subordinate-to": "subordinate_to", "subordinate_to": "subordinate_to",
    "aspect-of": "aspect_of", "aspect_of": "aspect_of",
    "goal-of": "goal_of", "goal_of": "goal_of",
    "milestone-of": "milestone_of", "milestone_of": "milestone_of",
    "deliverable-of": "deliverable_of", "deliverable_of": "deliverable_of",
    "scope-of": "scope_of", "scope_of": "scope_of",
    "has-goal": "has_goal", "has_goal": "has_goal",
    "has-milestone": "has_milestone", "has_milestone": "has_milestone",
    "has-deliverable": "has_deliverable", "has_deliverable": "has_deliverable",
    "has-part": "has_part", "has_part": "has_part",
    "contains": "contains", "targets": "targets",
}
EDGE_FIELDS = {**DAG_FIELDS, **CONTAINMENT_FIELDS}
# fields whose values are prose — a [[ref]] inside them is a soft mention, not a missed link
PROSE_FIELDS = {"what", "why", "alias", "aliases", "aka", "note", "quote"}
REF = re.compile(r"\[\[([^\]\n]+)\]\]")

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
# Arrow role is an open set (LMD_GRAMMAR: edge_role = dag_role | containment_role
# | ident). The six causal roles are privileged by READERS (--why walks only
# them), not by the writer refusing to compile everything else.
LINK = re.compile(r"^\[\[([^\]\n]+)\]\]\s*(?:→|-+>)\s*\(([A-Za-z0-9_-]+)\)\s*\[\[([^\]\n]+)\]\]\s*$")
THINK_OPEN = re.compile(r"^@@([A-Za-z]+)\s+(.*)$")
ATTR = re.compile(r'([A-Za-z_]+)=(?:"([^"]*)"|(\S+))')


def slug(label: str) -> str:
    return (label or "").strip().lower().replace(" ", "_")


def parse(src: str):
    entities: dict[str, dict] = {}
    edges: list[dict] = []
    thinks: list[dict] = []
    problems: list[tuple[str, str]] = []   # (severity, message)
    cur: dict | None = None
    lines = src.replace("\r\n", "\n").split("\n")
    i = 0
    while i < len(lines):
        ln = lines[i]
        lno = i + 1
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
                "line": lno,
            })
            i += 1
            continue
        s = ln.strip()
        m = LINK.match(s)
        if m:
            raw = m.group(2)
            role = EDGE_FIELDS.get(raw.lower(), raw)  # canonicalize spellings; free roles pass through
            if role not in ROLES and role not in CONTAINMENT_FIELDS.values():
                close = difflib.get_close_matches(raw.lower(), ROLES, n=1, cutoff=0.78)
                if close:
                    problems.append(("warning",
                        f"line {lno}: role ({raw}) looks like a misspelling of ({close[0]}) — "
                        f"causal roles must be exact to power --why"))
            edges.append({"src": m.group(1).strip(), "dst": m.group(3).strip(),
                          "role": role, "line": lno})
            i += 1
            continue
        m = DECL.match(s)
        if m:
            label = m.group(2).strip()
            key = slug(label)
            if key in entities and entities[key]["label"] != label:
                problems.append(("error",
                    f"line {lno}: [[{label}]] collides with [[{entities[key]['label']}]] "
                    f"(both slug to '{key}') — rename one"))
            cur = entities.setdefault(key, {"label": label, "type": None, "fields": {},
                                            "stable_id": None, "line": lno})
            i += 1
            continue
        m = PROP.match(s)
        if m and cur is not None:
            k, v = m.group(1), m.group(2)
            cur["fields"][k] = v
            if k == "type":
                cur["type"] = v
            if k == "id":  # SPEC §3.1: the authored, rename-safe handle
                if v.startswith("lp_"):
                    cur["stable_id"] = v
                else:
                    problems.append(("warning", f"line {lno}: >>id: should start with lp_ (got {v!r})"))
            refs = REF.findall(v)
            if refs:
                ck = k.lower()
                if ck in EDGE_FIELDS:  # SPEC §4.2: an edge-role key + ref value = an edge
                    for r in refs:
                        edges.append({"src": cur["label"], "dst": r.strip(),
                                      "role": EDGE_FIELDS[ck], "line": lno})
                elif ck not in PROSE_FIELDS and ck != "id":
                    problems.append(("warning",
                        f"line {lno}: >>{k}: holds [[{refs[0].strip()}]] but '{k}' is not an "
                        f"edge field — refs here do NOT become links. Write: "
                        f"[[{cur['label']}]] →({k}) [[{refs[0].strip()}]]"))
            i += 1
            continue
        i += 1
    seen: set[tuple[str, str, str]] = set()   # arrow + field forms may repeat a link
    edges = [ed for ed in edges
             if (key := (ed["src"], ed["dst"], ed["role"])) not in seen and not seen.add(key)]
    return entities, edges, thinks, problems


def validate(entities, edges, thinks, problems, *, allow_dangling: bool = False):
    """Build-time consistency. Dangling references are ERRORS by default — the
    pack is a build artifact, so a rename in source that misses a link line must
    fail the build, not ship a silently broken graph."""
    dang = "warning" if allow_dangling else "error"
    known = {e["label"] for e in entities.values()}
    ids_seen: dict[str, str] = {}
    for eid, e in entities.items():
        if e.get("stable_id"):
            if e["stable_id"] in ids_seen:
                problems.append(("error", f"[[{e['label']}]] reuses >>id: {e['stable_id']} "
                                          f"(already on [[{ids_seen[e['stable_id']]}]])"))
            ids_seen[e["stable_id"]] = e["label"]
        substance = {k for k in e["fields"] if k not in ("type", "id")}
        if not substance:  # >>claim:/>>finding:/>>role: … carry essence just as well as >>what:
            problems.append(("warning", f"[[{e['label']}]] has no fields beyond type — it will be a bare label"))
    for ed in edges:
        for end in (ed["src"], ed["dst"]):
            if end not in known:
                problems.append((dang, f"line {ed['line']}: link references undeclared node [[{end}]]"))
        if ed["src"] == ed["dst"]:
            problems.append(("error", f"line {ed['line']}: self-link on [[{ed['src']}]]"))
    # Orphans: a pack is a graph, not a list. A node no link touches is either
    # missing its relations or is a fact that belongs on another node as a
    # >>property. (Single-node packs are exempt — nothing to link to.)
    if len(entities) > 1:
        touched = {slug(ed[end]) for ed in edges for end in ("src", "dst")}
        orphans = [e["label"] for key, e in entities.items() if key not in touched]
        if orphans:
            listed = " · ".join(f"[[{o}]]" for o in orphans[:8]) + (" …" if len(orphans) > 8 else "")
            problems.append(("warning",
                f"{len(orphans)} node(s) have no links: {listed} — connect them "
                f"([[A]] →(role) [[B]], any kebab-case role) or fold them into a "
                f"parent node as >>properties"))
    tids = {t["think_id"] for t in thinks if t["think_id"]}
    for t in thinks:
        if t["host"] and t["host"] not in known and slug(t["host"]) not in entities:
            problems.append((dang, f"line {t['line']}: think on=\"{t['host']}\" references an undeclared node"))
        for th in t["thens"]:
            if th not in tids:
                problems.append(("warning", f"line {t['line']}: then> {th} does not match any think id"))
    # then> cycles (a think's predecessor chain must be acyclic)
    nxt = {t["think_id"]: t["thens"] for t in thinks if t["think_id"]}
    state: dict[str, int] = {}
    def walk(n: str) -> bool:
        if state.get(n) == 1: return True
        if state.get(n) == 2: return False
        state[n] = 1
        hit = any(walk(m2) for m2 in nxt.get(n, []) if m2 in nxt)
        state[n] = 2
        return hit
    for n in list(nxt):
        if walk(n):
            problems.append(("error", f"then> cycle involving think id {n}"))
            break
    return problems


def write_pack(out: str, src: str, entities, edges, thinks, *, name: str, owner: str, shard: str):
    if os.path.exists(out):  # a pack is a build artifact — always rebuilt whole
        os.remove(out)
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    sha = hashlib.sha256(src.encode("utf-8")).hexdigest()[:16]
    con = sqlite3.connect(out)
    con.executescript(_SCHEMA)
    con.execute("DELETE FROM manifest")
    for k, v in [("format_version", "3"), ("created_at", now), ("writer_version", "laplaspack_writer/0.2"),
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
             e.get("stable_id")))  # ONLY the authored >>id: is rename-safe; deriving one from the label would defeat it
    for ed in edges:  # edges reference entities by LABEL (v2 identity, SPEC §3.1)
        kind = "knowing" if ed["role"] in ROLES else "subject"   # SPEC §3.3 partition
        con.execute("INSERT INTO edges(src, dst, role, kind, commit_sha, time) VALUES(?,?,?,?,?,?)",
                    (ed["src"], ed["dst"], ed["role"], kind, sha, now))
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
    ap.add_argument("--allow-dangling", action="store_true",
                    help="downgrade dangling node references from errors to warnings")
    a = ap.parse_args()
    src = open(a.lmd, encoding="utf-8").read()
    entities, edges, thinks, problems = parse(src)
    if not entities:
        print("no [[entities]] found — is this LMD? (see LMD_GRAMMAR.ebnf)", file=sys.stderr)
        return 1
    validate(entities, edges, thinks, problems, allow_dangling=a.allow_dangling)
    errors = [msg for sev, msg in problems if sev == "error"]
    for sev, msg in problems:
        print(f"{sev}: {msg}", file=sys.stderr)
    if errors:
        print(f"\n{len(errors)} error(s) — pack NOT built. Fix the source, or pass "
              f"--allow-dangling to downgrade dangling references.", file=sys.stderr)
        return 1
    missing_ids = [e["label"] for e in entities.values() if not e.get("stable_id")]
    if missing_ids:
        print(f"note: {len(missing_ids)} node(s) have no >>id: — add authored ids "
              f"(e.g. >>id: lp_{{12 hex}}) to make renames survive rebuilds (SPEC §3.1). "
              f"Without one, identity is the label.", file=sys.stderr)
    m = re.search(r"^#\s+(.+)$", src, re.M)
    name = a.name or (m.group(1).strip() if m else a.lmd.rsplit("/", 1)[-1])
    out = a.out or (a.lmd.rsplit(".", 1)[0] + ".laplaspack")
    write_pack(out, src, entities, edges, thinks, name=name, owner=a.owner,
               shard=a.lmd.rsplit("/", 1)[-1])
    print(f"wrote {out}: {len(entities)} entities · {len(edges)} edges · {len(thinks)} thinks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
