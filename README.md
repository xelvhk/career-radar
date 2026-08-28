# Career Radar

Career Radar is an evidence-first career intelligence project. It is designed to
turn verifiable project work into vacancy matches, application arguments, and a
market-driven learning roadmap without inventing experience.

The repository combines the data foundation in [`docs/spec.md`](docs/spec.md)
with deterministic manual matching and a private local Opportunity Inbox with a
browser panel. There is no vacancy scraper or LLM pipeline yet.

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
- `career_radar/panel.py` — loopback-only API for the local browser panel
- `scripts/match_vacancy.py` — manual vacancy-to-evidence match report
- `scripts/inbox.py` — persistent manual import, ranking, review, and status CLI
- `scripts/run_panel.py` — local Opportunity Inbox web panel

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

## Open the local web panel

Install the web runtime, then start the loopback-only server:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[test]'
.venv/bin/python scripts/run_panel.py \
  --profile career_profile.local.yaml
```

Open `http://127.0.0.1:8765`. The panel supports manual vacancy paste, ranked
Inbox filters, evidence/gap review, provenance, and independent
`new`/`shortlisted`/`dismissed` decisions. Full vacancy text remains in the
ignored local SQLite database and is never returned by the browser API.

The first source adapter uses the official HeadHunter API. Before enabling live
scans, register your application at `dev.hh.ru`, then create the ignored local
configuration:

```bash
cp hh_source.local.example.yaml hh_source.local.yaml
```

Set `registered_application: true` only after registration and replace the
example `HH-User-Agent` contact. Then choose one saved profile and press
`Scan vacancies`. Without confirmed local configuration, the action returns a
safe `blocked` result before making a network request. No OAuth token, HH login,
password, or API key is read or stored in this slice.

The panel loads no remote scripts, fonts, or analytics. Vacancy descriptions
retrieved from HH stay in local SQLite and are processed only by the local
deterministic matcher. See
[`docs/headhunter-source-spec.md`](docs/headhunter-source-spec.md) and
[`docs/local-web-panel-spec.md`](docs/local-web-panel-spec.md).
