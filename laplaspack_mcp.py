#!/usr/bin/env python3
"""laplaspack_mcp — mount any .laplaspack into any MCP client. Zero dependencies.

The sqlite3-CLI of laplaspack: not an app, not an account — a reader that
speaks MCP over stdio, so a pack file someone handed you becomes a queryable
memory inside Claude, Cursor, or any other MCP client, in one config line:

    { "mcpServers": { "my-pack": {
        "command": "python3",
        "args": ["/path/to/laplaspack_mcp.py", "/path/to/mind.laplaspack"] } } }

Tools (all read-only):
    find         full-text search over atoms (FTS5, LIKE fallback)
    open         one atom: properties, typed links, attached thoughts
    directory    every atom's label + type — the map of the mind
    why          the reasoning chain behind an atom (typed-edge walk)
    blind_spots  unclosed loops (exact H1 of the clique complex) — what this
                 memory doesn't know it's missing

Python 3.9+ · stdlib only · multiple packs may be mounted (pass several paths).
"""
from __future__ import annotations
import json
import os
import re
import sqlite3
import sys
from collections import defaultdict

# lineage/mention edges are structural noise for reading; DAG_UP drives `why`
SKIP_RELS = {"then", "mentions"}
DAG_UP = {"derived-from", "supports", "raises", "closes", "supersedes",
          "part_of", "belongs_to", "aspect_of", "goal_of", "milestone_of",
          "deliverable_of", "contradicts"}


def _slug(x: str) -> str:
    return (x or "").strip().lower().replace(" ", "_")


