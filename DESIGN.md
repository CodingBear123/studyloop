---
name: Claude Study Tool
description: A neo-brutalist study desk of chunky printed blocks for quizzing and tracking progress.
colors:
  navy-ink: "#14213D"
  misty-base: "#EEF4F2"
  paper: "#F7FAF9"
  ocean-teal: "#2E6F87"
  teal-deep: "#24596D"
  soft-mint: "#9ED8CF"
  mint-soft: "#CDEBE5"
  apricot: "#F2A97E"
  slate-muted: "#4A5A72"
---

# Claude Study Tool: design notes

Carried over from the first (timer) version; the timer slab is gone, everything else keeps the same construction.

## World

A study desk built from chunky printed blocks. Every surface is a flat slab with a 3px navy-ink rule and a hard offset shadow (6px, 5px on phones) on a misty ground. Loud in construction, quiet in behaviour: buttons press down into their shadow, a ticked task gets slammed, and nothing moves while you read a question.

## Colour roles

- **Navy ink**: all text, rules and shadows. No pure black or white anywhere.
- **Misty base / paper**: page ground and blocks; paper (slightly lighter) for inputs, options and code.
- **Ocean teal**: hero blocks (Claude's round, the round score, the progress overview), the brand tile, level-3 streak cells, strong area bars. Carries misty-base text.
- **Soft mint**: on, selected tab, done task, the correct option, the "correct" verdict. **Mint soft**: selected option, inline code, light fills.
- **Apricot**: only the streak badge, streak underline, a perfect-round celebration, and error messages that need to shout.
- A wrong answer is never coloured red: it gets a dashed 4px border and an "✗ your answer" chip, so the right answer (mint) is what the eye lands on.

## Type

- **Archivo Black**: numerals only (score, stats, question numbers, option letters, streak cells). Never words, except the round title on the teal hero.
- **Space Grotesk** 500–700: everything else. Headlines 1.5rem/700.
- **Monospace** for code, tab size 4, highlighted with highlight.js's GitHub light theme on a paper background.

## Components

- **Block**: base slab, 3px rule, 6px shadow, padding clamp(1rem, 2.4vw, 1.75rem).
- **Button**: 3px rule, 4px shadow, lifts 2px on hover and sinks fully on press. Mint for the primary action.
- **Tabs**: one segmented block, the current tab filled mint.
- **Option**: a paper slab with a square letter tile. Selected = mint-soft with a teal tile; after grading, correct = mint with an ink tile and a "✓ correct" chip.
- **Area bar**: bordered track with a fill (teal ≥70%, mint 40–69%, mint-soft below), dashed track when untested.
- **Streak grid**: six weeks, cells levelled by questions answered (1+, 6+, 12+), apricot underline for the current streak, today outlined.

## Layout

Max width 1240px. Quiz home: practice blocks left, To do right (one column below 980px). Progress: teal overview, then areas left, open concepts + streak right.

## Don't

- Don't round corners or use soft shadows.
- Don't use apricot for anything that isn't a streak, a celebration or an error.
- Don't reflow or re-indent code.
