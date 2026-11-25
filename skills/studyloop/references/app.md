# The page, rounds, bank and results

`APP/server.py` (standard library Python, binds to 127.0.0.1:8765) serves `APP/index.html`. One server
covers every StudyVault under `--root`. Each vault is addressed by its id: the path from the root to the
folder that holds `StudyVault/` (e.g. `HS26/SoCo`).

```bash
python3 APP/server.py --root ~/notes            # every StudyVault under ~/notes
python3 APP/server.py --vault path/to/StudyVault # just this one
```

It finds vaults at startup, so restart it after creating one. Port taken → it's probably already running:
`curl -s http://127.0.0.1:8765/api/vaults`.

## Tabs

- **Quiz**: the round Claude wrote (`?round=current`), practice rounds from the bank, the To do list (`tasks.json`).
- **Notes**: every note of the vault rendered from its Markdown (headings, tables, callouts with folds, code,
  `[[wiki links]]`, `![[images]]`, `$math$` and `$$math$$` via KaTeX), with a filter and an "Open in Obsidian" link. Deep link:
  `?view=notes&note=<path in the vault>&h=<heading anchor>`.
- **Progress**: rate per area and the open concepts with their error notes, streak of answers per day.
- **Question bank**: add and edit questions per area (validated by `studyvault.py` before saving).

