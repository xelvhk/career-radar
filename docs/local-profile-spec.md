# Spec: Private Local Career Profile

## Objective

Allow the local matcher to resolve mandatory experience, production, location,
and seniority constraints from user-confirmed facts without committing personal
data to the public evidence catalog.

## Contract

The optional profile is a UTF-8 YAML file passed explicitly to the CLI:

```bash
cp career_profile.local.example.yaml career_profile.local.yaml
python3 scripts/match_vacancy.py vacancy.txt --profile career_profile.local.yaml
```

Its schema is intentionally narrow:

```yaml
schema_version: 1
profile:
  commercial_years: null                 # integer 0..60 or null
  confirmed_production_experience: null  # true, false, or null
  current_country_code: null              # ISO 3166-1 alpha-2 or null
  target_seniority: []                    # junior, middle, senior, lead
```

`null` means unknown. Only an explicit `true` for production experience can
resolve a production requirement. The profile overlays a copy of
`career_goals.yaml` in memory; it is not written back and is never included in
JSON or Markdown reports.

## Boundaries

Always:

- validate profile shape and values at the file boundary;
- keep the profile optional, so matching without it remains deterministic;
- ignore the default `career_profile.local.yaml` path in Git;
- show unresolved constraints when data is absent or insufficient.

Ask first:

- add contact information, employment history, salary, passport, or other
  identity-sensitive fields;
- synchronize the profile to a cloud service or external job board.

Never:

- add a real local profile to version control;
- infer its values from projects, evidence, or vacancy content;
- emit its values in matcher output.

## Acceptance Criteria

- An omitted profile preserves existing match behavior.
- A valid profile can resolve only the constraints it explicitly covers.
- Invalid, non-UTF-8, or oversized profile files fail with concise errors that
  do not echo private content.
- The example profile validates but contributes no facts.
- Full repository validation and tests pass offline.
