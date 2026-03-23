# External Demo Script

This script is for truthful external demos. It is designed to show the system as a serious local research OS, not as an autonomous trading product.

Canonical inspection routes used below include `GET /system/manifest`, `GET /portfolio/proposals`, `GET /reports/proposals/{portfolio_proposal_id}/scorecard`, and `GET /reviews/queue`.

When the script uses `make api`, keep that server running in a separate terminal while you issue the HTTP inspection commands.

Use `make demo` for the lighter baseline walkthrough. Use `make final-proof` when you want the strongest single build-cycle proof artifact, including the explicit approval-only paper-ledger appendix.

## Founder / YC Track

**Target duration:** 8-10 minutes

**Exact commands**

```bash
anhf manifest
anhf capabilities
make final-proof
make api
curl -s http://127.0.0.1:8000/system/manifest
curl -s http://127.0.0.1:8000/reviews/queue
curl -s http://127.0.0.1:8000/portfolio/proposals
PORTFOLIO_PROPOSAL_ID=<paste from previous output>
curl -s http://127.0.0.1:8000/reports/proposals/${PORTFOLIO_PROPOSAL_ID}/scorecard
```

**What to show**

1. Show `anhf manifest` and `anhf capabilities` first to anchor the discussion in real services and workflows rather than slides.
2. Run `make final-proof` to prove the current local end-to-end path exists and that the repo can extend it into an explicit approval-only paper-ledger appendix.
3. Start the API and show `GET /system/manifest` to demonstrate that the platform exposes an honest inspection surface.
4. Show `GET /reviews/queue` and `GET /portfolio/proposals` to make the review-bound stopping point explicit.
5. Show the proposal scorecard endpoint to demonstrate that the system produces inspectable downstream artifacts, not just a demo narrative.

**Safe claims to make**

- The repo already has a real typed artifact chain from ingestion to review-bound portfolio proposals.
- Human review is a core product boundary, not a future compliance add-on.
- The system is strongest on traceability, timing discipline, and workflow structure.
- The demo proves coherent workflow wiring and inspectability.
- The platform is packaging research operations, not pretending to automate live trading.

**Claims that must not be made**

- Do not claim alpha, Sharpe, hit rate, or any validated return profile.
- Do not claim this is a live trading system or a broker-connected execution stack.
- Do not claim paper trading is realistic execution simulation.
- Do not imply the missing eligibility gate is already solved.
- Do not present the local demo as production readiness.

## Engineer / Infra Track

**Target duration:** 10-12 minutes

**Exact commands**

```bash
anhf capabilities
anhf manifest
make final-proof
make api
curl -s http://127.0.0.1:8000/system/manifest
curl -s http://127.0.0.1:8000/system/capabilities
curl -s http://127.0.0.1:8000/reviews/queue
curl -s http://127.0.0.1:8000/portfolio/proposals
PORTFOLIO_PROPOSAL_ID=<paste from previous output>
curl -s http://127.0.0.1:8000/reports/proposals/${PORTFOLIO_PROPOSAL_ID}/scorecard
```

**What to show**

1. Start with `anhf capabilities` and call out the service boundaries: data quality, evaluation, operator review, reporting, paper ledger, and daily workflow.
2. Run `make final-proof` and point out that the default branch stays review-bound while the appendix only proceeds through explicit approvals.
3. Show `anhf manifest` and `GET /system/manifest` to demonstrate that the interface surface is generated from the real service registry.
4. Show the review queue and proposal listing endpoints to prove the API is not just health checks.
5. Show a proposal scorecard and explain that it links back to construction, risk, validation, and reporting artifacts.

**Safe claims to make**

- The repo has explicit service boundaries and typed schemas instead of one opaque orchestration file.
- Validation, monitoring, reporting, and review are real subsystems with persisted artifacts.
- The API and CLI are now coherent and honest local interfaces over the same workflows.
- The platform is inspectable enough for skeptical technical review.
- The main technical debt is visible rather than hidden.

**Claims that must not be made**

- Do not claim this is production infrastructure.
- Do not imply the local filesystem is a durable storage strategy.
- Do not describe the API as a secure or multi-tenant control plane.
- Do not claim snapshot-native selection is complete.
- Do not claim all readiness and policy decisions are already hard-enforced.

## Quant / Risk Track

**Target duration:** 12-15 minutes

**Exact commands**

```bash
make final-proof
make daily-run
make api
curl -s http://127.0.0.1:8000/reviews/queue
curl -s http://127.0.0.1:8000/portfolio/proposals
PORTFOLIO_PROPOSAL_ID=<paste from previous output>
curl -s http://127.0.0.1:8000/reports/proposals/${PORTFOLIO_PROPOSAL_ID}/scorecard
curl -s http://127.0.0.1:8000/system/manifest
```

**What to show**

1. Run `make final-proof` to establish the deterministic local path and the explicit approval-only appendix.
2. Run `make daily-run` to show that the operating workflow is review-bound and often ends in `attention_required`, which here is a visible stop state rather than fake “success.”
3. Show `GET /reviews/queue` to make clear that proposals and trades do not skip human review.
4. Show `GET /portfolio/proposals` and then the proposal scorecard to surface constraint handling, warnings, and measured dimensions.
5. Use `GET /system/manifest` at the end to show that the system exposes its real operating surface and is not hiding unsupported capabilities.

**Safe claims to make**

- The system preserves evidence lineage, review state, and proposal/risk context.
- Backtests are exploratory and paper trading is approval-gated.
- Construction, reconciliation, and reporting are inspectable rather than narrative-only.
- The workflow is designed to surface uncertainty and stop states instead of smoothing them over.
- The platform is suitable for scrutiny about process integrity, not for performance marketing.

**Claims that must not be made**

- Do not claim realistic market microstructure or live execution semantics.
- Do not claim the paper ledger is broker-verified or performance-reporting quality.
- Do not claim a validated edge from the demo or current backtests.
- Do not claim evaluation is already a hard promotion gate.
- Do not suggest the current risk layer is institutional risk infrastructure.
