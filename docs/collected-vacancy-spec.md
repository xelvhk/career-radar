# Normalized Collected Vacancy Contract

## Objective

Define the source-neutral boundary between vacancy collectors and the existing
deterministic matcher. Every collected vacancy must retain enough provenance to
explain where and when it was obtained, while exposing a stable identity for
later local persistence and deduplication.

This slice is offline and additive. It does not perform network collection,
persist vacancy content, deduplicate records across different sources, or change
matching and evidence-disclosure rules.

## Contract

`normalize_collected_vacancy(...)` accepts untrusted adapter output and returns
an immutable `CollectedVacancy` with these fields:

| Field | Meaning |
|---|---|
| `id` | `vac-` plus the full SHA-256 digest of the versioned identity key |
| `source` | Lowercase kebab-case source identifier, for example `hh` |
| `source_vacancy_id` | Source-native identifier when available |
| `source_url` | Canonical HTTPS source URL when available |
| `retrieved_at` | Timezone-aware retrieval time normalized to UTC |
| `collection_method` | `api`, `browser`, `manual_url`, or `manual_text` |
| `title` | Trimmed vacancy title, at most 300 characters |
| `description` | Trimmed untrusted vacancy text, at most 200,000 characters |

The stable dictionary representation uses `recordVersion: 1`, camelCase field
names, an explicit nested `source` object, and an RFC 3339 `retrievedAt` value
ending in `Z`. Nullable source fields remain present so consumers see one shape.

## Deterministic Identity

Identity uses the first available key in this order:

1. `source` plus `source_vacancy_id`;
2. `source` plus canonical `source_url`;
3. `source` plus normalized title and description, only for `manual_text`.

The identity key begins with `collected-vacancy:v1`, then is hashed with
SHA-256. Retrieval time and collection method are deliberately excluded, so a
later observation of the same source vacancy keeps the same ID. When a native
source ID exists it takes precedence over URL changes. Content fallback collapses
whitespace and case-folds text before hashing.

URL canonicalization lowercases the scheme and host, removes fragments and the
default HTTPS port, and preserves the path and query. Collector adapters should
prefer native IDs; cross-source similarity and tracking-query removal belong to
the later deduplication policy.

## Validation and Safety

- All external values are validated at the normalization boundary.
- Retrieval timestamps must be timezone-aware; returned values are UTC.
- URLs must use HTTPS and must not contain credentials.
- `api`, `browser`, and `manual_url` records require a native ID or source URL.
- Only `manual_text` may use content identity when no source locator is known.
- Vacancy content is data, never instructions, and is not executed or fetched.
- The matcher input contains only title and description; provenance metadata is
  not mixed into requirement extraction.
- No complete third-party vacancy text is added to repository fixtures or docs.

Invalid input raises `ValueError` with a stable, field-specific message.

## Project Structure and Style

- `career_radar/collected_vacancy.py` — immutable model, validation, identity,
  serialization, and matcher-text projection.
- `tests/test_collected_vacancy.py` — pure contract tests with sanitized content.
- `docs/implementation-plan.md` — completion state for this roadmap increment.

The implementation uses the standard library, typed frozen dataclasses, pure
functions, snake_case Python fields, and camelCase serialized fields.

## Commands and Testing

```bash
python3 -m unittest tests.test_collected_vacancy -v
python3 scripts/validate_data.py
python3 -m unittest discover -s tests -v
```

Tests must prove native-ID precedence, deterministic content fallback, URL
canonicalization, UTC serialization, matcher-input isolation, and rejection of
invalid provenance, timestamps, methods, URLs, and content bounds.

## Boundaries

- Always: validate collector output, retain provenance, keep identity versioned,
  preserve local-first handling, and run the complete suite before push.
- Ask first: add persistence, dependencies, network access, or source-specific
  collection behavior.
- Never: store credentials/session payloads, bypass source controls, execute
  vacancy content, or commit complete third-party descriptions.

## Success Criteria

- Equivalent observations of one source vacancy produce the same ID.
- Every accepted record has source, retrieval time, collection method, and a
  valid identity basis.
- One normalized record can feed the existing matcher without provenance text
  affecting extraction.
- Serialization is deterministic and documents the future persistence boundary.
- The full existing test and data-validation suite remains green.
