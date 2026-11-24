# Studyloop

Two agent skills and a local quiz page for studying from a **StudyVault**, a folder of Markdown notes that
also opens as an Obsidian vault.

| Command | What it does |
|---|---|
| `/study-vault` | Builds a StudyVault from your course material (slides, PDFs, old exams): notes per area, exam blueprint, practice files, a seeded question bank, empty trackers. Also updates a vault with new material, migrates an older `/tutor-setup` vault, and checks a vault for broken data. |
| `/study` | Quizzes you from the vault: diagnostic, drill weak areas, one area, exam simulation, or a timed study plan. Rounds open in the local page (code keeps its indentation), Claude grades them and records the result. Also answers "how am I doing". |

Both write vault data only through `skills/study/app/studyvault.py`, so the trackers, dashboard and question
bank never drift apart. `studyvault.py check` proves it.

## How it works

```
  Course material                 StudyVault/                        Study page
                                                                  (local website)
+------------------+         +--------------------+         +--------------------------+
| slides, PDFs,    | /study- | notes per area,    | reads   | Quiz: answer rounds      |
| old exams,       |-------->| question bank,     |<------->| Notes: read, Ask Claude  |
| your notes       |  vault  | concept trackers,  | saves   | Progress                 |
|                  |         | rounds, results    |         | Question bank: edit      |
+------------------+         +--------------------+         +--------------------------+
                                        ^                                 |
                                        | /study: writes                  | checks open
                                        | rounds, grades,                 | answers,
                                        | records                         | Ask Claude
                             +--------------------+                       |
                             |    Claude Code     |<----------------------+
                             +--------------------+
```

1. **Build the vault.** In Claude Code, open your course folder and type `/study-vault`. Claude reads your
   slides, PDFs and old exams and writes a `StudyVault/`: one folder of notes per topic area, an exam blueprint
   (what the exam asks and how), practice questions, a question bank and an empty concept tracker per area.
   Old exams decide how you get asked, not what: the scope is what your course material covers.
2. **Study.** Type `/study`. Claude picks a session from your progress (diagnostic, drill your weak spots,
   one area, exam simulation, or a timed plan) and writes a round. You answer it on the **study page**: a small
   website that runs only on your computer (`http://127.0.0.1:8765`) and reads and saves the vault directly.
   Code keeps its indentation there and formulas render. Open it any time with the Studyloop app, also
   without Claude: practice rounds from the question bank, your notes, your progress.
3. **Track.** Claude grades the round, explains every miss with a link to the note section to reread, and
   records each answer in the concept tracker: 🔴 concepts you got wrong, 🟢 once you get them right. The next
   round targets the 🔴 ones. Practice rounds you start on the page are graded by the page and recorded the
   same way; for open answers it can ask Claude for a check, and every question and note has an "Ask Claude"
   button. (The page calls Claude Code in the background for these, so they need it installed and signed in.)

