# Career Radar

Career Radar is an evidence-first career intelligence project. It is designed to
turn verifiable project work into vacancy matches, application arguments, and a
market-driven learning roadmap without inventing experience.

The repository combines the data foundation in [`docs/spec.md`](docs/spec.md)
with a deterministic manual matching slice. There is no vacancy scraper, LLM
pipeline, persistence layer, or UI yet.

## Current scope

- `CAREER_EVIDENCE.md` — human-readable evidence register
- `skills.yaml` — structured skills and evidence links
- `projects.yaml` — projects that can substantiate skills
- `career_goals.yaml` — role, market, and constraint preferences
- `scripts/validate_data.py` — local contract and reference validation
- `scripts/audit_sources.py` — read-only verification against local Git checkouts
- `matching.yaml` — deterministic RU/EN aliases, weights, and decision thresholds
- `scripts/match_vacancy.py` — manual vacancy-to-evidence match report

## Quick start

```bash
python3 -m pip install -e .
python3 scripts/validate_data.py
python3 -m unittest discover -s tests -v
```

To audit pinned artifacts without storing local paths:

```bash
python3 scripts/audit_sources.py \
  --repo project-id=/absolute/path/to/checkout
```

Verified evidence remains separate from disclosure. Private repository evidence
may be marked `on_request`, but it never qualifies as `public_evidence`.

## Match one vacancy

Save the vacancy as UTF-8 text, then generate a local report:

```bash
python3 scripts/match_vacancy.py vacancy.txt
python3 scripts/match_vacancy.py vacancy.txt --format json
```

The matcher is deterministic and offline. It recognizes only configured skills,
shows unmapped lines, unknown dimensions, and unverified experience or location
constraints explicitly, and never follows instructions or URLs embedded in
vacancy text. See
[`docs/manual-vacancy-match-spec.md`](docs/manual-vacancy-match-spec.md).

The first real-vacancy calibration uses eight sanitized, source-attributed Habr
Career fixtures. Results and known limitations are recorded in
[`docs/calibration/2026-08-17-habr-baseline.md`](docs/calibration/2026-08-17-habr-baseline.md).
