# Devpost draft — truthful test-build fallback

**Publication status:** Draft only; not submitted. Real Bedrock inference and AWS deployment are unresolved. This limitation must remain in the public description and testing instructions until verified. Repository: https://github.com/hansonxdxd/prizehunter-aws . Demo video: not yet recorded. Hosted AWS URL: none.

## Inspiration

Finding a competition is easy. Understanding its rules, checking whether you qualify and deciding whether it deserves your time is much harder. Prior PrizeHunter research explored this gap. The AWS Edition focuses on evidence-grounded decisions and remembering which opportunities have already been reviewed.

## What it does

PrizeHunter turns competition evidence into eligibility, Fit, recommendation and a human-reviewed Action Plan. Literal claims retain source support, uncertainty remains visible and confirmed blockers stop downstream inference. Opportunity Watch saves a goal's state, suppresses repeated decisions and detects controlled rule/deadline changes while preserving the last successful baseline after retrieval failure. It does not send notifications or run a scheduler.

The browser accepts residence, citizenship, participant facts and Fit preferences through progressive disclosure into the existing Core contracts. Blank facts remain unknown. Custom-profile eligibility is checked against synthetic evidence, while arbitrary personalized Fit and Plan are explicitly unavailable offline. The original scripted demo remains a one-click saved example.

## How we built it

We connected one Strands agent to bounded evidence tools and the existing provider-neutral PrizeHunter Core. The agent produces schema-constrained drafts; deterministic Core guards validate evidence, eligibility and final decisions. The AWS Edition adds a gated Bedrock adapter, HTTP/PDF retrieval controls, local JSON Watch state and a compact Python browser test build. Current verification uses Strands with scripted model responses. No real Bedrock request or AWS deployment has succeeded yet because AWS account verification is pending, despite successful temporary login and STS identity verification.

## Challenges

Strict typed schemas must survive the SDK tool boundary without weakening Core's contracts. Another challenge is separating literal textual support from an uncertain interpretation, and preserving useful state when retrieval fails. AWS account verification blocked live validation, so we retained a reproducible test build and documented the missing live proof instead of presenting replay as inference.

## Accomplishments

The test build runs a real Strands tool loop, preserves the reused Core byte-for-byte, blocks downstream inference on a synthetic hard blocker and demonstrates Watch counts of 1, 0, 1, 0, 0 across first, duplicate, controlled change, repeat and failed retrieval. The offline suite passes 90 tests with one paid live test skipped. Source provenance, setup, tests and limitations are available in the public repository.

## What we learned

Agent output becomes more useful when uncertainty is a first-class result and business gates remain outside model discretion. Reproducible replay is valuable for integration tests, but it cannot establish live model capability. Clear evidence levels make a prototype easier to assess honestly.

## What's next

After AWS finishes account verification, verify a bounded real Strands + Bedrock analysis on the official competition rules, validate Watch against that real baseline and deploy the smallest viable AWS-hosted demo. Broader discovery, scheduling and notifications are future possibilities, not current capabilities.

## Technologies

Python, Strands Agents SDK, Pydantic, BeautifulSoup, pypdf, pytest, uv and the provider-neutral PrizeHunter Core. Amazon Bedrock integration is implemented but **not verified live**. No AWS hosting service is claimed as actually deployed.

## Testing instructions

Clone the public repo, install Python 3.12 and uv, run `uv sync --frozen --python 3.12`, then `uv run --no-sync python -m prizehunter_aws.web --port 8080`. Open `http://127.0.0.1:8080/`, run the verified test build and inspect eligibility, recommendation, action plan and evidence. Try the synthetic hard blocker and the five Watch buttons in order. Tests: `uv run --no-sync pytest -ra`. The demo requires no AWS credentials or payment. All model responses in this release's demo are synthetic replay, not Bedrock inference. There is no public hosted endpoint or completed demo video yet.

## Prior Work Disclosure

PrizeHunter AWS Edition builds on prior PrizeHunter product research, a Google-based prototype and an existing provider-neutral PrizeHunter Core. The reused Core, research, schemas and fixtures are prior work where applicable. New AWS Edition work adds the Strands implementation, AWS integration adapter, Opportunity Watch and this submission-specific browser/testing/material work. It is not clean-room or entirely new-from-zero code. A new public Git lineage excludes private history while retaining exact source hashes and honest provenance. The private Google submission and PrizeHunter_NEXT were not modified or relicensed.
