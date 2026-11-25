"""A StudyVault's notes for the page: the note tree, one note, and the section that covers a question.

Standard library only. Read-only: nothing here writes to the vault.

A question can name its section explicitly with `"ref": "Note title#Heading"` (or a path from the
vault, `"01-Objects/Design Basics.md#Cohesion"`). Without one, `find_section` picks the section of the
question's area whose words overlap most with the question's concept, prompt and explanation.
"""
import math
import re
from collections import Counter
from pathlib import Path

HEAD_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
FENCE_RE = re.compile(r"^\s*(```|~~~)")
WORD_RE = re.compile(r"[a-z0-9_äöüß]+")
IMAGE_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif",
               ".webp": "image/webp", ".svg": "image/svg+xml"}
SKIP_DIRS = {"question-bank"}
TRACKERS = "concepts"
PRACTICE_RE = re.compile(r"(^|\s)(practice|übung|uebung)\b", re.I)
WEAK_HEADS = {"exam patterns", "related notes", "related concepts", "prüfungsmuster", "verwandte notizen"}
CALL_RE = re.compile(r"(?<![.\w])([A-Za-z_]\w*)\s*\(")  # save(...), not x.append(...)
CODE_RE = re.compile(r"^```[^\n]*\n(.*?)^```", re.M | re.S)
BUILTINS = set(dir(__import__("builtins"))) | {"def", "class", "if", "elif", "while", "for", "return", "and", "or", "not",
                                               "in", "is", "with", "assert", "lambda", "yield", "except", "print"}
STOP = set("""
the and for are but not you your with this that what which when where who why how does did was were
has have had its it's can could would should will shall may might must than then them they their there
these those from into onto out over under about after before again also any all both each few more most
other some such only own same too very just one two three use used using via per like yes no
what's which whose here been being do doing done is am be of to in on at by or if as an a so
question answer correct wrong true false following given code print prints printed output value
der die das und oder nicht ist sind ein eine einer eines mit für von zu im in auf aus bei was wie wer
""".split())


def anchor(text):
    """Heading -> link anchor. index.html's anchor() must give the same result."""
    s = re.sub(r"[`*_\[\]()]", "", text).strip().lower()
    s = re.sub(r"[^\w\s-]", "", s)
    return re.sub(r"\s+", "-", s)


def words(text):
    return [w for w in WORD_RE.findall((text or "").lower()) if len(w) > 2 and w not in STOP]


def split_front(text):
    """(frontmatter dict, body) for a note that may start with a --- YAML block."""
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        if end != -1:
            meta = {}
            for line in text[4:end].splitlines():
                k, sep, v = line.partition(":")
                if sep and k.strip() and not k.startswith(" "):
                    meta[k.strip()] = v.strip()
            return meta, text[end + 4:].lstrip("\n")
    return {}, text


def sections(body):
    """Split a note body at its headings. The text before the first heading has heading ''."""
    out, cur, fence = [], {"heading": "", "level": 0, "lines": []}, False
    for line in body.splitlines():
        if FENCE_RE.match(line):
            fence = not fence
        m = None if fence else HEAD_RE.match(line)
        if m:
            out.append(cur)
            cur = {"heading": m[2], "level": len(m[1]), "lines": []}
        else:
            cur["lines"].append(line)
    out.append(cur)
    res = []
    for s in out:
        text = "\n".join(s["lines"]).strip()
        if s["heading"] or text:
            res.append({"heading": s["heading"], "level": s["level"], "anchor": anchor(s["heading"]), "text": text})
    return res


