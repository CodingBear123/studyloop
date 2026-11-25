#!/usr/bin/env python3
"""Studyloop: local quiz + progress page for StudyVaults.

Serves index.html and a small JSON API. Standard library only, binds to 127.0.0.1.
All vault reads and writes go through studyvault.py.

    python3 server.py --root DIR           # every StudyVault under DIR (default: current folder)
    python3 server.py --vault PATH [...]   # specific StudyVault folder(s)

Every API call takes ?vault=<id>, where <id> is the path from the root to the
folder that holds the StudyVault (e.g. "HS26/SoCo"). GET /api/vaults lists them.
"""
import argparse
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import notes as nt  # noqa: E402
import studyvault as sv  # noqa: E402
import updater as up  # noqa: E402

FONT_NAMES = {p.name for p in (HERE / "fonts").glob("*.woff2")}
ICON_NAMES = {p.name for p in (HERE / "icons").glob("*.png")}
# installable app: manifest and service worker sit next to index.html
APP_FILES = {"/manifest.webmanifest": ("manifest.webmanifest", "application/manifest+json"),
             "/sw.js": ("sw.js", "text/javascript")}

# Open answers on the page: graded by the user (self-check against the model answer) or by a
# one-off headless Claude Code call (`claude -p`, no tools, no session saved). Nothing runs in
# the background: each check is one short process.
CLAUDE = os.environ.get("STUDY_CLAUDE") or shutil.which("claude")
# Aliases follow the newest model of a family; the full IDs pin one version. STUDY_CLAUDE_MODELS
# (comma-separated) replaces the list, and the page also takes any other "claude-..." ID.
ALIASES = ("sonnet", "opus", "haiku", "fable")
DEFAULT_MODELS = ALIASES + (
    "claude-fable-5-2", "claude-fable-5-1",
    "claude-opus-5-5", "claude-opus-5", "claude-opus-4-8", "claude-opus-4-7", "claude-opus-4-6",
    "claude-sonnet-5-5", "claude-sonnet-5", "claude-sonnet-4-6",
    "claude-haiku-5-5", "claude-haiku-4-5",
)
MODELS = tuple(m.strip() for m in os.environ.get("STUDY_CLAUDE_MODELS", "").split(",") if m.strip()) or DEFAULT_MODELS
MODEL_ID_RE = re.compile(r"^claude-[a-z0-9][a-z0-9.\-]{0,60}(\[1m\])?$")
CLAUDE_MODEL = os.environ.get("STUDY_CLAUDE_MODEL", "sonnet")
THEMES = ("light", "dark", "system")
OLD_THEMES = {"tide": "light", "garden": "light"}  # the three themes before light/dark
MAX_BODY = 5_000_000  # bytes; the largest legitimate body is a question bank
# Theme and model live here too, not only in the browser: localStorage is per address, so
# 127.0.0.1:8765, localhost:8765 and another port would each forget the choice.
PREFS_FILE = Path(os.environ.get("STUDY_PREFS") or Path.home() / ".config" / "studyloop" / "prefs.json")
OLD_PREFS_FILE = Path.home() / ".config" / "claude-study" / "prefs.json"  # before the rename to Studyloop
if not os.environ.get("STUDY_PREFS") and not PREFS_FILE.exists() and OLD_PREFS_FILE.is_file():
    try:
        PREFS_FILE.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(OLD_PREFS_FILE, PREFS_FILE)
    except OSError:
        pass
GRADE_SCHEMA = {
    "type": "object",
    "properties": {
        "correct": {"type": "boolean"},
        "feedback": {"type": "string"},
        "confusion": {"type": "string"},
        "key_point": {"type": "string"},
    },
    "required": ["correct", "feedback", "confusion", "key_point"],
}


def valid_model(model):
    return isinstance(model, str) and (model in MODELS or model in ALIASES or bool(MODEL_ID_RE.match(model)))


def pick_model(model):
    return model if valid_model(model) else CLAUDE_MODEL


