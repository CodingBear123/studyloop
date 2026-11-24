---
name: Crunch Time
description: A neo-brutalist study desk of chunky printed blocks; the Pomodoro timer is one teal slab you hit with a spacebar.
colors:
  navy-ink: "#14213D"
  misty-base: "#EEF4F2"
  ocean-teal: "#2E6F87"
  teal-deep: "#24596D"
  soft-mint: "#9ED8CF"
  mint-soft: "#CDEBE5"
  apricot: "#F2A97E"
  slate-muted: "#4A5A72"
typography:
  display:
    fontFamily: "Archivo Black, Space Grotesk, system-ui, sans-serif"
    fontSize: "clamp(4.5rem, 29cqi, 18rem)"
    fontWeight: 400
    lineHeight: 0.9
    letterSpacing: "0em"
  numeral:
    fontFamily: "Archivo Black, Space Grotesk, system-ui, sans-serif"
    fontSize: "1.35rem"
    fontWeight: 400
    lineHeight: 1
  headline:
    fontFamily: "Space Grotesk, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "1.5rem"
    fontWeight: 700
    lineHeight: 1.1
    letterSpacing: "-0.015em"
  title:
    fontFamily: "Space Grotesk, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "1.05rem"
    fontWeight: 600
    lineHeight: 1.3
  body:
    fontFamily: "Space Grotesk, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "1rem"
    fontWeight: 500
    lineHeight: 1.45
  label:
    fontFamily: "Space Grotesk, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "0.78rem"
    fontWeight: 700
    letterSpacing: "0.04em"
rounded:
  none: "0px"
spacing:
  gap: "clamp(1rem, 2.2vw, 1.75rem)"
  pad: "clamp(1rem, 2.4vw, 1.75rem)"
  list: "0.8rem"
  inline: "0.75rem"
components:
  block:
    backgroundColor: "{colors.misty-base}"
    textColor: "{colors.navy-ink}"
    rounded: "{rounded.none}"
    padding: "{spacing.pad}"
  timer-slab:
    backgroundColor: "{colors.ocean-teal}"
    textColor: "{colors.misty-base}"
    rounded: "{rounded.none}"
    padding: "{spacing.pad}"
  timer-slab-break:
    backgroundColor: "{colors.teal-deep}"
    textColor: "{colors.misty-base}"
  button:
    backgroundColor: "{colors.misty-base}"
    textColor: "{colors.navy-ink}"
    rounded: "{rounded.none}"
    padding: "0.6rem 1.15rem"
    height: "3rem"
  button-mint:
    backgroundColor: "{colors.soft-mint}"
    textColor: "{colors.navy-ink}"
    rounded: "{rounded.none}"
    padding: "0.6rem 1.15rem"
    height: "3rem"
  icon-button:
    backgroundColor: "{colors.misty-base}"
    textColor: "{colors.navy-ink}"
    rounded: "{rounded.none}"
    size: "2.75rem"
  icon-button-pressed:
    backgroundColor: "{colors.soft-mint}"
  mode-switch-active:
    backgroundColor: "{colors.soft-mint}"
    textColor: "{colors.navy-ink}"
    padding: "0.55rem 1rem"
    height: "2.75rem"
  mode-switch-hover:
    backgroundColor: "{colors.mint-soft}"
  chip:
    backgroundColor: "{colors.misty-base}"
    textColor: "{colors.navy-ink}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    padding: "0.05rem 0.45rem"
  task-row:
    backgroundColor: "{colors.misty-base}"
    textColor: "{colors.navy-ink}"
    typography: "{typography.title}"
    rounded: "{rounded.none}"
    padding: "0.7rem 0.7rem 0.7rem 0.8rem"
  task-row-done:
    backgroundColor: "{colors.soft-mint}"
  field:
    backgroundColor: "{colors.misty-base}"
    textColor: "{colors.navy-ink}"
    rounded: "{rounded.none}"
    padding: "0.55rem 0.8rem"
    height: "3rem"
  check:
    backgroundColor: "{colors.misty-base}"
    rounded: "{rounded.none}"
    size: "1.9rem"
  streak-badge:
    backgroundColor: "{colors.apricot}"
    textColor: "{colors.navy-ink}"
    padding: "0.4rem 0.85rem"
  done-flag:
    backgroundColor: "{colors.apricot}"
    textColor: "{colors.navy-ink}"
    padding: "0.45rem 0.9rem"
  key-hint:
    backgroundColor: "{colors.misty-base}"
    textColor: "{colors.navy-ink}"
    padding: "0.45rem 0.9rem"
---

# Design System: Crunch Time

## Overview

**Creative North Star: "The Printed Block Desk"**

