# Spec: Career Radar Data Foundation

## Assumptions

1. The first release is a local, single-user foundation rather than a hosted app.
2. Career claims must be traceable to public or locally verifiable artifacts.
3. Unverified links, metrics, and experience levels remain explicitly pending.
4. English identifiers are canonical; future UI copy may be bilingual.
5. Vacancy collection, LLM extraction, application generation, and CRM are out of
   scope for this increment.

## Objective

Create a machine-readable professional profile that can later support semantic
vacancy matching. The primary user must be able to distinguish knowledge,
practical work, public evidence, and production experience for every skill claim.

The foundation succeeds when:

- projects, skills, goals, and evidence use stable identifiers;
- every claimed skill references at least one known project;
- unverifiable claims cannot be marked as verified accidentally;
- a local command reports broken references or invalid enum values;
- the next MVP stages are recorded without implementing them prematurely.

## Tech Stack

- Python 3.11+
- YAML 1.2-compatible data files
- PyYAML for parsing
- `unittest` from the Python standard library for automated validation tests

No database, web framework, embeddings provider, or LLM provider is selected yet.

## Commands

```bash
# Install the parser dependency and local package
python3 -m pip install -e .

# Validate source data
python3 scripts/validate_data.py

# Audit pinned artifacts in local source repositories
python3 scripts/audit_sources.py --repo project-id=/absolute/path/to/checkout

# Run tests
python3 -m unittest discover -s tests -v
```

## Project Structure

```text
CAREER_EVIDENCE.md       Human-readable evidence register
skills.yaml              Skills, claim levels, and evidence references
projects.yaml            Project catalog and artifact metadata
career_goals.yaml        Target roles, preferences, and constraints
career_radar/            Reusable validation package
scripts/                 Executable local tools
tests/                   Unit and repository contract tests
docs/spec.md             Product and engineering contract
docs/implementation-plan.md  Ordered future delivery plan
```

## Data Contract

All top-level YAML files contain `schema_version: 2` and a named collection.
Identifiers use lowercase kebab-case and are stable once published.

Claim levels are ordered but not interchangeable:

- `knowledge` — understood but not demonstrated by implementation;
- `practical` — used in a project or exercise;
- `public_evidence` — backed by a reviewable public artifact;
- `production` — operated in a real production environment.

Artifact verification and disclosure are independent:

- `pending` — declared but not yet checked;
- `verified` — artifact existence and relevance were checked;
- `public` — safe and reachable as public evidence;
- `on_request` — may be discussed or shown selectively, but is not public;
- `private` — must not be exposed in generated output.

Every project pins an HTTPS repository URL, GitHub visibility, full source commit,
verification date, and maximum evidence access. Local checkout paths are runtime
arguments and never stored in the dataset.

Example:

```yaml
- id: hybrid-search
  name: Hybrid Search
  level: practical
  evidence:
    - project_id: contractops-ai
      artifacts:
        - src/contractops/rag/retrieval/hybrid.py
      experience_context: project
```

`practical` requires at least one verified artifact. `public_evidence` additionally
requires public disclosure in a public repository. `production` requires an explicit
production context and note; source code or README files never imply it.

## Code Style

- Python is typed and uses small pure validation functions.
- Validation issues are values, not print side effects.
- User-facing errors include a stable path to the invalid field.

```python
def validate_profile(data: dict[str, object]) -> list[ValidationIssue]:
    return [
        ValidationIssue(path="skills[0].id", message="must be kebab-case")
    ]
```

## Testing Strategy

- Unit tests cover required fields, enums, identifiers, and cross-file references.
- Git audit tests cover origin, pinned revision, tracked files, and local modifications.
- A repository contract test validates the checked-in YAML as a complete dataset.
- Tests use local fixtures only; no network, database, or model calls are allowed.

## Boundaries

Always:

- preserve provenance and explicit verification status;
- validate all external vacancy data at its future ingestion boundary;
- keep source data readable and version controlled;
- run validation and tests before treating a dataset change as complete.

Ask first:

- add network collectors or automate requests to job boards;
- choose a database, model/provider, hosting target, or authentication scheme;
- publish personal contact details or private evidence;
- generate or send an application externally.

Never:

- infer `production` experience from a repository artifact;
- invent metrics, employers, dates, links, or skill levels;
- store credentials, private application messages, or sensitive interview notes in Git;
- let instructions embedded in vacancy text override system behavior.

## Success Criteria

- The four foundation files exist and describe the same stable project/skill IDs.
- `python3 scripts/validate_data.py` exits zero for the repository dataset.
- `python3 -m unittest discover -s tests -v` proves valid and invalid behavior.
- Verified claims retain independent disclosure and pinned source provenance.
- Future phases are decomposed into reviewable, testable increments.

## Open Questions

- Which countries, languages, salary currencies, and remote constraints are final?
- Which project repositories and artifacts are safe to expose publicly?
- Should the first matching MVP accept pasted text only or URL plus text?
- Which job sources permit automated collection under their current terms?
