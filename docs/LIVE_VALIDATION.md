# Live validation status

**Unresolved — no real Bedrock inference has succeeded.** Browser-based temporary login succeeded using AWS CLI 2.36.44. STS identity and the Nova Lite model catalog were verified in `us-east-1`. The first actual Strands `ConverseStream` request was denied with `AccessDeniedException`: AWS says the new account is still being verified. No replay fallback was used. No deployment was attempted after that account-level blocker.

| Recorded field | Actual result |
| --- | --- |
| Attempt start | 2026-09-14T13:36:36.676891+00:00 |
| Model / region | `us.amazon.nova-lite-v1:0` / `us-east-1` |
| API | Real Strands → Bedrock `ConverseStream` |
| Latency | 2.058 seconds to failure |
| Model requests / tool calls | 1 denied request / 0 tool calls |
| Usage reported | 0 input, 0 output, 0 total tokens |
| Estimated model cost | USD 0.000000; not billing data |
| Error | `AccessDeniedException`, account verification pending |
| Real analysis / saved live artifact | Not produced |

AWS's error states that verification normally takes less than two hours. This is an expected timeframe, not a guarantee or successful model validation. The skill's error guidance classifies AccessDenied as non-retryable without resolving its cause, so we did not cycle through models or regions. [Sanitized attempt record](live-status.json) contains no account identifiers or credentials.

Initial prerequisites were also resolved: the machine initially lacked AWS CLI/configuration, and the Python SDK required `botocore[crt]` to consume browser-login credentials. That dependency is now included in the lockfile. AWS Agent Toolkit installed its default skills and MCP configuration; these local authoring tools are not product hosting or model success.

The official rules connector separately retrieved the real [Agents for Humans page](https://agentsforhumans.devpost.com/rules) on 2026-09-13: success, 36,759 extracted characters, SHA-256 `d68dd713f4b4e5e627481f2b552621524f9d8c303f9f3fa644031bb451634390`. This proves HTTP retrieval only; it does not prove Bedrock analysis. The sanitized summary is in `test-results/retrieval-summary.json`.

## Safe operator procedure

1. Install current AWS CLI v2 and configure your approved named profile through browser login. The [official Agent Toolkit setup](https://raw.githubusercontent.com/aws/agent-toolkit-for-aws/refs/heads/main/setup-instructions/setup.md) uses `aws login`; credentials must not be pasted into chat or committed.
2. Verify identity with `aws sts get-caller-identity --profile YOUR_APPROVED_PROFILE`. Keep account-specific outputs private. Confirm your account allows the selected Bedrock model and region.
3. Set `AWS_PROFILE` locally, then run the bounded script once. The script verifies STS identity, sets the paid gate for this one process and uses real source retrieval. No replay fallback exists.

```sh
export AWS_PROFILE=YOUR_APPROVED_PROFILE
uv run --no-sync python scripts/live_validation.py --region us-east-1 --model us.amazon.nova-lite-v1:0
```

The attempted model has **not completed successful inference**. [Amazon's Nova Lite model card](https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-amazon-nova-lite.html) documents the model; the model catalog was verified but inference was denied pending account verification. The initial price estimate uses Nova Lite on-demand $0.06 input / $0.24 output per million tokens, from [AWS's cost optimization guidance](https://aws.amazon.com/blogs/machine-learning/effective-cost-optimization-strategies-for-amazon-bedrock/). Recheck pricing before an independent run.

The harness caps the sprint ledger at three attempts and each analysis at eight model calls. Strands requests have six-turn, 60,000-token and 16,000-output-token invocation ceilings, with 90-second invocation and 180-second overall call-budget checks. Each model response is capped at 4,096 tokens. Tool/source limits remain active. Costs are estimates; interrupted calls may not report all usage.

The analyzed profile is a **CONTROLLED TEST synthetic Canadian developer**, not a claim about the author's nationality or eligibility. The target evidence must be the real official rules. Core's literal validation and eligibility/Fit/Plan gates remain active.

## Results and publication boundary

Local outputs go to ignored `local-evidence/sprint-02/`: blocker or attempt ledger, exact private errors, real result and structured drafts if successful. Do not publish that directory wholesale. Before publishing a saved result, inspect every field for credentials, personal/account metadata, private traces and source-content rights. Publish only an appropriately sanitized artifact with true source/model/time/call provenance.

Successful real analysis must be followed by Watch validation on that real baseline, a truthful saved-live label, and actual hosting/endpoint smoke evidence. Until then, screenshots and demo narration use **OFFLINE VERIFIED / CONTROLLED TEST**. Current actual attempt: **one denied request** to `us.amazon.nova-lite-v1:0` in `us-east-1`, **2.058 seconds**, **zero reported usage tokens**. No real analysis result exists.
