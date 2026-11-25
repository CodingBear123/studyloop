# Note templates

Obsidian markdown. `[[wiki links]]` by note name, callouts with `> [!type]`, folds with `> [!type]-`.

## Concept note: `NN-Area/<Title>.md`

````markdown
---
source: Session 05 slides, p. 12-30
keywords: closures, late-binding, nonlocal
---

# Closures (★★★)

| Idea | In one line |
|---|---|
| closure | a function that keeps the variables of the scope it was made in |
| late binding | captured names are looked up when the function runs, not when it is made |

## How it works

3-6 lines, then an example:

```python
def make():
    fs = [lambda: i for i in range(3)]
    return [f() for f in fs]   # [2, 2, 2]
```

> [!warning] Exception
> Default arguments are evaluated at definition time: `lambda i=i: i` captures the value.

## Exam Patterns

| How it's asked | What to answer |
|---|---|
| "What does this print?" with lambdas in a loop | the last loop value, every time |

## Related Notes
- [[Variable Scope LEGB]] · [[Call Stack]] · [[04 Practice - Scope, Stack and Closures]]
````

Stars: ★★★ asked in most exams, ★★ sometimes, ★ background.

## Practice file: `NN-Area/NN Practice - <Title>.md`

```markdown
---
source: Session 05 slides; HS24 exam Q3
keywords: practice, closures
---

# Practice: Scope, Stack and Closures (8 questions)

## Related Concepts
- [[Closures]] · [[Variable Scope LEGB]]

> [!hint]- Key patterns
> | Cue | Answer |
> |---|---|
> | lambda in a loop | late binding |

---

## Q1 · Late binding [recall]
> What does `[f() for f in [lambda: i for i in range(3)]]` evaluate to?

> [!answer]- Answer
> `[2, 2, 2]`: `i` is looked up when each lambda runs, after the loop ended. → [[Closures]]

---

## Q2 · Fix it [application]
> ...

> [!answer]- Answer
> ...
```

## `00-Dashboard/MOC - <Subject>.md`

```markdown
---
keywords: moc, study-map
---

# <Subject>: Study Map

## Exam
Date, length, format, and the scope rule (one line each). → [[Exam Blueprint]]

## Areas
| # | Area | Notes | Practice | Source |
|---|---|---|---|---|
| 01 | Objects and Classes | [[Design Basics]], [[Inheritance and Polymorphism]] | [[01 Practice - Objects and Classes]] | Sessions 1-2 |

## Tools
- [[Learning Dashboard]]: progress (generated, don't edit)
- [[Quick Reference]] · [[Exam Traps]] · past exams: [[HS24 Exam (real)]]

## Out of scope
| Topic | Why |
|---|---|
| VM / assembler | only in old exams, not in this year's sessions |
```

## `00-Dashboard/Exam Blueprint.md`

```markdown
# Exam Blueprint

| Area | HS23 | HS24 mock | HS24 | Points (avg) | Notes |
|---|---|---|---|---|---|
| Interpreter | Q2, OA.1 | Q3 | OA.2 | 12 | if-chain → dispatch table repeats |

> [!important] Takeaways
> 1. Questions that repeat across years.
> 2. Question types and how many points they're worth.
> 3. The scope rule.
```

## `00-Dashboard/Quick Reference.md`

One section per area, each heading ends with `→ [[Concept Note]]`; short tables of definitions, syntax,
formulas. A "must know" list at the end, each item linked.

## `00-Dashboard/Exam Traps.md`

```markdown
# Exam Traps

## Protocols
> [!danger]- `__exit__` returning True swallows the exception
> - The trap: ...
> - Why it's confusing: ...
> - Right answer: ...
> - [[Context Managers]]
```

## Past exam: `NN-Past-Exams/<Exam>.md`

Each question as in the exam (code included), the answer in a fold, and `→ [[note]]` links to the notes that
cover it. Mark questions on out-of-scope topics instead of dropping them.
