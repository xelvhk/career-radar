# Hybrid Vacancy Watchlist

## Status

Accepted product direction on 2026-08-14.

## Problem Statement

How might Career Radar let one user search several job sites with one action,
using evidence-backed skill profiles, while keeping collection failures,
authentication, and site restrictions isolated from deterministic matching?

## Recommended Direction

Add a local Vacancy Watchlist that runs saved search profiles through independent
source adapters, normalizes and deduplicates the results, and sends each vacancy
through the existing evidence-aware matcher. The user sees an Opportunity Inbox
ranked by `APPLY`, `REVIEW`, and `SKIP`, with per-source status and explainable
evidence or gaps.

Use a hybrid collection boundary: prefer an official API when its terms and
capabilities fit the use case; otherwise use an explicitly authorized browser
session. Manual URL or text import remains the fallback. The panel must never
store site passwords or attempt to bypass CAPTCHA or anti-bot controls.

Roll sources out sequentially: HeadHunter first, then a generic manual fallback,
Habr Career, LinkedIn, and Indeed. The adapter contract should make later foreign
sources additive rather than requiring changes to matching logic.

## Key Assumptions to Validate

- [ ] Queries generated from verified skills produce relevant results. Test with
      20-30 vacancies across the initial search profiles.
- [ ] A shortlist of 10-20 explained matches is more useful than a large raw
      result set. Review top-ranked results manually.
- [ ] Official APIs or an authorized browser session can retrieve enough vacancy
      detail without prohibited automation. Verify current source terms before
      implementing each adapter.
- [ ] Cross-source deduplication can group the same vacancy without hiding
      materially different roles. Test deterministic identity and similarity
      rules against fixtures.
- [ ] Local persistence is sufficient for the first user and can keep credentials
      outside the application store.

## MVP Scope

- Local web panel with saved profiles such as `AI Backend`, `RAG / LLM Engineer`,
  `Python / FastAPI`, and `Document AI`.
- One `Scan vacancies` action with visible progress and isolated source failures.
- One production-quality HeadHunter adapter after official-source research.
- Manual URL or text import as a universal fallback.
- Normalized vacancy records with source URL, source vacancy ID when available,
  retrieval time, and collection method.
- Deterministic deduplication and an Opportunity Inbox.
- Existing evidence mapping, gaps, confidence, and
  `APPLY` / `REVIEW` / `SKIP` ranking.
- Local result storage with no site passwords or raw private session data.

## Not Doing (and Why)

- **All source adapters at once** — one reliable adapter proves the contract and
  failure model before multiplying external dependencies.
- **Automatic applications or messages** — every external action remains under
  explicit human control.
- **CAPTCHA or anti-bot bypass** — unsupported technically and outside the product
  boundary.
- **Cloud account synchronization** — local-first storage is sufficient for the
  initial user and reduces privacy risk.
- **Scheduled scans in the first increment** — manual scans validate relevance
  before background automation creates noise.
- **LLM search or ranking** — deterministic queries and matching must be calibrated
  first; a model may later be an untrusted extraction adapter.

## Success Criteria

- One action searches the enabled sources and preserves usable results when one
  source fails.
- Every vacancy retains source provenance and collection time.
- Duplicate results do not create duplicate inbox entries.
- The top-ranked results are manually judged relevant on a 20-30 vacancy sample.
- Private evidence disclosure remains unchanged from Manual Vacancy Match.
- No source credential, private session payload, or local absolute path is stored
  in checked-in data or reports.

## Open Questions

- Which HeadHunter access method is allowed and adequate under its current terms?
- Which local persistence format best fits deduplication and inbox state?
- Which query variants and exclusions belong in each saved search profile?
- What relevance threshold should hide a result from the default inbox view?
