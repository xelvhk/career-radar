# Career Radar

Career Radar is an evidence-first career intelligence project. It is designed to
turn verifiable project work into vacancy matches, application arguments, and a
market-driven learning roadmap without inventing experience.

The repository is intentionally starting with the data foundation described in
[`docs/spec.md`](docs/spec.md). There is no vacancy scraper, LLM pipeline, or UI
yet.

## Current scope

- `CAREER_EVIDENCE.md` — human-readable evidence register
- `skills.yaml` — structured skills and evidence links
- `projects.yaml` — projects that can substantiate skills
- `career_goals.yaml` — role, market, and constraint preferences
- `scripts/validate_data.py` — local contract and reference validation
- `scripts/audit_sources.py` — read-only verification against local Git checkouts

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
