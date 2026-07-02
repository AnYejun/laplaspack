#!/usr/bin/env python3
"""
laplaspack_seal — Ed25519 sealing for .laplaspack files (SPEC §3.7).

This is the ONE tool in this repo that is not stdlib-only: Python's standard
library has no Ed25519, so sealing declares a single dependency —

    pip install cryptography

The reader stays zero-dependency: it REPORTS signature presence; checking it
is this tool's job. Verification needs no secret and no network — anyone with
the pack can run `verify`.

    python3 laplaspack_seal.py keygen  --key me.key            # once
    python3 laplaspack_seal.py sign    pack.laplaspack --key me.key
    python3 laplaspack_seal.py verify  pack.laplaspack         # 0 valid · 1 invalid · 2 unsigned

What is signed: a canonical SHA-256 digest over the pack's CONTENT tables
(manifest minus the sig_* keys, lmd_source, entities, edges, thinks, commits),
rows sorted, so byte-level SQLite differences don't matter — content does.
Any edit to a sealed pack makes `verify` fail.
"""
from __future__ import annotations
import argparse
import hashlib
import os
import sqlite3
import sys

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey, Ed25519PublicKey)
except ImportError:  # pragma: no cover
    print("this tool needs the 'cryptography' package:  pip install cryptography",
          file=sys.stderr)
    sys.exit(3)

SIG_KEYS = ("sig_alg", "sig_pubkey", "sig", "sig_digest_v")


def _rows(con, sql) -> list[tuple]:
    try:
        return sorted(tuple("" if v is None else str(v) for v in r)
                      for r in con.execute(sql))
    except sqlite3.OperationalError:
        return []


def digest(path: str) -> bytes:
    """Canonical content digest (v1): sorted rows of the content tables,
    fields joined with 0x1f, rows with 0x1e, tables prefixed by name."""
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    h = hashlib.sha256()
    tables = [
        ("manifest", "SELECT key, value FROM manifest WHERE key NOT IN "
                     "('sig_alg','sig_pubkey','sig','sig_digest_v')"),
        ("lmd_source", "SELECT shard_id, content FROM lmd_source"),
        ("entities", "SELECT id, label, type, layer, fields_json, stable_id FROM entities"),
        ("edges", "SELECT src, dst, role, kind FROM edges"),
        ("thinks", "SELECT host, think_id, type, title, body, author, at, status, due, deleted FROM thinks"),
        ("commits", "SELECT sha, time, author, parents FROM commits"),
    ]
    for name, sql in tables:
        h.update(b"\x1d" + name.encode())
        for row in _rows(con, sql):
            h.update(b"\x1e" + b"\x1f".join(v.encode("utf-8") for v in row))
    con.close()
    return h.digest()


def cmd_keygen(a) -> int:
    if os.path.exists(a.key):
        print(f"{a.key} already exists — not overwriting", file=sys.stderr)
        return 1
    priv = Ed25519PrivateKey.generate()
    seed = priv.private_bytes_raw().hex()
    fd = os.open(a.key, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(seed + "\n")
    pub = priv.public_key().public_bytes_raw().hex()
    print(f"wrote {a.key} (keep it secret)\npublic key: {pub}")
    return 0


def cmd_sign(a) -> int:
    seed = open(a.key).read().strip()
    priv = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(seed))
    d = digest(a.pack)
    sig = priv.sign(d)
    pub = priv.public_key().public_bytes_raw().hex()
    con = sqlite3.connect(a.pack)
    for k, v in [("sig_alg", "ed25519"), ("sig_pubkey", pub),
                 ("sig", sig.hex()), ("sig_digest_v", "1")]:
        con.execute("INSERT OR REPLACE INTO manifest(key, value) VALUES(?, ?)", (k, v))
    con.commit(); con.close()
    print(f"sealed {a.pack}\n  alg    ed25519\n  key    {pub[:16]}…\n  digest sha256:{d.hex()[:16]}…")
    return 0


def cmd_verify(a) -> int:
    con = sqlite3.connect(f"file:{a.pack}?mode=ro", uri=True)
    man = {k: v for k, v in con.execute("SELECT key, value FROM manifest")}
    con.close()
    if not man.get("sig"):
        print(f"{a.pack}: UNSIGNED — no seal present")
        return 2
    if man.get("sig_alg") != "ed25519" or man.get("sig_digest_v") != "1":
        print(f"{a.pack}: unknown seal scheme ({man.get('sig_alg')}/{man.get('sig_digest_v')})")
        return 1
    try:
        pub = Ed25519PublicKey.from_public_bytes(bytes.fromhex(man["sig_pubkey"]))
        pub.verify(bytes.fromhex(man["sig"]), digest(a.pack))
    except Exception:
        print(f"{a.pack}: INVALID — content does not match the seal "
              f"(key {man.get('sig_pubkey', '')[:16]}…)")
        return 1
    print(f"{a.pack}: VALID — sealed by {man['sig_pubkey'][:16]}… (ed25519)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Seal / verify a .laplaspack (Ed25519, SPEC §3.7).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("keygen"); g.add_argument("--key", default="laplaspack.key")
    s = sub.add_parser("sign"); s.add_argument("pack"); s.add_argument("--key", required=True)
    v = sub.add_parser("verify"); v.add_argument("pack")
    a = ap.parse_args()
    return {"keygen": cmd_keygen, "sign": cmd_sign, "verify": cmd_verify}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
