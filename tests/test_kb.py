"""Acceptance tests: all scientific-looking content is synthetic and stays in fixtures."""
import contextlib
import datetime as dt
import hashlib
import json
from pathlib import Path
import selectors
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from kb import KBError, Store, build, parse


class FixtureCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        shutil.copytree(ROOT / "tests/fixtures", self.root, dirs_exist_ok=True)

    def change(self, kid, update=None, body=None):
        folder = "sources" if kid.startswith("S-") else "knowledge"
        path = self.root / folder / (kid + ".md")
        meta, oldbody, _ = parse(path.read_bytes(), str(path))
        if update:
            update(meta)
        path.write_text("---\n" + json.dumps(meta, ensure_ascii=False, indent=2) + "\n---\n" + (oldbody if body is None else body), encoding="utf-8")

    @contextlib.contextmanager
    def store(self, **kw):
        s = Store(self.root, **kw)
        try:
            yield s
        finally:
            s.close()

    def ids(self, result):
        return {c["id"] for c in result["results"]}

    def tree_hash(self):
        return {p.relative_to(self.root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in self.root.rglob("*") if p.is_file()}


class Acceptance(FixtureCase):
    def test_empty_formal_collection(self):
        s = Store(ROOT)
        self.addCleanup(s.close)
        self.assertEqual(s.status()["knowledge_count"], 0)
        self.assertEqual(s.status()["source_count"], 0)
        self.assertEqual(s.search("合成测试")["results"], [])

    def test_long_chinese_tail_and_exact_order(self):
        body = "# TEST FIXTURE ONLY\n\n## 长中文章节\n\n" + "这是没有空格的长中文测试段落。" * 7000
        body += "\n\n后半段特有词：稀疏条件迁移。只用于测试。\n"
        self.change("K-900001", body=body)
        with self.store() as s:
            result = s.search("稀疏条件迁移", include_examples=True)
            self.assertEqual(self.ids(result), {"K-900001"})
            self.assertEqual(s.search("移迁件条疏稀", include_examples=True)["results"], [])
            self.assertIn("稀疏条件迁移", result["results"][0]["match_context"])
            self.assertEqual(s.read_card("K-900001")["markdown"], (self.root/"knowledge/K-900001.md").read_text())
        build(self.root)
        db = sqlite3.connect(self.root / ".cache/search.sqlite")
        self.addCleanup(db.close)
        self.assertIn(("K-900001",), db.execute('SELECT id FROM fulltext WHERE fulltext MATCH ?', ('"稀" AND "疏" AND "迁"',)).fetchall())

    def test_default_status_and_examples_and_replication_are_separate(self):
        with self.store() as s:
            self.assertEqual(s.search("合成测试")["results"], [])
            self.assertEqual(self.ids(s.search("合成测试", include_examples=True)), {"K-900001","K-900002","K-900003","K-900004"})
            self.assertEqual(len(s.search("合成测试", include_inactive=True, include_examples=True)["results"]), 7)
            self.assertEqual(s.read_card("K-900001")["metadata"]["evidence"]["replication"], "not_attempted")
        # Simulate nonexample content only inside a temporary test store.
        self.change("S-900001", lambda m: m.update(example=False, source_type="documentation"))
        for n in range(1,8):
            self.change(f"K-90000{n}", lambda m: m.update(example=False))
        with self.store() as s:
            self.assertEqual(self.ids(s.search("合成测试")), {"K-900001","K-900002","K-900003","K-900004"})

    def test_expiry_evaluated_at_query_time(self):
        build(self.root)
        with self.store(today=dt.date(2100,1,1)) as s:
            self.assertEqual(s.status()["disk_index"], "current")
            self.assertEqual(s.search("合成测试", include_examples=True)["results"], [])

    def test_conditions_preserved_and_conflicts_do_not_overwrite(self):
        before = self.tree_hash()
        with self.store() as s:
            result = s.conflicts("K-900001")
            self.assertEqual(len(result["edges"]), 1)
            self.assertEqual(result["edges"][0]["verification"], "unverified")
            scopes = {n["conditions"][0] for n in result["nodes"]}
            self.assertEqual(len(scopes), 2)
            self.assertIn("do not automatically", result["review_advice"])
        self.assertEqual(before, self.tree_hash())

    def test_two_hops_and_reverse_update_impact(self):
        with self.store() as s:
            out = s.relations("K-900001", hops=2, types=["depends_on"])
            self.assertEqual({n["id"] for n in out["nodes"]}, {"K-900001","K-900002","K-900004"})
            self.assertEqual({e["hop"] for e in out["edges"]}, {1,2})
            incoming = s.impact("K-900004", 2)
            self.assertTrue({"K-900001","K-900002"} <= {n["id"] for n in incoming["nodes"]})
            self.assertIn("K-900001", s.impact("S-900001", 2)["direct_citations"])
            self.assertEqual(s.relations("K-900001", hops=1, types=["depends_on"])["edges"][0]["target"], "K-900002")

    def test_sources_and_card_return_complete_original_and_locators(self):
        with self.store() as s:
            result = s.trace_sources("K-900001")
            source = result["sources"][0]
            self.assertEqual(source["markdown"], (self.root/"sources/S-900001.md").read_text())
            self.assertEqual(source["metadata"]["version"], "fixture-v1")
            self.assertEqual(result["citations"][0]["locator"], "fixture-scope")
            self.assertIn("Fixture scope", source["sections"])
            self.assertIn("example.invalid", source["metadata"]["original_url"])

    def test_modify_delete_rename_stale_and_rebuild_consistency(self):
        build(self.root)
        old = json.loads((self.root/"index.json").read_text())["input_version"]
        self.change("K-900003", body="# TEST FIXTURE ONLY\n\n## Scope\n\n修改后专用检索标记。\n")
        (self.root/"knowledge/K-900003.md").rename(self.root/"knowledge/renamed-card.md")
        (self.root/"knowledge/K-900006.md").unlink()
        with self.store() as s:
            self.assertNotEqual(s.version, old)
            self.assertEqual(s.status()["disk_index"], "missing_or_stale")
            self.assertEqual(self.ids(s.search("修改后专用检索标记", include_examples=True)), {"K-900003"})
            self.assertEqual(s.read_card("K-900003")["path"], "knowledge/renamed-card.md")
            with self.assertRaisesRegex(KBError, "unknown stable ID"):
                s.read_card("K-900006")
        with self.assertRaisesRegex(KBError, "VERSION_MISMATCH"):
            Store(self.root, old)
        build(self.root)
        current = json.loads((self.root/"index.json").read_text())
        self.assertNotIn("K-900006", {k["id"] for k in current["knowledge"]})
        self.assertEqual(next(k for k in current["knowledge"] if k["id"]=="K-900003")["path"], "knowledge/renamed-card.md")
        with self.store() as s:
            self.assertEqual(s.status()["disk_index"], "current")
        first = (self.root/"index.json").read_bytes(), (self.root/"index.md").read_bytes()
        build(self.root)
        self.assertEqual(first, ((self.root/"index.json").read_bytes(), (self.root/"index.md").read_bytes()))

    def test_index_deleted_or_corrupt_is_safe_and_readonly(self):
        build(self.root)
        (self.root/"index.json").write_text('{"input_version":"invalid"}')
        (self.root/".cache/search.sqlite").write_bytes(b"not a database")
        before = self.tree_hash()
        with self.store() as s:
            self.assertEqual(s.status()["disk_index"], "missing_or_stale")
            self.assertEqual(len(s.search("合成测试", include_examples=True)["results"]), 4)
        self.assertEqual(before, self.tree_hash())
        build(self.root)
        db = sqlite3.connect(self.root / ".cache/search.sqlite")
        self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        db.close()
        (self.root/"index.json").unlink()
        (self.root/"index.md").unlink()
        (self.root/".cache/search.sqlite").unlink()
        with self.store() as s:
            self.assertEqual(s.status()["disk_index"], "missing_or_stale")
        build(self.root)
        self.assertTrue((self.root/".cache/search.sqlite").is_file())

    def test_duplicate_id_and_dangling_relation_are_rejected(self):
        p = self.root/"knowledge/K-900001.md"
        shutil.copy(p, p.with_name("duplicate.md"))
        with self.assertRaisesRegex(KBError, "duplicate stable ID"):
            Store(self.root)
        p.with_name("duplicate.md").unlink()
        (self.root/"knowledge/K-900004.md").unlink()
        with self.assertRaisesRegex(KBError, "missing relation target K-900004"):
            Store(self.root)

    def test_source_completeness_and_version_checked(self):
        self.change("S-900001", lambda m: m.update(version="fixture-v2"))
        with self.assertRaisesRegex(KBError, "source version mismatch"):
            Store(self.root)
        self.change("S-900001", lambda m: m.update(version="fixture-v1", locators={}))
        with self.assertRaisesRegex(KBError, "locators"):
            Store(self.root)

    def test_dependency_cycle_has_explicit_path(self):
        def add(m):
            m["relations"].append({"type":"depends_on","target":"K-900001","reason":"synthetic cycle",
                                   "conditions":["test only"],"evidence":m["sources"],"verification":"unverified"})
        self.change("K-900004", add)
        with self.assertRaisesRegex(KBError, "dependency cycle: K-900001 -> K-900002 -> K-900004 -> K-900001"):
            Store(self.root)

    def test_symlink_and_path_escape_rejected(self):
        (self.root/"knowledge/external.md").symlink_to(self.root/"sources/S-900001.md")
        with self.assertRaisesRegex(KBError, "symlink"):
            Store(self.root)

    def test_schema_rejects_unknown_fields_and_bad_relation_types(self):
        self.change("K-900001", lambda m: m.update(unknown_field="typo"))
        with self.assertRaisesRegex(KBError, "unknown field"):
            Store(self.root)
        self.change("K-900001", lambda m: m.pop("unknown_field"))
        def malformed(m):
            m["relations"][0]["target"] = ["K-900002"]
        self.change("K-900001", malformed)
        with self.assertRaisesRegex(KBError, "expected string"):
            Store(self.root)


class MCPAcceptance(FixtureCase):
    def start(self):
        process = subprocess.Popen([sys.executable,"-B",str(ROOT/"scripts/mcp_server.py"),"--root",str(self.root)],
                                   stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE, text=True, encoding="utf-8")
        self.addCleanup(self.stop, process)
        return process

    @staticmethod
    def stop(process):
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        for stream in (process.stdin,process.stdout,process.stderr):
            stream.close()

    def send(self, process, value):
        process.stdin.write(json.dumps(value, ensure_ascii=False)+"\n")
        process.stdin.flush()

    def receive(self, process):
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            self.assertTrue(selector.select(timeout=10), "MCP response timed out")
        line = process.stdout.readline()
        self.assertTrue(line, "MCP process ended unexpectedly")
        return json.loads(line)

    def rpc(self, process, method, params=None, rid=1):
        self.send(process, {"jsonrpc":"2.0","id":rid,"method":method,"params":params or {}})
        return self.receive(process)

    def initialize(self, process):
        result = self.rpc(process,"initialize",{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"stdlib-acceptance-client","version":"1"}})["result"]
        self.assertEqual(result["protocolVersion"], "2025-11-25")
        self.send(process,{"jsonrpc":"2.0","method":"notifications/initialized"})
        return result

    def call(self, process, name, arguments=None):
        return self.rpc(process,"tools/call",{"name":name,"arguments":arguments or {}})

    def test_mcp_subprocess_all_tools_and_no_writes(self):
        self.change("K-900001", body="# TEST FIXTURE ONLY\n\n## 长章节\n\n"+"长中文内容。"*7000+"\n后半段词语云端稀疏迁移\n")
        before = self.tree_hash()
        process = self.start()
        self.initialize(process)
        tools = self.rpc(process,"tools/list")["result"]["tools"]
        expected = {"search_knowledge","read_card","read_relations","view_conflicts","trace_sources","query_update_impact","index_status"}
        self.assertEqual({t["name"] for t in tools}, expected)
        self.assertTrue(all(t["annotations"]["readOnlyHint"] for t in tools))
        inputs = {"search_knowledge":{"query":"云端稀疏迁移","include_examples":True}, "read_card":{"id":"K-900001"},
                  "read_relations":{"id":"K-900001","hops":2}, "view_conflicts":{"id":"K-900001"},
                  "trace_sources":{"id":"K-900001"}, "query_update_impact":{"id":"K-900004","hops":2}, "index_status":{}}
        results = {}
        for name, arguments in inputs.items():
            result = self.call(process,name,arguments)["result"]
            self.assertFalse(result["isError"], result)
            self.assertEqual(json.loads(result["content"][0]["text"]), result["structuredContent"])
            results[name] = result["structuredContent"]
        self.assertEqual(self.ids(results["search_knowledge"]), {"K-900001"})
        self.assertEqual(results["read_card"]["markdown"], (self.root/"knowledge/K-900001.md").read_text())
        self.assertIn("K-900001", {n["id"] for n in results["query_update_impact"]["nodes"]})
        self.assertEqual(results["trace_sources"]["sources"][0]["markdown"], (self.root/"sources/S-900001.md").read_text())
        self.assertEqual(self.call(process,"search_knowledge",{"query":"合成测试"})["result"]["structuredContent"]["results"], [])
        self.assertEqual(self.call(process,"write_card",{"id":"K-900001"})["error"]["code"], -32602)
        self.assertEqual(self.call(process,"read_card",{"id":"../../etc/passwd"})["error"]["code"], -32602)
        self.assertEqual(self.call(process,"read_relations",{"id":"K-900001","hops":True})["error"]["code"], -32602)
        self.assertEqual(self.call(process,"read_card",{"id":"K-900001","write":True})["error"]["code"], -32602)
        self.assertEqual(self.tree_hash(), before)
        process.stdin.close()
        self.assertEqual(process.wait(timeout=5), 0)
        self.assertEqual(process.stderr.read(), "")

    def test_mcp_session_pins_input_and_detects_live_changes(self):
        process = self.start()
        self.initialize(process)
        current = self.call(process,"index_status")["result"]["structuredContent"]["input_version"]
        self.change("K-900003", body="# TEST FIXTURE ONLY\n\nChanged content.\n")
        result = self.call(process,"read_card",{"id":"K-900001","expected_version":current})["result"]
        self.assertTrue(result["isError"])
        self.assertIn("VERSION_MISMATCH", result["content"][0]["text"])

    def test_mcp_lifecycle_and_protocol_errors(self):
        process = self.start()
        self.assertEqual(self.rpc(process,"tools/list")["error"]["code"], -32002)
        self.assertEqual(self.rpc(process,"ping")["result"], {})
        self.initialize(process)
        self.assertEqual(self.rpc(process,"delete_everything")["error"]["code"], -32601)
        process.stdin.write("not json\n")
        process.stdin.flush()
        self.assertEqual(self.receive(process)["error"]["code"], -32700)
        self.send(process, [])
        self.assertEqual(self.receive(process)["error"]["code"], -32600)
        self.assertEqual(self.call(process,"read_card",{"id":"K-000000"})["result"]["isError"], True)


if __name__ == "__main__":
    unittest.main()
