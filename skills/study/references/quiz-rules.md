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

- Single choice: 4 options (2–8 allowed), one right.
- Open answer: free text, graded by you against the notes and the bank's `model_answer`.
- Code goes in `code` or in fenced blocks, never squashed onto one line. Set `lang`.
- Program output as options: set `options_code: true`.
