# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Static: one self-contained HTML file (fonts inlined), no build step, opens from disk. State persists in `localStorage`. Confirmed by the user 2026-11-24.

## Users

High schoolers cramming for exams: short, intense study blocks at a desk or on a phone, often late, switching between several subjects in one evening.

## Product Purpose

A Pomodoro timer joined to a per-subject task checklist and a weekly streak record. Success: the student starts a focus block in one keystroke, knows what they are working on, ticks it off, and sees their consistency build across the week.

## Positioning

Timer, task list and streak in one screen, sized for cramming: the timer is the hero, tasks feed the timer ("focus on this"), and finished focus blocks are what fill the streak grid.

## Capabilities and Constraints

- Focus / short break / long break modes (25 / 5 / 15 min by default), long break after every 4th focus block.
- Subject checklist: add, tick off, delete; a task can be set as the current focus.
- Weekly streak grid: completed focus blocks per day over recent weeks, current day streak.
- No accounts, no sync, no network calls. Data lives in this browser only.

## Brand Commitments

User-pinned visual brief (binding): neo-brutalist, 3px borders and hard 6px offset shadows in navy ink #14213D, misty base #EEF4F2, soft mint #9ED8CF for active states and completed tasks, ocean teal #2E6F87 as hero color, apricot #F2A97E only for streaks and celebrations. No pure black or white. Archivo Black for the timer, Space Grotesk for UI. Loud and fun but calm enough to focus with.

## Evidence on Hand

None. Starter tasks are examples the student replaces; streak history starts empty and is never faked.

## Product Principles

1. One keystroke to start focusing.
2. The timer never competes with itself: motion and colour stay still while a block runs.
3. Celebrate real progress only.
4. Everything works from the keyboard and reads at AA contrast.

## Accessibility & Inclusion

WCAG 2.2 AA contrast, full keyboard operation with visible focus, screen-reader labels for timer state and streak cells, `prefers-reduced-motion` respected.