class Notes:
    def __init__(self, vault):
        self.v = vault  # a studyvault.Vault
        self._index, self._key = None, None

    # ----- tree and files -----

    def files(self, trackers=True):
        """Every visible note; concept trackers only with trackers=True (they never answer a question)."""
        root = self.v.path
        out = []
        for p in root.rglob("*.md"):
            rel = p.relative_to(root)
            top = rel.parts[0] if len(rel.parts) > 1 else ""
            if any(part.startswith(".") for part in rel.parts) or top in SKIP_DIRS or (top == TRACKERS and not trackers):
                continue
            out.append(p)
        return out

    def tree(self):
        """Folders in manifest order (areas, then extra folders, then the rest), notes before practice files."""
        root = self.v.path
        by_folder = {}
        for p in self.files():
            rel = p.relative_to(root)
            top = rel.parts[0] if len(rel.parts) > 1 else ""
            by_folder.setdefault(top, []).append(p)
        areas = {a.get("folder"): a for a in self.v.areas()}
        order = [a.get("folder") for a in self.v.areas()] + list(self.v.manifest.get("extra_folders") or [])
        rest = sorted(f for f in by_folder if f not in order and f != TRACKERS) + [TRACKERS] * (TRACKERS in by_folder)
        groups = []
        for folder in [f for f in order if f in by_folder] + rest:
            a = areas.get(folder)
            title = "Concept trackers" if folder == TRACKERS else a["title"] if a else (re.sub(r"^\d+[-_ ]+", "", folder).replace("-", " ") if folder else "Vault")
            notes = sorted(by_folder[folder], key=lambda p: (bool(PRACTICE_RE.search(p.stem)), p.stem.lower()))
            groups.append({"folder": folder, "title": title, "area": a["slug"] if a else None,
                           "notes": [{"path": p.relative_to(root).as_posix(), "title": p.stem,
                                      "practice": bool(PRACTICE_RE.search(p.stem))} for p in notes]})
        return groups

    def safe(self, rel):
        """Resolve a vault-relative .md path, refusing anything outside the vault or hidden."""
        rel = (rel or "").strip().lstrip("/")
        p = (self.v.path / rel).resolve()
        root = self.v.path.resolve()
        if p.suffix.lower() != ".md" or root not in p.parents or not p.is_file():
            raise ValueError(f"no such note {rel!r}")
        if any(part.startswith(".") for part in p.relative_to(root).parts):
            raise ValueError(f"no such note {rel!r}")
        return p

    def asset(self, name):
        """An image embedded with ![[name]]: a vault path, or a file name found anywhere in the vault."""
        root = self.v.path.resolve()
        name = (name or "").strip().lstrip("/")
        p = (root / name).resolve()
        if not p.is_file():
            p = next((f.resolve() for f in root.rglob(Path(name).name) if f.is_file()), p)
        if p.suffix.lower() not in IMAGE_TYPES or root not in p.parents or not p.is_file() \
                or any(part.startswith(".") for part in p.relative_to(root).parts):
            raise ValueError(f"no such image {name!r}")
        return p

    def read(self, rel):
        p = self.safe(rel)
        meta, body = split_front(p.read_text(encoding="utf-8"))
        return {"path": p.relative_to(self.v.path.resolve()).as_posix(), "title": p.stem, "meta": meta,
                "body": body, "abs": str(p)}

    def section_text(self, rel, anc="", limit=7000):
        """The text of one section (with its sub-sections), or the whole note, for Claude's context."""
        note = self.read(rel)
        body = note["body"]
        if anc:
            secs, keep, level = sections(body), [], None
            for s in secs:
                if level is None and s["anchor"] == anc:
                    level = s["level"]
                elif level is not None and s["heading"] and s["level"] <= level:
                    break
                if level is not None:
                    keep.append(("#" * s["level"] + " " + s["heading"] + "\n" if s["heading"] else "") + s["text"])
            if keep:
                body = "\n\n".join(keep)
        return note["title"], body[:limit]

    def definitions(self, text, limit=3, size=2500):
        """[(note title, code block)] from the notes that define the functions or classes `text` calls
        without defining them itself, e.g. the course's save() for a question about save(writer, x)."""
        names = []
        for n in CALL_RE.findall(text or ""):
            if n not in names and n not in BUILTINS and not re.search(rf"^\s*(def|class)\s+{re.escape(n)}\b", text, re.M):
                names.append(n)
        if not names:
            return []
        blocks = []
        for f in sorted(self.files(trackers=False), key=lambda f: (bool(PRACTICE_RE.search(f.stem)), str(f))):
            try:
                body = split_front(f.read_text(encoding="utf-8"))[1]
            except OSError:
                continue
            blocks += [(f.stem, b) for b in CODE_RE.findall(body)]
        out, found = [], set()
        # top-level definitions first: save(writer, x) means the function save, not some class's save method
        for indent in (r"", r"[ \t]+"):
            for title, block in blocks:
                hits = [n for n in names if n not in found
                        and re.search(rf"^{indent}(def|class)\s+{re.escape(n)}\b", block, re.M)]
                if hits:
                    found.update(hits)
                    out.append((title, block.rstrip()[:size]))
                    if len(out) >= limit or len(found) == len(names):
                        return out
        return out

    # ----- question -> section -----

    def index(self):
        files = self.files(trackers=False)
        key = tuple(sorted((str(p), p.stat().st_mtime) for p in files))
        if key == self._key:
            return self._index
        root = self.v.path
        secs = []
        for p in files:
            rel = p.relative_to(root)
            _, body = split_front(p.read_text(encoding="utf-8"))
            practice = bool(PRACTICE_RE.search(p.stem))
            for s in sections(body):
                toks = words(s["heading"] + "\n" + s["text"])
                if not toks:
                    continue
                secs.append({"path": rel.as_posix(), "folder": rel.parts[0] if len(rel.parts) > 1 else "",
                             "title": p.stem, "heading": s["heading"], "anchor": s["anchor"], "practice": practice,
                             "tf": Counter(toks), "n": len(toks), "head": set(words(s["heading"] + " " + p.stem))})
        df = Counter(t for s in secs for t in s["tf"])
        n = len(secs) or 1
        idf = {t: math.log((n + 1) / (c + 1)) + 1 for t, c in df.items()}
        self._index, self._key = (secs, idf), key
        return self._index

    def find_section(self, q, area_folder=None):
        """Best section for a question dict, or None."""
        weights = {}
        for field, w in (("prompt", 1.0), ("statements", 1.0), ("code", 0.6), ("explanation", 1.5), ("model_answer", 1.5),
                         ("concept", 3.0)):
            val = q.get(field)
            for t in words(" ".join(map(str, val)) if isinstance(val, list) else val):
                weights[t] = max(weights.get(t, 0), w)
        if not weights:
            return None
        secs, idf = self.index()
        pool = [s for s in secs if area_folder and s["folder"] == area_folder] or secs
        best, best_score = None, 0.0
        for s in pool:
            score = 0.0
            for t, w in weights.items():
                tf = s["tf"].get(t)
                if tf:
                    score += w * idf.get(t, 1) * (1 + math.log(tf))
                    if t in s["head"]:
                        score += w * idf.get(t, 1) * 1.5
            score /= 1 + math.log(1 + s["n"] / 80)
            if s["practice"]:
                score *= 0.6
            if s["heading"].strip().lower() in WEAK_HEADS:
                score *= 0.5
            if score > best_score:
                best, best_score = s, score
        if not best:
            return None
        return {"path": best["path"], "title": best["title"], "heading": best["heading"], "anchor": best["anchor"],
                "auto": True}

    def resolve_ref(self, ref):
        """'Note#Heading' or 'folder/Note.md#Heading' -> section dict, or None if the note doesn't exist."""
        target, _, head = str(ref).partition("#")
        target = target.strip().removesuffix(".md").lower()
        if not target:
            return None
        hit = None
        for p in self.files():
            rel = p.relative_to(self.v.path).with_suffix("").as_posix().lower()
            if rel == target or p.stem.lower() == target or rel.endswith("/" + target):
                hit = p
                break
        if not hit:
            return None
        return {"path": hit.relative_to(self.v.path).as_posix(), "title": hit.stem, "heading": head.strip(),
                "anchor": anchor(head) if head.strip() else "", "auto": False}

    def note_for(self, q, area_folder=None):
        if q.get("ref"):
            r = self.resolve_ref(q["ref"])
            if r:
                return r
        return self.find_section(q, area_folder)