def raw_prefs():
    """The whole prefs file (launch.py keeps the notes folder there too)."""
    try:
        d = json.loads(PREFS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return d if isinstance(d, dict) else {}


def read_prefs():
    """What the page may see and set: theme and model."""
    return clean_prefs(raw_prefs())


def clean_prefs(d):
    out = {}
    theme = OLD_THEMES.get(d.get("theme"), d.get("theme"))
    if theme in THEMES:
        out["theme"] = theme
    if valid_model(d.get("model")):
        out["model"] = d["model"]
    return out


def write_prefs(d):
    prefs = {**raw_prefs(), **clean_prefs(d if isinstance(d, dict) else {})}
    try:
        PREFS_FILE.parent.mkdir(parents=True, exist_ok=True)
        PREFS_FILE.write_text(json.dumps(prefs, indent=2) + "\n", encoding="utf-8")
    except OSError as e:
        raise ValueError(f"couldn't save preferences: {e}")
    return clean_prefs(prefs)


def index_html():
    """index.html with the saved preferences inlined, so the theme is right before first paint."""
    prefs = json.dumps(read_prefs()).replace("<", "\\u003c")
    html = (HERE / "index.html").read_text(encoding="utf-8")
    return html.replace("<!--STUDY_PREFS-->", f"<script>window.STUDY_PREFS = {prefs};</script>", 1)


def run_claude(prompt, model=None, schema=None, timeout=120):
    """One headless Claude Code call: no tools, no MCP servers, no saved session, empty working folder.

    Returns structured_output (with a schema) or the answer text."""
    if not CLAUDE:
        raise ValueError("the claude command isn't on this server's PATH")
    cmd = [CLAUDE, "-p", prompt, "--output-format", "json", "--model", pick_model(model), "--tools", "",
           "--strict-mcp-config", "--no-session-persistence"]
    if schema:
        cmd += ["--json-schema", json.dumps(schema)]
    with tempfile.TemporaryDirectory() as tmp:  # empty cwd: no project files or CLAUDE.md
        try:
            out = subprocess.run(cmd, cwd=tmp, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            raise ValueError(f"Claude took longer than {timeout // 60} minutes; try again")
    try:
        res = json.loads(out.stdout)
        if res.get("is_error"):
            raise ValueError(res.get("result") or "error")
        if schema:
            return res.get("structured_output") or json.loads(res.get("result") or "{}")
        return str(res["result"])
    except (ValueError, KeyError, TypeError) as e:
        msg = (out.stderr or "").strip().splitlines() or [str(e)]
        raise ValueError("Claude call failed: " + msg[-1][:200])


def answered(a):
    """Whether a saved answer holds anything: a choice, ticked options, a Kprim true/false or typed text."""
    return (a.get("choice") is not None or bool(a.get("choices"))
            or any(x is not None for x in a.get("tf") or []) or bool((a.get("text") or "").strip()))


def reorder_explanation(text, order, letters=False):
    """Follow a shuffle in an explanation written per item: lines starting "(1)" (Kprim) or "(A)"/"A)" (options).

    order[new] is the old index. Each marked line, with the lines after it up to the next mark, moves to its
    item's new place and gets the new number. Returns the text unchanged when nothing is marked, and None
    when the marks don't cover every item exactly once (the caller then doesn't shuffle)."""
    n = len(order)
    labels = [chr(65 + i) for i in range(n)] if letters else [str(i + 1) for i in range(n)]
    mark = re.compile(r"^(\s*(?:[-*]\s+)?(?:\*\*)?\(?)([A-H]|[a-h])(\))" if letters
                      else r"^(\s*(?:[-*]\s+)?(?:\*\*)?\()(\d)(\))")
    lines = text.split("\n")
    marked = [(i, m) for i, l in enumerate(lines) if (m := mark.match(l))]
    if not marked:
        return text
    found = [m[2].upper() for _, m in marked]
    if sorted(found) != sorted(labels):
        return None
    head = lines[:marked[0][0]]
    blocks = {}
    for k, (i, m) in enumerate(marked):
        end = marked[k + 1][0] if k + 1 < len(marked) else len(lines)
        blocks[labels.index(m[2].upper())] = (m, lines[i:end])
    out = list(head)
    for new, old in enumerate(order):
        m, block = blocks[old]
        label = labels[new] if m[2].isupper() or not letters else labels[new].lower()
        out += [m[1] + label + m[3] + block[0][m.end():]] + block[1:]
    return "\n".join(out)


def lang_word(lang):
    return "German" if lang == "de" else "English"


def question_text(q):
    """The question as plain text for a prompt: prompt, code, lettered options."""
    parts = ["QUESTION:", str(q.get("prompt") or "")]
    if q.get("code"):
        parts += ["", "CODE:", str(q["code"])]
    opts, ans, L = q.get("options") or [], q.get("answer"), "ABCDEFGH"
    if isinstance(opts, list) and opts:
        many = q.get("type") == "multi"
        parts += ["", "OPTIONS (select all that apply):" if many else "OPTIONS:"]
        parts += [f"{L[i]}) {o}" for i, o in enumerate(opts[:8])]
        if isinstance(ans, int) and not isinstance(ans, bool) and 0 <= ans < len(opts):
            parts += [f"CORRECT OPTION: {L[ans]}"]
        elif many and isinstance(ans, list):
            parts += ["CORRECT OPTIONS: " + ", ".join(L[a] for a in ans if isinstance(a, int) and 0 <= a < len(opts))]
    sts = q.get("statements") or []
    if isinstance(sts, list) and sts:
        parts += ["", "STATEMENTS (Kprim: judge each one true or false):"] + [f"{i + 1}. {x}" for i, x in enumerate(sts[:8])]
        if isinstance(ans, list) and len(ans) == len(sts):
            parts += ["CORRECT: " + ", ".join(f"{i + 1} {'true' if a else 'false'}" for i, a in enumerate(ans))]
    if q.get("type") == "numeric":
        unit = f" {q['unit']}" if q.get("unit") else ""
        parts += ["", f"ANSWER IS A NUMBER{(' in' + unit) if unit else ''}."]
        if isinstance(ans, (int, float)) and not isinstance(ans, bool):
            tol = q.get("tolerance")
            parts += [f"CORRECT ANSWER: {ans}{unit}" + (f" (± {tol})" if tol else "")]
    return parts


def ask_claude(q, text, subject, lang, model=None, note=None, code=None):
    """Grade one open answer with headless Claude Code. Returns the GRADE_SCHEMA dict."""
    parts = [
        f"You grade one open exam answer for the course \"{subject}\", like a fair human corrector.",
        "correct is true when the student has the core idea of the model answer, in their own words: a short",
        "or informal answer is fine, and a minor detail left out doesn't make it wrong. correct is false when",
        "the core idea is missing or misunderstood, or when the answer says something that is actually wrong.",
        "The model answer is a short key, not the only right answer: a detail it doesn't mention is NOT a",
        "mistake if it is true for this course. Check such details against the COURSE NOTES below; only call",
        "them wrong if the notes contradict them. If you can't tell, don't hold it against the student.",
        "Write feedback (1-3 sentences, to the student: what was right, then what would make it complete),",
        "confusion (what they actually got wrong, one line, empty if correct) and key_point (the correct idea,",
        "one line) in " + lang_word(lang) + ".", ""] + question_text(q)
    parts += ["", "MODEL ANSWER:", q.get("model_answer") or "(none)"]
    if q.get("explanation"):
        parts += ["", "EXPLANATION:", q["explanation"]]
    if note:
        parts += ["", "COURSE NOTES (the section that covers this question):", note]
    parts += code_context(code)
    parts += ["", "STUDENT ANSWER:", text.strip() or "(empty)"]
    verdict = run_claude("\n".join(parts), model, GRADE_SCHEMA)
    try:
        verdict["correct"] = bool(verdict["correct"])
    except (KeyError, TypeError):
        raise ValueError("Claude check failed: no verdict in the answer")
    return verdict


def code_context(code):
    """Prompt lines for code from the notes that the question uses."""
    out = []
    for title, block in code or ():
        out += ["", f"CODE FROM THE COURSE NOTES ({title}):", "```", block, "```"]
    return out


def ask_tutor(subject, lang, message, history=(), question=None, student=None, note=None, model=None, code=None):
    """Answer a free question from the student, with the question and the course notes as context."""
    parts = [
        f"You are a tutor for the university course \"{subject}\". The student is studying for the exam and",
        "asks you something. Answer the question they asked, clearly and briefly (usually under 200 words),",
        f"in {lang_word(lang)} unless they write in another language. Use Markdown; put code in fenced blocks",
        "with indentation kept. Base the answer on the course notes and code below; only if none of it covers",
        "the question, say so (\"the excerpts below don't show ...\") and answer from general knowledge.",
        "You have no tools and only see the excerpts below, not all the notes, so never claim something is",
        "missing from the course."]
    if question:
        parts += ["", "THE PRACTICE QUESTION THEY ARE LOOKING AT"] + question_text(question)
        for k, label in (("model_answer", "MODEL ANSWER"), ("explanation", "EXPLANATION")):
            if question.get(k):
                parts += ["", label + ":", str(question[k])]
        if student:
            parts += ["", "WHAT THE STUDENT ANSWERED:", student]
    if note:
        parts += ["", f"COURSE NOTES ({note[0]}):", note[1]]
    parts += code_context(code)
    if history:
        parts += ["", "CONVERSATION SO FAR:"]
        for h in list(history)[-10:]:
            who = "Student" if h.get("role") == "user" else "Tutor"
            parts += [f"{who}: {str(h.get('text') or '')[:3000]}"]
    parts += ["", "STUDENT'S QUESTION:", message.strip()]
    return run_claude("\n".join(parts), model, timeout=240)


class App:
    """The page's view of one vault."""

    def __init__(self, path):
        self.v = sv.Vault(path)
        self.notes = nt.Notes(self.v)

    def folder(self, slug):
        a = self.v.area(slug or "")
        return a.get("folder") if a else None

    def with_notes(self, qs):
        """Attach the note section that covers each question ("note"; the page shows it after grading)."""
        for q in qs:
            try:
                q["note"] = self.notes.note_for(q, self.folder(q.get("area")))
            except (OSError, ValueError):
                q["note"] = None
        return qs

    @property
    def vault(self):
        return self.v.path

    def need_area(self, slug):
        if not self.v.area(slug):
            raise ValueError(f"unknown area {slug!r}")

    def areas(self):
        out = []
        for a in self.v.areas():
            rows, _ = self.v.concepts(a["slug"])
            out.append({"slug": a["slug"], "title": a["title"], "excluded": bool(a.get("excluded")),
                        "count": len(self.v.bank(a["slug"]).get("questions", [])),
                        "unresolved": sum(r["status"] == "open" for r in rows)})
        return out

    def get_bank(self, slug):
        self.need_area(slug)
        return self.v.bank(slug)

    def sample_round(self, slugs, n, types):
        """Pick n bank questions; weight open concepts ×4 and prefer ones seen less often."""
        seen = {}
        for r in self.v.results():
            for a in r.get("answers", []):
                key = (a.get("area"), a.get("id"))
                seen[key] = seen.get(key, 0) + 1
        pool = []
        for slug in slugs:
            self.need_area(slug)
            rows, _ = self.v.concepts(slug)
            red = {r["name"].lower() for r in rows if r["status"] == "open"}
            for q in self.v.bank(slug).get("questions", []):
                if types and q.get("type") not in types:
                    continue
                w = 4.0 if (q.get("concept") or "").lower() in red else 1.0
                w /= 1 + seen.get((slug, q.get("id")), 0)
                pool.append((w, dict(q, area=slug)))
        picked = []
        while pool and len(picked) < n:
            r = random.uniform(0, sum(w for w, _ in pool))
            for i, (w, _) in enumerate(pool):
                r -= w
                if r <= 0:
                    picked.append(pool.pop(i)[1])
                    break
            else:
                picked.append(pool.pop()[1])
        for q in picked:  # shuffle options or statements, remap the answer and the explanation's (1)/(A) lines
            if not q.get("shuffle", True):
                continue
            kprim = q.get("type") == "kprim" and isinstance(q.get("answer"), list)
            if q.get("type") not in ("single", "multi") and not kprim:
                continue
            items = q["statements"] if kprim else q["options"]
            order = list(range(len(items)))
            random.shuffle(order)
            expl = reorder_explanation(q.get("explanation") or "", order, letters=not kprim)
            if expl is None:  # it refers to positions in a way we can't follow: keep the bank's order
                continue
            if q.get("explanation"):
                q["explanation"] = expl
            if kprim:
                q["statements"], q["answer"] = [items[i] for i in order], [q["answer"][i] for i in order]
            else:
                q["options"] = [items[i] for i in order]
                if isinstance(q.get("answer"), int):
                    q["answer"] = order.index(q["answer"])
                elif isinstance(q.get("answer"), list):
                    q["answer"] = sorted(order.index(a) for a in q["answer"])
        return {"id": datetime.now().strftime("bank-%Y%m%d-%H%M%S"), "source": "bank",
                "title": ", ".join(self.v.title(s) for s in slugs), "reveal": True,
                "questions": self.with_notes(picked)}

    def get_round(self, rid):
        if not sv.ID_RE.match(rid):
            raise ValueError("bad round id")
        data = sv.load_json(self.v.bank_dir / "rounds" / f"{rid}.json")
        if not isinstance(data, dict):
            return None
        data.setdefault("id", rid)
        data.setdefault("source", "claude")
        data.setdefault("reveal", False)
        for q in data.get("questions", []):
            ref = q.pop("bank_ref", None)
            if ref:
                bq = self.v.bank_question(ref.get("area", ""), ref.get("id", ""))
                if bq:
                    q.update(dict(bq, area=ref["area"]))
        self.with_notes(data.get("questions", []))
        return data

    def save_results(self, data):
        rid = data.get("round_id") or "unknown"
        if not sv.ID_RE.match(rid):
            raise ValueError("bad round id")
        data["submitted_at"] = datetime.now().isoformat(timespec="seconds")
        if data.get("source") == "bank":
            self.track(data)
        res = self.v.bank_dir / "results"
        sv.write_json(res / f"{rid}.json", data)
        sv.write_json(res / "latest.json", data)
        return str(res / f"{rid}.json")

    def track(self, data):
        """Bank rounds carry their answer key, so the server records the answers the page graded
        (single, multi, kprim, numeric).

        Each recorded answer gets "recorded": true. "tracked" is true only when nothing is left
        for Claude to grade (no answered open questions)."""
        graded, hits = [], []
        for a in data.get("answers", []):
            area, concept = a.get("area") or "", (a.get("concept") or "").strip()
            if a.get("type") == "open" or a.get("correct") is None or not concept or not self.v.area(area):
                continue
            q = self.v.bank_question(area, a.get("id")) or {}
            picked = (a.get("choice_text") or "").strip().replace("\n", " ⏎ ")
            graded.append({"area": area, "concept": concept, "correct": bool(a["correct"]),
                           "confusion": f"answered `{picked[:120]}` in a practice round." if picked
                           else "left it unanswered.",
                           "key_point": sv.plain(q.get("explanation"))
                           or f"see {a.get('id')} in question-bank/{area}.json"})
            hits.append(a)
        if graded:
            self.v.record(graded)
            for a in hits:
                a["recorded"] = True
        open_left = sum(1 for a in data.get("answers", [])
                        if a.get("type") == "open" and (a.get("text") or "").strip())
        data["tracked"] = open_left == 0
        data["tracked_count"] = len(graded)

    def grade_open(self, data):
        """Grade one open answer of a saved bank round, record it, and update the results file.

        data: {"round_id", "n", "mode": "self"|"claude", "correct": bool (self only)}"""
        rid = data.get("round_id") or ""
        if not sv.ID_RE.match(rid):
            raise ValueError("bad round id")
        res_dir = self.v.bank_dir / "results"
        res = sv.load_json(res_dir / f"{rid}.json")
        if not isinstance(res, dict):
            raise ValueError("this round wasn't saved; submit it first")
        a = next((x for x in res.get("answers", []) if x.get("n") == data.get("n") and x.get("type") == "open"), None)
        if a is None:
            raise ValueError("no open answer with that number")
        if a.get("recorded"):
            raise ValueError("already graded")
        area = a.get("area") or ""
        q = self.v.bank_question(area, a.get("id")) or {}
        if not q.get("model_answer"):
            raise ValueError("no model answer for this question; grade it in the chat with Claude")
        text = a.get("text") or ""
        mode = data.get("mode")
        if mode == "claude":
            note = None
            try:  # the note section that covers it, so details the short model answer leaves out can be checked
                ref = self.notes.note_for(q, self.folder(area))
                if ref and ref.get("path"):
                    note = self.notes.section_text(ref["path"], ref.get("anchor") or "", limit=5000)[1]
            except Exception:
                pass
            code = self.notes.definitions("\n".join(question_text(q)))
            verdict = ask_claude(q, text, self.v.manifest.get("subject", ""), self.v.lang, data.get("model"), note, code)
        elif mode == "self":
            verdict = {"correct": bool(data.get("correct")), "feedback": "", "confusion": "", "key_point": ""}
        else:
            raise ValueError("mode must be self or claude")
        concept = (a.get("concept") or "").strip()
        if concept and self.v.area(area):
            wrote = text.strip().replace("\n", " ")[:120]
            self.v.record([{
                "area": area, "concept": concept, "correct": verdict["correct"],
                "confusion": verdict.get("confusion") or (f"wrote `{wrote}` in a practice round." if wrote
                                                          else "left it unanswered."),
                "key_point": verdict.get("key_point") or sv.plain(q.get("explanation"))
                or sv.plain(q.get("model_answer")),
            }])
        a.update(correct=verdict["correct"], recorded=True, graded_by=mode)
        if verdict.get("feedback"):
            a["feedback"] = verdict["feedback"]
        res["tracked"] = not any(x.get("type") == "open" and (x.get("text") or "").strip() and not x.get("recorded")
                                 for x in res.get("answers", []))
        sv.write_json(res_dir / f"{rid}.json", res)
        latest = sv.load_json(res_dir / "latest.json")
        if isinstance(latest, dict) and latest.get("round_id") == rid:
            sv.write_json(res_dir / "latest.json", res)
        return {"correct": verdict["correct"], "feedback": verdict.get("feedback", ""), "tracked": res["tracked"],
                "recorded": bool(concept)}

    def ask(self, data):
        """Free question to Claude about a question of a round, or about a note.

        data: {"message", "history": [{"role": "user"|"claude", "text"}], "model",
               "question": {area, id, prompt, code, options, model_answer, explanation} (optional),
               "student": what they answered (optional), "note": {"path", "anchor"} (optional)}"""
        message = str(data.get("message") or "").strip()
        if not message:
            raise ValueError("write a question first")
        q = data.get("question") if isinstance(data.get("question"), dict) else None
        if q:  # the page's copy wins (its options may be shuffled); the bank fills in what is missing
            bq = self.v.bank_question(q.get("area") or "", q.get("id") or "") if q.get("id") else None
            keep = ("type", "prompt", "code", "options", "statements", "unit", "tolerance", "answer", "model_answer",
                    "explanation")
            given = {k: q[k] for k in keep if q.get(k) not in (None, "", [])}
            if bq and "options" not in given and "prompt" not in given:
                given = dict(bq)
            elif bq:
                for k in ("model_answer", "explanation"):
                    if bq.get(k):
                        given.setdefault(k, bq[k])
            q = given
        note = None
        ref = data.get("note") if isinstance(data.get("note"), dict) else None
        if ref and ref.get("path"):
            note = self.notes.section_text(ref["path"], ref.get("anchor") or "")
        history = [h for h in (data.get("history") or []) if isinstance(h, dict)]
        student = str(data.get("student") or "")[:4000] or None
        code = self.notes.definitions("\n".join(question_text(q)) if q else message)
        answer = ask_tutor(self.v.manifest.get("subject", ""), self.v.lang, message[:4000], history, q, student,
                           note, data.get("model"), code)
        return {"answer": answer, "model": pick_model(data.get("model"))}

    def progress(self):
        st = self.v.stats()
        areas, open_concepts = [], []
        for a in st["areas"]:
            row = {k: a[k] for k in ("slug", "title", "excluded", "attempts", "correct", "rate", "level", "concepts")}
            row["open"] = len(a["open"])
            row["bank"] = len(self.v.bank(a["slug"]).get("questions", []))
            areas.append(row)
            open_concepts += [dict(r, area=a["slug"], area_title=a["title"]) for r in a["open"]]
        activity = {}
        for r in self.v.results():
            day = (r.get("submitted_at") or "")[:10]
            if day:
                activity[day] = activity.get(day, 0) + sum(1 for a in r.get("answers", []) if answered(a))
        return {"areas": areas, "open": open_concepts, "activity": activity,
                "total": {"attempts": st["total"], "correct": st["correct"], "rate": st["rate"], "level": st["level"]}}

    def get_tasks(self):
        data = sv.load_json(self.vault / "tasks.json", {"tasks": []})
        return data if isinstance(data, dict) else {"tasks": []}

    def put_tasks(self, data):
        tasks = data.get("tasks")
        if not isinstance(tasks, list):
            raise ValueError("tasks must be a list")
        clean = []
        for t in tasks[:200]:
            text = str(t.get("text", "")).strip()[:160]
            if text:
                clean.append({"id": str(t.get("id") or "")[:40] or f"t{len(clean)}", "text": text,
                              "done": bool(t.get("done"))})
        sv.write_json(self.vault / "tasks.json", {"tasks": clean})


def make_handler(vaults):
    def pick(q):
        vid = q.get("vault", [""])[0]
        if vid in vaults:
            return vaults[vid]
        if not vid and len(vaults) == 1:
            return next(iter(vaults.values()))
        raise ValueError(f"unknown vault {vid!r}; GET /api/vaults")

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            sys.stderr.write("[study] " + fmt % args + "\n")

        def send(self, code, body, ctype="application/json", cache=False):
            if not isinstance(body, (bytes, str)):
                body = json.dumps(body, ensure_ascii=False)
            if isinstance(body, str):
                body = body.encode("utf-8")
            self.send_response(code)
            binary = ctype.startswith(("font/", "image/"))
            self.send_header("Content-Type", ctype + ("" if binary else "; charset=utf-8"))
            self.send_header("Cache-Control", "max-age=86400" if cache else "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def body(self):
            try:
                n = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                n = -1
            if not 0 <= n <= MAX_BODY:
                raise ValueError(f"request body must be 0-{MAX_BODY // 1_000_000} MB")
            try:
                data = json.loads(self.rfile.read(n) or b"{}")
            except (UnicodeDecodeError, json.JSONDecodeError):
                raise ValueError("request body isn't JSON")
            if not isinstance(data, dict):
                raise ValueError("request body must be a JSON object")
            return data

        def refused(self, method):
            """Why this request may not come from another website, or None if it may be served.

            The server listens on 127.0.0.1 only, but any page in the browser can still send it requests.
            A Host other than our own address means DNS rebinding (a page that can read our answers);
            writes must come from the study page itself: JSON (needs a CORS preflight, which we refuse)
            and, when the browser names it, our own Origin."""
            port = self.server.server_address[1]
            ours = {f"127.0.0.1:{port}", f"localhost:{port}"}
            if (self.headers.get("Host") or "").lower() not in ours:
                return "unknown Host; open the page at http://127.0.0.1:%d/" % port
            if method in ("POST", "PUT"):
                ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
                if ctype != "application/json":
                    return "Content-Type must be application/json"
                origin = self.headers.get("Origin")
                if origin is not None and origin.lower() not in {"http://" + h for h in ours}:
                    return "requests from other websites are refused"
            return None

        def handle_any(self, method):
            why = self.refused(method)
            if why:
                return self.send(403, {"error": why})
            url = urlparse(self.path)
            q = parse_qs(url.query)
            p = url.path
            try:
                if method == "GET" and p in ("/", "/index.html"):
                    return self.send(200, index_html(), "text/html")
                if method == "GET" and p.startswith("/fonts/"):
                    name = p.rsplit("/", 1)[-1]
                    if name in FONT_NAMES:
                        return self.send(200, (HERE / "fonts" / name).read_bytes(), "font/woff2", cache=True)
                    return self.send(404, {"error": "not found"})
                if method == "GET" and p.startswith("/icons/"):
                    name = p.rsplit("/", 1)[-1]
                    if name in ICON_NAMES:
                        return self.send(200, (HERE / "icons" / name).read_bytes(), "image/png", cache=True)
                    return self.send(404, {"error": "not found"})
                if method == "GET" and p in APP_FILES:
                    name, ctype = APP_FILES[p]
                    return self.send(200, (HERE / name).read_bytes(), ctype)
                if method == "GET" and p == "/api/vaults":
                    return self.send(200, [{"id": k, "path": str(a.vault), "subject": a.v.manifest.get("subject"), "language": a.v.lang,
                                            "claude_check": bool(CLAUDE), "models": list(MODELS),
                                            "default_model": pick_model(CLAUDE_MODEL)} for k, a in vaults.items()])
                if p == "/api/update":
                    if method == "GET":
                        return self.send(200, up.status(force="check" in q))
                    if method == "POST":
                        res = up.apply()
                        self.send(200, res)
                        return up.restart_later(self.server)
                if method == "POST" and p == "/api/restart":  # launch.py --restart, after editing the code
                    self.send(200, {"ok": True})
                    return up.restart_later(self.server)
                if p == "/api/prefs":
                    if method == "GET":
                        return self.send(200, read_prefs())
                    if method == "PUT":
                        return self.send(200, write_prefs(self.body()))
                app = pick(q) if p.startswith("/api/") else None
                if method == "GET" and p == "/api/areas":
                    return self.send(200, app.areas())
                if method == "GET" and p == "/api/notes":
                    return self.send(200, app.notes.tree())
                if method == "GET" and p == "/api/asset":
                    f = app.notes.asset(q.get("path", [""])[0])
                    return self.send(200, f.read_bytes(), nt.IMAGE_TYPES[f.suffix.lower()], cache=True)
                if method == "GET" and p == "/api/note":
                    return self.send(200, app.notes.read(q.get("path", [""])[0]))
                if method == "POST" and p == "/api/note-ref":
                    d = self.body()
                    qd = d.get("question") if isinstance(d.get("question"), dict) else {}
                    return self.send(200, {"note": app.notes.note_for(qd, app.folder(d.get("area")))})
                if method == "POST" and p == "/api/ask":
                    return self.send(200, app.ask(self.body()))
                if method == "GET" and p == "/api/progress":
                    return self.send(200, app.progress())
                if p == "/api/tasks":
                    if method == "GET":
                        return self.send(200, app.get_tasks())
                    if method == "PUT":
                        app.put_tasks(self.body())
                        return self.send(200, {"ok": True})
                if p.startswith("/api/bank/"):
                    slug = p.rsplit("/", 1)[-1]
                    if method == "GET":
                        return self.send(200, app.get_bank(slug))
                    if method == "PUT":
                        app.v.put_bank(slug, self.body())
                        return self.send(200, {"ok": True})
                if method == "GET" and p == "/api/round":
                    if "id" in q:
                        r = app.get_round(q["id"][0])
                        return self.send(200, r) if r else self.send(404, {"error": "no such round"})
                    slugs = [s for s in ",".join(q.get("area", [])).split(",") if s]
                    if not slugs:
                        slugs = [a["slug"] for a in app.areas() if a["count"] and not a["excluded"]]
                    types = set(q["types"][0].split(",")) if "types" in q else None
                    n = max(1, min(20, int(q.get("n", ["4"])[0])))
                    return self.send(200, app.sample_round(slugs, n, types))
                if method == "POST" and p == "/api/results":
                    data = self.body()
                    path = app.save_results(data)
                    return self.send(200, {"ok": True, "path": path, "tracked": data.get("tracked", False),
                                           "tracked_count": data.get("tracked_count", 0)})
                if method == "POST" and p == "/api/grade-open":
                    return self.send(200, app.grade_open(self.body()))
                return self.send(404, {"error": "not found"})
            except ValueError as e:
                return self.send(400, {"error": str(e)})
            except Exception as e:  # malformed input that slipped past the checks: answer instead of dropping the connection
                self.log_message("error on %s %s: %r", method, self.path, e)
                return self.send(500, {"error": "the server couldn't handle that request"})

        def do_GET(self):
            self.handle_any("GET")

        def do_PUT(self):
            self.handle_any("PUT")

        def do_POST(self):
            self.handle_any("POST")

    return Handler


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".", help="folder to search for StudyVaults (default: current folder)")
    ap.add_argument("--vault", action="append", help="specific StudyVault folder (repeatable)")
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()
    root = Path(args.root).expanduser().resolve()
    paths = [sv.resolve_vault(v) for v in args.vault] if args.vault else sv.find_vaults(root)
    vaults = {}
    for v in paths:
        if not v.is_dir():
            sys.exit(f"not a directory: {v}")
        try:
            vid = str(v.parent.relative_to(root))
        except ValueError:
            vid = v.parent.name
        if vid in ("", "."):
            vid = v.parent.name
        vaults[vid] = App(v)
    if not vaults:
        sys.exit(f"no StudyVault folders under {root}")
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(vaults))
    print(f"[study] http://127.0.0.1:{args.port}/  vaults: {', '.join(vaults)}", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
