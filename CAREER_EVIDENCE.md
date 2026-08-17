# Career Evidence Register

This is the human review layer for `projects.yaml` and `skills.yaml`. Structured
data remains the source of truth for matching. No repository artifact is treated
as production experience.

## Evidence policy

- `verified` means the artifact exists at the pinned commit and directly supports
  the claim.
- `public` means the artifact is safe to link from a public application.
- `on_request` means: **private repository; walkthrough or selected code samples
  available on request**.
- `private` means the artifact must not appear in generated output.
- A project or README demonstrates implementation, not production operation.
- Metrics require a reproducible command, fixture description, and dated result.

## Verified projects

| Project | Repository | Access | Pinned revision | Strong evidence |
|---|---|---|---|---|
| ContractOps AI | `xelvhk/contractops_ai` | On request | `deadee8` | `src/contractops/rag/retrieval/hybrid.py`, `docs/evaluation.md`, `src/contractops/cli/retrieval_benchmark.py` |
| Onboardica | `xelvhk/onboardica` | On request | `5f46688` | `apps/api/app/services.py`, `apps/api/tests/test_tenant_isolation.py`, `apps/web/app/page.tsx` |
| Onboardica public case study | [`xelvhk/aboutme`](https://github.com/xelvhk/aboutme) | Public | `ad3882a` | [Sanitized case study](https://xelvhk.github.io/aboutme/#/case-studies/onboardica), `src/pages/onboardicaCaseStudy.jsx`, sanitized screenshots |
| Vasya AI | [`xelvhk/vasya_ai`](https://github.com/xelvhk/vasya_ai) | Public | `fd8e641` | `services/ollama_client.py`, `apps/api/rate_limit.py`, `docs/adr/ADR-003-public-app-and-private-user-data.md` |

GitHub visibility and pinned revisions for the original private project set were checked on 2026-08-12. The sanitized Onboardica public case study was checked on 2026-08-17. Visibility must be refreshed before generating a real application.

## Skill evidence matrix

| Skill | Strongest evidence | Project | Representative artifacts |
|---|---|---|---|
| Python | Public | Vasya AI | `apps/api/main.py`, `core/orchestrator.py` |
| FastAPI | Public | Vasya AI | `apps/api/main.py`, `apps/api/routes/chat.py` |
| REST API design | Public | Vasya AI | `apps/api/routes/chat.py`, `tests/test_api_security_e2e.py` |
| PostgreSQL | On request | ContractOps / Onboardica | `src/contractops/infrastructure/database/session.py`, `apps/api/app/core/database.py` |
| SQLAlchemy | On request | ContractOps / Onboardica | `src/contractops/infrastructure/database/session.py`, `apps/api/app/domain.py` |
| Docker and Compose | On request | ContractOps / Onboardica | `docker-compose.yml`, `docker-compose.prod.yml` |
| RAG | On request | ContractOps AI | `src/contractops/rag/question_answering/service.py`, `apps/api/routers/questions.py` |
| Hybrid search | On request | ContractOps AI | `src/contractops/rag/retrieval/hybrid.py`, `tests/unit/test_hybrid_retrieval.py` |
| Qdrant | On request | ContractOps AI | `src/contractops/infrastructure/vector_store/qdrant_store.py`, `src/contractops/infrastructure/vector_store/qdrant_sparse_retriever.py` |
| Reranking | On request | ContractOps AI | `src/contractops/rag/retrieval/hybrid.py`, `tests/unit/test_hybrid_retrieval.py` |
| LLM/retrieval evaluation | On request | ContractOps AI | `docs/evaluation.md`, `evaluation/fixtures/golden_questions.jsonl`, `tests/unit/test_evaluation_harness.py` |
| Multi-tenant systems | On request | Onboardica | `apps/api/app/domain.py`, `apps/api/tests/test_tenant_isolation.py` |
| Onboarding analytics | On request | Onboardica | `apps/api/app/services.py`, `apps/api/tests/test_proficiency.py` |
| Gamification | On request | Onboardica | `apps/api/app/services.py`, `apps/api/tests/test_gamification.py` |
| Next.js and TypeScript | On request | Onboardica | `apps/web/app/page.tsx`, `apps/web/package.json` |
| Local LLM integration | Public | Vasya AI | `services/ollama_client.py`, `apps/api/routes/chat.py` |
| Local-first architecture | Public | Vasya AI | `docs/adr/ADR-003-public-app-and-private-user-data.md`, `services/project_registry_store.py` |
| API security controls | Public | Vasya AI | `apps/api/deps.py`, `apps/api/rate_limit.py`, `tests/test_api_security_e2e.py` |
| External integration boundaries | Public | Vasya AI | `services/github_obsidian_sync_service.py`, `docs/adr/ADR-003-public-app-and-private-user-data.md` |
| Agent orchestration | Public | Vasya AI | `core/orchestrator.py`, `apps/api/routes/chat.py` |
| Kubernetes | Gap | None | No verified artifact |
| AWS | Gap | None | No verified artifact |
| Observability | Gap | None | No verified artifact |

## Application rules

- Public evidence may be linked directly. For Onboardica, link the sanitized public case study, not the private source repository.
- On-request evidence may be summarized factually, followed by the approved
  availability statement; private source links must not be presented as public.
- Gap skills must not be rewritten as practical experience.
- Generated claims must map to the exact artifact list in `skills.yaml`.
- No claim may use the `production` level until operational context is recorded
  separately and verified.

## Verification commands

```bash
python3 scripts/validate_data.py
python3 scripts/audit_sources.py \
  --repo contractops-ai=/path/to/document_ops_ai \
  --repo onboardica=/path/to/onboardica \
  --repo vasya-ai=/path/to/ai_pal
python3 -m unittest discover -s tests -v
```
