# Career Radar

Career Radar is an evidence-first career intelligence project. It is designed to
turn verifiable project work into vacancy matches, application arguments, and a
market-driven learning roadmap without inventing experience.

The repository combines the data foundation in [`docs/spec.md`](docs/spec.md)
with deterministic manual matching and a private local Opportunity Inbox. There
is no vacancy scraper, LLM pipeline, or UI yet.

## Current scope

- `CAREER_EVIDENCE.md` — human-readable evidence register
- `skills.yaml` — structured skills and evidence links
- `projects.yaml` — projects that can substantiate skills
- `career_goals.yaml` — role, market, and constraint preferences
- `scripts/validate_data.py` — local contract and reference validation
- `scripts/audit_sources.py` — read-only verification against local Git checkouts
- `matching.yaml` — deterministic RU/EN aliases, weights, and decision thresholds
- `search_profiles.yaml` — evidence-backed, source-neutral vacancy search plans
- `career_radar/collected_vacancy.py` — normalized collector provenance and
  deterministic vacancy identity contract
- `career_radar/opportunity_store.py` — transactional local SQLite inbox
- `scripts/match_vacancy.py` — manual vacancy-to-evidence match report
- `scripts/inbox.py` — persistent manual import, ranking, review, and status CLI

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

## Optional private profile

To resolve mandatory experience, production, location, and seniority constraints
without putting personal facts in Git, copy the local-only template and pass it
explicitly:

```bash
cp career_profile.local.example.yaml career_profile.local.yaml
python3 scripts/match_vacancy.py vacancy.txt --profile career_profile.local.yaml
```

`career_profile.local.yaml` is ignored by Git. It is never written back to
`career_goals.yaml` or included in matcher output. See
[`docs/local-profile-spec.md`](docs/local-profile-spec.md) for the restricted
schema and privacy boundary.

## Inspect saved searches

Generate the structured plans that future source adapters and the local panel
will consume:

```bash
python3 scripts/list_search_queries.py
python3 scripts/list_search_queries.py --format json
```

The command is offline and read-only. It currently emits eight variants across
AI Backend, RAG / LLM, Python / FastAPI, and Document AI. Site-specific quoting
and negation remain the responsibility of each future adapter. See
[`docs/search-profile-spec.md`](docs/search-profile-spec.md).

## Use the local Opportunity Inbox

Import and match a vacancy into the private local SQLite inbox:

```bash
python3 scripts/inbox.py import vacancy.txt \
  --source manual \
  --source-url https://example.com/vacancy/123 \
  --profile career_profile.local.yaml
```

Review the ranked queue and record a human decision independently from the
matcher recommendation:

```bash
python3 scripts/inbox.py list --recommendation APPLY --status new
python3 scripts/inbox.py show VACANCY_ID
python3 scripts/inbox.py set-status VACANCY_ID shortlisted
```

The default `career_radar.local.sqlite3` database is ignored by Git and created
with private permissions on POSIX. Full vacancy text stays inside that local
database and is omitted from CLI JSON/Markdown output. Use `--db PATH` on any
command to select another local database. See
[`docs/opportunity-inbox-spec.md`](docs/opportunity-inbox-spec.md).
