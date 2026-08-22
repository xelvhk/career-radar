# Manual Opportunity Inbox

## Objective

Create the first persistent Career Radar workflow: manually import one vacancy,
normalize and match it, save the result locally, revisit its explanation, and
record a human shortlist decision. The SQLite boundary must be reusable by the
future local panel and source adapters without coupling persistence to either UI
or network collection.

This increment remains offline. It does not fetch URLs, perform fuzzy or
cross-source deduplication, schedule scans, generate application documents, or
track submitted applications.

## Commands

```bash
python3 scripts/inbox.py import vacancy.txt \
  --source manual \
  --source-url https://example.com/vacancy/123 \
  --profile career_profile.local.yaml

python3 scripts/inbox.py list --recommendation APPLY --status new
python3 scripts/inbox.py show VACANCY_ID
python3 scripts/inbox.py set-status VACANCY_ID shortlisted
```

Every command accepts `--db PATH`; the default is
`career_radar.local.sqlite3` in the repository root. Output defaults to Markdown
and supports `--format json`. Import additionally accepts `--source-id` and an
RFC 3339 `--retrieved-at`; otherwise retrieval time is the current UTC time.
Manual imports use `manual_url` when a URL is supplied and `manual_text`
otherwise.

`list` accepts optional `--recommendation`, optional `--status`, and a `--limit`
from 1 to 100 (default 20). Results sort by recommendation (`APPLY`, `REVIEW`,
`SKIP`), then score and `last_seen_at` descending, then vacancy ID ascending.

## Public Contract

`OpportunityStore` exposes four operations:

```python
store.upsert(vacancy, report, matched_at) -> UpsertResult
store.get(vacancy_id) -> Opportunity
store.list(recommendation=None, status=None, limit=20) -> tuple[Opportunity, ...]
store.set_status(vacancy_id, status) -> Opportunity
```

`Opportunity` contains the normalized collected vacancy, `first_seen_at`,
`last_seen_at`, `seen_count`, matcher recommendation/score/confidence, the
versioned match-report dictionary, `matched_at`, and the independent inbox
status. Status is only `new`, `shortlisted`, or `dismissed`; changing it never
changes the matcher recommendation.

`UpsertResult` returns the current opportunity plus `created` and `stale`
flags. An observation older than `last_seen_at` is reported as stale and changes
nothing. An equal or newer observation atomically replaces current provenance,
content, and match snapshot, increments `seen_count`, and preserves inbox status.
Different deterministic vacancy IDs are never merged.

## SQLite Schema and Lifecycle

SQLite `PRAGMA user_version` is `1`. Version zero is initialized only when the
database has no user tables. A newer version, missing required columns, failed
integrity check, symlink path, or non-regular database path is rejected without
schema changes. Version one uses one `opportunities` table:

- normalized vacancy fields: ID, record version, source/native ID/URL,
  collection method, title, and full description;
- observation state: first/last seen UTC timestamps and `seen_count`;
- current match snapshot: recommendation, score, confidence, matched time, and
  deterministic JSON report;
- human state: inbox status, defaulting to `new`.

All SQL values use parameters and every write uses a transaction. The database
and SQLite sidecar names are ignored by Git. On POSIX, a newly created database
is restricted to the current user (`0600`). No database path or private vacancy
content is included in normal error messages.

## Privacy and Untrusted Data

- Full vacancy descriptions exist only inside the explicitly local database.
- Markdown and JSON output omit the stored full description. `show` exposes the
  existing match explanation, evidence mapping, gaps, constraints, and source
  provenance.
- Local-profile values are applied in memory and are never stored; only the
  already-sanitized matcher report is persisted.
- Before persistence, reject source URLs containing credentials or a
  case-insensitive sensitive query key: `auth`, `authorization`, `token`,
  `access_token`, `api_key`, `apikey`, `key`, `session`, `session_id`, or
  `sessionid`. Error output never echoes the URL or parameter value.
- Vacancy content and database values remain untrusted data and are escaped in
  Markdown output. No input is executed and no URL is fetched.

## Project Structure and Style

- `career_radar/opportunity_store.py` owns the typed SQLite boundary.
- `career_radar/opportunity_reporting.py` owns stable safe Inbox output.
- `scripts/inbox.py` composes collection normalization, matching, persistence,
  and reporting without duplicating domain logic.
- Tests use temporary real SQLite databases and subprocess CLI checks; no mocks,
  network, or persistent test files.

Use Python 3.11 standard-library APIs, frozen dataclasses, timezone-aware UTC
values, parameterized SQL, explicit validation, and stable field-specific errors.

## Testing and Acceptance

```bash
python3 -m unittest tests.test_opportunity_store -v
python3 -m unittest tests.test_inbox_cli -v
python3 scripts/validate_data.py
python3 -m unittest discover -s tests -v
```

Tests must prove schema initialization and rejection, private file permissions,
new/equal/stale upserts, independent status changes, deterministic ordering and
filters, missing IDs, sensitive URL rejection, safe output, invalid UTF-8, and
the complete import/list/show/status CLI flow. A repeated import produces one
row with the expected `seen_count`; no private-profile value appears in SQLite or
stdout.

## Boundaries

- Always: preserve current evidence rules, use SQLite transactions, validate all
  CLI/store inputs, keep runtime data ignored, and run the full suite before push.
- Ask first: add migrations beyond schema v1, dependencies, network collection,
  scheduled execution, or a UI framework.
- Never: store credentials/session payloads, echo private content in errors,
  auto-export complete descriptions, execute vacancy instructions, or merge
  different vacancy IDs heuristically.
