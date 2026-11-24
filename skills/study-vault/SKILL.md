---
name: study-vault
description: >
  Build or update an Obsidian StudyVault from course material (lecture slides, PDFs, notes, old exams)
  for studyloop. Use when the user wants to turn course files into study notes, add new
  lecture material to an existing vault, convert an older /tutor-setup vault, or check a vault for
  broken data. Triggers: "/study-vault", "make a study vault", "set up my notes for studying",
  "add session 12 to my vault". Quizzing is /study.
---

# /study-vault

Turn course material into a StudyVault that `/study` can quiz from: notes per area, an exam blueprint, practice
files, a seeded question bank and empty trackers, all registered in `studyvault.json`.

Needs the `study` skill installed next to this one: `TOOL` below means `../study/app/studyvault.py`
(relative to this file) and the vault format is `../study/references/studyvault-spec.md`. Read the spec first.

## Pick the mode

| Mode | When |
|---|---|
| **Create** | no `StudyVault/` yet |
| **Update** | a vault exists and there is new material (a new session, a new old exam) |
| **Migrate** | a vault without `studyvault.json` (made by /tutor-setup or by hand) |
| **Check** | "is my vault ok?" — run `TOOL check VAULT`, fix the errors, report |

Say which mode you picked and why in one line, then go.

**Boundary**: read sources only inside the current folder. If the user points elsewhere, ask them to copy the
files in. Never delete or rewrite tracking data (`concepts/`, `question-bank/results/`, `tasks.json`).

## Create

### 1. Sources

1. List candidate files (`pdf`, `pptx`, `md`, `txt`, `html`, `epub`; skip `.git`, `node_modules`, `StudyVault`).
   Show the list and ask which are course material and which are old exams.
2. Extract text. PDF: `pdftotext -layout file.pdf out.txt` (install poppler if missing), then read the `.txt`.
   Never read PDFs as images when text extraction works. Scanned PDFs: say so and ask how to proceed.
3. **Map what each file really covers**: read the title page, the outline and a few pages from the middle and
   end. File names lie (lecture 07 may be chapter 5). Build `file → topics → pages` and show it to the user.

### 2. Scope and exam shape

1. Decide the scope with the user and write it down. Default: **the course material defines the scope; old
   exams show how in-scope topics are asked**. Topics that only appear in old exams are out unless the user says
   otherwise.
2. If there are old exams, analyse them: question types, points, which topics come up, repeats across years.
   This becomes `00-Dashboard/Exam Blueprint.md` (template in `references/templates.md`).
3. Ask for exam date, length and format if the user knows them (they go into the manifest's `exam`).

### 3. Areas

Group the topics into 6–12 areas that follow the course order. Each area gets a folder `NN-Title-In-Words`
and a slug (the folder name without the number, lowercase). Show the area list and get a yes, then:

```bash
python3 TOOL init VAULT --subject "Software Construction" --scope "..." \
  --area "01-Objects-and-Classes=Objects and Classes" --area "02-Testing=Testing" ...
```

This writes `studyvault.json`, the folders, empty trackers, empty banks and the dashboard. Add `exam` and
extra folders (e.g. `11-Past-Exams`) to the manifest by hand afterwards. Pass `--language de` for German
material (German structure words in trackers and dashboard).

Optional: list each area's key concepts in its tracker as untested rows (`| name | 0 | 0 | - | untested |`), so
`/study` can run diagnostics concept by concept. This is the only time a tracker is written by hand; run
`check` afterwards.

### 4. Notes (per area, in its folder)

Follow `references/templates.md`:
- 2–5 concept notes per area, 3–5 related ideas per note. Frontmatter: `source`, `keywords` (English).
  `source` must match the verified mapping from step 1; write `source: not in the material` if it isn't there.
- Every topic in the material gets covered, even ones mentioned briefly. If the material lists "three kinds
  of X", each kind gets its own section.
- Tables over prose, a worked example for every mechanism, real code for code subjects, ASCII diagrams for
  flows, and a `> [!warning]` for every exception to a simple rule.
- `## Exam Patterns` (how this gets asked, from the blueprint) and `## Related Notes` in every note.

### 5. Practice and question bank

- One `NN Practice - <Title>.md` per area folder, 8+ questions, answers in `> [!answer]- Answer` folds,
  tagged `[recall]` / `[application]` / `[analysis]` (≥60% recall, ≥20% application, ≥2 analysis).
  Use old exam questions where they fit, with their source.
- Seed `question-bank/<slug>.json` with 6–10 questions per area in the format of `../study/references/app.md`:
  every question has `id` (`<prefix>-001`), `concept`, `type`, `difficulty`, `explanation`; use the types the old
  exams use (`single`, `multi`, `kprim`, `numeric`, `open`, see `quiz-rules.md`); every type but open has
  `answer`, open has `model_answer`; give `ref` (`"Note title#Heading"`) for the section that answers it.
  Follow `../study/references/quiz-rules.md`. These power the page's
  practice rounds, so they must be correct: double-check every answer key, and run code you put in questions
  when you can.

### 6. Dashboard folder

`00-Dashboard/`: `MOC - <Subject>.md`, `Exam Blueprint.md` (if there are exams), `Quick Reference.md`,
`Exam Traps.md`. Templates in `references/templates.md`. Old exams go in their own extra folder, one note per
exam with the questions, the answers, and links to the notes that cover each question.

### 7. Links and check

1. Link everything: MOC → every note; Quick Reference and Exam Traps → concept notes; practice ↔ notes;
   siblings ↔ siblings.
2. Run `python3 TOOL recompute VAULT` and `python3 TOOL check VAULT`. Fix every error and every broken link.
3. Go through `references/checklist.md`. Then report: areas, note and question counts, what is out of scope,
   and "run `/study` to start".

## Update

1. Map the new material (Create step 1) and decide which areas it belongs to, or whether it's a new area.
2. New area: add it to `areas` in `studyvault.json`, create its folder, run `TOOL migrate VAULT --write`
   (keeps the manifest, creates the tracker and bank).
3. Add or extend notes, practice questions and bank questions. Update the MOC, Quick Reference, Exam Traps
   and the blueprint if the scope changed.
4. Never rename a slug or touch `concepts/` by hand. Finish with `TOOL check VAULT`.

## Migrate

1. `python3 TOOL migrate VAULT` prints the manifest it would write, inferred from the `NN-` folders, the old
   dashboard and the tracker files. Check it with the user: titles, which folders are areas, the subject name,
   the scope (copy it from the blueprint if there is one).
2. `python3 TOOL migrate VAULT --write`, then fill in `subject`, `scope`, `exam` in the manifest.
3. `python3 TOOL check VAULT`; fix errors. Tracking numbers must not change: compare the totals of the old
   dashboard (now in `.migrated-<date>/`) with `TOOL status VAULT`, area by area. Report paired notes and any
   placeholder notes to the user. Old dashboard totals can themselves be wrong; trust the per-area sums.
4. Bank questions without a `concept` will show as warnings: add concepts so practice rounds can track them.

## Language

Notes in the language of the material (or what the user asks for). File names, folder names, JSON keys,
tags and frontmatter keys in English.