The vault is plain Markdown, so you can also read and edit it in [Obsidian](https://obsidian.md) or any editor.

## Install

You need [Claude Code](https://claude.com/claude-code) (the installer offers to set it up) and a Claude
account. Everything else the installer checks and sets up for you.

[Obsidian](https://obsidian.md) is optional. The vault is ordinary Markdown, and the study page shows the notes
itself. If you like Obsidian, open the folder that contains `StudyVault/` as a vault there.

**Mac**

1. On GitHub, click **Code → Download ZIP** and open the ZIP (or `git clone` the repository).
2. In the unpacked folder, right-click **Install on Mac.command** → **Open** → **Open**. (Right-click only the
   first time: macOS doesn't open downloaded scripts on a plain double-click.)
3. Follow the window. If Python is missing, macOS offers to install it; afterwards run step 2 again.

**Windows**

1. On GitHub, click **Code → Download ZIP**, right-click it → **Extract All**.
2. In the extracted folder, double-click **Install on Windows.cmd**. If Windows shows "Windows protected your
   PC", click **More info → Run anyway**.
3. Follow the window. It installs Python with winget when it's missing.

**Terminal, one line** (works only while the repository is public):

```bash
curl -fsSL https://raw.githubusercontent.com/CodingBear123/studyloop/main/install.sh | sh
```

```powershell
irm https://raw.githubusercontent.com/CodingBear123/studyloop/main/install.ps1 | iex
```

The installer puts `/study` and `/study-vault` into `~/.claude/skills` (a link on Mac/Linux, a copy on
Windows), adds a **Studyloop** app (Mac: `~/Applications`, Spotlight, optional Desktop shortcut; Windows:
Desktop and Start menu; Linux: app menu) and a `studyloop` terminal command, and offers `pdftotext` for
reading PDF slides. It installs with git when git is there, so the page can update itself (see
[Updating](#updating)); otherwise run it again to update. A copy installed under the old name (Claude Study)
is moved over and the old app and command are removed.

Other ways, for agents besides Claude Code or for development:

```bash
npx skills add CodingBear123/studyloop                  # any agent that reads Agent Skills
claude plugin marketplace add CodingBear123/studyloop && claude plugin install studyloop@studyloop
ln -s "$PWD/skills/study" ~/.claude/skills/study        # from a clone: edits go live
ln -s "$PWD/skills/study-vault" ~/.claude/skills/study-vault
```

Needs Python 3.9+ (standard library only).

## Use it

1. Open Claude Code in the folder with your course material and type `/study-vault`. It builds a
   `StudyVault` folder with your notes.
2. To study, type `/study`, or open the **Studyloop** app. The first time, the app asks for the folder
   that holds your StudyVault and remembers it (pick another one with `studyloop --choose`).

## The page

`/study` and the Studyloop app start it for you. By hand:

```bash
python3 skills/study/app/launch.py                       # what the app runs: start if needed, open the browser
python3 skills/study/app/server.py --root ~/path/to/notes  # just the server
```

Open http://127.0.0.1:8765/. Tabs: **Quiz** (Claude's round, practice rounds from the bank, To do list),
**Notes** (the vault's notes, readable on the page), **Progress** (rate per area, open concepts with error
notes, daily streak), **Question bank** (editor).

After grading, each question links to the note section that covers it, and **Ask Claude** answers follow-up
questions about it (also at the end of every note). Checks and questions are one-off `claude -p` calls
with no tools; the **Claude** picker in the header chooses the model: the newest Sonnet, Opus, Haiku or
Fable, a specific version such as Opus 4.8, or any other `claude-...` model ID.

| Round | Graded by | Recorded by |
|---|---|---|
| Written by Claude | Claude, after you say "done" | `studyvault.py record` |
| Practice round from the bank | the page; open answers by you (against the model answer) or by "Check with Claude" | the server |

Themes: Tide (default), Dark Lab and Soft Garden, switched from the swatches in the header. The theme and the
model are saved in `~/.config/studyloop/prefs.json` (override with `STUDY_PREFS`), so they stay the
same on every address and port the page is opened from. Dark Lab and Soft Garden load their fonts from Google Fonts.

## Updating

When GitHub has a newer version, an **Update Studyloop** button shows up in the page header (hover it to see
what changed). It runs `git pull --ff-only` in the install folder, copies the skills again on Windows, and
restarts the page, which reloads itself. Your vaults aren't touched. The page checks at most once an hour.

It needs a git checkout (what the installers make when git is installed). If you changed Studyloop's own
files, the button says so instead of overwriting them: commit or stash first. Without git, run the
installer again.

## Working on Studyloop

No reinstall needed. On Mac and Linux `~/.claude/skills/study` and `study-vault` are links into the folder
you installed from, so edits to `SKILL.md`, the references and `studyvault.py` count from the next `/study`.
The page is a running server, so after changing `server.py`, `notes.py`, `studyvault.py` or `updater.py`:

```bash
studyloop --restart      # or: python3 skills/study/app/launch.py --restart
```

That restarts every open study page on its own port, then opens it. A plain reload is enough for
`index.html`. On Windows the skills are copies: run `install.ps1` from your clone again after editing them.

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
