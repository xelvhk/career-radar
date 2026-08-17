# Matcher Calibration: Habr Baseline

## Scope

On 2026-08-17, Manual Vacancy Match was exercised against eight active public
Habr Career vacancies. Checked-in fixtures are short, paraphrased requirement
summaries with source URLs; they are not copies or durable snapshots of the full
third-party pages.

This sample calibrates deterministic extraction only. It is too small and lacks
user-labeled outcomes, so scoring weights and thresholds remain unchanged.

## Result

| Fixture | Score | Confidence | Decision | Extracted hard constraints |
|---|---:|---:|---|---|
| `01-lead-ai-ml.txt` | 82 | 45 | REVIEW | none |
| `02-ml-platform.txt` | 81 | 20 | REVIEW | 3 years, production |
| `03-backend-platform.txt` | 95 | 35 | REVIEW | 3 years, production |
| `04-ai-architect.txt` | 77 | 35 | REVIEW | outside RU and BY |
| `05-senior-fullstack.txt` | 83 | 30 | REVIEW | 5 years, production |
| `06-ml-devops.txt` | 76 | 20 | REVIEW | none |
| `07-junior-python.txt` | 94 | 30 | REVIEW | none |
| `08-python-llm-rag.txt` | 94 | 55 | REVIEW | 2 years |

Observed extraction coverage:

- 8/8 fixtures produced cataloged skill mappings offline;
- 8/8 work modes were recognized from natural Russian wording;
- 4/8 titles matched an existing target-role ID;
- four minimum-years constraints, three production constraints, and one
  multi-country location constraint were surfaced explicitly;
- 8/8 recommendations remained `REVIEW`: mandatory facts are unknown, required
  gaps exist, or extraction confidence is below the automatic threshold.

The conservative outcome is intentional. Career Radar does not infer commercial
years or production history from portfolio repositories, and it does not convert
an unknown location constraint into a mismatch.

## Verification

```bash
python3 scripts/validate_data.py
python3 -m unittest discover -s tests -v
```

At this baseline the commands pass with 51 tests. Calibration fixtures live in
`tests/fixtures/calibration/` and are processed without network access.

## Next Calibration Step

Before changing scores or thresholds:

1. explicitly decide whether to add private local profile fields for commercial
   years, verified production experience, current country, and target seniority;
2. expand the labeled sample to 20-30 vacancies across saved search profiles;
3. record false positives, false negatives, recurring unmapped requirements, and
   duplicate decisions;
4. use those observations to define the first local Watchlist search profiles.
