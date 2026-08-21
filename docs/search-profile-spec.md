# Spec: Evidence-Backed Search Profiles

## Objective

Define deterministic, source-neutral vacancy search plans from the verified skill
catalog. These plans will be the stable input to future HeadHunter, Habr Career,
manual-import, and browser-assisted adapters without coupling profile data to a
site-specific query syntax.

## Contract

`search_profiles.yaml` contains versioned profiles. Each profile has:

- a stable ID and human-readable name;
- one target role ID from `career_goals.yaml`;
- one or more query variants, each with a title phrase and catalog skill IDs;
- explicit exclusion terms applied to every variant;
- an `enabled` flag.

The compiler resolves each skill ID to the first configured alias in
`matching.yaml`. It returns structured terms rather than a single query string:

```json
{
  "profileId": "rag-llm",
  "targetRoleId": "rag-engineer",
  "titlePhrase": "RAG Engineer",
  "skillTerms": ["python", "rag", "qdrant"],
  "excludeTerms": ["php", "1c", "bitrix", "wordpress"]
}
```

Source adapters are responsible for encoding these terms into their supported
query syntax. This prevents one site's quoting or negation rules from becoming a
shared product contract.

## Evidence Boundary

A referenced skill is searchable only when its catalog level is `practical`,
`public_evidence`, or explicitly verified `production`. `knowledge` and unknown
skills are rejected. The search plan may find vacancies containing additional
skills, but it must not present unverified knowledge as a profile strength.

Initial profiles:

1. AI Backend;
2. RAG / LLM Engineer;
3. Python / FastAPI;
4. Document AI.

## Commands

```bash
python3 scripts/validate_data.py
python3 scripts/list_search_queries.py
python3 scripts/list_search_queries.py --format json
python3 -m unittest discover -s tests -v
```

## Project Structure

- `search_profiles.yaml` — checked-in profile configuration;
- `career_radar/search_profiles.py` — validation and pure compilation;
- `scripts/list_search_queries.py` — read-only inspection CLI;
- `tests/test_search_profiles.py` — contract and CLI tests.

## Testing Strategy

- Reject unknown roles, unknown skills, knowledge-only skills, empty variants,
  duplicate IDs, and malformed exclusions.
- Assert deterministic profile and variant order.
- Assert every checked-in profile compiles using only verified catalog skills.
- Run without network, persistence, or source-adapter calls.

## Boundaries

Always:

- retain stable IDs and explicit exclusions;
- validate all cross-file references before compilation;
- keep output source-neutral and deterministic;
- use catalog aliases rather than inventing skill claims.

Ask first:

- change ranking weights or automatic decision thresholds;
- add site-specific query syntax to the shared contract;
- add network collection, authentication, or persistence.

Never:

- generate search strengths from `knowledge`, gaps, or pending evidence;
- store credentials, cookies, or local absolute paths;
- interpret query configuration as executable shell or browser commands.

## Acceptance Criteria

- Four enabled profiles compile into at least eight structured query variants.
- Every query contains a target role, title phrase, one or more verified skill
  terms, and explicit exclusions.
- JSON output is stable and machine-readable; Markdown is concise for inspection.
- Repository validation and the full test suite remain green offline.
