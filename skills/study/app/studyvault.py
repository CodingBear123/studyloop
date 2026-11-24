#!/usr/bin/env python3
"""StudyVault data layer for claude-study-tool.

Every read and write of tracking data goes through this file, so the vault
stays consistent whether Claude, the browser app or you change it.
Standard library only.

    studyvault.py status   VAULT                 summary JSON (areas, rates, open concepts)
    studyvault.py check    VAULT                 validate everything; exit 1 on errors
    studyvault.py recompute VAULT                rebuild Learning Dashboard.md
    studyvault.py record   VAULT FILE|-          apply graded answers (JSON), then recompute
    studyvault.py validate-round VAULT [FILE]    check a round before the user opens it
    studyvault.py init     VAULT --subject S --area "01-Folder=Title" [...]
    studyvault.py migrate  VAULT [--write]       infer studyvault.json for an older vault
    studyvault.py find     ROOT                  list StudyVault folders under ROOT

VAULT may be the StudyVault folder or the folder that contains it.
The data format is described in ../references/studyvault-spec.md.
"""
import argparse
import json
import re
import sys
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path

VERSION = 1
MANIFEST = "studyvault.json"
DASHBOARD = "Learning Dashboard.md"
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")
FOLDER_RE = re.compile(r"^(\d{2})[- ](.+)$")
ROW_RE = re.compile(r"^\| (.+?) \| (\d+) \| (\d+) \| (\d{4}-\d{2}-\d{2}|-) \| (🔴|🟢|⚪) \|\s*$", re.M)
SEP_RE = re.compile(r"^\|[-:| ]+\|\s*$")
NOTE_RE = re.compile(r"^\*\*(.+?)\*\*\s*\n((?:- .*\n?)+)", re.M)
WIKI_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")
PRACTICE_GLOBS = ("*Practice*", "*practice*", "*Praxis*", "*bung*", "*Kprim*")
TYPES = ("single", "open")

# Structure words per vault language ("language" in studyvault.json). Parsing accepts all of them.
LABELS = {
    "en": {"tracker": "Concept Tracker", "head": ("Concept", "Attempts", "Correct", "Last Tested", "Status"),
           "notes": "### Error Notes", "confusion": "Confusion", "key": "Key point",
           "placeholder": "(added as concepts are missed)",
           "dash_intro": "concept tracking, built from `concepts/*.md` by claude-study-tool. "
                         "Don't edit the numbers here: run `studyvault.py recompute`.",
           "by_area": "Proficiency by Area", "cols": ("Area", "Correct", "Wrong", "Rate", "Level", "Details"),
           "excluded": "not on the exam", "stats": "Stats",
           "stat_names": ("Total Questions", "Cumulative Rate", "Unresolved Concepts", "Resolved Concepts",
                          "Weakest Area", "Strongest Area"),
           "levels": ("Weak", "Fair", "Good", "Mastered", "Unmeasured")},
    "de": {"tracker": "Konzept-Tracker", "head": ("Konzept", "Versuche", "Richtig", "Zuletzt getestet", "Status"),
           "notes": "### Fehlernotizen", "confusion": "Verwechslung", "key": "Kernpunkt",
           "placeholder": "(wird bei Fehlern ergänzt)",
           "dash_intro": "Konzept-Tracking, erzeugt aus `concepts/*.md` von claude-study-tool. "
                         "Zahlen nicht von Hand ändern: `studyvault.py recompute` ausführen.",
           "by_area": "Stand pro Bereich", "cols": ("Bereich", "Richtig", "Falsch", "Quote", "Stufe", "Details"),
           "excluded": "nicht prüfungsrelevant", "stats": "Statistik",
           "stat_names": ("Fragen total", "Kumulierte Quote", "Offene Konzepte", "Gelöste Konzepte",
                          "Schwächster Bereich", "Stärkster Bereich"),
           "levels": ("Schwach", "Mittel", "Gut", "Sicher", "Ungemessen")},
}
NOTES_HEADS = tuple(L["notes"] for L in LABELS.values())
PLACEHOLDERS = tuple(L["placeholder"] for L in LABELS.values())


def labels(lang):
    return LABELS.get((lang or "en")[:2], LABELS["en"])


def table_head(L):
    cells = L["head"]
    return "| " + " | ".join(cells) + " |\n|" + "|".join("-" * (len(c) + 2) for c in cells) + "|"


# kept for callers that use the English defaults
TABLE_HEAD = table_head(LABELS["en"])
NOTES_HEAD = LABELS["en"]["notes"]
PLACEHOLDER = LABELS["en"]["placeholder"]


# ---------- small helpers ----------

def load_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def write_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def slugify(text):
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s or "area"


def badge(rate, lang="en"):
    w = labels(lang)["levels"]
    if rate is None:
        return f"⬜ {w[4]}"
    return f"🟥 {w[0]}" if rate < 40 else f"🟨 {w[1]}" if rate < 70 else f"🟩 {w[2]}" if rate < 90 else f"🟦 {w[3]}"


def pct(rate):
    return f"{rate}%" if rate is not None else "-"


def clean_cell(text):
    """Concept names live in a markdown table row: no pipes (∣ looks the same), no newlines."""
    return re.sub(r"\s+", " ", str(text).replace("|", "∣")).strip()