Crunch Time is a study desk assembled from chunky printed blocks. Every surface is a flat slab of colour with a 3px navy-ink rule and a hard offset shadow, sitting on a cool misty ground. The timer is the biggest block on the desk: an ocean-teal slab carrying Archivo Black digits large enough to read from across the room. Everything else, the checklist and the streak grid, is a misty block of the same construction, so the page reads as one stack of objects rather than a layout of cards.

The world is loud in construction and quiet in behaviour. Colour is flat, shapes are square, shadows are solid ink, and objects respond physically: buttons press down into their shadow, a ticked task gets slammed, and while a focus block runs the timer slab itself sinks into its shadow and stays still. Celebration is reserved for real progress and is the only place the warm apricot appears.

Density is moderate: generous padding inside blocks, tight rhythm inside lists, nothing ornamental. The soft rounded wellness timer with a thin progress ring is the confirmed anti-reference.

**Key Characteristics:**
- Flat colour slabs, 3px navy-ink rules, square corners everywhere.
- Hard, unblurred ink offset shadows as the only depth device.
- Teal for the hero timer, mint for "on" and "done", apricot only for streaks and celebration.
- Archivo Black for numerals, Space Grotesk for every word.
- Press-into-shadow interaction; nothing moves while a block runs.

## Colors

A cool, low-chroma ground of mist and teal, punched with navy ink, with one warm accent held back for reward.

### Primary
- **Ocean Teal** (`ocean-teal`): the timer slab during focus mode, level-3 ("goal hit") streak cells, the brand mark tile, theme-color. Carries misty-base text (5.04:1).
- **Teal Deep** (`teal-deep`): the timer slab during short and long breaks, and the inset track of pips and the progress bar on a focus slab. Carries misty-base text (6.92:1).

### Secondary
- **Soft Mint** (`soft-mint`): the "on" and "done" colour. Active mode segment, pressed icon button (current focus task), Start and Add buttons, completed task rows, filled pips, progress fill, level-2 streak cells, text selection, focus ring on the teal slab. Ink on mint 10.02:1.
- **Mint Soft** (`mint-soft`): the quieter mint. Hover on mode segments and checkboxes, level-1 streak cells, chips inside done rows, the inset field shadow, scrollbar track. Ink on mint-soft 12.63:1.

### Tertiary
- **Apricot** (`apricot`): the reward colour. The streak badge (when the streak is above zero), the in-streak bar under streak cells, the block-done flag, the "All clear" tag, and the celebration burst squares. Ink on apricot 8.18:1.

### Neutral
- **Navy Ink** (`navy-ink`): all text on light surfaces, every rule, border and offset shadow, the focus outline, the check mark. Never pure black.
- **Misty Base** (`misty-base`): page ground, block surfaces, fields, buttons at rest, and the text colour on teal. Never pure white. Ink on base 14.34:1.
- **Slate Muted** (`slate-muted`): secondary text only: meta counts, hints, placeholders, streak row labels, dashed borders of future streak cells. 6.29:1 on base, 5.54:1 on mint-soft.

### Named Rules
**The Earned Apricot Rule.** Apricot appears only on the streak and on celebration of a finished block or a cleared list. It never marks errors, hovers, selection or ordinary UI state. A zero streak returns the badge to misty base.

**The Mint Means On Rule.** Mint is the single signal for "active" and "done": the selected mode, the current focus task, a ticked task, a finished pip, the filled progress bar. Do not introduce another colour for those states.

**The No Pure Extremes Rule.** No #000 and no #FFF anywhere. Navy ink and misty base are the darkest and lightest values.

## Typography

**Display Font:** Archivo Black (with Space Grotesk, system-ui fallback)
**Body Font:** Space Grotesk (with system-ui, -apple-system, Segoe UI fallback)

**Character:** A heavy poster numeral paired with a friendly, slightly technical grotesk. Archivo Black is for numbers only; Space Grotesk does every word, from the wordmark to the labels.

