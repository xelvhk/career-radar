# HeadHunter Source Adapter

Status: approved Phase 2B slice. Researched against official HeadHunter
documentation on 2026-08-28.

## Boundary

Career Radar uses the official `https://api.hh.ru` API. It does not scrape web
pages, collect HH credentials, or send vacancy data to a third party. The first
adapter is deliberately local, synchronous, and conservative:

- the application owner must register an application at `dev.hh.ru` and attest
  that registration in an ignored local configuration file;
- every request sends a locally configured `HH-User-Agent` value;
- one selected saved-search profile is scanned per action;
- each profile variant requests only page zero with at most ten results;
- vacancy details are fetched serially, without automatic retries;
- archived vacancies are skipped;
- raw vacancy descriptions remain only in local SQLite and never enter API
  responses, logs, fixtures, or Git.

The official documentation does not publish a numeric general rate limit for
vacancy search. The adapter therefore handles HTTP 429 and `Retry-After`, makes
no speculative retry, and reports the source failure without changing prior
Inbox records.

## Local configuration

The default file is `hh_source.local.yaml` and is ignored by Git. The checked-in
example is safe to copy:

```yaml
schema_version: 1
source:
  enabled: true
  registered_application: true
  user_agent: CareerRadar/0.1 (contact@example.com)
```

Missing, disabled, or unconfirmed configuration yields `blocked` before any
network request. The adapter has no OAuth flow in this slice and never reads or
stores HH login credentials, passwords, access tokens, or API keys.

## Adapter contract

`HeadHunterAdapter.collect(query)` returns validated `CollectedVacancy` records
with `source=hh`, `collection_method=api`, the HH vacancy ID, canonical
`alternate_url`, retrieval time, title, and full API description. External JSON
is untrusted: response shape, bounded strings, IDs, URLs, and redirect targets
are validated before persistence.

Search text is deterministic: the quoted title phrase followed by the selected
skill aliases and exclusions. Query parameters are fixed to page zero, ten
results, the recent seven-day window, and publication-time ordering. The base
URL is not configurable.

## Scan contract

`POST /api/scans` accepts exactly `{ "profileId": "..." }`. It returns a
versioned report with one source status:

- `completed`: all variants were collected and imported;
- `partial`: at least one variant succeeded and another failed;
- `blocked`: no request was made because local authorization/configuration is
  incomplete;
- `failed`: the configured source failed before producing usable observations.

Each source report contains counts and a bounded safe message, never query URLs,
response bodies, vacancy descriptions, local paths, or configuration values.
Repeated HH IDs use the existing deterministic Inbox upsert semantics.

## Failure and privacy rules

- HTTP status and official error category are mapped to stable local messages.
- Redirects outside `https://api.hh.ru` are rejected.
- One invalid vacancy is skipped and counted; it cannot corrupt other records.
- A failed scan does not delete or rewrite prior Inbox entries.
- Private career-profile values affect matching in memory only and are not
  included in scan reports or stored match snapshots.
- Scheduled scans, OAuth, archival cleanup, Habr Career, and fuzzy cross-source
  deduplication remain outside this slice.

## Official references

- HeadHunter API terms: https://hh.ru/article/15116
- OpenAPI reference: https://api.hh.ru/openapi/redoc
- Official API repository: https://github.com/hhru/api
- Authorization: https://github.com/hhru/api/blob/master/docs/authorization.md
- Errors: https://github.com/hhru/api/blob/master/docs/errors.md
- Vacancies: https://github.com/hhru/api/blob/master/docs/vacancies.md

## Acceptance

- No configuration or unconfirmed registration performs zero network calls.
- Contract fixtures cover successful search/detail responses, malformed data,
  archived vacancies, unsafe redirects, 429, and non-JSON failures.
- A scan imports deduplicated HH vacancies through the existing matcher/store.
- Source failure is visible and prior Inbox state remains intact.
- The browser action exposes selected-profile progress and a final source result.
