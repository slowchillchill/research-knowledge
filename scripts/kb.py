#!/usr/bin/env python3
"""Markdown-only research store, validation and disposable indexes. Standard library only."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sqlite3
import sys
import tempfile
import unicodedata
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELATIONS = ("depends_on", "supports", "limits", "conflicts_with", "supersedes", "transfer_to")
STATES = ("draft", "active", "superseded")
CHECKS = ("unverified", "checked", "rejected")
BUILD_FORMAT = "research-knowledge-v1"


class KBError(ValueError):
    pass


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def digest(value: bytes):
    return hashlib.sha256(value).hexdigest()


def require(ok, message):
    if not ok:
        raise KBError(message)


def text(value):
    return isinstance(value, str) and bool(value.strip())


def strings(value, nonempty=False):
    return isinstance(value, list) and (not nonempty or bool(value)) and all(text(x) for x in value)


def date(value, label):
    require(isinstance(value, str), f"{label}: expected ISO date")
    try:
        result = dt.date.fromisoformat(value)
    except ValueError as exc:
        raise KBError(f"{label}: invalid ISO date") from exc
    require(result.isoformat() == value, f"{label}: use YYYY-MM-DD")
    return result


def validate_schema(value, spec, label, document=None):
    """Validate the deliberately small JSON Schema vocabulary used by our schemas.

    Unsupported schema keywords fail closed rather than pretending full JSON Schema support.
    Cross-card references, dates, examples and cycles are additionally checked by load().
    """
    document = spec if document is None else document
    supported = {"$schema", "$defs", "$ref", "title", "type", "const", "enum", "properties", "required",
                 "additionalProperties", "minProperties", "items", "minItems", "minLength", "pattern", "format"}
    require(not (set(spec) - supported), f"{label}: unsupported schema keyword")
    if "$ref" in spec:
        reference = spec["$ref"]
        require(reference.startswith("#/$defs/"), f"{label}: only local schema definitions supported")
        return validate_schema(value, document["$defs"][reference[8:]], label, document)
    if "const" in spec:
        require(type(value) is type(spec["const"]) and value == spec["const"], f"{label}: unexpected constant")
    if "enum" in spec:
        require(value in spec["enum"], f"{label}: unsupported value")
    kind = spec.get("type")
    checks = {"object": isinstance(value, dict), "array": isinstance(value, list),
              "string": isinstance(value, str), "boolean": type(value) is bool}
    require(kind is None or checks.get(kind, False), f"{label}: expected {kind}")
    if kind == "object":
        require(len(value) >= spec.get("minProperties", 0), f"{label}: too few properties")
        require(not (set(spec.get("required", [])) - set(value)), f"{label}: missing required metadata fields")
        properties, extra = spec.get("properties", {}), spec.get("additionalProperties", True)
        for k,v in value.items():
            if k in properties:
                validate_schema(v, properties[k], label + "." + k, document)
            elif isinstance(extra, dict):
                validate_schema(v, extra, label + "." + k, document)
            else:
                require(extra, f"{label}: unknown field {k}")
    elif kind == "array":
        require(len(value) >= spec.get("minItems", 0), f"{label}: too few items")
        for v in value:
            validate_schema(v, spec["items"], label, document)
    elif kind == "string":
        require(len(value.strip()) >= spec.get("minLength", 0), f"{label}: empty string")
        if "pattern" in spec:
            require(re.search(spec["pattern"], value) is not None, f"{label}: invalid string format")
        if "format" in spec:
            require(spec["format"] == "date", f"{label}: unsupported schema format")
            date(value, label)


def parse(raw, path):
    try:
        content = raw.decode("utf-8")
        require(content.startswith("---\n"), f"{path}: expected JSON front matter between --- lines")
        header, body = content[4:].split("\n---\n", 1)
        def unique(pairs):
            result = {}
            for k, v in pairs:
                require(k not in result, f"{path}: duplicate JSON key {k}")
                result[k] = v
            return result
        meta = json.loads(header, object_pairs_hook=unique)
        require(isinstance(meta, dict) and text(body), f"{path}: metadata object and nonempty body required")
        return meta, body, content
    except (UnicodeError, ValueError) as exc:
        if isinstance(exc, KBError):
            raise
        raise KBError(f"{path}: invalid Markdown metadata: {exc}") from exc


def snapshot(root):
    """Read exactly the two content directories; never follow symlinks outside the clone."""
    root = Path(root).resolve()
    files = {}
    for name in ("knowledge", "sources"):
        base = root / name
        require(base.is_dir() and not base.is_symlink(), f"missing or symlinked directory: {name}")
        for p in sorted(base.rglob("*")):
            require(not p.is_symlink(), f"symlink is not allowed: {p.relative_to(root)}")
            if p.is_file() and p.suffix == ".md":
                files[p.relative_to(root).as_posix()] = p.read_bytes()
    # No commit ID or generated output is hashed: committing indexes cannot cause a build loop.
    build_files = [ROOT / "scripts" / "kb.py", ROOT / "scripts" / "mcp_server.py"]
    build_files += sorted((ROOT / "schema").glob("*.json"))
    inputs = {p: digest(raw) for p, raw in files.items()}
    implementation = {p.relative_to(ROOT).as_posix(): digest(p.read_bytes()) for p in build_files}
    manifest = {"format": BUILD_FORMAT, "content": inputs, "implementation": implementation}
    return files, manifest, digest(encoded(manifest).encode())


def validate_base(m, path, kind):
    prefix = "K" if kind == "knowledge" else "S"
    require(m.get("schema_version") == 1, f"{path}: schema_version must be 1")
    require(m.get("kind") == kind, f"{path}: kind must be {kind}")
    require(isinstance(m.get("id"), str) and re.fullmatch(prefix + r"-\d{6}", m["id"]),
            f"{path}: expected permanent {prefix}-ID (six digits)")
    for key in ("title", "version"):
        require(text(m.get(key)), f"{path}: missing {key}")
    require(type(m.get("example")) is bool, f"{path}: example must be boolean")


def validate_citation(c, sources, label):
    require(isinstance(c, dict), f"{label}: citation must be object")
    require(set(c) == {"id", "version", "locator", "role"}, f"{label}: citation fields id/version/locator/role required")
    require(all(text(c[x]) for x in c), f"{label}: citation fields must be strings")
    source = sources.get(c["id"])
    require(source is not None, f"{label}: missing source {c['id']}")
    require(c["version"] == source["meta"]["version"], f"{label}: source version mismatch {c['id']}")
    require(c["locator"] in source["meta"]["locators"], f"{label}: unknown source locator {c['locator']}")


def load(root):
    files, manifest, version = snapshot(root)
    knowledge, sources = {}, {}
    for path, raw in files.items():
        kind = "knowledge" if path.startswith("knowledge/") else "source"
        meta, body, markdown = parse(raw, path)
        schema_name = "knowledge" if kind == "knowledge" else "source"
        spec = json.loads((ROOT / "schema" / (schema_name + ".schema.json")).read_text())
        validate_schema(meta, spec, path)
        validate_base(meta, path, kind)
        dest = knowledge if kind == "knowledge" else sources
        require(meta["id"] not in dest, f"duplicate stable ID: {meta['id']}")
        dest[meta["id"]] = {"meta": meta, "body": body, "markdown": markdown,
                            "path": path, "content_hash": digest(raw)}
    for sid, s in sources.items():
        m, label = s["meta"], s["path"]
        require(m.get("source_type") in ("paper", "documentation", "dataset", "synthetic"), f"{label}: invalid source_type")
        require(m["source_type"] != "synthetic" or m["example"], f"{label}: synthetic sources must be examples")
        require(strings(m.get("authors"), True), f"{label}: authors required")
        for key in ("original_url", "version_url"):
            require(text(m.get(key)) and m[key].startswith("https://"), f"{label}: {key} must be HTTPS")
        date(m.get("accessed"), label + ": accessed")
        require(text(m.get("version_note")), f"{label}: version_note required")
        locators = m.get("locators")
        require(isinstance(locators, dict) and bool(locators) and all(text(k) and text(v) for k,v in locators.items()),
                f"{label}: named locators required")
    for kid, card in knowledge.items():
        m, label = card["meta"], card["path"]
        for key in ("summary",):
            require(text(m.get(key)), f"{label}: {key} required")
        require(m.get("lifecycle") in STATES, f"{label}: invalid lifecycle")
        for key in ("conditions", "limitations"):
            require(strings(m.get(key), True), f"{label}: {key} must be nonempty string array")
        for key, subkeys in (("tags", ("domains", "methods", "problems")), ("aliases", ("zh", "en"))):
            require(isinstance(m.get(key), dict) and set(m[key]) == set(subkeys), f"{label}: invalid {key}")
            for sub in subkeys:
                require(strings(m[key][sub], True), f"{label}: {key}.{sub} required")
        ev = m.get("evidence", {})
        require(isinstance(ev, dict) and ev.get("strength") in ("unassessed", "reported", "corroborated")
                and ev.get("replication") in ("not_attempted", "partial", "reproduced", "failed")
                and text(ev.get("note")), f"{label}: evidence strength/replication/note required")
        date(m.get("review_after"), label + ": review_after")
        require(isinstance(m.get("sources"), list) and bool(m["sources"]), f"{label}: sources required even for drafts")
        for c in m["sources"]:
            validate_citation(c, sources, label)
            require(m["example"] or not sources[c["id"]]["meta"]["example"], f"{label}: production card cites example")
        require(isinstance(m.get("relations"), list), f"{label}: relations array required")
        for edge in m["relations"]:
            require(isinstance(edge, dict), f"{label}: relation must be object")
            require(set(edge) == {"type", "target", "reason", "conditions", "evidence", "verification"}, f"{label}: invalid relation fields")
            require(edge["type"] in RELATIONS, f"{label}: invalid relation type")
            require(edge["target"] in knowledge, f"{label}: missing relation target {edge['target']}")
            require(edge["target"] != kid, f"{label}: self relation is not allowed")
            require(m["example"] or not knowledge[edge["target"]]["meta"]["example"], f"{label}: production relation targets example")
            require(text(edge["reason"]) and strings(edge["conditions"], True), f"{label}: relation reason/conditions required")
            require(edge["verification"] in CHECKS, f"{label}: invalid relation verification")
            require(isinstance(edge["evidence"], list) and bool(edge["evidence"]), f"{label}: relation evidence required")
            for c in edge["evidence"]:
                validate_citation(c, sources, label + ": relation")
                require(m["example"] or not sources[c["id"]]["meta"]["example"], f"{label}: relation cites example")
    # Iterative DFS handles long dependency chains without recursion limits.
    colors = {}
    for start in sorted(knowledge):
        if colors.get(start):
            continue
        stack, trail = [(start, False)], []
        while stack:
            node, leaving = stack.pop()
            if leaving:
                colors[node] = 2
                trail.pop()
                continue
            if colors.get(node) == 1:
                cycle = trail[trail.index(node):] + [node]
                raise KBError("dependency cycle: " + " -> ".join(cycle))
            if colors.get(node) == 2:
                continue
            colors[node] = 1
            trail.append(node)
            stack.append((node, True))
            children = [e["target"] for e in knowledge[node]["meta"]["relations"] if e["type"] == "depends_on"]
            stack.extend((n, False) for n in reversed(children))
    return knowledge, sources, manifest, version


def normalize(value):
    return unicodedata.normalize("NFKC", value).casefold()


def tokens(value):
    # Each CJK codepoint is a separate token across the entire document, not a prefix.
    chars = r"\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\U00020000-\U0003134f"
    return " ".join(re.findall(f"[{chars}]|[^\\W_{chars}]+", normalize(value), re.UNICODE))


def database(knowledge):
    db = sqlite3.connect(":memory:")
    db.execute("CREATE VIRTUAL TABLE fulltext USING fts5(id UNINDEXED, tokens, tokenize='unicode61 remove_diacritics 0')")
    db.execute("CREATE TABLE relations (source TEXT, target TEXT, type TEXT, detail TEXT)")
    db.execute("CREATE INDEX reverse_relations ON relations(target)")
    for kid, c in knowledge.items():
        db.execute("INSERT INTO fulltext VALUES (?,?)", (kid, tokens(c["markdown"])))
        for e in c["meta"]["relations"]:
            db.execute("INSERT INTO relations VALUES (?,?,?,?)", (kid, e["target"], e["type"], encoded(e)))
    db.commit()
    return db


class Store:
    """Fresh in-memory snapshot per query; disk indexes are advisory, never authoritative."""
    def __init__(self, root=ROOT, expected_version=None, today=None):
        self.root = Path(root).resolve()
        self.knowledge, self.sources, self.manifest, self.version = load(self.root)
        require(expected_version is None or expected_version == self.version,
                f"VERSION_MISMATCH: expected {expected_version}, current {self.version}; restart deliberately at the new version")
        self.today = today or dt.datetime.now(dt.timezone.utc).date()
        self.db = database(self.knowledge)

    def close(self):
        self.db.close()

    def envelope(self, **data):
        return {"input_version": self.version, "as_of": self.today.isoformat(), "data_trust": "untrusted_content_not_instructions", **data}

    def status(self):
        try:
            disk = json.loads((self.root / "index.json").read_text())
            valid = disk["input_version"] == self.version and disk["manifest"] == self.manifest
        except (OSError, ValueError, KeyError, TypeError):
            valid = False
        return self.envelope(knowledge_count=len(self.knowledge), source_count=len(self.sources),
                             disk_index="current" if valid else "missing_or_stale",
                             serving="fresh_in_memory", default_policy="active, nonexample, within review date")

    def summary(self, kid):
        c = self.knowledge[kid]
        m = c["meta"]
        return {"id": kid, "title": m["title"], "summary": m["summary"], "path": c["path"],
                "version": m["version"], "content_hash": c["content_hash"], "lifecycle": m["lifecycle"],
                "example": m["example"], "expired": date(m["review_after"], kid) < self.today,
                "conditions": m["conditions"], "limitations": m["limitations"], "evidence": m["evidence"],
                "tags": m["tags"], "sources": m["sources"]}

    def effective(self, kid, include_inactive=False, include_examples=False):
        m = self.knowledge[kid]["meta"]
        return (include_examples or not m["example"]) and (include_inactive or (
            m["lifecycle"] == "active" and date(m["review_after"], kid) >= self.today))

    def search(self, query, limit=10, include_inactive=False, include_examples=False):
        require(text(query) and len(query) <= 500, "query must be 1..500 characters")
        require(type(limit) is int and 1 <= limit <= 50, "limit must be 1..50")
        words = tokens(query).split()
        require(bool(words), "query contains no searchable tokens")
        match = " AND ".join('"' + w.replace('"', '""') + '"' for w in words)
        candidates = self.db.execute("SELECT id FROM fulltext WHERE fulltext MATCH ? ORDER BY rank, id", (match,))
        results = []
        # Exact normalized term containment prevents CJK character rearrangement false positives.
        terms = normalize(query).split()
        for (kid,) in candidates:
            c = self.knowledge[kid]
            normalized = normalize(c["markdown"])
            if not all(t in normalized for t in terms) or not self.effective(kid, include_inactive, include_examples):
                continue
            pos = normalized.find(terms[0])
            results.append({**self.summary(kid), "match_context": normalized[max(0,pos-60):pos+180]})
            if len(results) == limit:
                break
        return self.envelope(results=results, policy={"include_inactive": include_inactive, "include_examples": include_examples},
                             matching="NFKC/casefold literal terms (space-separated AND), full Markdown, no truncation")

    def read_card(self, id):
        require(id in self.knowledge or id in self.sources, f"unknown stable ID: {id}")
        c = self.knowledge.get(id) or self.sources[id]
        return self.envelope(id=id, path=c["path"], version=c["meta"]["version"], content_hash=c["content_hash"],
                             metadata=c["meta"], markdown=c["markdown"], sections=re.findall(r"^#{1,6} (.+)$", c["body"], re.M),
                             current=self.effective(id) if id in self.knowledge else None)

    def relations(self, id, direction="outgoing", hops=1, types=None):
        require(id in self.knowledge, f"unknown K-ID: {id}")
        require(direction in ("outgoing", "incoming", "both"), "invalid relation direction")
        require(type(hops) is int and 1 <= hops <= 2, "hops must be 1 or 2")
        require(types is None or (isinstance(types, list) and bool(types) and all(t in RELATIONS for t in types)), "invalid relation types")
        frontier, seen, edges, edge_keys = deque([(id, 0)]), {id}, [], set()
        while frontier:
            node, depth = frontier.popleft()
            if depth == hops:
                continue
            sql = {"outgoing": "source=?", "incoming": "target=?", "both": "source=? OR target=?"}[direction]
            args = (node, node) if direction == "both" else (node,)
            for src, dst, typ, detail in self.db.execute("SELECT * FROM relations WHERE " + sql + " ORDER BY source,target,type,detail", args):
                if types is not None and typ not in types:
                    continue
                key = (src, dst, typ, detail)
                if key not in edge_keys:
                    edges.append({"source": src, **json.loads(detail), "hop": depth+1})
                    edge_keys.add(key)
                other = dst if src == node else src
                if other not in seen:
                    seen.add(other)
                    frontier.append((other, depth+1))
        return self.envelope(root=id, direction=direction, hops=hops, edges=edges,
                             nodes=[self.summary(k) for k in sorted(seen)],
                             warning="Graph includes historical/example nodes with explicit status; edges are claims, not truth decisions.")

    def conflicts(self, id):
        result = self.relations(id, "both", 1, ["conflicts_with"])
        result["review_advice"] = "Compare scope, conditions and evidence manually; do not automatically choose a winner or overwrite cards."
        return result

    def trace_sources(self, id):
        require(id in self.knowledge, f"unknown K-ID: {id}")
        m = self.knowledge[id]["meta"]
        refs = list(m["sources"])
        refs += [ref for edge in m["relations"] for ref in edge["evidence"]]
        refs = [json.loads(s) for s in sorted({json.dumps(r, sort_keys=True) for r in refs})]
        source_ids = sorted({r["id"] for r in refs})
        return self.envelope(id=id, citations=refs, sources=[self.read_card(s) for s in source_ids])

    def impact(self, id, hops=2):
        require(id in self.knowledge or id in self.sources, f"unknown stable ID: {id}")
        require(type(hops) is int and 1 <= hops <= 2, "hops must be 1 or 2")
        if id in self.knowledge:
            result = self.relations(id, "incoming", hops)
            result["review_advice"] = "Potential review impact across typed incoming edges; no automatic invalidation or truth judgment."
            return result
        # Source changes affect direct citations (including edge evidence), then reverse relations.
        direct = []
        for kid, c in self.knowledge.items():
            refs = c["meta"]["sources"] + [r for e in c["meta"]["relations"] for r in e["evidence"]]
            if any(r["id"] == id for r in refs):
                direct.append(kid)
        graphs = [self.relations(k, "incoming", hops-1) for k in direct] if hops > 1 else []
        impacted = set(direct)
        for g in graphs:
            impacted.update(n["id"] for n in g["nodes"])
        return self.envelope(root=id, hops=hops, direct_citations=sorted(direct),
                             nodes=[self.summary(k) for k in sorted(impacted)], downstream=graphs,
                             review_advice="Source citation is hop 1; review potential impact manually.")


def build(root=ROOT, expected_version=None):
    store = Store(root, expected_version)
    try:
        index = store.envelope(manifest=store.manifest,
                               knowledge=[store.summary(k) for k in sorted(store.knowledge)],
                               sources=[{"id": k, "path": c["path"], "version": c["meta"]["version"],
                                         "content_hash": c["content_hash"]} for k,c in sorted(store.sources.items())],
                               reverse_relations={k: store.relations(k, "incoming")["edges"] for k in sorted(store.knowledge)})
        # Avoid wall-clock fields in tracked indexes. Expiry is evaluated at query time.
        index.pop("as_of")
        for c in index["knowledge"]:
            c.pop("expired")
        root = Path(root)
        for name in ("index.json", "index.md", ".cache"):
            require(not (root / name).is_symlink(), f"refusing symlinked build output: {name}")
        (root / "index.json").write_text(encoded(index), encoding="utf-8")
        lines = ["# Generated knowledge index", "", "Do not edit: rebuild with `python3 scripts/kb.py build`.", "",
                 f"Build input SHA-256: `{store.version}`", "", "Markdown is authoritative. Default retrieval requires active, nonexample, unexpired cards.", ""]
        for kid in sorted(store.knowledge):
            c = store.knowledge[kid]
            m = c["meta"]
            lines.append(f"- [{kid}]({c['path']}) — {m['title']} ({m['lifecycle']}; example={m['example']}; review_after={m['review_after']})")
        if not store.knowledge:
            lines.append("The formal knowledge collection is empty. Test fixtures are excluded.")
        (root / "index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        cache = root / ".cache"
        cache.mkdir(exist_ok=True)
        handle, name = tempfile.mkstemp(prefix="search-", suffix=".sqlite", dir=cache)
        os.close(handle)
        target = sqlite3.connect(name)
        try:
            store.db.backup(target)
            target.execute("CREATE TABLE IF NOT EXISTS build_info (input_version TEXT)")
            target.execute("DELETE FROM build_info")
            target.execute("INSERT INTO build_info VALUES (?)", (store.version,))
            target.commit()
        finally:
            target.close()
        os.replace(name, cache / "search.sqlite")
        return store.status()
    finally:
        store.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--expected-version")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("validate", "build", "status"):
        sub.add_parser(name)
    search = sub.add_parser("search")
    search.add_argument("query")
    search.add_argument("--include-inactive", action="store_true")
    search.add_argument("--include-examples", action="store_true")
    read = sub.add_parser("read")
    read.add_argument("id")
    for name in ("relations", "conflicts", "sources", "impact"):
        p = sub.add_parser(name)
        p.add_argument("id")
        if name in ("relations", "impact"):
            p.add_argument("--hops", type=int, default=2)
    args = parser.parse_args()
    store = None
    try:
        if args.command == "build":
            result = build(args.root, args.expected_version)
        else:
            store = Store(args.root, args.expected_version)
            actions = {"validate": store.status, "status": store.status,
                       "search": lambda: store.search(args.query, include_inactive=args.include_inactive, include_examples=args.include_examples),
                       "read": lambda: store.read_card(args.id),
                       "relations": lambda: store.relations(args.id, hops=args.hops),
                       "conflicts": lambda: store.conflicts(args.id), "sources": lambda: store.trace_sources(args.id),
                       "impact": lambda: store.impact(args.id, args.hops)}
            result = actions[args.command]()
        print(encoded(result), end="")
    except (KBError, OSError, sqlite3.Error) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    finally:
        if store:
            store.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