### Hierarchy
- **Display** (Archivo Black 400, clamp(4.5rem, 29cqi, 18rem) of the timer slab's width, line-height 0.9): the countdown digits only. Each digit sits in a fixed 0.7em cell (colon 0.34em) so the clock never reflows, with a 0.045em navy-ink text shadow that echoes the block shadows.
- **Numeral** (Archivo Black 400, 1.35rem to 1.5rem, line-height 1): counts in the header stats and streak stats, and day counts inside streak cells (clamp(.8rem, 1.6vw, 1.05rem)).
- **Headline** (Space Grotesk 700, 1.5rem, line-height 1.1, -0.015em): block headings (Tasks, Streak). The wordmark uses 700 at 1.35rem, -0.01em.
- **Title** (Space Grotesk 600, 1.05rem, line-height 1.3): task text, settings summary (700).
- **Body** (Space Grotesk 500, 1rem, line-height 1.45): the focus line (clamp(1.05rem, 2.4cqi, 1.3rem), max 40ch), hints, legend. Buttons and form labels are 700.
- **Label** (Space Grotesk 700, 0.78rem, 0.04em, uppercase): subject chips only. Key hints use 700 at 0.82rem, not uppercase.

### Named Rules
**The Numbers Are Poster Rule.** Archivo Black is reserved for numerals: the clock, counts, and streak cell values. Words are never set in it.

## Layout

A single screen. Content sits in a centred container capped at 1440px, padded by `pad` (clamp(1rem, 2.4vw, 1.75rem)), with `gap` plus 6px between blocks so the offset shadows never touch a neighbour.

- **Desktop (980px and up):** two columns, `minmax(0, 1.45fr) minmax(340px, 1fr)`. Left column stacks the timer slab over the streak block; the task block spans both rows on the right and stretches level with the left column.
- **Below 980px:** one column in story order: timer, tasks, streak.
- **Phone (520px and down):** the shadow lift drops to 5px, the mode switch spans full width with equal segments, Start takes a full row with Reset and Skip sharing the next, "break" is dropped from mode labels, and the streak grid tightens its cell spacing.
- **Rhythm:** 0.8rem between task rows, 0.75rem inside a row, 1.1rem under block headings, 1.5rem between streak grid and stats. Interactive targets are at least 2.75rem square; primary buttons are 3rem tall and Start is 3.5rem.
- The clock scales with the slab's own width (container query units), not the viewport.

## Elevation & Depth

Depth is entirely hard offset shadow in navy ink: no blur, no spread, no tonal layering, no transparency. The shadow is an object's physical thickness, and interaction moves the object into or out of it. The scale steps down with the object's size.

### Shadow Vocabulary
- **Block** (`box-shadow: 6px 6px 0 #14213D`; 5px on phone): the three main blocks (timer, tasks, streak).
- **Control** (`box-shadow: 4px 4px 0 #14213D`): buttons, the mode switch, task rows, the progress bar, the done flag and key hint. Hover lifts to 6px with a -2px translate.
- **Small** (`box-shadow: 3px 3px 0 #14213D`): icon buttons, header stats, the brand tile, the All clear tag, the skip link. Hover lifts to 4px.
- **Micro** (`box-shadow: 2px 2px 0 #14213D`): key caps only.
- **Inset field** (`box-shadow: inset 3px 3px 0 #CDEBE5`): the recessed lip inside text and number fields.
- **Current task** (`box-shadow: 4px 4px 0 #14213D, inset 0 0 0 3px #2E6F87`): the task chosen as focus gains a teal inner rule.

### Named Rules
**The Press Into Shadow Rule.** An active press translates the object by exactly its shadow offset and collapses the shadow to zero, so the object lands where its shadow was. Hover does the reverse by a step.

**The Sinking Slab Rule.** While a focus or break block runs, the timer slab translates by the full lift and its shadow goes to zero: the whole slab is pressed down and holds still until paused.

## Shapes

Every corner is square (0px). Borders are 3px solid navy ink on blocks, controls, fields, checkboxes and streak cells; 2px is used only on the smallest objects (chips, key caps, legend swatches, the in-streak bar's top edge). Segmented controls share their 3px dividers rather than doubling them. A dashed 3px border marks absence: the empty task list, and future streak cells (in slate-muted). Icons are drawn in the same language: 24px grid, 2.5 to 3px strokes, square caps, miter joins.

## Components

### Buttons
Tactile slabs that move when touched.
- **Shape:** square (0px), 3px ink border, 4px control shadow, min-height 3rem, Space Grotesk 700 1rem, 0.01em, optional 1.25rem leading icon.
- **Default:** misty base. **Mint variant:** soft mint, for the one primary action in a block (Start, Add).
- **Hover:** translate(-2px, -2px), shadow to 6px. **Active:** translate(4px, 4px), shadow to 0. Transitions 0.12s on the out easing.
- **Icon button:** 2.75rem square (2.5rem on phone), 3px small shadow, 1.2rem icon; hover lifts 1px, active presses 3px. `aria-pressed="true"` fills it mint.
- **Link button:** text-only destructive or tertiary action (Clear all data), 600 weight, 2px underline at 0.2em offset.

### Mode Switch
- One bordered strip on misty base with a 4px control shadow; segments split by 3px ink rules.
- Hover fills mint-soft; the selected segment fills soft mint. Focus ring is drawn inset (-7px offset) so it stays inside the segment.

### Chips
- **Style:** subject tags. Misty base, 2px ink border, 0.78rem uppercase 700 at 0.04em, square.
- **State:** inside a done task row the chip turns mint-soft. Chips are data (the subject name), never decorative labels.

### Cards / Containers
- **Corner Style:** square (0px).
- **Background:** misty base; the timer slab is ocean teal (focus) or teal deep (breaks).
- **Shadow Strategy:** Block shadow (6px), which the running timer slab gives up.
- **Border:** 3px navy ink.
- **Internal Padding:** `pad` (clamp(1rem, 2.4vw, 1.75rem)).

### Inputs / Fields
- **Style:** misty base, 3px ink border, square, min-height 3rem, inset 3px mint-soft lip, slate-muted placeholder. Number fields have their spinners removed.
- **Focus:** the global 3px ink outline at 2px offset.
- **Error:** `aria-invalid` plus a message in the live region below the form.

### Checkbox
- 1.9rem square, 3px ink border, misty base; hover fills mint-soft. The check is a square-capped ink tick that scales in from 0 on the snap easing. Used both for task completion and settings toggles.

### Task Row (signature)
- A 4px-shadow block row: checkbox, subject chip over task text, then focus and delete icon buttons.
- **Done:** the row fills soft mint and plays the slam: it drops into its shadow (5px, slight scale and tilt), rebounds past rest to a 7px shadow, then settles, 0.5s on the snap easing, while the chip pops. An ink strike bar (0.12em, at 60% height) sweeps across the text over 0.36s, wrapping across lines.
- **Current focus:** a 3px teal inner rule and a mint target button; the task's chip and text appear on the timer slab's focus line.

### Timer Slab (signature)
- Teal block holding the mode switch and cycle pips, the clock, the focus line, the Start/Reset/Skip controls, a 1.1rem progress bar (mint fill scaling from the left on a teal-deep track), and key-cap shortcut hints (hidden on touch devices).
- Focus ring inside the slab is mint, not ink.
- **Pips:** four 1rem squares with ink borders, teal-deep when pending, mint when done.
- **Done flag:** apricot tag with a 4px shadow, tilted 2deg, shown after a finished block. **Key hint:** misty tag with a 4px shadow, shown when a destructive key needs a second press during a run. Either replaces the cycle readout in the slab's top bar.
- **Celebration:** on a finished focus block, 18 bordered squares (apricot, mint, base) burst from the clock and fall away over about 1s, and the streak badge pops. Skipped entirely under reduced motion.

### Streak Grid (signature)
- A six-week table of square cells (5:3 on desktop), 3px ink borders, Archivo Black day counts.
- **Levels:** 0 misty base, 1 mint-soft (started), 2 soft mint (halfway to goal), 3 ocean teal with base text (goal hit). Future days are dashed slate-muted outlines with no fill.
- **Today:** a 3px ink outline at 3px offset. **In streak:** a 0.4rem apricot bar with a 2px ink top edge along the cell's foot. Today's cell pops when a block finishes.
- A legend of 1.1rem swatches mirrors every state.

### Header Stats
- Small-shadow tags: Archivo Black count plus a 600-weight label. The streak tag is apricot while the streak is above zero and misty base at zero.

## Do's and Don'ts

### Do:
- **Do** build every new surface as a flat block: 3px navy-ink border, square corners, hard ink offset shadow sized to the object (6px block, 4px control, 3px small, 2px micro).
- **Do** make pressable things press into their shadow: translate by the shadow offset and collapse it to 0 on active.
- **Do** use mint for every "on" or "done" state and mint-soft for its hover or quiet variant.
- **Do** keep apricot to the streak and celebration of finished work.
- **Do** set numerals in Archivo Black and every word in Space Grotesk.
- **Do** use the snap easing (cubic-bezier(.2, 1.6, .4, 1)) for overshooting reward moments and the out easing (cubic-bezier(.16, 1, .3, 1)) for presses and settles.
- **Do** collapse all animation and transition durations under `prefers-reduced-motion` and skip the burst.
- **Do** keep text at AA: ink on base, mint, mint-soft or apricot; base on teal or teal deep; slate-muted only on base or mint-soft.

### Don't:
- **Don't** round corners, blur shadows, or use tinted or translucent shadows.
- **Don't** use pure black (#000) or pure white (#FFF).
- **Don't** animate anything on or around the timer while a block runs; the slab sinks once and holds still.
- **Don't** use apricot for errors, warnings, hover or selection.
- **Don't** put navy-ink text directly on ocean teal or teal deep (2.84:1 and 2.07:1); text on teal is misty base.
- **Don't** set words in Archivo Black.
- **Don't** build a soft, rounded wellness-style timer with a thin progress ring.
