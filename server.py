#!/usr/bin/env python3
"""Crunch Time: local quiz + progress app for /tutor StudyVaults.

Serves index.html and a small JSON API over StudyVault folders.
Standard library only. Binds to 127.0.0.1.

    python3 server.py                      # all StudyVaults under this folder's parent
    python3 server.py --root DIR           # all StudyVaults under DIR
    python3 server.py --vault PATH [...]   # specific StudyVault folder(s)
    python3 server.py --recompute PATH     # rebuild a vault's Learning Dashboard, then exit

Every API call takes ?vault=<id>, where <id> is the vault's parent path relative
to the root (e.g. "HS26/SoCo"). GET /api/vaults lists them.

Layout under each vault:
    question-bank/{area}.json         question bank, one file per area
    question-bank/rounds/current.json round written by Claude (optional)
    question-bank/results/*.json      submitted rounds (latest.json = last one)
    concepts/{area}.md                concept trackers (bank rounds update these)
    Learning Dashboard.md             recomputed after every tracked round
    tasks.json                        study to-do list shown on the Quiz page
"""
import argparse
import json
import random
import re
import sys
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

HERE = Path(__file__).resolve().parent
SLUG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
ROUND_RE = re.compile(r"^[A-Za-z0-9_-]+$")
FONT_RE = re.compile(r"^[a-z0-9-]+\.woff2$")
ROW_RE = re.compile(r"^\| (?!Concept \||-)(.+?) \| (\d+) \| (\d+) \| ([\d-]+) \| (🔴|🟢) \|\s*$", re.M)
DASH_ROW_RE = re.compile(r"^\| (?!\*\*|Area \|)(.+?) \|.*\[\[concepts/([A-Za-z0-9_-]+)\]\] \|\s*$", re.M)
NOTES_HEAD = "### Error Notes"
PLACEHOLDER = "(added as concepts are missed)"


