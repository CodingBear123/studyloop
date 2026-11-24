"""Tests for the StudyVault data layer and the server's bank-round tracking.

    python3 -m unittest discover -s tests
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "skills" / "study" / "app"
sys.path.insert(0, str(APP))
import studyvault as sv  # noqa: E402
import server  # noqa: E402


def make_vault(tmp):
    v, _ = sv.init_vault(Path(tmp) / "Course" / "StudyVault", "Test Course",
                         ["01-Closures=Closures", "02-Binary-Data=Binary Data"], scope="sessions only")
    for a in v.areas():
        (v.path / a["folder"] / f"{a['title']} Practice.md").write_text("# practice\n[[Closures]]\n")
    (v.path / "01-Closures" / "Closures.md").write_text("# Closures\n`[[not a link]]`\n")
    return v


class VaultTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.v = make_vault(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_init_is_consistent(self):
        errs, warns = self.v.check()
        self.assertEqual(errs, [])
        self.assertEqual(warns, [])
        self.assertEqual([a["slug"] for a in self.v.areas()], ["closures", "binary-data"])
        self.assertTrue((self.v.path / "concepts" / "binary-data.md").exists())
        self.assertTrue((self.v.path / "question-bank" / "closures.json").exists())

    def test_record_and_recompute(self):
        self.v.record([
            {"area": "closures", "concept": "late binding", "correct": False,
             "confusion": "thought i was captured by value", "key_point": "closures look names up at call time"},
            {"area": "closures", "concept": "nonlocal", "correct": True},
        ], today="2026-11-24")
        rows, notes = self.v.concepts("closures")
        self.assertEqual([(r["name"], r["attempts"], r["correct"], r["status"]) for r in rows],
                         [("late binding", 1, 0, "🔴"), ("nonlocal", 1, 1, "🟢")])
        self.assertIn("late binding", notes)
        self.assertNotIn(sv.PLACEHOLDER, self.v.concept_path("closures").read_text())
        st = self.v.stats()
        self.assertEqual((st["total"], st["correct"], st["rate"], st["unresolved"]), (2, 1, 50, 1))
        self.assertEqual(self.v.check()[0], [])
        # right the second time: 🟢, note kept as history
        self.v.record([{"area": "closures", "concept": "Late Binding", "correct": True}], today="2026-11-25")
        rows, notes = self.v.concepts("closures")
        self.assertEqual((rows[0]["name"], rows[0]["attempts"], rows[0]["correct"], rows[0]["status"]),
                         ("late binding", 2, 1, "🟢"))
        self.assertIn("late binding", notes)
        self.assertEqual(self.v.check()[0], [])

    def test_wrong_again_replaces_note(self):
        a = {"area": "closures", "concept": "c", "correct": False, "confusion": "x1", "key_point": "k1 \\d"}
        self.v.record([a])
        self.v.record([dict(a, confusion="x2", key_point="k2")])
        text = self.v.concept_path("closures").read_text()
        self.assertIn("x2", text)
        self.assertNotIn("x1", text)
        self.assertEqual(text.count("**c**"), 1)

    def test_record_rejects_bad_input(self):
        with self.assertRaises(ValueError):
            self.v.record([{"area": "nope", "concept": "c", "correct": True}])
        with self.assertRaises(ValueError):
            self.v.record([{"area": "closures", "concept": "c", "correct": False}])
        self.assertEqual(self.v.stats()["total"], 0)  # nothing half-written

    def test_check_finds_problems(self):
        self.v.concept_path("closures").write_text(
            "# C\n\n" + sv.TABLE_HEAD + "\n| x | 1 | 2 | 2026-11-24 | 🟢 |\n| y | 1 | 0 | 2026-11-24 | 🔴 |\n")
        (self.v.path / "concepts" / "stray.md").write_text("# stray\n")
        (self.v.path / "question-bank" / "closures.json").write_text(json.dumps(
            {"area": "closures", "questions": [{"id": "a", "type": "single", "prompt": "p", "options": ["1", "2"]},
                                               {"id": "a", "type": "open", "prompt": "q"}]}))
        errs, _ = self.v.check()
        text = "\n".join(errs)
        for needle in ("impossible", "without an error note", "stray.md", "duplicate id", "need an answer",
                       "out of date"):
            self.assertIn(needle, text)

    def test_validate_round(self):
        self.v.put_bank("closures", {"questions": [
            {"id": "c-1", "type": "single", "concept": "c", "prompt": "p", "options": ["a", "b"], "answer": 1}]})
        ok = {"id": "claude-1", "questions": [
            {"area": "closures", "concept": "c", "type": "open", "prompt": "Why?"},
            {"bank_ref": {"area": "closures", "id": "c-1"}}]}
        self.assertEqual(self.v.validate_round(ok), [])
        bad = {"id": "claude 1", "questions": [
            {"area": "zzz", "type": "single", "prompt": "p", "options": ["a", "b"], "answer": 0},
            {"bank_ref": {"area": "closures", "id": "missing"}}]}
        errs = "\n".join(self.v.validate_round(bad))
        for needle in ("round id", "not in studyvault.json", "concept missing", "leak", "not found"):
            self.assertIn(needle, errs)

    def test_migrate_old_vault(self):
        old = Path(self.tmp.name) / "Old" / "StudyVault"
        (old / "01-Topic-One").mkdir(parents=True)
        (old / "01-Topic-One" / "01 Practice.md").write_text("x")
        (old / "00-Dashboard").mkdir()
        (old / "concepts").mkdir()
        (old / "concepts" / "topic-one.md").write_text(
            "# T\n\n" + sv.TABLE_HEAD + "\n| a | 2 | 1 | 2026-11-20 | 🟢 |\n\n### Error Notes\n")
        (old / sv.DASHBOARD).write_text("| Topic One | 1 | 1 | 50% | 🟨 Fair | [[concepts/topic-one]] |\n")
        data, _ = sv.migrate_vault(old, write=True)
        self.assertEqual(data["areas"], [{"slug": "topic-one", "title": "Topic One", "folder": "01-Topic-One"}])
        self.assertEqual(data["extra_folders"], ["00-Dashboard"])
        v = sv.Vault(old)
        self.assertEqual(v.check()[0], [])
        self.assertEqual(v.stats()["rate"], 50)


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        v = make_vault(self.tmp.name)
        v.put_bank("closures", {"questions": [
            {"id": "c-1", "type": "single", "concept": "late binding", "prompt": "p",
             "options": ["a", "b", "c"], "answer": 2, "explanation": "because"}]})
        self.app = server.App(v.path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_bank_round_tracks_itself(self):
        r = self.app.sample_round(["closures"], 4, None)
        q = r["questions"][0]
        wrong = (q["answer"] + 1) % 3
        self.app.save_results({"round_id": r["id"], "source": "bank", "answers": [
            {"n": 1, "id": "c-1", "area": "closures", "concept": "late binding", "type": "single",
             "choice": wrong, "choice_text": q["options"][wrong], "answer": q["answer"], "correct": False}]})
        latest = sv.load_json(self.app.v.bank_dir / "results" / "latest.json")
        self.assertTrue(latest["tracked"])
        self.assertTrue(latest["answers"][0]["recorded"])
        rows, notes = self.app.v.concepts("closures")
        self.assertEqual(rows[0]["status"], "🔴")
        self.assertIn("because", notes["late binding"])
        self.assertEqual(self.app.v.check()[0], [])

    def test_progress_shape(self):
        p = self.app.progress()
        self.assertEqual({"areas", "open", "activity", "total"}, set(p))
        self.assertEqual(p["areas"][0]["bank"], 1)


if __name__ == "__main__":
    unittest.main()
