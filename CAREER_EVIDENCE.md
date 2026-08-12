# Career Evidence Register

This file is the human review layer for `projects.yaml` and `skills.yaml`. A
claim is application-ready only when its evidence is relevant, safe to share,
and marked `verified` in the structured data.

## Verification rules

- `pending` means the artifact has not been checked. It must not be presented as
  proof in a generated application.
- `verified` means the artifact exists and directly supports the claim.
- `private` means the evidence may inform local matching but must not be included
  in public output.
- A public repository proves implementation, not automatically production use.
- Metrics require a reproducible command, dataset description, and dated result.

## Evidence inventory

| Project | Claim area | Candidate artifacts | Status | Verification needed |
|---|---|---|---|---|
| ContractOps AI | Document RAG pipeline | Repository URL, architecture docs | Pending | Confirm repository and exact implementation |
| ContractOps AI | Hybrid retrieval and reranking | `benchmark.py` | Pending | Run benchmark and document dataset/config |
| ContractOps AI | Evaluation | `EVALUATION.md`, `evaluation/results.json` | Pending | Confirm metrics, command, and result provenance |
| Onboardica | To be classified | None recorded | Pending | Add summary, repository, and reviewable artifacts |
| Vasya AI | To be classified | None recorded | Pending | Add summary, repository, and reviewable artifacts |

## Claim review queue

The initial profile proposes the following claims for verification:

- Backend: Python, REST API, PostgreSQL.
- AI engineering: RAG, hybrid search, Qdrant, reranking, evaluation.
- Infrastructure: Docker.
- Knowledge gaps or evidence gaps: Kubernetes, AWS, observability.

These entries are hypotheses until their referenced artifacts are checked. The
system must preserve that distinction in matching and application generation.

## Evidence acceptance checklist

For each claim:

- [ ] The project repository or private source is identified.
- [ ] The artifact exists at the recorded path or URL.
- [ ] The artifact demonstrates the named skill directly.
- [ ] The level is no stronger than the evidence supports.
- [ ] Public sharing is permitted and contains no secrets or personal data.
- [ ] Any metric includes reproduction instructions and context.
- [ ] `projects.yaml` and `skills.yaml` are updated together.

## Next verification pass

1. Locate the canonical ContractOps AI repository and verify the three proposed
   artifact paths.
2. Add concise, factual summaries and safe repository URLs for Onboardica and
   Vasya AI.
3. Replace empty artifact lists for Python, REST API, PostgreSQL, Docker, RAG,
   and Qdrant with exact paths.
4. Downgrade or remove any claim that cannot be substantiated.
