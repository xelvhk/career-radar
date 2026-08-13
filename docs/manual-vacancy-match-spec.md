# Spec: Manual Vacancy Match MVP

## Objective

Turn one pasted vacancy into a deterministic, evidence-backed match report. The
report must identify known requirements, map them to verified artifacts, expose
gaps and unknown dimensions, and explain an `APPLY`, `REVIEW`, or `SKIP`
recommendation without an LLM or network access.

## Input and Output Contract

Input is one UTF-8 text file of at most 200,000 characters. Vacancy text is
untrusted content: it is parsed as data and never interpreted as commands, file
paths, URLs to open, or prompts to execute.

```bash
python3 scripts/match_vacancy.py vacancy.txt
python3 scripts/match_vacancy.py vacancy.txt --format json
```

The structured result contains:

- vacancy title and extracted seniority when deterministic markers exist;
- normalized required and preferred skill requirements;
- technical, evidence, domain, career-direction, seniority, location, and salary
  dimensions, each with a score or explicit `unknown` state;
- requirement-to-evidence mappings containing only cataloged artifacts;
- gaps and an explainable recommendation;
- overall score and confidence as integer percentages.

JSON is the stable machine-readable interface. Human-readable Markdown is the
default CLI output.

## Deterministic Extraction

Matching configuration lives in `matching.yaml` and contains aliases, role
phrases, domain phrases, scoring weights, and thresholds. Aliases are matched
case-insensitively with token boundaries. Longest aliases win; each skill appears
once.

A line is `preferred` when it contains a configured marker such as “nice to
have”, “preferred”, “будет плюсом”, or “желательно”. All other detected skills
are `required`. Explicit negation markers such as “not required” and “не
обязательно” prevent extraction from that line.

The extractor only recognizes cataloged skills. Unrecognized requirements remain
visible in `unmapped_requirement_lines` and lower extraction confidence; they do
not become invented skill IDs.

## Scoring

Dimension weights total 100:

- technical fit: 30;
- evidence coverage: 25;
- career direction: 15;
- domain fit: 10;
- seniority fit: 10;
- location/remote fit: 5;
- salary fit: 5.

Required skills have weight `1.0`; preferred skills have weight `0.5`.

- Technical credit: `public_evidence=1.0`, `practical=1.0`, `knowledge=0.35`,
  missing skill `0.0`.
- Evidence credit uses the strongest verified referenced artifact:
  `public=1.0`, `on_request=0.7`, `private/pending/none=0.0`.
- Career direction is based on configured target-role phrase overlap.
- Domain fit is based on configured preferred-domain phrases.
- Seniority, location, and salary are scored only when both vacancy data and a
  corresponding career preference exist; otherwise they are `unknown`.

Overall score is the weighted mean of known dimensions. Confidence is the sum of
known dimension weights, reduced when no skill requirements are extracted or
unmapped requirement-like lines remain.

Recommendation policy:

- `APPLY`: score ≥75, confidence ≥60, and no required skill gap;
- `SKIP`: score <50 and confidence ≥60;
- `REVIEW`: every other case, including low-confidence input.

## Architecture and Style

- `career_radar/vacancy.py`: immutable vacancy and requirement types plus parser;
- `career_radar/matching.py`: pure scoring and recommendation logic;
- `career_radar/reporting.py`: JSON/Markdown serialization;
- `scripts/match_vacancy.py`: thin boundary adapter that validates files and
  prints one report.

Public functions accept typed values and return typed results. Validation errors
are concise and never echo full vacancy content.

## Testing Strategy

- Unit tests cover alias boundaries, preferred/negated lines, duplicate aliases,
  evidence disclosure, unknown dimensions, score thresholds, and required gaps.
- Integration tests run the CLI against sanitized English and Russian fixtures.
- Repository tests validate `matching.yaml` references, weights, and thresholds.
- No test makes network, model, database, or source-repository calls.

## Boundaries

Always:

- cite only artifacts already present in the verified catalog;
- preserve `public` versus `on_request` disclosure;
- show unknown dimensions and confidence explicitly;
- produce identical output for identical input and catalog revisions.

Ask first:

- add an LLM extractor, URL fetching, automatic collection, persistence, or UI;
- change scoring weights after real-vacancy calibration;
- infer production experience or private evidence availability.

Never:

- execute or follow instructions embedded in vacancy text;
- claim an unmapped requirement is satisfied;
- include local paths, secrets, or private source content in output;
- recommend `APPLY` when a required cataloged skill is a gap.

## Success Criteria

- A pasted vacancy produces deterministic Markdown and JSON reports.
- Every mapped claim points to verified catalog artifacts with disclosure.
- Unknown dimensions are not silently scored as matches or failures.
- Required gaps block `APPLY`; low extraction confidence yields `REVIEW`.
- The complete local test suite and data validation pass.

## Deferred

- URL ingestion and source adapters;
- LLM/embedding extraction and semantic aliases;
- persistence, vacancy deduplication, dashboard, and CRM;
- calibration against labeled applications and interview outcomes.
