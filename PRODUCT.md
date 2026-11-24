# Product

## Platform

Claude Study Tool: two agent skills (`/study`, `/study-vault`) plus a local web app. `skills/study/app/server.py` (Python standard library) serves `index.html` plus fonts; every read and write of vault data goes through `studyvault.py`. Binds to 127.0.0.1 only. highlight.js comes from cdnjs; without a network, code keeps its indentation, just without colours.

## Users

A university student cramming for exams with the `/study` skill, usually at a desk, sometimes on a phone, often several subjects in one evening.

## Product Purpose

Answer exam-style questions with real, correctly indented code, and see progress build up in the same StudyVault that `/study` quizzes from. Success: a round takes one click to start, the result lands in the vault right away, and weak concepts are obvious at a glance.

## Capabilities

- Quiz: Claude-written rounds and bank practice rounds (open concepts weighted 4×, unseen questions preferred).
- Automatic tracking for bank rounds: concept rows, error notes and the Learning Dashboard update on submit.
- Progress: per-area rate, open concepts with error notes, a daily streak of questions answered.
- To-do list per vault.
- Question bank editor with a live preview.

The Pomodoro timer from the first version was removed (2026-11-24): nobody used it.

## Brand Commitments

Neo-brutalist, see `DESIGN.md`: 3px navy-ink rules, hard offset shadows, misty base, mint for active and correct, ocean teal for hero blocks, apricot only for streaks and celebrations. Archivo Black for numbers only, Space Grotesk for everything else.

## Principles

1. One click from opening the page to answering a question.
2. Code is shown exactly as written: indentation is content.
3. Celebrate real progress only; streak history is never faked.
4. Everything works from the keyboard and reads at AA contrast.
