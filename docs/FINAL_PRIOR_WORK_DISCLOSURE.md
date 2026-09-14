# Final prior-work disclosure

## Detailed version

PrizeHunter AWS Edition builds on prior PrizeHunter product research and a Google-based prototype. The product problem, provider-neutral PrizeHunter Core, reusable schemas and compatibility fixtures predate this AWS edition. They are legitimate reused work, not newly authored solely for this submission.

Core's prior implementation checkpoint is `1e79cc177c7dc451fdb0206ed6b428ad9b3b89cf` (2026-09-08). The included export is pinned to `f269f7f3af4cf61f79771d63bcf3af0acf356955`: 16 package files plus 5 tests/fixtures, 21 original byte hashes in `SOURCE_MANIFEST.json`. Verification does not require the private source projects. Core was not re-extracted or redesigned during the AWS work. An additional MIT LICENSE file for the authorized distribution does not modify those 21 files.

AWS Edition work implemented on September 13–14 includes the one-agent Strands runtime and structured-output seam, gated AWS Bedrock adapter, bounded HTTP/PDF retrieval integration, run-once local Opportunity Watch, browser/profile mapping and test-build presentation, AWS-specific tests, packaging, public-release review and submission materials. Profile UX borrows interaction ideas from the earlier Google prototype; the AWS transport uses the existing Core contracts. No earlier Google results, users, scores or operational metrics are presented as newly achieved by AWS.

The original Google submission and PrizeHunter_NEXT remain private/read-only and are not relicensed, pushed or deployed by this release. Public Git history is a separately reviewed lineage excluding private working material; a fresh history does not erase provenance or imply a from-zero build.

MIT covers author-owned code in this AWS distribution under the author's explicit authorization, including the Core export. Third-party software retains its own notices/licenses, and fetched website text belongs to its owners. Private account/model traces and full fetched pages are not published wholesale.

This disclosure is not a determination that reuse satisfies every contest rule and does not claim organizer approval. HUMAN CONFIRM: review final eligibility, prior-work presentation and any required organizer clarification before submitting. The fictional Taiwan demo is not proof of the author's identity or eligibility.

## Concise Devpost-ready version

PrizeHunter AWS Edition builds on earlier PrizeHunter research, a Google-based prototype and an existing provider-neutral Core, including reused schemas and compatibility fixtures. The AWS-specific work adds a one-agent Strands implementation, gated Bedrock integration, bounded retrieval, local Opportunity Watch, the AWS browser/profile experience, tests and submission packaging. The pinned Core is preserved unchanged and its provenance is documented. This is not a clean-room or entirely new-from-zero project, and no organizer approval of reuse is claimed. MIT applies to author-owned code in this distribution; third-party notices are retained.

Evidence: [SOURCE_MANIFEST](../SOURCE_MANIFEST.json), [prior record](PRIOR_WORK.md), [Core pin verifier](../scripts/verify_manifest.py), [claims C22](FINAL_CLAIMS_MATRIX.md).
