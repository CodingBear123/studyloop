# Crunch Time

Local quiz and progress app for `/tutor` StudyVaults. One server covers every `StudyVault` under `obsidian_local`.

```bash
python3 ~/Documents/obsidian_notes/obsidian_local/_tutor-quiz/server.py
```

Then open http://127.0.0.1:8765/ and pick a subject at the top (the picker only shows up when there is more than one vault).

- **Quiz**: take the round `/tutor` wrote (`?round=current`), or a 4-question practice round from the bank. The **To do** list sits next to it (saved in `StudyVault/tasks.json`).
- **Progress**: rate per area and the open (🔴) concepts with their error notes, both read from `concepts/*.md`, plus a streak grid of questions answered per day.
- **Question bank**: add or edit questions per area, stored in `question-bank/{area}.json`.

## How tracking works

| Round | Who grades | Who updates `concepts/*.md` and `Learning Dashboard.md` |
|---|---|---|
| Practice round from the bank | the page (the answer key is in the bank) | **the server**, on submit (`results/*.json` gets `"tracked": true`) |
| Round written by Claude | Claude, after you say "done" | Claude (`/tutor` Phase 6) |

Open-answer questions are never auto-graded; Claude grades them.

Rebuild a dashboard by hand (e.g. after Claude edits concept files):

```bash
python3 ~/Documents/obsidian_notes/obsidian_local/_tutor-quiz/server.py --recompute ~/Documents/obsidian_notes/obsidian_local/HS26/SoCo/StudyVault
```

Restart the server after creating a new StudyVault. Full data format: `~/.claude/skills/tutor/references/quiz-frontend.md`. Visual system: `DESIGN.md`.
