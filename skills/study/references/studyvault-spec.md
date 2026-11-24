# StudyVault format (version 1)

One `StudyVault/` per subject. `studyvault.json` is the single source of truth for which areas exist; the
area slug ties a folder, a concept tracker and a question bank together. File and folder names and JSON keys
are always English; note content may be in any language.

```
StudyVault/
├── studyvault.json              manifest (below)
├── Learning Dashboard.md        GENERATED from concepts/ by `studyvault.py recompute`
├── tasks.json                   to-do list / study plan shown on the page (optional)
├── 00-Dashboard/                MOC, Quick Reference, Exam Traps, Exam Blueprint (optional)
├── 01-<Area-Folder>/            notes for one area + one "<NN> Practice - <Title>.md"
├── ...
├── NN-Past-Exams/               optional extra folder
├── concepts/<slug>.md           concept tracker, one per area
└── question-bank/
    ├── <slug>.json              question bank, one per area
    ├── rounds/current.json      round Claude wrote for the page
    └── results/<round_id>.json  submitted rounds; latest.json = the last one
```

## `studyvault.json`

```json
{
  "version": 1,
  "subject": "Software Construction",
  "language": "en",
  "exam": {"date": "2027-01-20", "duration_min": 90, "format": "single choice + Kprim + open answers"},
  "scope": "The HS26 session slides define the scope. Old exams are style references only.",
  "areas": [
    {"slug": "objects-and-classes", "title": "Objects and Classes", "folder": "01-Objects-and-Classes"},
    {"slug": "vm", "title": "Virtual Machine", "folder": "10-VM", "excluded": true}
  ],
  "extra_folders": ["00-Dashboard", "11-Past-Exams"]
}
```

| Key | Rule |
|---|---|
| `version` | `1` |
| `areas[].slug` | lowercase, digits, dashes; unique; names `concepts/<slug>.md` and `question-bank/<slug>.json` |
| `areas[].title` | display name used on the dashboard and the page |
| `areas[].folder` | `NN-Name` folder with that area's notes and practice file |
| `areas[].excluded` | optional: tracked but not on the exam; /study skips it, weakest/strongest ignore it |
| `extra_folders` | every other `NN-` folder (dashboard, past exams) |
| `exam`, `scope` | optional, free text; /study reads them to plan and to stay in scope |

Adding an area = add it to `areas`, create the folder, then `studyvault.py migrate VAULT --write` (it keeps
the manifest and creates the missing tracker and bank files). Never rename a slug that has tracking data.

## `concepts/<slug>.md`

```markdown
# Persistence — Concept Tracker

| Concept | Attempts | Correct | Last Tested | Status |
|---------|----------|---------|-------------|--------|
| naive save aliasing | 2 | 0 | 2026-11-24 | 🔴 |
| dispatch by type name | 1 | 1 | 2026-11-24 | 🟢 |

### Error Notes

**naive save aliasing**
- Confusion: what the user mixed up
- Key point: the correct idea
```

- Status is the result of the **last** attempt: 🟢 right, 🔴 wrong. ⚪ means planned but not tested yet:
  `| name | 0 | 0 | - | ⚪ |` (a vault may list every concept of an area up front; /study uses them for
  diagnostics, and the first answer turns the row 🟢 or 🔴).
- Concept names never contain `|`; use `∣` (U+2223), which `record` substitutes automatically.
- Every 🔴 row has an error note. Notes stay when the concept turns 🟢 (learning history); a new miss
  replaces the note.
- Only `studyvault.py record` writes these files.

## Language

`language` in the manifest (`en` or `de`) sets the structure words: tracker title, table header, error-notes
heading and bullet labels, and the dashboard's headings and levels. German trackers use
`| Konzept | Versuche | Richtig | Zuletzt getestet | Status |`, `### Fehlernotizen`, `- Verwechslung:` and
`- Kernpunkt:`. Parsing accepts both languages. Other languages fall back to English structure words.

## Migrating an older vault

`studyvault.py migrate VAULT` (dry run) / `--write`:
- infers the manifest from `NN-Name` or `NN Name` folders, the old dashboard and the tracker files
- rewrites trackers in the canonical format under their slug (`01-Computer-Networks.md` → `computer-networks.md`),
  keeping every number, note and any text above the table; `\|` and `|` in names become `∣`; `—` dates of
  untested rows become `-`
- pairs error notes whose title drifted from the row name (by similarity) and adds a marked placeholder note
  only for a 🔴 row that has none
- moves old dashboards (`Lern-Dashboard.md`, `00-Dashboard/Learning Dashboard.md`, a hand-written one) and old
  tracker files to `StudyVault/.migrated-<date>/`, and rewrites links to them
- is idempotent: running it again changes nothing

## `Learning Dashboard.md`

Generated. One row per manifest area, in manifest order: correct, wrong, rate, level, `[[concepts/<slug>]]`;
then a total row and Stats (total questions, cumulative rate, unresolved and resolved concepts, weakest and
strongest area). Levels: 🟥 Weak 0–39% · 🟨 Fair 40–69% · 🟩 Good 70–89% · 🟦 Mastered 90–100% · ⬜ Unmeasured.
Anything you write in it is overwritten by the next `recompute`; put notes in `00-Dashboard/` instead.

## Question bank, rounds, results

See `app.md`. A bank file is `{"area": "<slug>", "title": "...", "questions": [...]}`; every bank question
except `open` needs `answer` (its shape depends on the type, see `app.md`), and every question should have a
`concept`.

## What `studyvault.py check` enforces

Errors (exit code 1):
- manifest missing or invalid; duplicate or malformed slugs; an area folder that doesn't exist
- a concept tracker or bank file without a manifest area, or an area without a tracker
- malformed tracker rows, duplicate concepts, `correct > attempts`, bad dates, 🔴 without an error note,
  ⚪ rows that aren't `0 | 0 | -`
- invalid bank JSON, wrong `area` key, duplicate ids, invalid questions, a question without `answer` (except open)
- invalid results JSON or `tasks.json`
- `Learning Dashboard.md` missing or different from what `recompute` would write

Warnings:
- `NN-` folders missing from the manifest; area without a practice file; missing bank file
- bank questions without a `concept`; results not recorded yet; problems in `rounds/current.json`
- broken `[[wiki links]]` (code and dot folders are ignored; vault-root paths like `HS26/X/StudyVault/…` resolve)
- error notes without a table row
