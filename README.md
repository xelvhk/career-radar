# Career Radar

[Русская версия](README.ru.md)

Evidence-first local career intelligence project. It turns verified project work into deterministic vacancy matching, application arguments, and a market-driven learning roadmap without inventing experience.

## Problem

- Project evidence, skills, and vacancy requirements are usually scattered across notes, repos, and job descriptions.
- Manual vacancy review is slow and easy to bias toward weak matches.
- Private career facts should not be committed to Git, but matching still needs structured constraints.

## Stack

- Python 3.11+
- FastAPI + Uvicorn for the local panel
- SQLite for the private Opportunity Inbox
- PyYAML for structured evidence, goals, and matching config
- unittest + local deterministic fixtures

## Setup

```bash
git clone https://github.com/xelvhk/career-radar.git
cd career-radar
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[test]'
.venv/bin/python scripts/validate_data.py
.venv/bin/python -m unittest discover -s tests -v
```

Optional private profile:

```bash
cp career_profile.local.example.yaml career_profile.local.yaml
```

`career_profile.local.yaml` and the local SQLite inbox are ignored by Git.

## Architecture

```text
YAML evidence layer
  skills.yaml, projects.yaml, career_goals.yaml, matching.yaml, search_profiles.yaml

Matching layer
  career_radar/matching.py, matching_config.py, validation.py

Opportunity Inbox
  opportunity_store.py, opportunity_service.py, scripts/inbox.py

Local panel
  career_radar/panel.py, scripts/run_panel.py

Source adapters
  hh_source.py, scan_service.py, source_audit.py
```

The matcher is deterministic and offline. Source adapters must fail closed when local configuration is incomplete.

## Demo

Validate evidence and matching rules:

```bash
python3 scripts/validate_data.py
python3 scripts/list_search_queries.py
```

Match one saved vacancy:

```bash
python3 scripts/match_vacancy.py vacancy.txt
python3 scripts/match_vacancy.py vacancy.txt --format json
```

Run the local panel:

```bash
python3 scripts/run_panel.py --profile career_profile.local.yaml
```

Open `http://127.0.0.1:8765`.

## Privacy Boundary

- Full vacancy text stays in the ignored local SQLite database.
- Private profile data stays in `career_profile.local.yaml`.
- Repository files contain public evidence, sanitized fixtures, and source-neutral configuration only.

## Roadmap

- [ ] Improve evidence scoring explanations in the local panel.
- [ ] Add exportable Markdown reports for shortlisted opportunities.
- [ ] Expand source adapters while keeping fail-closed configuration checks.

## Status

Active development

## License

License is not specified yet.

## Quality gates

Install the development checks and run the same gates as CI:

```bash
.venv/bin/python -m pip install -e '.[test,quality]'
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy career_radar scripts
.venv/bin/coverage run -m unittest discover -s tests
.venv/bin/coverage combine
.venv/bin/coverage report
```

The enforced complexity ceiling is 20. The long-term target is 10; remaining
reductions should be small behavior-preserving refactors. Mutation testing is
intentionally explicit because it is slower than the per-push checks:

```bash
.venv/bin/python -m pip install -e '.[test,quality,mutation]'
.venv/bin/mutmut run "career_radar.matching*"
.venv/bin/mutmut run "career_radar.vacancy*"
.venv/bin/mutmut run "career_radar.opportunity_store*"
```