API (all take `?vault=<id>`): `GET /api/vaults`, `GET /api/areas`, `GET /api/progress`,
`GET|PUT /api/tasks`, `GET|PUT /api/bank/<area>`, `GET /api/round?id=current`,
`GET /api/round?area=a,b&n=4&types=single`, `POST /api/results`, `POST /api/grade-open`, `GET /api/notes`
(the note tree), `GET /api/note?path=`, `GET /api/asset?path=` (embedded images), `POST /api/note-ref`
(`{"area", "question"}` → the section that covers it), `POST /api/ask`. Without `?vault`: `GET|PUT /api/prefs`
(`{"theme", "model"}`; theme is `light`, `dark` or `system`, older `tide`/`garden` read as `light`; saved in
`~/.config/studyloop/prefs.json` or `STUDY_PREFS`, inlined into the page so the theme is right before first
paint), `GET /api/update` (`?check` skips the hourly cache: is GitHub
ahead of this git checkout), `POST /api/update` (`git pull --ff-only`, re-copy Windows skill copies, restart),
`POST /api/restart` (`launch.py --restart` after editing the app's Python files). Static: `/fonts/*.woff2`,
`/icons/*.png`, `/manifest.webmanifest` and `/sw.js` (the page is an installable app; the service worker caches
fonts and icons and shows a "Studyloop isn't running" page when the server is down).

Only the page itself may use the API: requests need `Host: 127.0.0.1:<port>` (or `localhost`), and POST/PUT
need `Content-Type: application/json` and no foreign `Origin`. Other websites in the browser get 403.

## Question

```json
{
  "id": "per-003",                 // bank only; unique in the file; letters, digits, - _
  "area": "persistence",           // manifest slug; required in rounds, implied in the bank
  "concept": "naive save aliasing",// tracker row name; hidden from the user until graded
  "type": "single",                // single | multi | kprim | numeric | open
  "lang": "python",                // highlight language
  "difficulty": "hard",            // easy | medium | hard
  "prompt": "What does `load(save(x))` return? Supports `inline`, **bold**, ```fences```.",
  "code": "a = [1]\nx = [a, a]",   // shown as a block, indentation kept exactly
  "options": ["...", "..."],       // single and multi, 2-8
  "options_code": true,            // render options as code
  "answer": 2,                     // the key, see below. Bank: required. Your rounds: OMIT
  "model_answer": "...",           // open only, bank
  "explanation": "...",            // shown after submit when the round reveals answers
  "source": "HS24 exam OA.3",
  "ref": "Persistence Format#Aliasing"  // optional: the note section that covers it (see below)
}
```

**Answer key per type.** `single`: option index (`2`). `multi`: list of the correct option indexes
(`[0, 2]`, at least one). `kprim`: `statements` (2–8 strings, usually 4) instead of `options`, and `answer` is one
true/false per statement (`[true, false, false, true]`). `numeric`: a number (`1024`, `7.71`), plus optional
`tolerance` (± absolute, default exact) and `unit` (`"CHF"`, `"%"`); the page accepts `1'024`, `1 024`, `7,7`,
`3/4`. `open`: no `answer`; the bank gives `model_answer`.

**Images.** `prompt`, `options`, `statements`, `explanation` and `model_answer` can embed an image from the
vault the Obsidian way: `![[diagram.png]]`, `![[diagram.png|Alt text]]` or `![[diagram.png|300]]` (width in
pixels). A vault path or just the file name works; the page loads it through `/api/asset` and fits it to the
card. `studyvault.py check` warns when an embedded image is not in the vault. Inside backticks and in `code`
it stays text.

**Note reference.** After grading, every question links to the note section that covers it ("Read: Note ›
Heading", opens in a side panel). `ref` names it as `Note title#Heading` or `folder/Note.md#Heading`. Without
`ref` the server picks the section of the question's area whose words match the concept, prompt and
explanation best (practice files and "Exam Patterns" sections count less). Set `ref` when the automatic pick
is wrong; `check` warns when a `ref` names no note. The bank editor shows the automatic pick.

## Round you write: `question-bank/rounds/current.json`

```json
{"id": "claude-20261124-1", "title": "Drill: Persistence", "reveal": false,
 "questions": [ {question}, {"bank_ref": {"area": "interpreter", "id": "int-001"}} ]}
```

- `id`: `claude-YYYYMMDD-N`. Overwrite the file each round.
- No `answer` in questions you write (the page would leak it). A `bank_ref` brings its stored answer along,
  so keep `reveal: false`.
- Run `studyvault.py validate-round VAULT` after writing it.

## Results: `question-bank/results/<round_id>.json` and `latest.json`

```json
{"round_id": "claude-20261124-1", "source": "claude", "submitted_at": "2026-11-24T15:02:11",
 "tracked": false,
 "answers": [
   {"n": 1, "id": null, "area": "persistence", "concept": "naive save aliasing", "type": "single",
    "choice": 1, "choice_letter": "B", "choice_text": "...", "answer": null, "correct": null},
   {"n": 2, "area": "java", "concept": "...", "type": "open", "text": "their answer", "correct": null}]}
```

Other types: `multi` gives `choices` (sorted indexes) and `choice_letters` (`"AC"`); `kprim` gives `tf` (one
`true`/`false`/`null` per statement, in the order shown) and `right` (how many match, bank rounds only);
`numeric` gives `text` (as typed) and `value` (parsed number or `null`). Every type but `open` has
`choice_text`, a readable summary. Options and statements are shuffled only in bank rounds, so in your rounds
indexes match your key.

- `source: "claude"`: you grade everything, then `studyvault.py record` with the `round_id`, which sets
  `"tracked": true`.
- `source: "bank"`: the user started it on the page. The page graded every answer with a key (all types but
  open), the server recorded
  them and set `"recorded": true` on each. Open answers with a bank `model_answer` can be graded on the page
  too (see below), which also sets `"recorded": true` plus `"graded_by": "self" | "claude"` and `"feedback"`.
  `"tracked": true` means nothing is left. Otherwise grade only the answered open questions without
  `"recorded"` and record those with the `round_id`.
- Fallback paste string: `STUDY round=<id> | 1=B | 2="free text" | 3=AC | 4=TFFT | 5="7,7"` (`-` = no answer;
  multi lists the letters, Kprim gives T/F per statement, numbers come quoted as typed).

## Bank practice rounds

The server picks questions at random, weights ones whose concept is open four times higher, prefers questions
seen less often, shuffles options and reveals answers after submit. A new error note from a practice round
uses the option the user picked as the confusion and the question's `explanation` as the key point, so give
bank questions a useful `explanation` and a `concept`.

## Open answers on the page

After a practice round is saved, each answered open question shows its model answer and three buttons:
**I had it** / **I missed it** (self-grading) and **Check with Claude**. All three call
`POST /api/grade-open {"round_id", "n", "mode": "self"|"claude", "correct"}`, which records the concept
(right or wrong, with an error note) and updates the results file. "Check with Claude" runs one headless
`claude -p` call (no tools, empty working folder, no saved session, model `sonnet`, override with
`STUDY_CLAUDE_MODEL`), which takes a few seconds; nothing runs in the background. The button only shows
when the server finds the `claude` command (or `STUDY_CLAUDE`). Rounds Claude wrote are still graded in the
chat: the page has no model answers for them.

## Asking Claude on the page

After grading, every question has **Ask Claude**, and every note in the Notes tab and the side panel ends
with an Ask box. Each message is one headless `claude -p` call like the check above (no tools, no files),
with the question, the user's answer, the answer key when the page has it, the note section and the thread
so far in the prompt. The **Claude** picker in the header sets the model for checks and questions:
the aliases (`sonnet`, `opus`, `haiku`, `fable`: newest of each), pinned versions (`claude-opus-4-8`, ...;
`STUDY_CLAUDE_MODELS=a,b,c` replaces the list), or any other `claude-...` ID typed in. The server passes only
those to `--model`; anything else falls back to `STUDY_CLAUDE_MODEL` (default `sonnet`). The choice is saved
with the theme (`/api/prefs`). Threads live in the page
only and are gone after a reload.
