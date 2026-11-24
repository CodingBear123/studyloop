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
        data, _, _ = sv.migrate_vault(old, write=True)
        self.assertEqual(data["areas"], [{"slug": "topic-one", "title": "Topic One", "folder": "01-Topic-One"}])
        self.assertEqual(data["extra_folders"], ["00-Dashboard"])
        v = sv.Vault(old)
        self.assertEqual(v.check()[0], [])
        self.assertEqual(v.stats()["rate"], 50)


class OldFormatTests(unittest.TestCase):
    """Trackers written by older /tutor versions, as found in real vaults."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "Mathe" / "StudyVault"
        (self.root / "01 Mengen").mkdir(parents=True)
        (self.root / "01 Mengen" / "Kprim 1.1.md").write_text("x")
        (self.root / "concepts").mkdir()
        (self.root / "concepts" / "01 Mengen.md").write_text(
            "# 01 Mengen – Konzept-Tracker\n\n> Notiz oben.\n\n"
            "| Konzept | Versuche | Richtig | Zuletzt getestet | Status |\n|---|---|---|---|---|\n"
            "| Betrag \\|x\\| | 2 | 0 | 2026-11-18 | 🔴 |\n"
            "| O(|Q|²) Laufzeit | 0 | 0 | — | ⚪ |\n"
            "| Teilmenge vs. Element (Definition) | 1 | 0 | 2026-11-18 | 🔴 |\n\n"
            "### Fehlernotizen\n\n**Betrag |x|**\n- Verwechslung: a\n- Kernpunkt: b\n\n"
            "**Teilmenge vs. Element**\n- Verwechslung: c\n- Kernpunkt: d\n")
        (self.root / "Lern-Dashboard.md").write_text(
            "| 01 Mengen | 0 | 3 | 0% | 🟥 Schwach | [[concepts/01 Mengen]] |\n")
        (self.root / "notes.md").write_text("see [[concepts/01 Mengen]] and [[Lern-Dashboard]]\n")

    def tearDown(self):
        self.tmp.cleanup()

    def test_migrate_converts_and_keeps_numbers(self):
        data, _, plan = sv.migrate_vault(self.root, write=True)
        self.assertEqual(data["language"], "de")
        self.assertEqual(plan["renamed"], {"01 Mengen.md": "mengen.md"})
        self.assertIn("Teilmenge vs. Element (Definition)", plan["notes_paired"]["mengen.md"].values())
        v = sv.Vault(self.root)
        self.assertEqual(v.check(), ([], []))
        rows, notes = v.concepts("mengen")
        self.assertEqual([r["status"] for r in rows], ["🔴", "⚪", "🔴"])
        self.assertEqual(rows[0]["name"], "Betrag ∣x∣")
        self.assertEqual(v.stats()["total"], 3)
        text = v.concept_path("mengen").read_text()
        self.assertIn("> Notiz oben.", text)
        self.assertIn("### Fehlernotizen", text)
        self.assertIn("Stand pro Bereich", v.dashboard.read_text())
        self.assertIn("[[concepts/mengen]] and [[Learning Dashboard]]", (self.root / "notes.md").read_text())
        self.assertFalse((self.root / "Lern-Dashboard.md").exists())
        self.assertEqual(len(list(self.root.glob(".migrated-*/Lern-Dashboard.md"))), 1)
        # running it again changes nothing
        _, _, again = sv.migrate_vault(self.root)
        self.assertEqual((again["renamed"], again["normalized"], again["moved"]), ({}, [], []))

    def test_untested_row_becomes_tested(self):
        sv.migrate_vault(self.root, write=True)
        v = sv.Vault(self.root)
        v.record([{"area": "mengen", "concept": "O(|Q|²) Laufzeit", "correct": False,
                   "confusion": "x", "key_point": "y"}], today="2026-11-24")
        rows, notes = v.concepts("mengen")
        self.assertEqual((rows[1]["attempts"], rows[1]["last"], rows[1]["status"]), (1, "2026-11-24", "🔴"))
        self.assertIn("- Verwechslung: x", v.concept_path("mengen").read_text())
        self.assertEqual(v.check()[0], [])


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

    def test_open_answer_self_and_claude_grading(self):
        self.app.v.put_bank("closures", {"questions": [
            {"id": "c-2", "type": "open", "concept": "cell objects", "prompt": "What is a cell?",
             "model_answer": "a box shared by closure and outer scope", "explanation": "cells hold free variables"}]})
        rid = "bank-20261124-000001"
        self.app.save_results({"round_id": rid, "source": "bank", "answers": [
            {"n": 1, "id": "c-2", "area": "closures", "concept": "cell objects", "type": "open", "text": "no idea", "correct": None}]})
        self.assertFalse(sv.load_json(self.app.v.bank_dir / "results" / f"{rid}.json")["tracked"])
        r = self.app.grade_open({"round_id": rid, "n": 1, "mode": "self", "correct": False})
        self.assertEqual((r["correct"], r["tracked"]), (False, True))
        rows, notes = self.app.v.concepts("closures")
        self.assertEqual((rows[0]["name"], rows[0]["status"]), ("cell objects", "🔴"))
        self.assertIn("no idea", notes["cell objects"])
        latest = sv.load_json(self.app.v.bank_dir / "results" / "latest.json")
        self.assertTrue(latest["answers"][0]["recorded"] and latest["tracked"])
        with self.assertRaises(ValueError):  # no double counting
            self.app.grade_open({"round_id": rid, "n": 1, "mode": "self", "correct": True})
        self.assertEqual(self.app.v.check()[0], [])
        # Claude mode, with the CLI call stubbed
        rid2 = "bank-20261124-000002"
        self.app.save_results({"round_id": rid2, "source": "bank", "answers": [
            {"n": 1, "id": "c-2", "area": "closures", "concept": "cell objects", "type": "open", "text": "a shared box"}]})
        real = server.ask_claude
        server.ask_claude = lambda *a, **k: {"correct": True, "feedback": "Yes.", "confusion": "", "key_point": ""}
        try:
            r = self.app.grade_open({"round_id": rid2, "n": 1, "mode": "claude"})
        finally:
            server.ask_claude = real
        self.assertEqual((r["correct"], r["feedback"]), (True, "Yes."))
        self.assertEqual(self.app.v.concepts("closures")[0][0]["status"], "🟢")

    def test_notes_tree_read_and_question_refs(self):
        folder = self.app.v.path / "01-Closures"
        (folder / "Cells.md").write_text(
            "---\nsource: S04\n---\n# Cells\nintro\n## Late binding of loop variables\n"
            "Closures capture the variable, not the value, so late binding gives the last loop value.\n"
            "```python\n# not a heading\n```\n## Other\nunrelated text about bytes\n")
        tree = self.app.notes.tree()
        self.assertEqual(tree[0]["title"], "Closures")
        self.assertEqual(tree[0]["notes"][-1]["practice"], True)  # practice files last
        note = self.app.notes.read("01-Closures/Cells.md")
        self.assertEqual(note["meta"], {"source": "S04"})
        self.assertTrue(note["body"].startswith("# Cells"))
        for bad in ("../x.md", "concepts/../../../etc/passwd", ".migrated/x.md", "studyvault.json"):
            with self.assertRaises(ValueError):
                self.app.notes.read(bad)
        q = self.app.sample_round(["closures"], 1, None)["questions"][0]  # concept "late binding"
        self.assertEqual((q["note"]["path"], q["note"]["anchor"]), ("01-Closures/Cells.md", "late-binding-of-loop-variables"))
        self.assertEqual(self.app.notes.section_text(q["note"]["path"], q["note"]["anchor"])[1].count("not a heading"), 1)
        self.assertNotIn("bytes", self.app.notes.section_text(q["note"]["path"], q["note"]["anchor"])[1])
        explicit = self.app.notes.note_for({"ref": "Cells#Other", "concept": "late binding"})
        self.assertEqual((explicit["anchor"], explicit["auto"]), ("other", False))
        self.app.v.put_bank("closures", {"questions": [dict(self.app.v.bank_question("closures", "c-1"), ref="Nope#x")]})
        self.assertTrue(any("names no note" in w for w in self.app.v.check()[1]))

    def test_ask_passes_question_and_note(self):
        (self.app.v.path / "01-Closures" / "Cells.md").write_text("# Cells\n## Boxes\ncells are boxes\n")
        seen = {}
        real = server.run_claude
        server.run_claude = lambda prompt, model=None, schema=None, timeout=0: seen.update(p=prompt, m=model) or "An answer."
        try:
            r = self.app.ask({"message": "why?", "model": "opus", "question": {"area": "closures", "id": "c-1"},
                              "student": "B", "note": {"path": "01-Closures/Cells.md", "anchor": "boxes"},
                              "history": [{"role": "user", "text": "first"}, {"role": "claude", "text": "reply"}]})
        finally:
            server.run_claude = real
        self.assertEqual(r, {"answer": "An answer.", "model": "opus"})
        for part in ("because", "CORRECT OPTION: C", "cells are boxes", "Student: first", "Tutor: reply", "why?"):
            self.assertIn(part, seen["p"])
        self.assertEqual(server.pick_model("gpt"), server.CLAUDE_MODEL)
        with self.assertRaises(ValueError):
            self.app.ask({"message": "  "})

    def test_progress_shape(self):
        p = self.app.progress()
        self.assertEqual({"areas", "open", "activity", "total"}, set(p))
        self.assertEqual(p["areas"][0]["bank"], 1)


if __name__ == "__main__":
    unittest.main()