class Pack:
    def __init__(self, path: str):
        self.path = path
        self.name = re.sub(r"\.laplaspack$", "", os.path.basename(path), flags=re.I)
        self.db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        self.db.row_factory = sqlite3.Row
        self.ents: dict[str, dict] = {}
        for r in self.db.execute("SELECT id, label, type, fields_json FROM entities"):
            fields = {}
            try:
                fields = json.loads(r["fields_json"] or "{}")
            except Exception:
                pass
            self.ents[r["id"]] = {"label": r["label"] or r["id"],
                                  "type": (r["type"] or "node"), "fields": fields}
        self.by_label = {}
        for eid, e in self.ents.items():
            self.by_label.setdefault(e["label"].strip().lower(), eid)
        # edges may reference endpoints by label in older packs — resolve all forms
        self.edges: list[tuple[str, str, str]] = []
        for r in self.db.execute("SELECT src, dst, role FROM edges"):
            a, b = self.rid(r["src"]), self.rid(r["dst"])
            role = (r["role"] or "link").strip()
            if a and b and a != b and role not in SKIP_RELS:
                self.edges.append((a, b, role))
        self.has_fts = bool(self.db.execute(
            "SELECT name FROM sqlite_master WHERE name='entities_fts'").fetchone())

    def rid(self, x: str) -> str | None:
        if x in self.ents:
            return x
        k = (x or "").strip().lower()
        if k in self.by_label:
            return self.by_label[k]
        s = _slug(x)
        return s if s in self.ents else None

    def find(self, query: str, k: int) -> list[dict]:
        out, seen = [], set()
        if self.has_fts and query.strip():
            try:
                q = " OR ".join('"' + t.replace('"', "") + '"' for t in query.split())
                for r in self.db.execute(
                        "SELECT id FROM entities_fts WHERE entities_fts MATCH ? "
                        "ORDER BY bm25(entities_fts) LIMIT ?", (q, k)):
                    eid = self.rid(r["id"])
                    if eid and eid not in seen:
                        seen.add(eid)
                        out.append(self._brief(eid))
            except sqlite3.OperationalError:
                pass
        if not out:                                   # LIKE fallback / FTS miss
            pat = f"%{query.strip()}%"
            for r in self.db.execute(
                    "SELECT id FROM entities WHERE label LIKE ? OR fields_json LIKE ? LIMIT ?",
                    (pat, pat, k)):
                eid = self.rid(r["id"])
                if eid and eid not in seen:
                    seen.add(eid)
                    out.append(self._brief(eid))
        return out

    def _brief(self, eid: str) -> dict:
        e = self.ents[eid]
        return {"id": eid, "label": e["label"], "type": e["type"], "pack": self.name}

    def open(self, eid: str) -> dict:
        e = self.ents[eid]
        links = [{"role": role, "to": self.ents[b]["label"], "to_type": self.ents[b]["type"]}
                 for a, b, role in self.edges if a == eid] + \
                [{"role": role, "from": self.ents[a]["label"], "from_type": self.ents[a]["type"]}
                 for a, b, role in self.edges if b == eid]
        thinks = []
        try:
            for r in self.db.execute(
                    "SELECT type, body, status, at FROM thinks WHERE host=? "
                    "AND (deleted IS NULL OR deleted=0) ORDER BY at", (eid,)):
                body = " ".join(ln.strip() for ln in (r["body"] or "").splitlines()
                                if ln.strip() and not ln.strip().startswith("then>"))
                thinks.append({"type": r["type"] or "note", "body": body[:400],
                               "status": r["status"] or "", "at": r["at"] or ""})
        except sqlite3.OperationalError:
            pass                                       # pre-thinks pack
        return {**self._brief(eid), "properties": e["fields"], "links": links, "thinks": thinks}

    def why(self, eid: str, depth: int = 4) -> list[str]:
        lines, seen, frontier = [], {eid}, [eid]
        for _ in range(depth):
            nxt = []
            for x in frontier:
                for a, b, role in self.edges:
                    if a == x and role in DAG_UP and b not in seen:
                        lines.append(f"{self.ents[a]['label']} —{role}→ {self.ents[b]['label']} ({self.ents[b]['type']})")
                        seen.add(b)
                        nxt.append(b)
            frontier = nxt
            if not frontier:
                break
        return lines

    # ── the shape of the memory: exact H1 of the clique complex ─────────
    def blind_spots(self) -> dict:
        nodes = set(self.ents)
        E = sorted({tuple(sorted((a, b))) for a, b, _ in self.edges})
        adj = defaultdict(set)
        for u, v in E:
            adj[u].add(v); adj[v].add(u)
        eidx = {e: i for i, e in enumerate(E)}
        seen, comps = set(), 0
        for s in nodes:
            if s in seen:
                continue
            comps += 1
            st = [s]
            while st:
                x = st.pop()
                if x in seen:
                    continue
                seen.add(x)
                st.extend(adj[x] - seen)
        z = len(E) - len(nodes) + comps
        rows, order = [], {x: i for i, x in enumerate(sorted(nodes))}
        for u, v in E:
            for w in adj[u] & adj[v]:
                if order[w] > order[v] > order[u]:
                    rows.append((1 << eidx[(u, v)]) | (1 << eidx[tuple(sorted((v, w)))])
                                | (1 << eidx[tuple(sorted((u, w)))]))
        piv, r2 = {}, 0
        for r in rows:
            while r:
                hb = r.bit_length() - 1
                if hb in piv:
                    r ^= piv[hb]
                else:
                    piv[hb] = r; r2 += 1; break
        h1 = z - r2
        holes = []
        if h1 > 0:                                    # fundamental-cycle representatives
            parent, dep = {}, {}
            for s in nodes:
                if s in parent:
                    continue
                parent[s], dep[s] = None, 0
                st = [s]
                while st:
                    x = st.pop()
                    for y in adj[x]:
                        if y not in parent:
                            parent[y], dep[y] = x, dep[x] + 1
                            st.append(y)
            tree = {tuple(sorted((x, p))) for x, p in parent.items() if p is not None}
            for u, v in E:
                if (u, v) in tree:
                    continue
                a, b, pa, pb = u, v, [u], [v]
                while dep[a] > dep[b]:
                    a = parent[a]; pa.append(a)
                while dep[b] > dep[a]:
                    b = parent[b]; pb.append(b)
                while a != b:
                    a = parent[a]; pa.append(a)
                    b = parent[b]; pb.append(b)
                cyc = pa + pb[::-1][1:]
                if len(cyc) >= 4:
                    holes.append(" — ".join(f"{self.ents[x]['label']}({self.ents[x]['type']})" for x in cyc))
        return {"pack": self.name, "nodes": len(nodes), "edges": len(E), "h1": h1,
                "unclosed_loops": holes[:6]}


