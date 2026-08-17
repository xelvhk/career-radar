# Implementation Plan: Career Radar

## Architecture Decisions

- Start with versioned files and deterministic validation; add persistence only
  after real usage reveals query and privacy requirements.
- Keep evidence as a first-class entity referenced by skills and matching output.
- Treat model extraction as an untrusted adapter; deterministic scoring contracts
  remain independent of any model provider.
- Deliver vertical slices beginning with pasted vacancy text.

## Phase 0: Evidence Foundation

- [x] Define the product/data specification.
- [x] Add conservative project, skill, goal, and evidence seed data.
- [x] Add deterministic validation and repository contract tests.
- [x] Separate verification from public/on-request/private disclosure.
- [x] Verify the three source repositories at pinned revisions.
- [x] Replace seed paths with an artifact-level evidence catalog.

Acceptance: checked-in records validate locally and contain no invented proof.

Verification: `python3 scripts/validate_data.py && python3 -m unittest discover -s tests -v`

## Phase 1: Manual Vacancy Match MVP

- [x] Define a normalized vacancy contract and safe text-ingestion boundary.
- [x] Extract requirements from pasted text with a deterministic/manual fallback.
- [x] Calculate technical, domain, seniority, evidence, direction, location, and
      salary dimensions separately.
- [x] Present requirement-to-evidence mapping, gaps, confidence, and an
      `APPLY`/`REVIEW`/`SKIP` recommendation with explainable weights.
- [x] Calibrate deterministic extraction against the first eight sanitized real
      vacancies without changing weights or inventing career history.

Acceptance: one pasted vacancy produces a reproducible score breakdown and never
promotes a pending evidence item as verified.

## Phase 2: Hybrid Vacancy Watchlist

Product direction: [`ideas/hybrid-vacancy-watchlist.md`](ideas/hybrid-vacancy-watchlist.md).

### Phase 2A: Local Watchlist Vertical Slice

- [ ] Define saved search profiles generated from verified skills and explicit
      query exclusions.
- [ ] Define a normalized collected-vacancy contract with source provenance,
      retrieval time, collection method, and deterministic identity.
- [ ] Select local persistence only after documenting inbox, deduplication, and
      privacy requirements.
- [ ] Add a local panel with one `Scan vacancies` action, per-source progress,
      and isolated failure visibility.
- [ ] Route normalized vacancies through the existing matcher into an Opportunity
      Inbox ranked by `APPLY`, `REVIEW`, and `SKIP`.

Acceptance: one manual scan produces a persistent, deduplicated, explainable inbox
without storing credentials or changing evidence-disclosure rules.

### Phase 2B: Source Adapters

- [ ] Research current terms, official APIs, authentication boundaries, and rate
      limits before implementing each source.
- [ ] Implement HeadHunter as the first production-quality adapter.
- [ ] Preserve manual URL or text import as the universal fallback.
- [ ] Add Habr Career after the adapter contract and failure modes are proven.
- [ ] Add LinkedIn and Indeed sequentially, using an explicitly authorized browser
      session only where permitted and necessary.
- [ ] Retain source attribution and useful prior results when one adapter fails.

Acceptance: each enabled source has contract fixtures, rate-limit behavior,
provenance, and failure tests; no adapter failure corrupts prior inbox data.

### Phase 2C: Calibration and Scheduled Collection

- [ ] Review ranking quality against 20-30 real vacancies across the saved search
      profiles before changing weights or thresholds.
- [ ] Record false positives, false negatives, duplicate decisions, and unmapped
      requirements as calibration data.
- [ ] Add opt-in scheduled scans only after manual scans demonstrate useful signal.
- [ ] Surface last-success, last-failure, and stale-source state in the panel.

Acceptance: ranking changes are justified by labeled examples, and scheduled scans
are observable, rate-limited, and safe to rerun.

## Phase 3: Application Preparation

- [ ] Generate a requirement-to-evidence outline before prose.
- [ ] Produce editable cover-letter and CV suggestions with citations.
- [ ] Require human approval before export or sending.

Acceptance: every generated claim links to verified evidence; no external send is
automatic.

## Phase 4: Application CRM

- [ ] Track application stages, next actions, and outcome reasons.
- [ ] Store private application data outside the public repository.
- [ ] Report funnel conversion without exposing personal details.

Acceptance: state changes persist locally and privacy boundaries are tested.

## Phase 5: Market Intelligence

- [ ] Aggregate recurring gaps across suitable vacancies.
- [ ] Rank learning/project tasks by estimated opportunity impact and effort.
- [ ] Track whether completed evidence changes match coverage over time.

Acceptance: every recommendation shows sample size, time window, and affected
vacancies rather than presenting model intuition as market fact.

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Hallucinated experience | High | Verification states and claim-level constraints |
| Biased or opaque scores | High | Separate dimensions, explicit weights, explanations |
| Job-source restrictions | High | Official-source research before collectors |
| Personal-data leakage | High | Local/private runtime store; sanitized public fixtures |
| Premature infrastructure | Medium | Files first; database only after demonstrated need |
| Stale market conclusions | Medium | Time windows, sample sizes, source provenance |

## Checkpoints

- Foundation: contracts and checked-in data pass local validation.
- MVP: pasted vacancy flows end-to-end with no external dependency required.
- Watchlist: one action creates a persistent, deduplicated, explainable inbox.
- Collection: one authorized source works reliably before adding another.
- Applications: a human reviews all claims and actions before export.
- Intelligence: recommendations are reproducible from stored observations.
