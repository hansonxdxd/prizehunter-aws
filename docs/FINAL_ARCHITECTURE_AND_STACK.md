# Final architecture and stack facts

![Actual implementation](architecture.svg)

Submission diagram: [architecture.svg](architecture.svg), English, scalable, identical to packaged `src/prizehunter_aws/assets/architecture.svg`; the browser capture is screenshot 05. It shows only the currently running local architecture. The Profile-to-Watch chain is conceptual: browser Watch uses its separate saved baseline, not the custom form's null-Fit output.

| Runtime component / dependency | Actual role and state |
| --- | --- |
| Python | Verified with 3.12.13; packages declare >=3.11,<3.14 |
| prizehunter-aws 0.1.0 | Local CLI, web server, adapters, orchestration and Watch |
| strands-agents 1.55.1 | One real Agent, sequential research tools, structured-output responses and bounded calls |
| ReplayModel | Synthetic scripted model protocol used for verified offline demo; no neural inference |
| BedrockModel + boto3 1.43.93 | Implemented server-side live adapter; one denied request, no successful inference |
| botocore 1.43.93 / awscrt 0.36.0 | AWS request configuration and browser-login temporary credential support; not cloud hosting |
| prizehunter-core 0.1.0 / pydantic 2.13.5 | Existing typed contracts, evidence/claims, deterministic eligibility and guarded Fit/Plan |
| beautifulsoup4 4.15.0 / pypdf 6.18.1 | Bounded HTML/text/PDF extraction in an isolated worker; not browser rendering/OCR |
| Python ThreadingHTTPServer / HTML, CSS, JavaScript | Loopback test build and progressively disclosed form; no paid browser route |
| Local JSON / pathlib / os.replace | Per-goal Watch baseline, atomic file replacement; browser process lock, no database service |
| pytest 8.4.2 / ruff 0.16.7 / uv + Hatchling | Test, lint, lockfile installation and wheel/source builds |
| Human | Reviews uncertainty, recommendations and checklists; executes any eventual external action |

Declared direct requirements are in `pyproject.toml` and `packages/core/pyproject.toml`; exact resolved versions and transitive dependencies are in `uv.lock`, with license inventory in `THIRD_PARTY_INVENTORY.json`. Library presence does not imply its hosted service is deployed.

Data flow: UserProfile + FitPreferences → approved/saved evidence through Strands tools → CompetitionRecord/claims → Core validation/eligibility → optional guarded Fit/Plan → separately invoked Watch comparison → human review. Research tools: read_evidence; search_opportunities explicitly unavailable. Research stage cannot expand approved URLs from page instructions.

Actual AWS service interaction is STS identity plus Bedrock catalog and one denied Bedrock Runtime request. There is no AgentCore, App Runner, Lambda, S3 hosting, Cognito, scheduler, cloud database or notification service in this runtime. Local URLs are not public endpoints. The diagram intentionally describes the verified replay path; a future live deployment requires a new verified diagram/state record.

See [Source of Truth](FINAL_SUBMISSION_SOURCE_OF_TRUTH.md) for exact call/retrieval bounds and [verification](FINAL_VERIFICATION.md) for evidence. No diagram arrow is proof of successful Bedrock inference.
