# Studyloop

Turn your course material into study notes, then let Claude quiz you on them until the gaps are gone.

Studyloop is two commands for [Claude Code](https://claude.com/claude-code) plus a small study page that runs
on your own computer:

- **`/studyloop-setup`** reads your slides, PDFs and old exams and writes a **StudyVault**: a folder of clear
  notes per topic, an exam blueprint, practice questions and a question bank.
- **`/studyloop`** quizzes you from that vault, grades your answers, and remembers every concept you got wrong,
  so the next round goes after exactly those.
- **The study page** is where you answer, read your notes, see your progress and practise on your own, with
  or without Claude.

Everything stays on your machine as plain Markdown and JSON. The vault also opens in
[Obsidian](https://obsidian.md) if you use it.

> Studyloop is a work in progress. It is used every day for real exams, but things still change often.

---

## Contents

- [How it works](#how-it-works)
- [Install](#install)
- [Commands in Claude Code](#commands-in-claude-code)
  - [`/studyloop-setup`: build your notes](#studyloop-setup-build-your-notes)
  - [`/studyloop`: get quizzed](#studyloop-get-quizzed)
  - [What you can say](#what-you-can-say)
- [The study page](#the-study-page)
- [The `studyloop` command](#the-studyloop-command)
- [Updating](#updating)
- [Your data](#your-data)
- [Working on Studyloop](#working-on-studyloop)

---

## How it works

```
   your course folder              StudyVault/                     study page
                                                               127.0.0.1:8765
 +------------------+         +------------------+         +--------------------+
 | slides, PDFs,    | /study- | notes per area   |  reads  | Quiz               |
 | old exams,       |-------->| question bank    |<------->| Notes              |
 | your own notes   |  vault  | concept trackers |  saves  | Progress           |
 +------------------+         +------------------+         | Question bank      |
                                       ^                   +--------------------+
                                       |  /studyloop: writes rounds,      |
                                       |  grades, records             | "Ask Claude",
                              +------------------+                    | "Check with Claude"
                              |   Claude Code    |<-------------------+
                              +------------------+
```

The loop has three steps:

1. **Build once.** `/studyloop-setup` turns your material into a StudyVault. The rule it follows: *your course
   material decides what is in scope; old exams only show how it gets asked.*
2. **Quiz.** `/studyloop` picks what to practise from your progress, writes a round of questions, and opens it on
   the study page. Code keeps its indentation there and formulas render properly.
3. **Track.** Claude grades the round, explains every miss with a link to the note section to reread, and
   records each concept as `open` (got it wrong) or `solved` (got it right since). The next round goes after the
   open ones. Repeat until nothing is open.

---

## Install

You need [Claude Code](https://claude.com/claude-code) and a Claude account. The installer checks everything
else (Python 3.9+, and `pdftotext` for reading PDF slides) and offers to set it up.

**Mac**

1. On GitHub, click **Code → Download ZIP** and open the ZIP (or `git clone` the repository).
2. In the unpacked folder, right-click **Install on Mac.command** → **Open** → **Open**. Right-click is only
   needed the first time: macOS doesn't open downloaded scripts on a plain double-click.
3. Follow the window. If Python is missing, macOS offers to install it; run step 2 again afterwards.

**Windows**

1. On GitHub, click **Code → Download ZIP**, then right-click it → **Extract All**.
2. In the extracted folder, double-click **Install on Windows.cmd**. If Windows shows "Windows protected your
   PC", click **More info → Run anyway**.
3. Follow the window. It installs Python with winget if it's missing.

**Terminal, one line** (only while the repository is public)

```bash
curl -fsSL https://raw.githubusercontent.com/CodingBear123/studyloop/main/install.sh | sh
```

```powershell
irm https://raw.githubusercontent.com/CodingBear123/studyloop/main/install.ps1 | iex
```

**What the installer sets up**

| | |
|---|---|
| `/studyloop` and `/studyloop-setup` | in `~/.claude/skills` (a link on Mac and Linux, a copy on Windows) |
| **Studyloop** app | Mac: `~/Applications`, Spotlight, optional Desktop shortcut. Windows: Desktop and Start menu. Linux: app menu |
| `studyloop` command | Mac and Linux, in `~/.local/bin` |
| Start at login (optional) | the study page is already running when you open it |

It installs with git when git is available, so the page can update itself later. Run the installer again at
any time; it updates what is there.

<details>
<summary>Other ways to install (other agents, development)</summary>

```bash
npx skills add CodingBear123/studyloop                  # any agent that reads Agent Skills
claude plugin marketplace add CodingBear123/studyloop && claude plugin install studyloop@studyloop
ln -s "$PWD/skills/studyloop" ~/.claude/skills/studyloop        # from a clone: your edits go live
ln -s "$PWD/skills/studyloop-setup" ~/.claude/skills/studyloop-setup
```

</details>

---

## Commands in Claude Code

Open Claude Code **in your course folder** (the folder with your slides, or the one that holds your
`StudyVault/`), then type one of these:

| Command | Use it to | You get |
|---|---|---|
| `/studyloop-setup` | turn course material into notes, add new material, repair a vault | a `StudyVault/` folder |
| `/studyloop` | get quizzed, drill weak spots, follow a study plan, check progress | a round on the study page, graded and tracked |

You can type the command alone and Claude asks what you want, or add what you want right after it:
`/studyloop drill my weak areas`. Plain sentences work too ("quiz me on closures"), but the command is the
surest way to start the right skill. Claude answers in the language you write in.

### `/studyloop-setup`: build your notes

Run it in the folder with your course files. It picks one of four modes from what it finds:

| Mode | When | Example |
|---|---|---|
| **Create** | there is no `StudyVault/` yet | `/studyloop-setup` |
| **Update** | you have new material | `/studyloop-setup add the slides from session 12` |
| **Migrate** | an older vault from `/tutor-setup` or made by hand | `/studyloop-setup convert my old vault` |
| **Check** | something looks off | `/studyloop-setup check my vault` |

What happens on **Create**, and where Claude stops to ask you:

1. **Sources.** Claude lists the files it found and asks which are course material and which are old
   exams. It reads what each file really covers (file names often lie) and shows you that map.
2. **Scope and exam.** It agrees the scope with you and, if there are old exams, analyses them: question
   types, points, which topics come up every year. That becomes `00-Dashboard/Exam Blueprint.md`. It asks for
   the exam date and format if you know them.
3. **Areas.** It proposes 6–12 topic areas in course order and waits for your yes.
4. **Notes.** One folder per area with 2–5 notes each: tables, worked examples, real code, warnings for every
   exception to a rule, and an "Exam Patterns" section in each note.
5. **Practice and bank.** A practice file per area and a seeded question bank, so you can practise on the
   page right away.
6. **Check.** It validates the vault and reports.

Claude only reads files inside the current folder, and it never deletes or rewrites your tracking data.

### `/studyloop`: get quizzed

Run it in the folder that holds your `StudyVault/` (or a folder above it). Claude reads your progress and
suggests a session, or you name one:

| Session | What Claude does | Example |
|---|---|---|
| **Diagnostic** | one question per untested area or concept, to find where you stand | `/studyloop` (the default on a new vault) |
| **Drill** | your open concepts again, rephrased in new contexts | `/studyloop drill my weak spots` |
| **Area** | four questions on one topic | `/studyloop quiz me on persistence` |
| **Exam simulation** | a mixed round in the shape of the real exam, open questions included | `/studyloop exam simulation` |
| **Study plan** | splits your time into ~20-minute blocks weighted by exam weight × weakness, then runs them | `/studyloop I have 2 hours` |
| **Progress** | a report from your trackers, no questions | `/studyloop how am I doing?` |

**One round, step by step**

1. Claude writes the round (usually 4 questions: single choice, multiple choice, true/false grids, numbers,
   open answers) and gives you a link to the study page, or opens it.
2. You answer on the page and click **Submit answers**.
3. You type **`done`** in Claude Code.
4. Claude grades the round: a table of right and wrong, then a short explanation for each miss with the note
   to reread.
5. Claude records the result. Open concepts you now got right become `solved`; solved ones you get wrong
   again go back to `open`.
6. Claude offers to save good questions to the question bank, so you can practise them later without Claude.

If you submitted a round and never said `done`, the next `/studyloop` grades it first.

### What you can say

You don't need exact wording. Some things that work:

| You say | Claude |
|---|---|
| `/studyloop-setup` | builds a vault from the files in this folder |
| `/studyloop-setup add lecture 9 and the 2024 exam` | updates the vault with the new material |
| `/studyloop-setup is my vault ok?` | checks it and fixes broken data |
| `/studyloop` | suggests a session from your progress |
| `/studyloop test me on recursion, hard questions` | one area, harder round |
| `/studyloop only open questions` | a round of written answers |
| `/studyloop exam in 3 days, make a plan` | a study plan you work through block by block |
| `done` | grades the round you just submitted |
| `explain question 3 again` | goes deeper on one answer |
| `/studyloop how am I doing?` | your rates per area and what is still open |

---

## The study page

Open the **Studyloop** app (or run `studyloop`). The first time it asks for the folder that holds your
StudyVault and remembers it. Everything below works **without** Claude Code open, except the buttons that
ask Claude.

| Tab | What's there |
|---|---|
| **Quiz** | the round Claude wrote, practice rounds from the question bank (pick areas and question types), your to-do list |
| **Notes** | every note in the vault, readable and searchable, with an **Ask Claude** box at the end of each note |
| **Progress** | overall rate, rate per area, open concepts with what you mixed up, a daily streak |
| **Question bank** | add, edit and delete bank questions per area |

**Who grades what**

| Round | Graded by | Recorded by |
|---|---|---|
| Written by Claude (`/studyloop`) | Claude, after you type `done` | Claude |
| Practice round from the bank | the page; open answers by you against the model answer, or by **Check with Claude** | the page |

After grading, every question links to the note section that covers it, and **Ask Claude** answers follow-up
questions about it. These buttons run a one-off Claude Code call in the background, so they need Claude Code
installed and signed in. The **Claude** picker in the header chooses the model (newest Sonnet, Opus, Haiku or
Fable, a specific version, or any `claude-...` model ID).

**Look.** One light mode and one dark mode, switched with the sun/moon button; until you pick one the page
follows your system. Your choice and model are saved in `~/.config/studyloop/prefs.json`.

**As an app.** The page opens in its own window, not a browser tab: the installed Studyloop app if you have
one, otherwise Chrome, Edge or Brave in app mode. To install it, open http://127.0.0.1:8765/ in Chrome or
Edge and choose **Install Studyloop** in the address bar; it then gets its own Dock or taskbar icon. If the
page isn't running, the window says so and tells you to run `studyloop`.

---

## The `studyloop` command

The Studyloop app runs this too.

| Command | What it does |
|---|---|
| `studyloop` | start the page if needed and open it |
| `studyloop ~/path/to/notes` | use this folder from now on |
| `studyloop --choose` | pick another folder |
| `studyloop --tab` | open in a normal browser tab instead of an app window |
| `studyloop --autostart on` | start the page in the background at login (`off`, `status`) |
| `studyloop --restart` | restart running pages so they load changed code |

On Windows, or without the command on your PATH, run the launcher with the same options:
`python3 skills/studyloop/app/launch.py` (Windows: `py skills\studyloop\app\launch.py`).

---

## Updating

When GitHub has a newer version, an **Update Studyloop** button appears in the page header (hover it to see
what changed). One click pulls the update, refreshes the skills, and restarts the page. Your vaults are never
touched. The page checks at most once an hour.

This needs a git checkout, which the installer makes when git is installed. If you changed Studyloop's own
files, the button says so instead of overwriting them. Without git, run the installer again.

---

## Your data

```
StudyVault/
  studyvault.json          areas, subject, scope, exam date
  Learning Dashboard.md    your rates per area (generated)
  00-Dashboard/            map of contents, Exam Blueprint, Quick Reference, Exam Traps
  01-…/ 02-…/              notes and one practice file per area
  concepts/<area>.md       concept tracker: every concept, attempts, open or solved, what you mixed up
  question-bank/           questions per area, plus rounds/ and results/
  tasks.json               study plan and to-do list
```

Read and edit the **notes** however you like, in Obsidian or any editor. Leave the **trackers, dashboard
and results** to Studyloop: every change to them goes through one script, so they never drift apart. If
something looks wrong, run `/studyloop-setup check my vault`, or by hand:

```bash
python3 skills/studyloop/app/studyvault.py check  path/to/StudyVault   # find problems
python3 skills/studyloop/app/studyvault.py status path/to/StudyVault   # summary as JSON
```

Full format: [studyvault-spec.md](skills/studyloop/references/studyvault-spec.md).

---

## Working on Studyloop

On Mac and Linux the installed skills are links into the folder you installed from, so edits to `SKILL.md`,
the references and `studyvault.py` count from the next `/studyloop`. On Windows they are copies: run
`install.ps1` again after editing.

| You changed | Then |
|---|---|
| `index.html` | reload the page |
| `server.py`, `notes.py`, `studyvault.py`, `updater.py` | `studyloop --restart` |

```bash
python3 -m unittest discover -s tests      # tests
```

Reference docs: [app.md](skills/studyloop/references/app.md) (page, round and bank formats, server API),
[quiz-rules.md](skills/studyloop/references/quiz-rules.md) (how questions are written),
[DESIGN.md](DESIGN.md), [PRODUCT.md](PRODUCT.md).

## Credits

The study workflow started from the `tutor` and `tutor-setup` skills in
[RoundTable02/tutor-skills](https://github.com/RoundTable02/tutor-skills).
