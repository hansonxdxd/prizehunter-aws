# Prior Work Disclosure

PrizeHunter AWS Edition builds on prior PrizeHunter product research and a Google-based prototype. Its provider-neutral Core, schemas and compatibility fixtures existed before this AWS edition. The project is not presented as clean-room, entirely new-from-zero work, or organizer-approved reuse.

| Component | Provenance | Treatment in this distribution |
| --- | --- | --- |
| Product problem and research | Prior PrizeHunter research / Google prototype | Disclosed prior work; no Google Edition outcomes are attributed to AWS |
| Provider-neutral Core | Implementation `1e79cc177c7dc451fdb0206ed6b428ad9b3b89cf`, 2026-09-08 | Reused unchanged, not re-extracted |
| Pinned export | Source HEAD `f269f7f3af4cf61f79771d63bcf3af0acf356955` | 16 Core package files and 5 tests/fixtures; 21 byte hashes in the manifest |
| Compatibility fixtures | Existing synthetic contract and conflict fixtures | Historical names retained honestly; no claim of live AWS execution |
| AWS-specific work | 2026-09-13–14 | One Strands agent, structured-output seam, Bedrock adapter, bounded retrieval, local Watch, browser test build and submission-specific tests/material |

`SOURCE_MANIFEST.json` precisely identifies the export. `python scripts/verify_manifest.py` validates all hashes without reading a private repository. The package depends on the included `packages/core`, never an absolute path to another checkout.

The original Google submission and PrizeHunter_NEXT remain private and unchanged. Their `.git` history, credentials, deployment, videos and internal handoffs are not part of this release. The new public lineage is a publication hygiene measure, not a claim that prior code was newly authored.

On 2026-09-14 the author explicitly authorized MIT for author-owned code in this AWS distribution, including the Core export. The root LICENSE and an identical additional `packages/core/LICENSE` provide this grant without modifying any of the 21 pinned source files; the latter also carries the notice into standalone Core builds. It does not change licensing in the private source repositories or replace any third-party license.

Third-party distributions are installed from the lockfile rather than vendored. Their license metadata and notice locations are preserved in `THIRD_PARTY_INVENTORY.json`; redistribution must retain applicable notices. Website content belongs to its respective owners. Full fetched rules pages and private model traces are excluded from the public candidate.
