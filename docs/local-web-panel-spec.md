# Local Web Panel Specification

## Goal

The local web panel is a thin browser surface over the existing
`OpportunityStore`. It completes the manual workflow without adding collection
adapters: paste a vacancy, match and persist it, review the explained ranking,
then record a human inbox status.

The panel is not a network collector, scheduler, application CRM, or document
generator. `Scan vacancies` remains disabled until at least one researched
source adapter exists; manual paste is the only ingestion action in this slice.

## Runtime boundary

- The server binds only to loopback (`127.0.0.1`, `localhost`, or `::1`).
- The default database remains `career_radar.local.sqlite3`; `--db` selects a
  different local file and `--profile` applies the existing private overlay at
  match time.
- HTML, CSS, and JavaScript are repository-owned static assets. The panel makes
  no external requests and loads no remote fonts, scripts, or analytics.
- The browser API never returns the stored vacancy description or private
  profile values. It returns the existing versioned match snapshot only.
- Mutating requests require the same local origin and the
  `X-Career-Radar-Request: 1` header. CORS is not enabled.
- Responses use a restrictive Content Security Policy, deny framing, disable
  MIME sniffing, avoid referrer disclosure, and are not cached.

## HTTP contract

All JSON responses are versioned with `panelVersion: 1`. Errors have one stable
shape and never include vacancy text, profile values, URLs, local paths, or
tracebacks:

```json
{"error":{"code":"VALIDATION_ERROR","message":"Invalid request"}}
```

### Read operations

```text
GET /api/opportunities?recommendation=APPLY&status=new&limit=20
GET /api/opportunities/{vacancy_id}
```

The list follows the store's stable ordering: `APPLY`, `REVIEW`, `SKIP`, then
score and last-seen time descending. The detail response includes evidence
mapping, reasons, gaps, confidence, provenance, and the human status.

### Mutating operations

```text
POST  /api/opportunities
PATCH /api/opportunities/{vacancy_id}
```

`POST` accepts JSON with `text` plus optional `source`, `sourceVacancyId`,
`sourceUrl`, and `retrievedAt`. Text is UTF-8 JSON content, 1-800,000 bytes,
with the first non-empty line used as the title. URL safety and deterministic
identity use the existing collected-vacancy and store contracts.

`PATCH` accepts exactly one user decision:

```json
{"status":"shortlisted"}
```

Allowed values are `new`, `shortlisted`, and `dismissed`. Updating status never
changes the matcher recommendation.

## User experience

- Desktop uses a ranked list and detail workspace; small screens stack them.
- Recommendation and human status are visually and semantically distinct.
- Filters update the Inbox without losing the selected opportunity.
- The import dialog has labelled fields, inline validation, explicit progress,
  and an accessible completion/error announcement.
- An empty database explains how to add the first vacancy. Error states keep
  prior useful data visible and offer a retry.
- All actions are keyboard reachable, focus is visible, headings are ordered,
  and status changes are announced through an ARIA live region.

## Acceptance

- A fresh local database renders a useful empty state.
- Manual paste creates or updates one deterministic Inbox entry and selects it.
- List filters, explained detail, and status changes work end to end.
- Full vacancy text and private profile values do not appear in API responses,
  HTML, browser logs, or committed fixtures.
- Unsafe URLs, oversized text, invalid filters/statuses, unknown IDs, malformed
  JSON, incompatible databases, non-loopback hosts, and cross-origin mutations
  fail with safe structured errors.
- Unit/integration tests, repository validation, and real desktop/mobile browser
  checks pass with a clean console and no external requests.
