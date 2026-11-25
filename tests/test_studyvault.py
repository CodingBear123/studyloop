"""Tests for the StudyVault data layer and the server's bank-round tracking.

    python3 -m unittest discover -s tests
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "skills" / "studyloop" / "app"
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

    def test_check_warns_about_missing_embedded_images(self):
        (self.v.path / "attachments").mkdir()
        (self.v.path / "attachments" / "graph.png").write_bytes(b"\x89PNG")
        q = {"id": "cl-001", "type": "single", "concept": "late binding", "answer": 0,
             "prompt": "Which plot? ![[graph.png]] and ![[attachments/graph.png|300]], not `![[code.png]]`",
             "options": ["![[gone.png|Alt]]", "b"]}
        self.assertEqual(sv.embedded_images(q), ["graph.png", "attachments/graph.png", "gone.png"])
        sv.write_json(self.v.bank_dir / "closures.json", {"area": "closures", "title": "Closures", "questions": [q]})
        errs, warns = self.v.check()
        self.assertEqual(errs, [])
        self.assertEqual([w for w in warns if "embeds" in w],
                         ["question-bank/closures.json: cl-001 embeds ![[gone.png]], which is not in the vault"])

    def test_record_and_recompute(self):
        self.v.record([
            {"area": "closures", "concept": "late binding", "correct": False,
             "confusion": "thought i was captured by value", "key_point": "closures look names up at call time"},
            {"area": "closures", "concept": "nonlocal", "correct": True},
        ], today="2026-11-24")
        rows, notes = self.v.concepts("closures")
        self.assertEqual([(r["name"], r["attempts"], r["correct"], r["status"]) for r in rows],
                         [("late binding", 1, 0, "open"), ("nonlocal", 1, 1, "solved")])
        self.assertIn("late binding", notes)
        self.assertNotIn(sv.PLACEHOLDER, self.v.concept_path("closures").read_text())
        st = self.v.stats()
        self.assertEqual((st["total"], st["correct"], st["rate"], st["unresolved"]), (2, 1, 50, 1))
        self.assertEqual(self.v.check()[0], [])
        # right the second time: solved, note kept as history
        self.v.record([{"area": "closures", "concept": "Late Binding", "correct": True}], today="2026-11-25")
        rows, notes = self.v.concepts("closures")
        self.assertEqual((rows[0]["name"], rows[0]["attempts"], rows[0]["correct"], rows[0]["status"]),
                         ("late binding", 2, 1, "solved"))
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


    def test_updating_the_last_row_keeps_the_table_apart(self):
        t = sv.concept_template("Area")
        for correct in (False, True, False):  # the last row is updated in place three times
            t = sv.apply_answer(t, "c1", correct, "mixed up", "the point", "2026-11-24")
        t = sv.apply_answer(t, "c2", False, "x", "y", "2026-11-24")  # a new concept lands in the table
        rows, notes = sv.parse_concepts_text(t)
        self.assertEqual([(r["name"], r["attempts"], r["correct"]) for r in rows], [("c1", 3, 1), ("c2", 1, 0)])
        self.assertNotIn("|###", t)
        self.assertIn("|\n\n### Error Notes", t)


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
        self.assertEqual([r["status"] for r in rows], ["open", "untested", "open"])
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
        self.assertEqual((rows[1]["attempts"], rows[1]["last"], rows[1]["status"]), (1, "2026-11-24", "open"))
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
        self.assertEqual(rows[0]["status"], "open")
        self.assertIn("because", notes["late binding"])
        self.assertEqual(self.app.v.check()[0], [])

    def test_question_types(self):
        ok = [
            {"id": "m", "type": "multi", "prompt": "p", "options": ["a", "b", "c"], "answer": [0, 2]},
            {"id": "k", "type": "kprim", "prompt": "p", "statements": ["s1", "s2", "s3", "s4"],
             "answer": [True, False, False, True]},
            {"id": "n", "type": "numeric", "prompt": "p", "answer": 7.7, "tolerance": 0.05, "unit": "%"},
        ]
        for q in ok:
            self.assertEqual(sv.validate_question(q, need_answer=True), [], q["id"])
        bad = [
            {"id": "m", "type": "multi", "prompt": "p", "options": ["a", "b"], "answer": []},
            {"id": "m", "type": "multi", "prompt": "p", "options": ["a", "b"], "answer": [0, 5]},
            {"id": "k", "type": "kprim", "prompt": "p", "statements": ["s1", "s2"], "answer": [True]},
            {"id": "k", "type": "kprim", "prompt": "p", "statements": ["s1", "s2"], "answer": [1, 0]},
            {"id": "n", "type": "numeric", "prompt": "p", "answer": "7.7"},
            {"id": "n", "type": "numeric", "prompt": "p", "answer": 1, "tolerance": -1},
            {"id": "n", "type": "numeric", "prompt": "p"},
        ]
        for q in bad:
            self.assertNotEqual(sv.validate_question(q, need_answer=True), [], q)
        # Claude-written rounds leave the key out
        self.assertEqual(sv.validate_question({"type": "kprim", "prompt": "p", "statements": ["a", "b"]}), [])

    def test_bank_round_shuffles_and_tracks_new_types(self):
        self.app.v.put_bank("closures", {"questions": [
            {"id": "m-1", "type": "multi", "concept": "free variables", "prompt": "p",
             "options": ["a", "b", "c", "d"], "answer": [1, 3]},
            {"id": "k-1", "type": "kprim", "concept": "cell objects", "prompt": "p",
             "statements": ["w", "x", "y", "z"], "answer": [True, True, False, False]}]})
        r = self.app.sample_round(["closures"], 4, None)
        by = {q["id"]: q for q in r["questions"]}
        m, k = by["m-1"], by["k-1"]
        self.assertEqual(sorted(m["options"][i] for i in m["answer"]), ["b", "d"])
        self.assertEqual({s for s, a in zip(k["statements"], k["answer"]) if a}, {"w", "x"})
        self.app.save_results({"round_id": r["id"], "source": "bank", "answers": [
            {"n": 1, "id": "m-1", "area": "closures", "concept": "free variables", "type": "multi",
             "choices": m["answer"], "choice_text": "b; d", "correct": True},
            {"n": 2, "id": "k-1", "area": "closures", "concept": "cell objects", "type": "kprim",
             "tf": [True, True, True, False], "choice_text": "1 true, 2 true, 3 true, 4 false", "correct": False}]})
        latest = sv.load_json(self.app.v.bank_dir / "results" / "latest.json")
        self.assertTrue(latest["tracked"])
        self.assertEqual(latest["tracked_count"], 2)
        status = {r["name"]: r["status"] for r in self.app.v.concepts("closures")[0]}
        self.assertEqual(status, {"free variables": "solved", "cell objects": "open"})
        text = "\n".join(server.question_text(dict(k, type="kprim")))
        self.assertIn("STATEMENTS", text)
        self.assertIn("CORRECT:", text)

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
        self.assertEqual((rows[0]["name"], rows[0]["status"]), ("cell objects", "open"))
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
        self.assertEqual(self.app.v.concepts("closures")[0][0]["status"], "solved")

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

    def test_ask_includes_code_the_question_calls(self):
        d = self.app.v.path / "01-Closures"
        (d / "Saver.md").write_text("# Saver\n```python\nclass Saver:\n    def save(self, x):\n        pass\n```\n"
                                    "```python\ndef save(writer, thing):\n    for item in thing:\n        save(writer, item)\n```\n")
        defs = self.app.notes.definitions("`x = [1]; x.append(x)`, then `save(writer, x)`. print(len(x))?")
        self.assertEqual(len(defs), 1)
        self.assertIn("def save(writer, thing)", defs[0][1])  # the function, not the method; no print/len/append
        self.assertEqual(self.app.notes.definitions("def save(w, t): ...\nsave(w, 1)"), [])  # defined in the question
        seen = {}
        real = server.run_claude
        server.run_claude = lambda prompt, model=None, schema=None, timeout=0: seen.update(p=prompt) or "ok"
        try:
            self.app.ask({"message": "what does save(writer, x) do?"})
        finally:
            server.run_claude = real
        self.assertIn("CODE FROM THE COURSE NOTES (Saver)", seen["p"])

    def test_model_ids_and_saved_prefs(self):
        for ok in ("opus", "fable", "claude-opus-4-8", "claude-sonnet-4-6[1m]", "claude-haiku-5-5"):
            self.assertEqual(server.pick_model(ok), ok)
        for bad in ("gpt-5", "--tools", "claude-", "claude-opus 4", "", None, 3):
            self.assertEqual(server.pick_model(bad), server.CLAUDE_MODEL)
        real = server.PREFS_FILE
        with tempfile.TemporaryDirectory() as tmp:
            server.PREFS_FILE = Path(tmp) / "sub" / "prefs.json"
            try:
                self.assertEqual(server.read_prefs(), {})
                server.write_prefs({"theme": "dark"})
                self.assertEqual(server.write_prefs({"model": "claude-opus-4-8", "theme": "neon", "x": 1}),
                                 {"theme": "dark", "model": "claude-opus-4-8"})
                html = server.index_html()
                self.assertIn('window.STUDY_PREFS = {"theme": "dark", "model": "claude-opus-4-8"};', html)
                self.assertLess(html.index("STUDY_PREFS"), html.index("applyTheme"))
            finally:
                server.PREFS_FILE = real

    def test_language_comes_from_the_notes(self):
        with tempfile.TemporaryDirectory() as d:
            v = Path(d) / "StudyVault"
            (v / "01-Basics").mkdir(parents=True)
            sv.write_json(v / "studyvault.json", {"subject": "X", "language": "en", "areas": []})
            self.assertEqual(sv.Vault(v).lang, "en")  # no notes yet: the manifest decides
            (v / "01-Basics" / "Grundlagen.md").write_text(
                "Die Bank ist ein Unternehmen, das Kredite vergibt und Einlagen von den Kunden annimmt. " * 10, encoding="utf-8")
            self.assertEqual(sv.detect_language(v), "de")
            self.assertEqual(sv.Vault(v).lang, "de")
            (v / "01-Basics" / "Grundlagen.md").write_text("The bank is a firm that lends and takes deposits from the public. " * 10)
            self.assertEqual(sv.Vault(v).lang, "en")

    def test_every_answer_type_counts_as_answered(self):
        for a in ({"choice": 0}, {"choices": [1, 2]}, {"tf": [None, True]}, {"text": " 42 "}):
            self.assertTrue(server.answered(a), a)
        for a in ({"choice": None}, {"choices": []}, {"tf": [None, None]}, {"text": "  "}, {}):
            self.assertFalse(server.answered(a), a)

    def test_explanation_follows_the_shuffle(self):
        text = "Kurz vorweg.\n(1) wahr: eins.\n(2) falsch: zwei\n  mit Fortsetzung.\n(3) wahr: drei.\n(4) falsch: vier."
        self.assertEqual(server.reorder_explanation(text, [3, 0, 2, 1]),
                         "Kurz vorweg.\n(1) falsch: vier.\n(2) wahr: eins.\n(3) wahr: drei.\n(4) falsch: zwei\n  mit Fortsetzung.")
        self.assertEqual(server.reorder_explanation("A) yes\nB) no", [1, 0], letters=True), "A) no\nB) yes")
        self.assertEqual(server.reorder_explanation("No numbers (2) here.", [1, 0]), "No numbers (2) here.")
        self.assertIsNone(server.reorder_explanation("(1) only one of two", [1, 0]))

    def test_old_themes_become_light(self):
        self.assertEqual(server.clean_prefs({"theme": "tide"}), {"theme": "light"})
        self.assertEqual(server.clean_prefs({"theme": "garden"}), {"theme": "light"})
        self.assertEqual(server.clean_prefs({"theme": "system"}), {"theme": "system"})
        self.assertEqual(server.clean_prefs({"theme": "neon"}), {})

    def test_autostart_files(self):
        import launch
        import plistlib
        real = launch.AGENT, launch.STARTUP, launch.DESKTOP
        with tempfile.TemporaryDirectory() as tmp:
            launch.AGENT, launch.STARTUP, launch.DESKTOP = (Path(tmp) / "a" / "agent.plist", Path(tmp) / "b" / "s.vbs",
                                                            Path(tmp) / "c" / "s.desktop")
            try:
                path = launch.set_autostart(True)
                self.assertTrue(path.is_file())
                self.assertTrue(str(path).startswith(tmp))
                text = path.read_text(encoding="utf-8")
                self.assertIn("launch.py", text)
                self.assertIn("--no-browser", text)
                if path.suffix == ".plist":
                    plist = plistlib.loads(path.read_bytes())
                    self.assertTrue(plist["RunAtLoad"])
                    self.assertEqual(plist["ProgramArguments"][-1], "--no-browser")
                self.assertEqual(launch.set_autostart(False), path)
                self.assertFalse(path.exists())
                launch.set_autostart(False)  # already off: no error
            finally:
                launch.AGENT, launch.STARTUP, launch.DESKTOP = real

    def test_launcher_remembers_folder(self):
        import launch
        real = server.PREFS_FILE
        with tempfile.TemporaryDirectory() as tmp:
            server.PREFS_FILE = Path(tmp) / "prefs.json"
            try:
                server.write_prefs({"theme": "dark"})
                root = self.app.vault.parent
                folder, vaults = launch.pick_vaults(str(root), False)
                self.assertEqual(vaults, [str(self.app.vault.resolve())])
                self.assertEqual(launch.pick_vaults(None, False), (folder, vaults))  # remembered, no dialog
                server.write_prefs({"model": "opus"})  # the page's saves keep the folder
                self.assertEqual(server.raw_prefs()["folder"], folder)
                self.assertEqual(server.read_prefs(), {"theme": "dark", "model": "opus"})
            finally:
                server.PREFS_FILE = real

    def test_progress_shape(self):
        p = self.app.progress()
        self.assertEqual({"areas", "open", "activity", "total"}, set(p))
        self.assertEqual(p["areas"][0]["bank"], 1)


if __name__ == "__main__":
    unittest.main()


class HTTPSecurityTests(unittest.TestCase):
    """The real HTTP server: only the study page itself may use it, not other websites."""

    def setUp(self):
        import threading
        from http.server import ThreadingHTTPServer
        self.tmp = tempfile.TemporaryDirectory()
        v = make_vault(self.tmp.name)
        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), server.make_handler({"Course": server.App(v.path)}))
        self.port = self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        self.tmp.cleanup()

    def req(self, method, path, body=None, headers=None):
        import http.client
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        c.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
        h = {"Host": f"127.0.0.1:{self.port}", "Content-Type": "application/json", **(headers or {})}
        data = body.encode() if isinstance(body, str) else body
        if data is not None and "Content-Length" not in h:
            h["Content-Length"] = str(len(data))
        for k, val in h.items():
            if val is not None:
                c.putheader(k, val)
        c.endheaders(data)
        r = c.getresponse()
        out = r.status, r.read()
        c.close()
        return out

    def test_page_works(self):
        self.assertEqual(self.req("GET", "/")[0], 200)
        self.assertEqual(self.req("GET", "/api/vaults", headers={"Host": f"localhost:{self.port}"})[0], 200)
        ok = {"Origin": f"http://127.0.0.1:{self.port}"}
        self.assertEqual(self.req("POST", "/api/note-ref", '{"area": "closures", "question": {}}', ok)[0], 200)
        self.assertEqual(self.req("PUT", "/api/tasks?vault=Course", '{"tasks": []}', ok)[0], 200)

    def test_app_files(self):
        # what makes it installable: manifest, service worker, icons
        for path, ctype in (("/manifest.webmanifest", "application/manifest+json"), ("/sw.js", "text/javascript"),
                            ("/icons/icon-192.png", "image/png"), ("/icons/icon-maskable-512.png", "image/png")):
            status, body = self.req("GET", path)
            self.assertEqual(status, 200, path)
            self.assertTrue(body, path)
        manifest = json.loads(self.req("GET", "/manifest.webmanifest")[1])
        self.assertEqual((manifest["name"], manifest["display"]), ("Studyloop", "standalone"))
        self.assertEqual(self.req("GET", "/icons/nope.png")[0], 404)
        self.assertEqual(self.req("GET", "/icons/../server.py")[0], 404)

    def test_other_websites_are_refused(self):
        # DNS rebinding: a foreign Host can't read anything
        self.assertEqual(self.req("GET", "/api/vaults", headers={"Host": "evil.example:%d" % self.port})[0], 403)
        self.assertEqual(self.req("GET", "/", headers={"Host": "evil.example"})[0], 403)
        # cross-site "simple" POSTs (no preflight) are refused before they touch the vault
        res = '{"round_id": "evil-1", "source": "bank", "answers": []}'
        self.assertEqual(self.req("POST", "/api/results", res, {"Content-Type": "text/plain"})[0], 403)
        self.assertEqual(self.req("POST", "/api/results", res, {"Content-Type": None})[0], 403)
        self.assertEqual(self.req("POST", "/api/results", res, {"Origin": "https://evil.example"})[0], 403)
        self.assertEqual(self.req("POST", "/api/ask", '{"message": "hi"}', {"Origin": "null"})[0], 403)
        self.assertFalse((Path(self.tmp.name) / "Course/StudyVault/question-bank/results/evil-1.json").exists())

    def test_bad_bodies(self):
        self.assertEqual(self.req("POST", "/api/note-ref", "{}", {"Content-Length": "-1"})[0], 400)
        self.assertEqual(self.req("POST", "/api/note-ref", "{}", {"Content-Length": "99999999999"})[0], 400)
        self.assertEqual(self.req("POST", "/api/note-ref", "[1, 2]")[0], 400)
        self.assertEqual(self.req("POST", "/api/note-ref", "not json")[0], 400)
        self.assertEqual(self.req("PUT", "/api/tasks", '{"tasks": [1]}')[0], 500)  # answered, not dropped
    def test_update_and_restart_need_the_page(self):
        evil = {"Origin": "https://evil.example"}
        self.assertEqual(self.req("POST", "/api/update", "{}", evil)[0], 403)
        self.assertEqual(self.req("POST", "/api/restart", "{}", {"Content-Type": "text/plain"})[0], 403)
        self.assertEqual(self.req("GET", "/api/update", headers={"Host": "evil.example"})[0], 403)


class UpdaterTests(unittest.TestCase):
    """The Update button: a git checkout that follows GitHub (here a local bare repository)."""

    def setUp(self):
        import subprocess
        import updater
        self.up, self.old_repo = updater, updater.REPO
        self.tmp = tempfile.TemporaryDirectory()
        t = Path(self.tmp.name)
        self.g = lambda cwd, *a: subprocess.run(["git", "-C", str(cwd), "-c", "user.name=t", "-c", "user.email=t@t",
                                                 *a], check=True, capture_output=True, text=True).stdout
        subprocess.run(["git", "init", "--bare", "-q", "-b", "main", str(t / "origin.git")], check=True)
        for name in ("mine", "other"):
            subprocess.run(["git", "clone", "-q", str(t / "origin.git"), str(t / name)], check=True, capture_output=True)
        self.mine, self.other = t / "mine", t / "other"
        self.commit(self.other, "skills/studyloop/SKILL.md", "v1", "first")
        self.g(self.other, "push", "-q", "origin", "HEAD:main")
        self.g(self.mine, "pull", "-q", "origin", "main")
        self.g(self.mine, "branch", "-q", "--set-upstream-to=origin/main")
        updater.REPO = self.mine

    def tearDown(self):
        self.up.REPO = self.old_repo
        self.tmp.cleanup()

    def commit(self, repo, rel, text, msg):
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text)
        self.g(repo, "add", "-A")
        self.g(repo, "commit", "-q", "-m", msg)

    def test_finds_and_pulls_an_update(self):
        self.assertFalse(self.up.status(force=True)["available"])
        self.commit(self.other, "skills/studyloop/SKILL.md", "v2", "Better hints")
        self.g(self.other, "push", "-q", "origin", "HEAD:main")
        st = self.up.status(force=True)
        self.assertEqual((st["behind"], st["can_update"], st["changes"]), (1, True, ["Better hints"]))
        self.up.apply()
        self.assertEqual((self.mine / "skills/studyloop/SKILL.md").read_text(), "v2")
        self.assertFalse(self.up.status(force=True)["available"])

    def test_local_edits_are_not_overwritten(self):
        self.commit(self.other, "skills/studyloop/SKILL.md", "v2", "theirs")
        self.g(self.other, "push", "-q", "origin", "HEAD:main")
        (self.mine / "skills/studyloop/SKILL.md").write_text("my edit")
        self.assertTrue(self.up.status(force=True)["local_changes"])
        with self.assertRaisesRegex(ValueError, "your own changes|Your own changes"):
            self.up.apply()
        self.assertEqual((self.mine / "skills/studyloop/SKILL.md").read_text(), "my edit")

    def test_not_a_git_checkout(self):
        self.up.REPO = Path(self.tmp.name) / "plain"
        st = self.up.status(force=True)
        self.assertFalse(st["can_update"])
        self.assertIn("installer", st["reason"])

    def test_windows_skill_copies_are_refreshed(self):
        home = Path(self.tmp.name) / "home"
        ours, theirs = home / ".claude/skills/studyloop", home / ".claude/skills/studyloop-setup"
        ours.mkdir(parents=True)
        (ours / ".claude-study-tool").write_text("old marker")
        theirs.mkdir(parents=True)
        (theirs / "SKILL.md").write_text("someone else's")
        self.assertEqual(self.up.refresh_copies(home), ["studyloop"])
        self.assertEqual((ours / "SKILL.md").read_text(), "v1")
        self.assertTrue((ours / ".studyloop").exists())
        self.assertEqual((theirs / "SKILL.md").read_text(), "someone else's")

    def test_old_skill_names_move_to_new_ones(self):
        home = Path(self.tmp.name) / "home"
        skills = home / ".claude/skills"
        skills.mkdir(parents=True)
        (skills / "study").symlink_to(self.mine / "skills" / "study")          # Mac link, dangling after the pull
        copy = skills / "study-vault"                                           # Windows copy of ours
        copy.mkdir()
        (copy / ".studyloop").write_text("ours")
        (skills / "other").symlink_to(self.mine)                               # someone else's link stays
        self.assertEqual(sorted(self.up.rename_old(home)), ["study", "study-vault"])
        self.assertFalse((skills / "study").is_symlink())
        self.assertEqual(Path(os.readlink(skills / "studyloop")), self.mine / "skills" / "studyloop")
        self.assertFalse(copy.exists())
        self.assertTrue((skills / "studyloop-setup").is_dir())
        self.assertTrue((skills / "other").is_symlink())


class StatusWordTests(unittest.TestCase):
    def test_restatus_rewrites_old_emoji(self):
        text = sv.TABLE_HEAD + "\n| x | 1 | 1 | 2026-11-24 | 🟢 |\n| y | 1 | 0 | 2026-11-24 | 🔴 |\n| z | 0 | 0 | - | ⚪ |\n"
        self.assertIn("| solved |", sv.restatus(text))
        self.assertIn("| open |", sv.restatus(text))
        self.assertIn("| neu |", sv.restatus(text, "de"))
        rows, _ = sv.parse_concepts_text(sv.restatus(text, "de"))
        self.assertEqual([r["status"] for r in rows], ["solved", "open", "untested"])

    def test_badge_has_no_emoji(self):
        self.assertEqual(sv.badge(50), "Fair")
        self.assertEqual(sv.badge(None, "de"), "Ungemessen")