def plain(md_text, limit=300):
    """One-line version of an explanation, for an error note."""
    s = re.sub(r"```\w*\n?", "", md_text or "").replace("\n", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s if len(s) <= limit else s[:limit - 1].rstrip() + "…"


def area_key(name):
    """Slug for an area named by a folder or an old tracker file: '01-Computer-Networks' -> 'computer-networks'."""
    m = FOLDER_RE.match(name)
    return slugify(m[2] if m else name)


def has_practice(folder):
    return any(p for g in PRACTICE_GLOBS for p in Path(folder).glob(g + ".md"))


def resolve_vault(path):
    v = Path(path).expanduser().resolve()
    if v.name != "StudyVault" and (v / "StudyVault").is_dir():
        v = v / "StudyVault"
    return v


def find_vaults(root):
    root = Path(root).expanduser().resolve()
    if root.name == "StudyVault" and root.is_dir():
        return [root]
    skip = {"node_modules", ".git", ".obsidian", ".trash"}
    out = []
    for p in sorted(root.rglob("StudyVault")):
        rel = p.relative_to(root).parts
        if p.is_dir() and not any(part.startswith(".") or part in skip for part in rel):
            out.append(p)
    return out


# ---------- questions and rounds ----------

def validate_question(q, where="", need_answer=False):
    errs = []
    qid = q.get("id") or where or "?"
    if q.get("type") not in TYPES:
        errs.append(f"{qid}: type must be 'single' or 'open'")
    if not q.get("prompt") and not q.get("code"):
        errs.append(f"{qid}: needs a prompt or code")
    if q.get("type") == "single":
        opts = q.get("options")
        if not isinstance(opts, list) or not 2 <= len(opts) <= 8 or not all(isinstance(o, str) for o in opts):
            errs.append(f"{qid}: single needs 2-8 string options")
            opts = []
        ans = q.get("answer")
        if ans is None and need_answer:
            errs.append(f"{qid}: bank questions need an answer index")
        if ans is not None and (not isinstance(ans, int) or isinstance(ans, bool) or not 0 <= ans < len(opts)):
            errs.append(f"{qid}: answer must be an index into options")
        if len(set(opts)) != len(opts):
            errs.append(f"{qid}: duplicate options")
    if q.get("difficulty") not in (None, "easy", "medium", "hard"):
        errs.append(f"{qid}: difficulty must be easy, medium or hard")
    return errs


# ---------- concept files ----------

def split_notes(text):
    """(table part, notes heading or None, notes part)."""
    for h in NOTES_HEADS:
        if h in text:
            a, b = text.split(h, 1)
            return a, h, b
    return text, None, ""


def parse_concepts_text(text):
    table, _, notes_part = split_notes(text)
    rows = [{"name": m[1].strip(), "attempts": int(m[2]), "correct": int(m[3]), "last": m[4], "status": m[5]}
            for m in ROW_RE.finditer(table)]
    notes = {m[1].strip().lower(): m[2].strip() for m in NOTE_RE.finditer(notes_part)}
    return rows, notes


def parse_concepts(path):
    path = Path(path)
    if not path.exists():
        return [], {}
    return parse_concepts_text(path.read_text(encoding="utf-8"))


def concept_template(title, lang="en"):
    L = labels(lang)
    return f"# {title} — {L['tracker']}\n\n{table_head(L)}\n\n{L['notes']}\n\n{L['placeholder']}\n"


def render_note(concept, confusion, key_point, lang="en"):
    L = labels(lang)
    return f"**{concept}**\n- {L['confusion']}: {plain(confusion, 600)}\n- {L['key']}: {plain(key_point, 600)}"


def apply_answer(text, concept, correct, confusion, key_point, today, lang="en"):
    """Return the concept-file text with one graded answer applied."""
    L = labels(lang)
    status = "🟢" if correct else "🔴"
    table, _, _ = split_notes(text)
    hit = next((m for m in ROW_RE.finditer(table) if m[1].strip().lower() == concept.lower()), None)
    if hit:
        concept = hit[1].strip()  # keep the existing spelling
        row = f"| {concept} | {int(hit[2]) + 1} | {int(hit[3]) + int(correct)} | {today} | {status} |"
        text = text[:hit.start()] + row + text[hit.end():]
    else:
        row = f"| {concept} | 1 | {int(correct)} | {today} | {status} |"
        lines = text.split("\n")
        n_table = table.count("\n")
        idx = max((i for i, l in enumerate(lines[:n_table + 1]) if l.startswith("|")), default=None)
        if idx is None:
            lines[1:1] = [""] + table_head(L).split("\n") + [row]
        else:
            lines.insert(idx + 1, row)
        text = "\n".join(lines)
    if not correct:
        _, notes = parse_concepts_text(text)
        note = render_note(concept, confusion, key_point, lang)
        if concept.lower() in notes:  # wrong again: the newest note replaces the old one
            text = re.sub(r"^\*\*" + re.escape(concept) + r"\*\*\s*\n(?:- .*\n?)+", lambda _: note + "\n", text,
                          count=1, flags=re.M | re.I)
        else:
            if split_notes(text)[1] is None:
                text = text.rstrip("\n") + f"\n\n{L['notes']}\n"
            for ph in PLACEHOLDERS:
                text = text.replace(ph + "\n", "").replace(ph, "")
            text = text.rstrip("\n") + "\n\n" + note + "\n"
    return text if text.endswith("\n") else text + "\n"


def lenient_rows(table):
    """Rows from an older tracker: any header language, pipes inside names, '—' dates, ⚪ untested."""
    rows = []
    lines = table.splitlines()
    for i, line in enumerate(lines):
        if not line.startswith("|") or SEP_RE.match(line):
            continue
        if i + 1 < len(lines) and SEP_RE.match(lines[i + 1]):
            continue  # header row
        cells = [c.strip() for c in line.replace("\\|", "∣").strip().strip("|").split("|")]
        if len(cells) < 5:
            raise ValueError(f"can't read row: {line[:80]}")
        name, att, cor, last, status = "∣".join(cells[:-4]), *cells[-4:]
        if not (att.isdigit() and cor.isdigit()):
            raise ValueError(f"can't read row: {line[:80]}")
        last = last if re.match(r"^\d{4}-\d{2}-\d{2}$", last) else "-"
        status = status if status in ("🔴", "🟢", "⚪") else ("⚪" if int(att) == 0 else "🔴")
        rows.append({"name": clean_cell(name), "attempts": int(att), "correct": int(cor), "last": last,
                     "status": status})
    return rows


def normalize_tracker(text, title, lang="en"):
    """Rewrite an older tracker in the canonical format. Returns (text, notes added for 🔴 rows)."""
    L = labels(lang)
    table, _, notes_part = split_notes(text)
    rows = lenient_rows(table)
    pre = []
    for line in table.splitlines():
        if line.startswith("|"):
            break
        if not line.startswith("# "):
            pre.append(line)
    preamble = "\n".join(pre).strip("\n")
    notes_part = re.sub(r"^\*\*(.+?)\*\*[ \t]*$", lambda m: f"**{clean_cell(m[1])}**", notes_part, flags=re.M)
    notes_part = notes_part.strip("\n")
    for ph in PLACEHOLDERS + ("*(none yet — populated after first assessment)*",):
        notes_part = notes_part.replace(ph, "").strip("\n")
    notes = {m[1].strip().lower() for m in NOTE_RE.finditer(notes_part + "\n")}
    # older trackers sometimes titled a note with shorter wording than its row: pair them by similarity
    orphans = [n for n in notes if n not in {r["name"].lower() for r in rows}]
    renamed = {}
    for r in rows:
        if r["name"].lower() in notes or not orphans:
            continue
        score, best = max((SequenceMatcher(None, r["name"].lower(), o).ratio(), o) for o in orphans)
        if score >= 0.55:
            orphans.remove(best)
            notes.discard(best)
            notes.add(r["name"].lower())
            renamed[best] = r["name"]
    for old, new in renamed.items():
        notes_part = re.sub(r"^\*\*" + re.escape(old) + r"\*\*[ \t]*$", lambda _: f"**{new}**", notes_part,
                            count=1, flags=re.M | re.I)
    added = []
    for r in rows:
        if r["status"] == "🔴" and r["name"].lower() not in notes:
            missing = {"en": ("not recorded (tracker migrated from an older format)", "reread the area notes"),
                       "de": ("nicht erfasst (Tracker aus älterem Format übernommen)",
                              "Bereichsnotizen nochmals lesen")}[lang if lang in ("en", "de") else "en"]
            notes_part += ("\n\n" if notes_part else "") + render_note(r["name"], *missing, lang=lang)
            added.append(r["name"])
    body = "\n".join(f"| {r['name']} | {r['attempts']} | {r['correct']} | {r['last']} | {r['status']} |"
                     for r in rows)
    out = f"# {title} — {L['tracker']}\n\n" + (preamble + "\n\n" if preamble else "")
    out += f"{table_head(L)}\n" + (body + "\n" if body else "")
    out += f"\n{L['notes']}\n\n" + (notes_part.strip("\n") if notes_part.strip() else L["placeholder"]) + "\n"
    return out, added, renamed


# ---------- the vault ----------

class Vault:
    def __init__(self, path):
        self.path = resolve_vault(path)
        self.bank_dir = self.path / "question-bank"
        self.concepts_dir = self.path / "concepts"
        self.dashboard = self.path / DASHBOARD
        self.manifest_path = self.path / MANIFEST
        self._manifest = None

    # ----- manifest -----

    @property
    def manifest(self):
        if self._manifest is None:
            data = load_json(self.manifest_path)
            self._manifest = data if isinstance(data, dict) else self.infer_manifest()
        return self._manifest

    def has_manifest(self):
        return self.manifest_path.exists()

    def reload(self):
        self._manifest = None

    def areas(self):
        return [a for a in self.manifest.get("areas", []) if isinstance(a, dict) and a.get("slug")]

    def area(self, slug):
        return next((a for a in self.areas() if a["slug"] == slug), None)

    def title(self, slug):
        a = self.area(slug)
        return a.get("title", slug) if a else slug

    @property
    def lang(self):
        return (self.manifest.get("language") or "en")[:2]

    def old_dashboards(self):
        """Dashboards an older vault may have, other than the generated one."""
        out = [self.path / "Lern-Dashboard.md"] + sorted(self.path.glob(f"*/{DASHBOARD}"))
        return [p for p in out if p.is_file()]

    def infer_manifest(self):
        """Build a manifest from an older /tutor-style vault (folders, trackers, old dashboard)."""
        titles = {}
        dash_re = re.compile(r"^\| (?!\*\*)(.+?) \|.*\[\[(?:concepts/)?([^\]|#]+)(?:\|[^\]]*)?\]\] \|\s*$", re.M)
        for d in [self.dashboard] + self.old_dashboards():
            if d.exists():
                for m in dash_re.finditer(d.read_text(encoding="utf-8")):
                    title = re.sub(r"^\d{2}\s*[—–-]?\s*", "", m[1].strip())
                    titles.setdefault(area_key(m[2]), title)
        tracked = set(titles)
        lang = "en"
        if self.concepts_dir.is_dir():
            for p in self.concepts_dir.glob("*.md"):
                tracked.add(area_key(p.stem))
                head = p.read_text(encoding="utf-8")
                if "| Konzept |" in head or "### Fehlernotizen" in head:
                    lang = "de"
        if self.bank_dir.is_dir():
            tracked |= {area_key(p.stem) for p in self.bank_dir.glob("*.json")}
        areas, extra, used = [], [], set()
        dirs = sorted(p for p in self.path.iterdir() if p.is_dir()) if self.path.is_dir() else []
        for d in dirs:
            m = FOLDER_RE.match(d.name)
            if not m:
                continue
            slug = slugify(m[2])
            if slug in tracked or (slug != "dashboard" and has_practice(d)):
                areas.append({"slug": slug, "title": titles.get(slug) or m[2].replace("-", " "), "folder": d.name})
                used.add(slug)
            else:
                extra.append(d.name)
        for slug in sorted(tracked - used):
            areas.append({"slug": slug, "title": titles.get(slug) or slug.replace("-", " ").capitalize(),
                          "folder": None})
        return {"version": VERSION, "subject": self.path.parent.name, "language": lang, "scope": "",
                "areas": areas, "extra_folders": extra}

    def write_manifest(self, data):
        write_json(self.manifest_path, data)
        self.reload()

    # ----- concept trackers -----

    def concept_path(self, slug):
        return self.concepts_dir / f"{slug}.md"

    def concepts(self, slug):
        return parse_concepts(self.concept_path(slug))

    def ensure_area_files(self):
        """Create missing concept trackers and empty bank files for every manifest area."""
        made = []
        for a in self.areas():
            cp = self.concept_path(a["slug"])
            if not cp.exists():
                write_text(cp, concept_template(a["title"], self.lang))
                made.append(str(cp.relative_to(self.path)))
            bp = self.bank_dir / f"{a['slug']}.json"
            if not bp.exists():
                write_json(bp, {"area": a["slug"], "title": a["title"], "questions": []})
                made.append(str(bp.relative_to(self.path)))
        for sub in ("rounds", "results"):
            (self.bank_dir / sub).mkdir(parents=True, exist_ok=True)
        return made

    def record(self, answers, round_id=None, today=None):
        """Apply graded answers [{area, concept, correct, confusion?, key_point?}] and recompute."""
        today = today or date.today().isoformat()
        errs = []
        for i, a in enumerate(answers, 1):
            if not self.area(a.get("area") or ""):
                errs.append(f"answer {i}: unknown area {a.get('area')!r}")
            if not clean_cell(a.get("concept") or ""):
                errs.append(f"answer {i}: concept missing")
            if not isinstance(a.get("correct"), bool):
                errs.append(f"answer {i}: correct must be true or false")
            elif not a["correct"] and not (a.get("confusion") and a.get("key_point")):
                errs.append(f"answer {i}: a wrong answer needs confusion and key_point")
        if errs:
            raise ValueError("; ".join(errs))
        texts = {}
        for a in answers:
            slug = a["area"]
            if slug not in texts:
                p = self.concept_path(slug)
                texts[slug] = (p.read_text(encoding="utf-8") if p.exists()
                               else concept_template(self.title(slug), self.lang))
            texts[slug] = apply_answer(texts[slug], clean_cell(a["concept"]), a["correct"],
                                       a.get("confusion", ""), a.get("key_point", ""), today, self.lang)
        for slug, text in texts.items():
            write_text(self.concept_path(slug), text)
        if round_id:
            self.mark_tracked(round_id, len(answers))
        return self.recompute()

    def mark_tracked(self, round_id, n):
        res = self.bank_dir / "results"
        for p in (res / f"{round_id}.json", res / "latest.json"):
            data = load_json(p)
            if isinstance(data, dict) and data.get("round_id") == round_id:
                data["tracked"] = True
                data["tracked_count"] = data.get("tracked_count", 0) + n
                write_json(p, data)

    # ----- dashboard -----

    def stats(self):
        lang = self.lang
        excluded = {a["slug"] for a in self.areas() if a.get("excluded")}
        areas, T, C, unres, res, untested, rates = [], 0, 0, 0, 0, 0, {}
        for a in self.areas():
            rows, notes = self.concepts(a["slug"])
            att = sum(r["attempts"] for r in rows)
            cor = sum(r["correct"] for r in rows)
            rate = int(100 * cor / att + 0.5) if att else None
            if rate is not None and a["slug"] not in excluded:
                rates[a["title"]] = rate
            T, C = T + att, C + cor
            unres += sum(r["status"] == "🔴" for r in rows)
            res += sum(r["status"] == "🟢" for r in rows)
            untested += sum(r["status"] == "⚪" for r in rows)
            areas.append({"slug": a["slug"], "title": a["title"], "excluded": bool(a.get("excluded")),
                          "attempts": att, "correct": cor, "rate": rate, "level": badge(rate, lang),
                          "concepts": len(rows), "untested": [r["name"] for r in rows if r["status"] == "⚪"],
                          "open": [dict(r, note=notes.get(r["name"].lower(), ""))
                                   for r in rows if r["status"] == "🔴"]})
        tr = int(100 * C / T + 0.5) if T else None
        # min/max keep the first of equal rates, in manifest order
        weak = min(rates, key=rates.get) if rates else "-"
        strong = max(rates, key=rates.get) if rates else "-"
        return {"areas": areas, "total": T, "correct": C, "rate": tr, "level": badge(tr, lang),
                "unresolved": unres, "resolved": res, "untested": untested, "weakest": weak, "strongest": strong}

    def render_dashboard(self, st=None):
        st = st or self.stats()
        L = labels(self.lang)
        subject = self.manifest.get("subject") or ""
        intro = f"{subject}: {L['dash_intro']}" if subject else L["dash_intro"][0].upper() + L["dash_intro"][1:]
        cols = L["cols"]
        lv = L["levels"]
        legend = (f"> 🟥 {lv[0]} (0-39%) · 🟨 {lv[1]} (40-69%) · 🟩 {lv[2]} (70-89%) · "
                  f"🟦 {lv[3]} (90-100%) · ⬜ {lv[4]}")
        lines = ["# Learning Dashboard", "", f"> {intro}", "", "---", "", f"## {L['by_area']}", "",
                 "| " + " | ".join(cols) + " |", "|" + "|".join("-" * (len(c) + 2) for c in cols) + "|"]
        for a in st["areas"]:
            name = a["title"] + (f" ({L['excluded']})" if a["excluded"] else "")
            lines.append(f"| {name} | {a['correct']} | {a['attempts'] - a['correct']} | {pct(a['rate'])} | "
                         f"{a['level']} | [[concepts/{a['slug']}]] |")
        n = L["stat_names"]
        lines += [f"| **Total** | **{st['correct']}** | **{st['total'] - st['correct']}** | **{pct(st['rate'])}** | "
                  f"{st['level']} | |", "", legend, "", "---", "", f"## {L['stats']}", "",
                  f"- **{n[0]}**: {st['total']}",
                  f"- **{n[1]}**: {pct(st['rate'])}",
                  f"- **{n[2]}**: {st['unresolved']}",
                  f"- **{n[3]}**: {st['resolved']}",
                  f"- **{n[4]}**: {st['weakest']}",
                  f"- **{n[5]}**: {st['strongest']}", ""]
        return "\n".join(lines)

    def recompute(self):
        st = self.stats()
        write_text(self.dashboard, self.render_dashboard(st))
        return {k: st[k] for k in ("total", "correct", "rate", "unresolved", "resolved", "untested",
                                   "weakest", "strongest")}

    # ----- bank, rounds, results -----

    def bank(self, slug):
        data = load_json(self.bank_dir / f"{slug}.json")
        if not isinstance(data, dict):
            data = {"area": slug, "title": self.title(slug), "questions": []}
        return data

    def put_bank(self, slug, data):
        if not self.area(slug):
            raise ValueError(f"unknown area {slug!r}; add it to {MANIFEST} first")
        qs = data.get("questions")
        if not isinstance(qs, list):
            raise ValueError("questions must be a list")
        errs = []
        for i, q in enumerate(qs, 1):
            if not isinstance(q.get("id"), str) or not ID_RE.match(q["id"]):
                errs.append(f"question {i}: id must be letters, digits, - or _")
            errs += validate_question(q, f"question {i}", need_answer=True)
        ids = [q.get("id") for q in qs]
        if len(ids) != len(set(ids)):
            errs.append("duplicate question ids")
        if errs:
            raise ValueError("; ".join(errs))
        write_json(self.bank_dir / f"{slug}.json", {"area": slug, "title": self.title(slug), "questions": qs})

    def bank_question(self, slug, qid):
        return next((q for q in self.bank(slug).get("questions", []) if q.get("id") == qid), None)

    def validate_round(self, data):
        errs = []
        if not isinstance(data, dict):
            return ["round must be a JSON object"]
        if not ID_RE.match(str(data.get("id", ""))):
            errs.append("round id must be letters, digits, - or _")
        qs = data.get("questions")
        if not isinstance(qs, list) or not qs:
            return errs + ["round needs a non-empty questions list"]
        for i, q in enumerate(qs, 1):
            where = f"Q{i}"
            if "bank_ref" in q:
                ref = q["bank_ref"] or {}
                if not self.bank_question(ref.get("area", ""), ref.get("id", "")):
                    errs.append(f"{where}: bank_ref {ref} not found")
                continue
            if not self.area(q.get("area") or ""):
                errs.append(f"{where}: area {q.get('area')!r} is not in {MANIFEST}")
            if not clean_cell(q.get("concept") or ""):
                errs.append(f"{where}: concept missing (needed to record the answer)")
            if "answer" in q and data.get("source", "claude") == "claude":
                errs.append(f"{where}: remove 'answer' from Claude-written questions (the page would leak it)")
            errs += validate_question(q, where)
        return errs

    def results(self):
        res = self.bank_dir / "results"
        out = []
        for p in sorted(res.glob("*.json")) if res.is_dir() else []:
            if p.name == "latest.json":
                continue
            data = load_json(p)
            if isinstance(data, dict):
                out.append(data)
        return out

    # ----- summary for Claude -----

    def status(self):
        st = self.stats()
        banks = {a["slug"]: len(self.bank(a["slug"]).get("questions", [])) for a in self.areas()}
        for a in st["areas"]:
            a["bank"] = banks[a["slug"]]
        untracked = [r.get("round_id") for r in self.results() if not r.get("tracked")]
        latest = load_json(self.bank_dir / "results" / "latest.json")
        m = self.manifest
        return {"vault": str(self.path), "subject": m.get("subject"), "language": m.get("language"),
                "exam": m.get("exam"), "scope": m.get("scope"), "manifest": self.has_manifest(), **st,
                "untracked_results": untracked,
                "latest_result": {k: latest.get(k) for k in ("round_id", "source", "submitted_at", "tracked")}
                if isinstance(latest, dict) else None}

    # ----- consistency check -----

    def check(self):
        E, W = [], []
        if not self.path.is_dir():
            return [f"no vault at {self.path}"], []
        if not self.has_manifest():
            E.append(f"{MANIFEST} missing: run `studyvault.py migrate VAULT --write` (or init)")
        m = self.manifest
        if m.get("version") != VERSION:
            E.append(f"{MANIFEST}: version must be {VERSION}")
        if not m.get("subject"):
            W.append(f"{MANIFEST}: subject is empty")
        slugs = [a.get("slug") for a in m.get("areas", [])]
        if not slugs:
            E.append(f"{MANIFEST}: no areas")
        if len(slugs) != len(set(slugs)):
            E.append(f"{MANIFEST}: duplicate area slugs")
        folders = set()
        for a in m.get("areas", []):
            s = a.get("slug") or "?"
            if not SLUG_RE.match(str(a.get("slug", ""))):
                E.append(f"area {s}: slug must be lowercase letters, digits and dashes")
            if not a.get("title"):
                E.append(f"area {s}: title missing")
            f = a.get("folder")
            if f:
                folders.add(f)
                if not (self.path / f).is_dir():
                    E.append(f"area {s}: folder {f}/ does not exist")
                elif not has_practice(self.path / f):
                    W.append(f"area {s}: no practice file in {f}/")
            else:
                W.append(f"area {s}: no folder (notes live elsewhere?)")
        for f in m.get("extra_folders", []):
            folders.add(f)
            if not (self.path / f).is_dir():
                W.append(f"extra folder {f}/ does not exist")
        for d in sorted(p.name for p in self.path.iterdir() if p.is_dir()):
            if FOLDER_RE.match(d) and d not in folders:
                W.append(f"folder {d}/ is not listed in {MANIFEST} (area or extra_folders)")
        known = set(slugs)

        # concept trackers
        for p in sorted(self.concepts_dir.glob("*.md")) if self.concepts_dir.is_dir() else []:
            if p.stem not in known:
                E.append(f"concepts/{p.name}: no area with slug {p.stem!r}")
        for s in known:
            p = self.concept_path(s)
            if not p.exists():
                E.append(f"concepts/{s}.md missing (run `studyvault.py init` or `migrate --write`)")
                continue
            text = p.read_text(encoding="utf-8")
            lines = split_notes(text)[0].splitlines()
            for i, line in enumerate(lines):
                header = i + 1 < len(lines) and SEP_RE.match(lines[i + 1])
                if line.startswith("|") and not ROW_RE.match(line) and not header and not SEP_RE.match(line):
                    E.append(f"concepts/{s}.md: malformed row: {line[:80]}")
            rows, notes = parse_concepts_text(text)
            names = [r["name"].lower() for r in rows]
            for n in {n for n in names if names.count(n) > 1}:
                E.append(f"concepts/{s}.md: duplicate concept {n!r}")
            for r in rows:
                tag = f"concepts/{s}.md: {r['name']!r}"
                if r["status"] == "⚪":
                    if r["attempts"] or r["correct"] or r["last"] != "-":
                        E.append(f"{tag}: ⚪ (untested) needs 0 | 0 | - ")
                    continue
                if r["attempts"] < 1 or r["correct"] > r["attempts"]:
                    E.append(f"{tag}: correct {r['correct']} / attempts {r['attempts']} is impossible")
                try:
                    date.fromisoformat(r["last"])
                except ValueError:
                    E.append(f"{tag}: bad date {r['last']!r}")
                if r["status"] == "🔴" and r["name"].lower() not in notes:
                    E.append(f"{tag}: 🔴 without an error note")
                if r["status"] == "🔴" and r["correct"] == r["attempts"]:
                    W.append(f"{tag}: 🔴 but every attempt was correct")
            for n in notes:
                if n not in names:
                    W.append(f"concepts/{s}.md: error note {n!r} has no table row")

        # question bank
        for p in sorted(self.bank_dir.glob("*.json")) if self.bank_dir.is_dir() else []:
            tag = f"question-bank/{p.name}"
            if p.stem not in known:
                E.append(f"{tag}: no area with slug {p.stem!r}")
                continue
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                E.append(f"{tag}: invalid JSON ({e})")
                continue
            if data.get("area") != p.stem:
                E.append(f"{tag}: \"area\" must be {p.stem!r}")
            qs = data.get("questions", [])
            ids = [q.get("id") for q in qs]
            for d in {i for i in ids if ids.count(i) > 1}:
                E.append(f"{tag}: duplicate id {d!r}")
            for i, q in enumerate(qs, 1):
                if not isinstance(q.get("id"), str) or not ID_RE.match(q["id"]):
                    E.append(f"{tag}: question {i} has a bad id")
                E += [f"{tag}: {e}" for e in validate_question(q, f"question {i}", need_answer=True)]
                if not clean_cell(q.get("concept") or ""):
                    W.append(f"{tag}: {q.get('id')} has no concept, so bank rounds can't track it")
        for s in known:
            if not (self.bank_dir / f"{s}.json").exists():
                W.append(f"question-bank/{s}.json missing (empty bank)")

        # rounds and results
        cur = self.bank_dir / "rounds" / "current.json"
        if cur.exists():
            try:
                W += [f"rounds/current.json: {e}" for e in self.validate_round(json.loads(cur.read_text("utf-8")))]
            except json.JSONDecodeError as e:
                W.append(f"rounds/current.json: invalid JSON ({e})")
        res = self.bank_dir / "results"
        for p in sorted(res.glob("*.json")) if res.is_dir() else []:
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                E.append(f"results/{p.name}: invalid JSON ({e})")
                continue
            if p.name != "latest.json" and not data.get("tracked"):
                W.append(f"results/{p.name}: not recorded yet (grade it, then `record` with its round_id)")
        tasks = self.path / "tasks.json"
        if tasks.exists() and not isinstance((load_json(tasks) or {}).get("tasks"), list):
            E.append("tasks.json: needs {\"tasks\": [...]}")

        # dashboard
        if not self.dashboard.exists():
            E.append(f"{DASHBOARD} missing: run `studyvault.py recompute`")
        elif self.has_manifest() and self.dashboard.read_text(encoding="utf-8") != self.render_dashboard():
            E.append(f"{DASHBOARD} is out of date with concepts/: run `studyvault.py recompute`")

        # wiki links (Obsidian resolves by file name, path suffix, or path from the Obsidian root)
        def visible(p):
            return not any(part.startswith(".") for part in p.relative_to(self.path).parts)
        names = set()
        for p in self.path.rglob("*"):
            if p.is_file() and visible(p):
                rel = p.relative_to(self.path)
                names |= {p.stem.lower(), p.name.lower(), str(rel.with_suffix("")).lower(), str(rel).lower()}
        broken = {}
        for p in self.path.rglob("*.md"):
            if not visible(p):
                continue
            text = re.sub(r"```.*?```", "", p.read_text(encoding="utf-8"), flags=re.S)
            text = re.sub(r"`[^`\n]*`", "", text)
            for target in WIKI_RE.findall(text):
                t = target.strip().rstrip("\\").strip().lower()
                if "studyvault/" in t:
                    t = t.split("studyvault/", 1)[1]
                if t and t not in names and t.rsplit("/", 1)[-1] not in names:
                    broken.setdefault(str(p.relative_to(self.path)), []).append(target.strip())
        for f, ts in sorted(broken.items()):
            W.append(f"{f}: broken link(s) {', '.join(sorted(set(ts))[:5])}")
        return E, W


# ---------- init / migrate ----------

def init_vault(path, subject, area_specs, language="en", scope=""):
    v = Vault(path)
    if v.has_manifest():
        raise ValueError(f"{v.manifest_path} already exists; edit it instead")
    areas = []
    for spec in area_specs:
        folder, _, title = spec.partition("=")
        folder = folder.strip()
        m = FOLDER_RE.match(folder)
        if not m:
            raise ValueError(f"area folder {folder!r} must look like 01-Some-Name")
        title = title.strip() or m[2].replace("-", " ")
        areas.append({"slug": slugify(m[2]), "title": title, "folder": folder})
        (v.path / folder).mkdir(parents=True, exist_ok=True)
    (v.path / "00-Dashboard").mkdir(parents=True, exist_ok=True)
    v.write_manifest({"version": VERSION, "subject": subject, "language": language, "scope": scope,
                      "areas": areas, "extra_folders": ["00-Dashboard"]})
    made = v.ensure_area_files()
    v.recompute()
    return v, made


def migrate_vault(path, write=False, today=None):
    """Bring an older vault to the current format. Without write, only report what would happen.

    Keeps every tracked number. Old tracker files are rewritten under their slug, old dashboards are
    moved to StudyVault/.migrated-<date>/, and links to both are updated."""
    v = Vault(path)
    data = load_json(v.manifest_path) if v.has_manifest() else v.infer_manifest()
    lang = (data.get("language") or "en")[:2]
    titles = {a["slug"]: a["title"] for a in data.get("areas", [])}
    plan = {"renamed": {}, "normalized": [], "notes_added": {}, "moved": [], "links_fixed": 0}
    trackers = sorted(v.concepts_dir.glob("*.md")) if v.concepts_dir.is_dir() else []
    converted = {}
    for p in trackers:
        slug = area_key(p.stem)
        if slug not in titles:
            raise ValueError(f"concepts/{p.name}: no area for it in the manifest")
        if slug in converted:
            raise ValueError(f"concepts/{p.name} and concepts/{converted[slug][0].name} both map to {slug!r}")
        text = p.read_text(encoding="utf-8")
        new, added, paired = normalize_tracker(text, titles[slug], lang)
        if paired:
            plan.setdefault("notes_paired", {})[f"{slug}.md"] = paired
        converted[slug] = (p, new)
        if p.stem != slug:
            plan["renamed"][p.name] = f"{slug}.md"
        if new != text:
            plan["normalized"].append(f"{slug}.md")
        if added:
            plan["notes_added"][f"{slug}.md"] = added
    old_dash = v.old_dashboards()
    if v.dashboard.exists() and "claude-study-tool" not in v.dashboard.read_text(encoding="utf-8"):
        old_dash.append(v.dashboard)
    plan["moved"] = [str(p.relative_to(v.path)) for p in old_dash]
    if not write:
        return data, [], plan
    stash = v.path / f".migrated-{today or date.today().isoformat()}"
    v.write_manifest(data)
    for slug, (p, new) in converted.items():
        if p.stem != slug:
            (stash / "concepts").mkdir(parents=True, exist_ok=True)
            p.replace(stash / "concepts" / p.name)
        write_text(v.concept_path(slug), new)
    for p in old_dash:
        dest = stash / p.relative_to(v.path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if p == v.dashboard:
            dest.write_bytes(p.read_bytes())
        else:
            p.replace(dest)
    # links to renamed trackers and old dashboards
    subs = []
    for old, new in plan["renamed"].items():
        old, new = old[:-3], new[:-3]
        subs.append((re.compile(r"\[\[(?:[^\]|]*/)?concepts/" + re.escape(old) + r"(?=[\]|#])"), f"[[concepts/{new}"))
        subs.append((re.compile(r"\[\[" + re.escape(old) + r"(?=[\]|#])"), f"[[concepts/{new}"))
    for p in old_dash:
        if p != v.dashboard:
            rel = str(p.relative_to(v.path).with_suffix(""))
            subs.append((re.compile(r"\[\[(?:[^\]|]*/)?" + re.escape(rel) + r"(?=[\]|#])"), "[[Learning Dashboard"))
    for md in v.path.rglob("*.md"):
        if any(part.startswith(".") for part in md.relative_to(v.path).parts):
            continue
        text = md.read_text(encoding="utf-8")
        new = text
        for rx, rep in subs:
            new, n = rx.subn(rep, new)
            plan["links_fixed"] += n
        if new != text:
            write_text(md, new)
    made = v.ensure_area_files()
    v.recompute()
    return data, made, plan


# ---------- CLI ----------

def main(argv=None):
    ap = argparse.ArgumentParser(prog="studyvault.py", description="StudyVault data tool (claude-study-tool)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("status", "check", "recompute"):
        sub.add_parser(name).add_argument("vault")
    p = sub.add_parser("record")
    p.add_argument("vault")
    p.add_argument("file", help="JSON file with {round_id?, answers: [...]}, or - for stdin")
    p = sub.add_parser("validate-round")
    p.add_argument("vault")
    p.add_argument("file", nargs="?")
    p = sub.add_parser("init")
    p.add_argument("vault")
    p.add_argument("--subject", required=True)
    p.add_argument("--area", action="append", required=True, help='"01-Folder-Name=Display Title"')
    p.add_argument("--language", default="en")
    p.add_argument("--scope", default="")
    p = sub.add_parser("migrate")
    p.add_argument("vault")
    p.add_argument("--write", action="store_true")
    sub.add_parser("find").add_argument("root")
    a = ap.parse_args(argv)

    def out(obj):
        print(json.dumps(obj, indent=2, ensure_ascii=False))

    try:
        if a.cmd == "find":
            out([str(p) for p in find_vaults(a.root)])
        elif a.cmd == "status":
            out(Vault(a.vault).status())
        elif a.cmd == "recompute":
            out(Vault(a.vault).recompute())
        elif a.cmd == "check":
            errs, warns = Vault(a.vault).check()
            for w in warns:
                print(f"warning: {w}")
            for e in errs:
                print(f"ERROR: {e}")
            print(f"{len(errs)} error(s), {len(warns)} warning(s)")
            return 1 if errs else 0
        elif a.cmd == "record":
            raw = sys.stdin.read() if a.file == "-" else Path(a.file).read_text(encoding="utf-8")
            data = json.loads(raw)
            answers = data.get("answers") if isinstance(data, dict) else data
            out(Vault(a.vault).record(answers or [], round_id=(data.get("round_id") if isinstance(data, dict) else None)))
        elif a.cmd == "validate-round":
            v = Vault(a.vault)
            f = Path(a.file) if a.file else v.bank_dir / "rounds" / "current.json"
            errs = v.validate_round(json.loads(f.read_text(encoding="utf-8")))
            for e in errs:
                print(f"ERROR: {e}")
            print("round ok" if not errs else f"{len(errs)} error(s)")
            return 1 if errs else 0
        elif a.cmd == "init":
            v, made = init_vault(a.vault, a.subject, a.area, a.language, a.scope)
            out({"vault": str(v.path), "created": made})
        elif a.cmd == "migrate":
            data, made, plan = migrate_vault(a.vault, a.write)
            out({"manifest": data, "written": a.write, "changes": plan, "created": made})
    except (ValueError, FileNotFoundError, json.JSONDecodeError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
