---
name: study
description: >
  Quiz and track study progress in an Obsidian StudyVault (claude-study-tool). Use when the user
  wants to be quizzed or tested, study or review a topic, drill weak areas, run an exam simulation,
  follow a timed study plan ("I have 2 hours"), grade a round they took in the browser app, or check
  their progress. Triggers: "/study", "quiz me", "test me", "let's study", "drill", "how am I doing".
  Needs a vault made by /study-vault (or an older /tutor vault, which it migrates).
---

# /study

Quiz the user, find what they don't know at the **concept level**, and keep the StudyVault's tracking data
consistent. Questions are answered in a local browser page (code keeps its indentation there), and every
write to tracking data goes through one script.

`APP` below means this skill's `app/` folder (next to this file). Run its scripts with `python3`.

## Ground rules

- **Never edit `concepts/*.md`, `Learning Dashboard.md` or `results/*.json` by hand.** Use
  `APP/studyvault.py record` and `recompute`. That is what keeps the vault consistent.
- **Scope comes from the vault**: `studyvault.json` → `scope`, plus `00-Dashboard/Exam Blueprint.md` if it exists.
  Only ask about topics in the area notes. Old exams show *how* topics get asked, not *what* is in scope.
  Skip areas marked `"excluded": true` unless the user asks for them.
- Read `references/quiz-rules.md` before writing any question. Zero hints.
- Talk in the user's language. Files keep their English names and keys.
- Don't use AskUserQuestion for quiz questions (it strips indentation and hides the chat). Use it only
  for the session choice, and only when the choice is unclear from the user's message.

## 1. Find the vault

1. Look for `StudyVault/` under the current folder (`python3 APP/studyvault.py find .`). If there are several,
   pick the one the user named or ask. If there is none, tell them to run `/study-vault` and stop.
2. If it has no `studyvault.json`, it's an older vault: run `studyvault.py migrate VAULT`, show the inferred
   areas, and after a yes run it again with `--write`.
3. Run `studyvault.py status VAULT` and `studyvault.py check VAULT`. Fix errors before quizzing
   (usually `recompute`); mention warnings in one line.
4. If `status` lists `untracked_results`, the user took a round you haven't graded: go to step 6 for it first.

## 2. Pick the session

Build the choice from `status` (rates, 🔴 open concepts, unmeasured ⬜ areas). Skip the question if the
user already said what they want.

| Session | When | Round |
|---|---|---|
| **Diagnostic** | ⬜ areas or ⚪ untested concepts exist | 1 question per unmeasured area, or ⚪ concepts (use their exact names), easy/medium |
| **Drill** | 🟥/🟨 areas or 🔴 concepts | 🔴 concepts rephrased in new contexts, medium/hard |
| **Area** | user names a topic | 4 questions from that area |
| **Exam simulation** | user asks, or near the exam | mix in the shape of `Exam Blueprint.md` / `11-Past-Exams/`, open questions included |
| **Study plan** | "I have N hours" | see below |
| **Progress** | "how am I doing" | report from `status`, no round |

**Study plan**: split the time into blocks of about 20 minutes (one round, grading, a short review of the
notes behind every miss). Weight blocks by exam weight × weakness. Write the plan into `StudyVault/tasks.json`
(`{"tasks": [{"id", "text", "done"}]}`; the page shows it as the To do list), then run the blocks in order and
tick them off. Stop when the user says pause; the tasks stay for next time.

## 3. Write the round

1. Read the area notes in the area's `folder` (from the manifest) and, when drilling, the 🔴 rows and error
   notes from `status`.
2. Look at `question-bank/{area}.json`. Reuse at most 2 bank questions per round via `bank_ref`, preferring
   ones on 🔴 concepts.
3. Write the rest yourself: 4 questions per round by default, `single` (4 options) and `open` mixed. For code
   subjects prefer output prediction and debugging with real, indented code in the `code` field.
4. Every question gets `area` (a manifest slug) and `concept`. Reuse the exact concept name from the tracker
   when testing an existing concept, so its row updates instead of a duplicate appearing.
5. Save to `question-bank/rounds/current.json` **without `answer` fields** (keep the key in your context), then
   run `studyvault.py validate-round VAULT` and fix what it reports.

Format: `references/app.md`.

## 4. Show it

1. Start the page if it isn't running (`curl -s http://127.0.0.1:8765/api/vaults` fails):
   `python3 APP/server.py --root <folder that contains the vault(s)>` in the background. Restart it if the
   vault you need isn't in that list.
2. Send the user `http://127.0.0.1:8765/?vault=<id>&round=current` (`id` from `/api/vaults`, URL-encoded), or
   open it in a browser tool if you have one. Ask them to say **done** after submitting.
3. **No browser possible?** Ask in chat: code in fenced blocks with indentation, options lettered A–D, and
   the user answers on one line (`1A 2C 3"free text" 4B`).

## 5. Grade

1. Read `question-bank/results/latest.json` and check `round_id` matches your round. A pasted
   `STUDY round=<id> | 1=B | 2="text" | …` string works too.
2. Grade single-choice against your key and open answers against the notes. Partly right counts as wrong for
   tracking, but say what was right.
3. Show a table (question, correct answer, their answer, ✅/❌), then a short explanation for each miss, with
   code in fenced blocks and a `[[note]]` to reread.

Practice rounds the user starts from the page (`source: "bank"`) are graded by the server: answers with
`"recorded": true` are already tracked. Report them and only grade the open answers that are left.

## 6. Record

Write the graded answers to a temp file and record them in one call:

```bash
python3 APP/studyvault.py record VAULT /tmp/graded.json
```

```json
{"round_id": "claude-20261124-1",
 "answers": [
   {"area": "persistence", "concept": "naive save aliasing", "correct": false,
    "confusion": "what they mixed up, in one line", "key_point": "the correct idea, in one line"},
   {"area": "java", "concept": "checked exceptions", "correct": true}]}
```

It updates the concept rows (new row, 🔴→🟢 when right, 🟢→🔴 when wrong again, error notes), recomputes
`Learning Dashboard.md`, and marks the results file as tracked. Don't include answers that already have
`"recorded": true`. If it rejects the input, fix the JSON, don't hand-edit files.

Then offer to save the good questions from this round to the bank (`question-bank/{area}.json`, with `id`,
`answer`, `explanation`, `concept`), and do it on a yes. Run `check` once at the end of the session.

## References

- `references/quiz-rules.md`: question rules (zero hints, distractors, difficulty mix)
- `references/app.md`: round, bank and results JSON; the page; the server API
- `references/studyvault-spec.md`: the vault format and what `check` enforces
