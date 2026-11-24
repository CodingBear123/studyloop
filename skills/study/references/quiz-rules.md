# Question rules

## Zero hints

A question must be answerable only by someone who knows the material.

1. Option text is neutral. It never explains why it is right.
   - Bad: `stderr: the error stream Cloud Run uses for classification`
   - Good: `stderr`
2. No "(Recommended)", no "best", no option that is obviously longer or more careful than the rest.
3. Randomize where the right answer sits. Across a round, don't put it in the same slot twice in a row.
4. Ask about behavior, purpose or output, not with the answer in the question.
   - Bad: "Which error stream does `error()` use?"
   - Good: "Where does the output of `error()` go?"
5. Distractors are real ideas from the course, ideally common mistakes (the ones in `Exam Traps.md` and
   the error notes are good sources).

## Kinds of question

| Kind | Example |
|---|---|
| Recall | "What does `struct.pack('<I', 1)` return?" |
| Understanding | "Why does the archiver hash file contents instead of names?" |
| Prediction | "What does this program print?" (code in the `code` field) |
| Comparison | "What changes if `nonlocal` is removed here?" |
| Debugging | "This test fails. Which line causes it?" |
| Writing (open) | "Write the dispatch-table version of this if-chain." |

Use the kinds the vault's past exams use. For code subjects, at least half of a round should involve real code.

## Difficulty

- Diagnostic: easy 40%, medium 40%, hard 20%
- Drill: medium 30%, hard 70%
- Area review and exam simulation: even, or the exam's own mix

## Drilling 🔴 concepts

- Never repeat the old question. Test the same idea from a new angle or in a new program.
- Use the error note: if the user confused X with Y, build a case where only X gives the right answer.
- Use the exact concept name from the tracker so the existing row updates.

## Concept names

A concept is one idea a question tests, named in a few words ("late binding in closures",
"`bool` is a subclass of `int`"). Not too broad ("closures") and not the question itself.
Reuse an existing row name when it fits. No `|` characters.

## Format

Pick the type that tests the concept best, and mirror the old exams: if they use Kprim, use Kprim.

| Type | Use it for | Rules |
|---|---|---|
| `single` | one best answer, output prediction, "which of these" | 4 options (2–8), one right |
| `multi` | "select all that apply" | 4–6 options, 1 to all-but-one right; vary how many, so the count gives nothing away |
| `kprim` | four related claims about one object (Swiss Kprim) | 4 statements, each true or false; mix them (never all true or all false in a row of rounds); each statement must be clearly true or false on its own |
| `numeric` | calculations with one result | the number only; set `unit` and a `tolerance` for rounding (e.g. 0.01 for 2 decimals); say in the prompt how to round |
| `open` | explain, compare, write code, proofs | free text, graded by you against the notes and the bank's `model_answer` |

In a round of 4, use at least two types when the area allows it.
- Code goes in `code` or in fenced blocks, never squashed onto one line. Set `lang`.
- Program output as options: set `options_code: true`.
