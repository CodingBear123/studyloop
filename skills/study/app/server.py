#!/usr/bin/env python3
"""Claude Study Tool: local quiz + progress page for StudyVaults.

Serves index.html and a small JSON API. Standard library only, binds to 127.0.0.1.
All vault reads and writes go through studyvault.py.

    python3 server.py --root DIR           # every StudyVault under DIR (default: current folder)
    python3 server.py --vault PATH [...]   # specific StudyVault folder(s)

Every API call takes ?vault=<id>, where <id> is the path from the root to the
folder that holds the StudyVault (e.g. "HS26/SoCo"). GET /api/vaults lists them.
"""
import argparse
import json
import random
import sys
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import studyvault as sv  # noqa: E402

FONT_NAMES = {p.name for p in (HERE / "fonts").glob("*.woff2")}


class App:
    """The page's view of one vault."""

    def __init__(self, path):
        self.v = sv.Vault(path)

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
                        "unresolved": sum(r["status"] == "🔴" for r in rows)})
        return out

    def get_bank(self, slug):
        self.need_area(slug)
        return self.v.bank(slug)

    def sample_round(self, slugs, n, types):
        """Pick n bank questions; weight 🔴 concepts ×4 and prefer ones seen less often."""
        seen = {}
        for r in self.v.results():
            for a in r.get("answers", []):
                key = (a.get("area"), a.get("id"))
                seen[key] = seen.get(key, 0) + 1
        pool = []
        for slug in slugs:
            self.need_area(slug)
            rows, _ = self.v.concepts(slug)
            red = {r["name"].lower() for r in rows if r["status"] == "🔴"}
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
        for q in picked:  # shuffle options, remap the answer index
            if q.get("type") == "single" and q.get("shuffle", True):
                order = list(range(len(q["options"])))
                random.shuffle(order)
                q["options"] = [q["options"][i] for i in order]
                if isinstance(q.get("answer"), int):
                    q["answer"] = order.index(q["answer"])
        return {"id": datetime.now().strftime("bank-%Y%m%d-%H%M%S"), "source": "bank",
                "title": ", ".join(self.v.title(s) for s in slugs), "reveal": True, "questions": picked}

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
        """Bank rounds carry their answer key, so the server records their single-choice answers.

        Each recorded answer gets "recorded": true. "tracked" is true only when nothing is left
        for Claude to grade (no answered open questions)."""
        graded, hits = [], []
        for a in data.get("answers", []):
            area, concept = a.get("area") or "", (a.get("concept") or "").strip()
            if a.get("type") != "single" or a.get("correct") is None or not concept or not self.v.area(area):
                continue
            q = self.v.bank_question(area, a.get("id")) or {}
            picked = (a.get("choice_text") or "").strip().replace("\n", " ⏎ ")
            graded.append({"area": area, "concept": concept, "correct": bool(a["correct"]),
                           "confusion": f"picked `{picked[:120]}` in a practice round." if picked
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
                activity[day] = activity.get(day, 0) + sum(
                    1 for a in r.get("answers", []) if a.get("choice") is not None or (a.get("text") or "").strip())
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
            self.send_header("Content-Type", ctype + ("" if ctype.startswith("font/") else "; charset=utf-8"))
            self.send_header("Cache-Control", "max-age=86400" if cache else "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def body(self):
            n = int(self.headers.get("Content-Length") or 0)
            return json.loads(self.rfile.read(n) or b"{}")

        def handle_any(self, method):
            url = urlparse(self.path)
            q = parse_qs(url.query)
            p = url.path
            try:
                if method == "GET" and p in ("/", "/index.html"):
                    return self.send(200, (HERE / "index.html").read_bytes(), "text/html")
                if method == "GET" and p.startswith("/fonts/"):
                    name = p.rsplit("/", 1)[-1]
                    if name in FONT_NAMES:
                        return self.send(200, (HERE / "fonts" / name).read_bytes(), "font/woff2", cache=True)
                    return self.send(404, {"error": "not found"})
                if method == "GET" and p == "/api/vaults":
                    return self.send(200, [{"id": k, "path": str(a.vault), "subject": a.v.manifest.get("subject")}
                                           for k, a in vaults.items()])
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
