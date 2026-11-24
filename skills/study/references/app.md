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
- **Progress**: rate per area and the 🔴 concepts with their error notes, streak of answers per day.
- **Question bank**: add and edit questions per area (validated by `studyvault.py` before saving).

API (all take `?vault=<id>`): `GET /api/vaults`, `GET /api/areas`, `GET /api/progress`,
`GET|PUT /api/tasks`, `GET|PUT /api/bank/<area>`, `GET /api/round?id=current`,
`GET /api/round?area=a,b&n=4&types=single`, `POST /api/results`.

## Question

```json
{
  "id": "per-003",                 // bank only; unique in the file; letters, digits, - _
  "area": "persistence",           // manifest slug; required in rounds, implied in the bank
  "concept": "naive save aliasing",// tracker row name; hidden from the user until graded
  "type": "single",                // "single" or "open"
  "lang": "python",                // highlight language
  "difficulty": "hard",            // easy | medium | hard
  "prompt": "What does `load(save(x))` return? Supports `inline`, **bold**, ```fences```.",
  "code": "a = [1]\nx = [a, a]",   // shown as a block, indentation kept exactly
  "options": ["...", "..."],       // single only, 2-8
  "options_code": true,            // render options as code
  "answer": 2,                     // single only: option index. Bank: required. Your rounds: OMIT
  "model_answer": "...",           // open only, bank
  "explanation": "...",            // shown after submit when the round reveals answers
  "source": "HS24 exam OA.3"
}
```

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

- `source: "claude"`: you grade everything, then `studyvault.py record` with the `round_id`, which sets
  `"tracked": true`.
- `source: "bank"`: the user started it on the page. The server graded the single-choice answers, recorded
  them and set `"recorded": true` on each. `"tracked": true` means nothing is left. Otherwise grade only the
  answered open questions and record those with the `round_id`.
- Fallback paste string: `STUDY round=<id> | 1=B | 2="free text" | 3=A | 4=-` (`-` = no answer).

## Bank practice rounds

The server picks questions at random, weights ones whose concept is 🔴 four times higher, prefers questions
seen less often, shuffles options and reveals answers after submit. A new error note from a practice round
uses the option the user picked as the confusion and the question's `explanation` as the key point, so give
bank questions a useful `explanation` and a `concept`.
