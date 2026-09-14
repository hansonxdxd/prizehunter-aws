# Three-minute demo shot list

Target length: **3:10**. Record the working local application, not a slide deck. This script reflects the present offline fallback. Do not say “live Bedrock” or “AWS hosted” unless those steps are actually verified and this material is updated.

| Time | Screen / action | Suggested narration |
| --- | --- | --- |
| 0:00–0:25 | Main input and problem | “Finding a competition is easy. Knowing whether you qualify and whether it deserves your time is harder. PrizeHunter turns rules into an evidence-grounded decision.” |
| 0:25–0:45 | Actual architecture SVG | “This edition uses one real Strands agent and the existing provider-neutral PrizeHunter Core. Today I am showing the reproducible test build: model responses are scripted; real Bedrock validation is unresolved because AWS account verification is pending.” |
| 0:45–1:10 | Profile → enter country / hours → check | “Unknown facts stay unknown. These inputs reach the existing Core. The evidence is synthetic; arbitrary personalized Fit and planning are unavailable offline.” |
| 1:10–1:35 | Evidence / provenance | “Every literal claim must be supported by source text. Here are the source, observed time and content hash. A failed or missing rule stays uncertain.” |
| 1:35–1:55 | Run saved synthetic example | “This one-click Canadian example has scripted Fit and Plan. Core keeps uncertainty at verify first; these saved drafts are not applied to my edited preferences.” |
| 1:55–2:10 | Try synthetic hard blocker | “This controlled profile fails the country rule. Fit and Planner inference are skipped rather than producing an application plan.” |
| 2:10–2:40 | Watch buttons 1 → 5 | “First observation creates one decision; the same input creates none. This deadline change is deliberately simulated. Repeating it creates no duplicate. Retrieval failure preserves the last good baseline. Nothing is sent externally.” |
| 2:40–3:10 | Public README / prior work / status | “The Core, schemas and prior product research are reused and disclosed. The AWS Edition adds Strands adapters, bounded retrieval and Opportunity Watch. Source and tests are public under MIT for author-owned code. Bedrock and cloud hosting remain explicit unresolved steps.” |

Before recording: start the server from a fresh clone; reset Watch; close private account/terminal pages; keep the mode label visible. Record exactly what the application does. A successful `aws login` alone is not a successful Bedrock analysis. No video or video URL has been produced by this document.