# ── MCP over stdio: newline-delimited JSON-RPC 2.0, stdlib only ──────────
TOOLS = [
    {"name": "find",
     "description": "Search this memory's atoms by meaning of words (full-text). Returns atoms to open or cite.",
     "inputSchema": {"type": "object", "properties": {
         "query": {"type": "string"}, "k": {"type": "integer", "description": "max results (default 8)"}},
         "required": ["query"]}},
    {"name": "open",
     "description": "Open ONE atom: its properties (the content), typed links to other atoms, and attached thoughts.",
     "inputSchema": {"type": "object", "properties": {
         "node": {"type": "string", "description": "atom id or label"}}, "required": ["node"]}},
    {"name": "directory",
     "description": "Every atom's label and type — the map of this memory. Scan it to locate what to open.",
     "inputSchema": {"type": "object", "properties": {
         "limit": {"type": "integer", "description": "default 200"}}}},
    {"name": "why",
     "description": "The reasoning chain behind an atom — walks typed edges (derived-from, supports, closes…) upward.",
     "inputSchema": {"type": "object", "properties": {
         "node": {"type": "string"}}, "required": ["node"]}},
    {"name": "blind_spots",
     "description": "What this memory doesn't know it's missing: unclosed loops (exact H1 of the typed graph). "
                    "Each loop is a set of claims nothing triangulates — a rationale that was never captured.",
     "inputSchema": {"type": "object", "properties": {}}},
]


def _text(payload) -> dict:
    return {"content": [{"type": "text",
                         "text": payload if isinstance(payload, str)
                         else json.dumps(payload, ensure_ascii=False, indent=1)}]}


def dispatch(packs: list[Pack], name: str, args: dict) -> dict:
    if name == "find":
        k = int(args.get("k") or 8)
        hits = [h for p in packs for h in p.find(str(args.get("query") or ""), k)]
        return _text(hits[: k * max(1, len(packs))] or "(no matches)")
    if name == "open":
        ref = str(args.get("node") or "")
        for p in packs:
            eid = p.rid(ref)
            if eid:
                return _text(p.open(eid))
        return _text(f"(no atom named '{ref}')")
    if name == "directory":
        lim = int(args.get("limit") or 200)
        out = [p._brief(eid) for p in packs for eid in list(p.ents)[:lim]]
        return _text(out)
    if name == "why":
        ref = str(args.get("node") or "")
        for p in packs:
            eid = p.rid(ref)
            if eid:
                chain = p.why(eid)
                return _text("\n".join(chain) if chain else "(no upward chain — this atom is a root)")
        return _text(f"(no atom named '{ref}')")
    if name == "blind_spots":
        return _text([p.blind_spots() for p in packs])
    raise ValueError(f"unknown tool: {name}")


def main() -> None:
    paths = [a for a in sys.argv[1:] if not a.startswith("-")]
    if not paths:
        print("usage: laplaspack_mcp.py <pack.laplaspack> [more.laplaspack ...]", file=sys.stderr)
        sys.exit(2)
    packs = [Pack(p) for p in paths]

    def send(obj: dict) -> None:
        sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
        sys.stdout.flush()

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except Exception:
            continue
        mid, method = msg.get("id"), msg.get("method") or ""
        params = msg.get("params") or {}
        try:
            if method == "initialize":
                send({"jsonrpc": "2.0", "id": mid, "result": {
                    "protocolVersion": params.get("protocolVersion") or "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "laplaspack-mcp", "version": "0.1.0"}}})
            elif method == "tools/list":
                send({"jsonrpc": "2.0", "id": mid, "result": {"tools": TOOLS}})
            elif method == "tools/call":
                res = dispatch(packs, params.get("name") or "", params.get("arguments") or {})
                send({"jsonrpc": "2.0", "id": mid, "result": res})
            elif method == "ping":
                send({"jsonrpc": "2.0", "id": mid, "result": {}})
            elif mid is not None:                      # unknown REQUEST → empty ok
                send({"jsonrpc": "2.0", "id": mid, "result": {}})
            # notifications (no id) are consumed silently
        except Exception as e:
            if mid is not None:
                send({"jsonrpc": "2.0", "id": mid,
                      "error": {"code": -32000, "message": f"{type(e).__name__}: {e}"}})


if __name__ == "__main__":
    main()
