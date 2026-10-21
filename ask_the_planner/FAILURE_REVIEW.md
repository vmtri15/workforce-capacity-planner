# Ask the Planner: failure review

## Latest run: the fixes, on gemini-3.5-flash-lite

The first run (below) ended with three proposed fixes. The first two were built as a third condition, "guided":
base case views in the evaluation database (`base_case_staffing`, `base_case_capacity`, `base_case_workload`,
`base_case_summary`), the base case rule moved into the main instructions, and three worked examples that are
not test questions. The older conditions see the same database without those views, so each condition is scored
on the schema it was given.

The first run's model, gemini-3.1-flash-lite, was unavailable for hours (503, "high demand"), so all three
conditions were run again on gemini-3.5-flash-lite, the newer small model. One run per question, temperature 0,
90 answers, no API errors. Results are in `results/gemini-3.5-flash-lite/`.

| | Schema only | + Glossary | + Guidance |
| --- | ---: | ---: | ---: |
| Correct answers (of 28) | 15 (54%) | 23 (82%) | 27 (96%) |
| The right numbers appeared in a query it ran | 46% | 79% | 96% |
| Declined the 2 questions it cannot answer | 0 of 2 | 2 of 2 | 2 of 2 |

- The glossary fixed 8 questions (Q05, Q06, Q12, Q13, Q16, Q17, Q18, Q24) and broke none.
- The guidance fixed 4 more (Q19, Q20, Q21, Q23) and broke none. All four were the old error: adding up the
  three planning runs. With the glossary alone, Q21 even said "in the base run" while giving 88,545 orders,
  three times the right 29,515. With the guidance it answered 29,515.
- **The one remaining miss, Q22:** "How many orders did the original data record in the planning window?" It
  summed the whole source table (53,628, about two years) instead of the 56 day window (5,903), even though the
  instructions name the window. This is the same error as in the first run. A fix to measure next: a
  `planning_window_source` view, like the base case views.
- **One rule to read by eye:** with the schema only, the Q29 answer ("the database contains modeled planning
  scenarios ... rather than actual historical financial records for 2023") is in effect a refusal, but the
  decline rule did not match its wording. Counted strictly as written, it stays a miss.

Read with the limits below: one run of one small model, 28 questions on one database. A one question difference
is not meaningful, but 15 to 23 to 27 is a large and consistent step, and no question got worse at either step.

## First run: gemini-3.1-flash-lite

### The run

- Model: gemini-3.1-flash-lite on the Gemini API free tier, temperature 0, one run per question.
- Questions: 30 written the way a manager would ask them. 28 can be answered from the database and 2 cannot.
- Database: a copy of the planner database with the planning engine run on it (`build_eval_db.py`). Read only.
- Two conditions with the same model, instructions and schema. The only difference is the business glossary.

| | Without glossary | With glossary |
| --- | ---: | ---: |
| Correct answers (of 28) | 12 (43%) | 16 (57%) |
| The right numbers appeared in a query it ran (of 28) | 10 (36%) | 14 (50%) |
| Declined the 2 questions it cannot answer | 1 of 2 | 2 of 2 |

The glossary fixed 5 questions (Q08, Q17, Q24, Q25 and the refusal Q30) and broke none.

By type of question, with the glossary: basics 5 of 5, data sources and quality 2 of 2, labor market 1 of 1, cost 2 of 3, staffing 2 of 4, capacity 3 of 8, demand 1 of 5.

### How a failure was decided

A question counts as correct when the final answer a manager reads states the right values. Rounding, percent instead of a share, plurals, short site names ("O'Hare") and common abbreviations ("OEWS") are accepted. Every gold answer was checked a second way in plain Python (`verify_gold.py`). Every failure below was confirmed by reading the answer and the SQL in `results/transcript.jsonl`. None of them is a scoring mistake.

### What went wrong

| Cause | Without glossary | With glossary |
| --- | ---: | ---: |
| Added up all three planning runs instead of using the base case | 14 | 11 |
| Gave up after 6 queries because it could not match a name | 2 | 0 |
| Made up an answer the data cannot support | 1 | 0 |
| Used the whole source history instead of the planning window | 0 | 1 |

**1. Adding up all three planning runs.** The database holds the same plan three times, once each for low, base and high productivity. A question like "how many workers do we have?" means the base case, but the model added up all three runs, so most answers are three times too large. The glossary states the rule ("a question that does not name a case means the base run"). The model followed it on some questions but not on most.

| Question | Answer given | Right answer |
| --- | --- | --- |
| Q06 Workers at each site | Joliet 84, O'Hare 84, Kenosha 39 | 28, 28, 13 |
| Q07 Workers in total | 207 | 69 |
| Q10 Staffing cost per day by site | $13,163.76, $13,163.76, $7,347.36 | $4,387.92, $4,387.92, $2,449.12 |
| Q12 Shortfall hours in total | 1,112.88 | 113.35 |
| Q13 Site with most shortfall hours | Joliet, 505.33 | Joliet, 51.73 |
| Q16 Days Kenosha misses the target | 11 | 2 |
| Q18 Worst single shortfall day | 2011-12-05, Joliet, picking, 96.91 h | same day, site and role, 33.58 h |
| Q19 Idle hours in total | 32,499.22 | 10,614.38 |
| Q20 Busiest day and its units | 2011-11-14, 714,465 units | 2011-11-14, 238,155 units |
| Q21 Orders planned in total | 88,545 | 29,515 |
| Q23 Order lines per day on average | 37,789 | 12,596 |

These are the answers with the glossary. Without it the same questions failed the same way, plus Q17 (shortfall by role) and Q24 (days with no source records, 72 instead of 8). Q18 is the most dangerous kind: the date, site and role are right, so it looks correct, but the hours come from the low productivity run.

**2. Giving up when a name does not match** (without glossary only). For Q08 and Q25 the model searched for "O'Hare" and "packer", which are not stored names (the data uses `ohare` and `packing_associate`). It kept exploring and stopped at the 6 query limit with no answer. With the glossary, which lists the ids, both were answered correctly. A related miss is Q16 without the glossary: it searched for a site named exactly "Kenosha", found nothing, and confidently said Kenosha never misses the target.

**3. Making up an answer** (without glossary only). Asked how many workers to hire (Q30), the model divided total shortfall hours by paid hours and said "139 additional workers". The database has no hiring logic, and the number also mixes all three runs. With the glossary, which says the data has no hiring recommendations, it declined correctly.

**4. The wrong time window** (with glossary, Q22). Asked how many orders the original data recorded in the planning window, it summed the whole source table, about two years, and answered 53,628 instead of 5,903.

### What would fix the main error

Fixes 1 and 2 were built and measured in the latest run above (27 of 28 correct). Fix 3 was not tested as a separate step:

1. Add a database view for the base case, so the simplest query is already the right one.
2. Move the base case rule from the glossary into the main instructions, and add two or three worked example questions with their SQL.
3. Try a larger model. This run used a small free model, and larger models usually follow instructions better.

### Limits of this evaluation

- One run of one small model. Answers can change from run to run, so a difference of one question is not meaningful. Each question is worth about 3.6 points.
- 28 answerable questions on one database. The results describe this database and this question set, not text to SQL in general.
- The two questions that cannot be answered are scored by a simple rule. I also read both answers in both conditions, and the rule agreed with my reading every time.
