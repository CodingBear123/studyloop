# Claude Study Tool

Two agent skills and a local quiz page for studying from an Obsidian **StudyVault**.

| Command | What it does |
|---|---|
| `/study-vault` | Builds a StudyVault from your course material (slides, PDFs, old exams): notes per area, exam blueprint, practice files, a seeded question bank, empty trackers. Also updates a vault with new material, migrates an older `/tutor-setup` vault, and checks a vault for broken data. |
| `/study` | Quizzes you from the vault: diagnostic, drill weak areas, one area, exam simulation, or a timed study plan. Rounds open in the local page (code keeps its indentation), Claude grades them and records the result. Also answers "how am I doing". |

Both write vault data only through `skills/study/app/studyvault.py`, so the trackers, dashboard and question
bank never drift apart. `studyvault.py check` proves it.

## Install

Any agent that reads Agent Skills (Claude Code, Codex, Cursor, Gemini CLI, Copilot, OpenCode, …):

```bash
npx skills add CodingBear123/claude-study-tool
```

Install both skills: `/study-vault` uses the tool and format that ship inside `study`.

Claude Code plugin instead (commands then show up as `/claude-study-tool:study`):

```bash
claude plugin marketplace add CodingBear123/claude-study-tool
claude plugin install claude-study-tool@claude-study-tool
```

From a clone, for development (edits go live):

```bash
ln -s "$PWD/skills/study" ~/.claude/skills/study
ln -s "$PWD/skills/study-vault" ~/.claude/skills/study-vault
```

Needs Python 3.9+ (standard library only) and, for PDFs, `pdftotext` (poppler).

## The page

`/study` starts it for you. By hand:

```bash
python3 skills/study/app/server.py --root ~/path/to/notes
```

Open http://127.0.0.1:8765/. Tabs: **Quiz** (Claude's round, practice rounds from the bank, To do list),
**Progress** (rate per area, open concepts with error notes, daily streak), **Question bank** (editor).

| Round | Graded by | Recorded by |
|---|---|---|
| Written by Claude | Claude, after you say "done" | `studyvault.py record` |
| Practice round from the bank | the page | the server, on submit; open answers are left for Claude |

## The vault

```
StudyVault/
  studyvault.json        areas (slug, title, folder), subject, scope, exam
  Learning Dashboard.md  generated from concepts/
  00-Dashboard/          MOC, Exam Blueprint, Quick Reference, Exam Traps
  01-…/ 02-…/            notes + one practice file per area
  concepts/<slug>.md     concept tracker per area
  question-bank/<slug>.json, rounds/, results/
  tasks.json             study plan / to-do list
```

Full format: [skills/study/references/studyvault-spec.md](skills/study/references/studyvault-spec.md).

```bash
python3 skills/study/app/studyvault.py check   path/to/StudyVault   # validate everything
python3 skills/study/app/studyvault.py status  path/to/StudyVault   # summary JSON
python3 skills/study/app/studyvault.py migrate path/to/StudyVault --write   # older /tutor vault
```

## Tests

```bash
python3 -m unittest discover -s tests
```

## Credits

The study workflow started from the `tutor` and `tutor-setup` skills in
[RoundTable02/tutor-skills](https://github.com/RoundTable02/tutor-skills).
Design notes: [DESIGN.md](DESIGN.md), [PRODUCT.md](PRODUCT.md).
