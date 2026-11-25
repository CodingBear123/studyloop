# Vault checklist

Run `python3 ../studyloop/app/studyvault.py check VAULT` first: it must report 0 errors. Then check by reading:

## Data (the tool checks these)
- [ ] `studyvault.json` lists every area folder; every `NN-` folder is an area or in `extra_folders`
- [ ] every area has `concepts/<slug>.md` and `question-bank/<slug>.json`
- [ ] `Learning Dashboard.md` was written by `recompute`
- [ ] no broken `[[links]]`

## Sources
- [ ] every source file was mapped from its content, not its name
- [ ] every note's `source` matches that mapping
- [ ] the scope rule is written in the manifest, the MOC and the blueprint; out-of-scope topics are listed

## Coverage
- [ ] every topic in the material has a note section; every member of an enumerated list has its own
- [ ] every area folder has 2+ concept notes and one practice file with 8+ questions
- [ ] each note has a table, an example, `## Exam Patterns` and `## Related Notes`

## Practice and bank
- [ ] practice answers are all folded (`> [!answer]-`); question kinds are tagged and mixed
- [ ] 6+ bank questions per area, each with `concept`, `difficulty`, `explanation`
- [ ] every answer key double-checked; code in questions runs and prints what the answer says
- [ ] no hints in options (see `../studyloop/references/quiz-rules.md`)

## Dashboard folder
- [ ] MOC links every note and practice file
- [ ] Exam Blueprint (when there are old exams) shows topic × exam, repeats and the scope rule
- [ ] Quick Reference headings link to their notes; Exam Traps link to their notes