def load_json(path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def write_text(path, text):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def title_from_slug(slug):
    return " ".join(w.capitalize() for w in slug.split("-"))


def badge(rate):
    if rate is None:
        return "⬜ Unmeasured"
    return "🟥 Weak" if rate < 40 else "🟨 Fair" if rate < 70 else "🟩 Good" if rate < 90 else "🟦 Mastered"


def validate_question(q):
    errs = []
    if not isinstance(q.get("id"), str) or not q["id"]:
        errs.append("id missing")
    if q.get("type") not in ("single", "open"):
        errs.append(f"{q.get('id')}: type must be 'single' or 'open'")
    if not q.get("prompt") and not q.get("code"):
        errs.append(f"{q.get('id')}: prompt or code required")
    if q.get("type") == "single":
        opts = q.get("options")
        if not isinstance(opts, list) or not 2 <= len(opts) <= 8:
            errs.append(f"{q.get('id')}: single needs 2-8 options")
        ans = q.get("answer")
        if ans is not None and (not isinstance(ans, int) or not 0 <= ans < len(opts or [])):
            errs.append(f"{q.get('id')}: answer must be an option index")
    return errs


# ---------- concept files ----------

def parse_concepts(path):
    """Rows and error notes of concepts/{area}.md."""
    if not path.exists():
        return [], {}
    text = path.read_text(encoding="utf-8")
    rows = [{"name": m[1].strip(), "attempts": int(m[2]), "correct": int(m[3]), "last": m[4], "status": m[5]}
            for m in ROW_RE.finditer(text)]
    notes = {}
    if NOTES_HEAD in text:
        body = text.split(NOTES_HEAD, 1)[1]
        for m in re.finditer(r"^\*\*(.+?)\*\*\s*\n((?:- .*\n?)+)", body, re.M):
            notes[m[1].strip().lower()] = m[2].strip()
    return rows, notes


def record_answer(path, area_title, concept, correct, confusion, key_point):
    """Apply one graded answer to concepts/{area}.md (tutor skill format)."""
    today = date.today().isoformat()
    if path.exists():
        text = path.read_text(encoding="utf-8")
    else:
        text = (f"# {area_title} — Concept Tracker\n\n| Concept | Attempts | Correct | Last Tested | Status |\n"
                f"|---------|----------|---------|-------------|--------|\n\n{NOTES_HEAD}\n\n{PLACEHOLDER}\n")
    status = "🟢" if correct else "🔴"
    hit = None
    for m in ROW_RE.finditer(text):
        if m[1].strip().lower() == concept.lower():
            hit = m
            break
    if hit:
        row = f"| {hit[1].strip()} | {int(hit[2]) + 1} | {int(hit[3]) + int(correct)} | {today} | {status} |"
        text = text[:hit.start()] + row + text[hit.end():]
    else:
        row = f"| {concept} | 1 | {int(correct)} | {today} | {status} |"
        lines = text.split("\n")
        idx = max((i for i, l in enumerate(lines) if l.startswith("|")), default=None)
        if idx is None:
            lines[1:1] = ["", "| Concept | Attempts | Correct | Last Tested | Status |",
                          "|---------|----------|---------|-------------|--------|", row]
        else:
            lines.insert(idx + 1, row)
        text = "\n".join(lines)
    if not correct:
        _, notes = parse_concepts_text(text)
        note = f"**{concept}**\n- Confusion: {confusion}\n- Key point: {key_point}"
        if concept.lower() in notes:  # replace the old note: it is wrong again
            text = re.sub(r"^\*\*" + re.escape(concept) + r"\*\*\s*\n(?:- .*\n?)+", lambda _: note + "\n", text,
                          count=1, flags=re.M | re.I)
        else:
            if NOTES_HEAD not in text:
                text = text.rstrip("\n") + f"\n\n{NOTES_HEAD}\n"
            text = text.replace(PLACEHOLDER + "\n", "").replace(PLACEHOLDER, "")
            text = text.rstrip("\n") + "\n\n" + note + "\n"
    write_text(path, text if text.endswith("\n") else text + "\n")


def parse_concepts_text(text):
    tmp_rows = list(ROW_RE.finditer(text))
    notes = {}
    if NOTES_HEAD in text:
        for m in re.finditer(r"^\*\*(.+?)\*\*\s*\n((?:- .*\n?)+)", text.split(NOTES_HEAD, 1)[1], re.M):
            notes[m[1].strip().lower()] = m[2]
    return tmp_rows, notes


def plain(md_text, limit=300):
    """One-line version of an explanation for an error note."""
    s = re.sub(r"```\w*\n?", "", md_text or "").replace("\n", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s if len(s) <= limit else s[:limit - 1].rstrip() + "…"


# ---------- vault ----------

class App:
    def __init__(self, vault):
        self.vault = vault
        self.bank = vault / "question-bank"
        self.concepts = vault / "concepts"
        self.dashboard = vault / "Learning Dashboard.md"

    # areas in dashboard order, with names from the dashboard table
    def area_list(self):
        out, seen = [], set()
        if self.dashboard.exists():
            for m in DASH_ROW_RE.finditer(self.dashboard.read_text(encoding="utf-8")):
                if m[2] not in seen:
                    out.append((m[2], m[1].strip()))
                    seen.add(m[2])
        extra = {p.stem for p in self.bank.glob("*.json")}
        extra |= {p.stem for p in self.concepts.glob("*.md")} if self.concepts.exists() else set()
        for slug in sorted(extra - seen):
            data = load_json(self.bank / f"{slug}.json", {}) or {}
            out.append((slug, data.get("title") or title_from_slug(slug)))
        return out

    def area_title(self, slug):
        return dict(self.area_list()).get(slug) or title_from_slug(slug)

    def areas(self):
        out = []
        for slug, title in self.area_list():
            data = load_json(self.bank / f"{slug}.json", {}) or {}
            rows, _ = parse_concepts(self.concepts / f"{slug}.md")
            out.append({"slug": slug, "title": title, "count": len(data.get("questions", [])),
                        "unresolved": sum(r["status"] == "🔴" for r in rows)})
        return out

    def unresolved(self, slug):
        rows, _ = parse_concepts(self.concepts / f"{slug}.md")
        return {r["name"].lower() for r in rows if r["status"] == "🔴"}

    def get_bank(self, slug):
        data = load_json(self.bank / f"{slug}.json")
        if data is None:
            data = {"area": slug, "title": self.area_title(slug), "questions": []}
        return data

    def put_bank(self, slug, data):
        qs = data.get("questions")
        if not isinstance(qs, list):
            raise ValueError("questions must be a list")
        errs = [e for q in qs for e in validate_question(q)]
        ids = [q.get("id") for q in qs]
        if len(ids) != len(set(ids)):
            errs.append("duplicate question ids")
        if errs:
            raise ValueError("; ".join(errs))
        data["area"] = slug
        data.setdefault("title", self.area_title(slug))
        write_json(self.bank / f"{slug}.json", data)

    def history(self):
        out = []
        for p in sorted((self.bank / "results").glob("*.json")):
            if p.name != "latest.json":
                out.append(load_json(p, {}) or {})
        return out

    def sample_round(self, slugs, n, types):
        """Pick n questions; weight unseen and 🔴-concept questions higher."""
        seen = {}
        for r in self.history():
            for a in r.get("answers", []):
                key = (a.get("area"), a.get("id"))
                seen[key] = seen.get(key, 0) + 1
        pool = []
        for slug in slugs:
            red = self.unresolved(slug)
            for q in self.get_bank(slug).get("questions", []):
                if types and q.get("type") not in types:
                    continue
                w = 1.0
                if (q.get("concept") or "").lower() in red:
                    w *= 4
                w /= 1 + seen.get((slug, q["id"]), 0)
                pool.append((w, dict(q, area=slug)))
        picked = []
        while pool and len(picked) < n:
            r = random.uniform(0, sum(w for w, _ in pool))
            for i, (w, q) in enumerate(pool):
                r -= w
                if r <= 0:
                    picked.append(pool.pop(i)[1])
                    break
            else:
                picked.append(pool.pop()[1])
        for q in picked:  # shuffle options, remap answer
            if q.get("type") == "single" and q.get("shuffle", True):
                order = list(range(len(q["options"])))
                random.shuffle(order)
                q["options"] = [q["options"][i] for i in order]
                if isinstance(q.get("answer"), int):
                    q["answer"] = order.index(q["answer"])
        rid = datetime.now().strftime("bank-%Y%m%d-%H%M%S")
        return {"id": rid, "source": "bank", "title": ", ".join(self.area_title(s) for s in slugs),
                "reveal": True, "questions": picked}

    def get_round(self, rid):
        if not ROUND_RE.match(rid):
            raise ValueError("bad round id")
        data = load_json(self.bank / "rounds" / f"{rid}.json")
        if data is None:
            return None
        data.setdefault("id", rid)
        data.setdefault("source", "claude")
        data.setdefault("reveal", False)
        for q in data.get("questions", []):
            if q.get("bank_ref"):  # {"area": ..., "id": ...} pulls from the bank
                ref = q.pop("bank_ref")
                for bq in self.get_bank(ref["area"]).get("questions", []):
                    if bq["id"] == ref["id"]:
                        q.update(dict(bq, area=ref["area"]))
        return data

    def save_results(self, data):
        rid = data.get("round_id") or "unknown"
        if not ROUND_RE.match(rid):
            raise ValueError("bad round id")
        data["submitted_at"] = datetime.now().isoformat(timespec="seconds")
        if data.get("source") == "bank":
            self.track(data)
        res = self.bank / "results"
        write_json(res / f"{rid}.json", data)
        write_json(res / "latest.json", data)
        return str(res / f"{rid}.json")

    def track(self, data):
        """Bank rounds carry their answer key, so the server grades and records them itself."""
        banks = {}
        n = 0
        for a in data.get("answers", []):
            area, concept = a.get("area"), (a.get("concept") or "").strip()
            if a.get("type") != "single" or a.get("correct") is None or not area or not concept:
                continue
            if not SLUG_RE.match(area):
                continue
            if area not in banks:
                banks[area] = {q["id"]: q for q in self.get_bank(area).get("questions", [])}
            q = banks[area].get(a.get("id"), {})
            picked = (a.get("choice_text") or "").strip().replace("\n", " ⏎ ")
            confusion = f"picked `{picked[:120]}` in a browser round." if picked else "left it unanswered."
            key = plain(q.get("explanation")) or f"see question {a.get('id')} in question-bank/{area}.json"
            record_answer(self.concepts / f"{area}.md", self.area_title(area), concept, bool(a["correct"]),
                          confusion, key)
            n += 1
        if n:
            self.recompute_dashboard()
        data["tracked"] = n > 0
        data["tracked_count"] = n

    def progress(self):
        areas, total_a, total_c, open_concepts = [], 0, 0, []
        for slug, title in self.area_list():
            rows, notes = parse_concepts(self.concepts / f"{slug}.md")
            a = sum(r["attempts"] for r in rows)
            c = sum(r["correct"] for r in rows)
            total_a += a
            total_c += c
            rate = round(100 * c / a) if a else None
            bank = load_json(self.bank / f"{slug}.json", {}) or {}
            areas.append({"slug": slug, "title": title, "attempts": a, "correct": c, "rate": rate,
                          "level": badge(rate), "bank": len(bank.get("questions", [])),
                          "concepts": len(rows), "open": sum(r["status"] == "🔴" for r in rows)})
            for r in rows:
                if r["status"] == "🔴":
                    open_concepts.append(dict(r, area=slug, area_title=title, note=notes.get(r["name"].lower(), "")))
        activity = {}
        for r in self.history():
            day = (r.get("submitted_at") or "")[:10]
            if day:
                answered = sum(1 for a in r.get("answers", [])
                               if a.get("choice") is not None or (a.get("text") or "").strip())
                activity[day] = activity.get(day, 0) + answered
        rate = round(100 * total_c / total_a) if total_a else None
        return {"areas": areas, "open": open_concepts, "activity": activity,
                "total": {"attempts": total_a, "correct": total_c, "rate": rate, "level": badge(rate)}}

    def recompute_dashboard(self):
        """Rebuild the proficiency table and Stats section of Learning Dashboard.md."""
        if not self.dashboard.exists():
            return None
        rows, T, C, unres, res, rates = [], 0, 0, 0, 0, {}
        for slug, title in self.area_list():
            crow, _ = parse_concepts(self.concepts / f"{slug}.md")
            a = sum(r["attempts"] for r in crow)
            c = sum(r["correct"] for r in crow)
            unres += sum(r["status"] == "🔴" for r in crow)
            res += sum(r["status"] == "🟢" for r in crow)
            r = round(100 * c / a) if a else None
            if r is not None:
                rates[title] = r
            T += a
            C += c
            rows.append(f"| {title} | {c} | {a - c} | {str(r) + '%' if r is not None else '-'} | {badge(r)} | [[concepts/{slug}]] |")
        tr = round(100 * C / T) if T else None
        rows.append(f"| **Total** | **{C}** | **{T - C}** | **{str(tr) + '%' if tr is not None else '-'}** | {badge(tr)} | |")
        weak = min(rates, key=rates.get) if rates else "-"
        strong = max(rates, key=rates.get) if rates else "-"
        s = self.dashboard.read_text(encoding="utf-8")
        s = re.sub(r"(\|------\|.*?\n)(.*?)(\n\n> 🟥)", lambda m: m[1] + "\n".join(rows) + m[3], s, count=1, flags=re.S)
        stats = (f"## Stats\n\n- **Total Questions**: {T}\n- **Cumulative Rate**: {str(tr) + '%' if tr is not None else '-'}\n"
                 f"- **Unresolved Concepts**: {unres}\n- **Resolved Concepts**: {res}\n"
                 f"- **Weakest Area**: {weak}\n- **Strongest Area**: {strong}\n")
        s = re.sub(r"## Stats.*", lambda m: stats, s, count=1, flags=re.S)
        write_text(self.dashboard, s)
        return {"total": T, "correct": C, "rate": tr, "unresolved": unres, "resolved": res,
                "weakest": weak, "strongest": strong}

    def get_tasks(self):
        return load_json(self.vault / "tasks.json", {"tasks": []}) or {"tasks": []}

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
        write_json(self.vault / "tasks.json", {"tasks": clean})


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
            sys.stderr.write("[crunch] " + fmt % args + "\n")

        def send(self, code, body, ctype="application/json", cache=False):
            if not isinstance(body, (bytes, str)):
                body = json.dumps(body, ensure_ascii=False)
            if isinstance(body, str):
                body = body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype + ("" if ctype.startswith("font/") else "; charset=utf-8"))
            self.send_header("Cache-Control", "max-age=86400" if cache else "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def body(self):
            n = int(self.headers.get("Content-Length") or 0)
            return json.loads(self.rfile.read(n) or b"{}")

        def area_slug(self, path):
            slug = path.rsplit("/", 1)[-1]
            if not SLUG_RE.match(slug):
                raise ValueError("bad area slug (letters, digits, dashes)")
            return slug

        def handle_any(self, method):
            url = urlparse(self.path)
            q = parse_qs(url.query)
            p = url.path
            try:
                if method == "GET" and p in ("/", "/index.html"):
                    return self.send(200, (HERE / "index.html").read_bytes(), "text/html")
                if method == "GET" and p.startswith("/fonts/"):
                    name = p.rsplit("/", 1)[-1]
                    f = HERE / "fonts" / name
                    if FONT_RE.match(name) and f.exists():
                        return self.send(200, f.read_bytes(), "font/woff2", cache=True)
                    return self.send(404, {"error": "not found"})
                if method == "GET" and p == "/api/vaults":
                    return self.send(200, [{"id": k, "path": str(a.vault)} for k, a in vaults.items()])
                app = pick(q) if p.startswith("/api/") else None
                if method == "GET" and p == "/api/areas":
                    return self.send(200, app.areas())
                if method == "GET" and p == "/api/progress":
                    return self.send(200, app.progress())
                if p == "/api/tasks":
                    if method == "GET":
                        return self.send(200, app.get_tasks())
                    if method == "PUT":
                        app.put_tasks(self.body())
                        return self.send(200, {"ok": True})
                if p.startswith("/api/bank/"):
                    slug = self.area_slug(p)
                    if method == "GET":
                        return self.send(200, app.get_bank(slug))
                    if method == "PUT":
                        app.put_bank(slug, self.body())
                        return self.send(200, {"ok": True})
                if method == "GET" and p == "/api/round":
                    if "id" in q:
                        r = app.get_round(q["id"][0])
                        return self.send(200, r) if r else self.send(404, {"error": "no such round"})
                    slugs = [s for s in ",".join(q.get("area", [])).split(",") if s]
                    for s in slugs:
                        if not SLUG_RE.match(s):
                            raise ValueError("bad area slug")
                    if not slugs:
                        slugs = [a["slug"] for a in app.areas() if a["count"]]
                    types = set(q["types"][0].split(",")) if "types" in q else None
                    n = int(q.get("n", ["4"])[0])
                    return self.send(200, app.sample_round(slugs, n, types))
                if method == "POST" and p == "/api/results":
                    data = self.body()
                    path = app.save_results(data)
                    return self.send(200, {"ok": True, "path": path, "tracked": data.get("tracked", False),
                                           "tracked_count": data.get("tracked_count", 0)})
                return self.send(404, {"error": "not found"})
            except ValueError as e:
                return self.send(400, {"error": str(e)})

        def do_GET(self):
            self.handle_any("GET")

        def do_PUT(self):
            self.handle_any("PUT")

        def do_POST(self):
            self.handle_any("POST")

    return Handler


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(HERE.parent), help="folder to search for StudyVaults")
    ap.add_argument("--vault", action="append", help="specific StudyVault folder (repeatable)")
    ap.add_argument("--recompute", metavar="VAULT", help="rebuild VAULT's Learning Dashboard.md and exit")
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()
    if args.recompute:
        v = Path(args.recompute).expanduser().resolve()
        if v.name != "StudyVault" and (v / "StudyVault").is_dir():
            v = v / "StudyVault"
        out = App(v).recompute_dashboard()
        if out is None:
            sys.exit(f"no Learning Dashboard.md in {v}")
        print(json.dumps(out, ensure_ascii=False))
        return
    root = Path(args.root).expanduser().resolve()
    if args.vault:
        paths = [Path(v).expanduser().resolve() for v in args.vault]
    else:
        paths = sorted(p for p in root.rglob("StudyVault")
                       if p.is_dir() and not any(part.startswith(".") for part in p.relative_to(root).parts))
    vaults = {}
    for v in paths:
        if not v.is_dir():
            sys.exit(f"not a directory: {v}")
        try:
            vid = str(v.parent.relative_to(root))
        except ValueError:
            vid = v.parent.name
        vaults[vid] = App(v)
    if not vaults:
        sys.exit(f"no StudyVault folders under {root}")
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(vaults))
    print(f"[crunch] http://127.0.0.1:{args.port}/  vaults: {', '.join(vaults)}", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
