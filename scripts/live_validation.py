"""Bounded real-source validation. Never substitutes replay or synthetic drafts."""

import argparse
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path

import boto3
from botocore.config import Config

from prizehunter_aws.demo import scenario
from prizehunter_aws.pipeline import run_analysis
from prizehunter_aws.retrieval import PublicRetriever
from prizehunter_aws.runtime import ResearchTools, StrandsRuntime, configured_bedrock

URL = "https://agentsforhumans.devpost.com/rules"
ORIGIN = "https://agentsforhumans.devpost.com"
# Official Amazon Nova 1 on-demand prices, USD per million tokens (2026-09-14 check).
RATES = {"amazon.nova-lite-v1:0": (0.06, 0.24), "us.amazon.nova-lite-v1:0": (0.06, 0.24)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="amazon.nova-lite-v1:0", choices=sorted(RATES))
    parser.add_argument(
        "--cross-region-verified",
        action="store_true",
        help="Operator has independently verified geographic inference support for this account",
    )
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument(
        "--account-verification-changed",
        action="store_true",
        help="Operator confirms the account verification blocker has changed before retrying",
    )
    parser.add_argument("--output-dir", default="local-evidence/sprint-02")
    args = parser.parse_args()
    if args.model.startswith("us.") and not args.cross_region_verified:
        parser.error(
            "Geographic cross-region inference needs verified account support; use amazon.nova-lite-v1:0 first"
        )
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    ledger_path = output / "live-attempt-ledger.json"
    ledger = json.loads(ledger_path.read_text()) if ledger_path.exists() else []
    if (
        ledger
        and ledger[-1].get("error_type") == "AccessDeniedException"
        and not args.account_verification_changed
    ):
        parser.error(
            "Previous access-denied blocker is unresolved; retry only after account verification changes"
        )
    if len(ledger) >= 3:
        raise SystemExit("Three-attempt sprint cap reached; inspect failures before any further spending.")
    os.environ["AWS_EC2_METADATA_DISABLED"] = "true"
    session = boto3.Session(region_name=args.region)
    if session.get_credentials() is None:
        record = {
            "outcome": "BLOCKED_NO_LOCAL_AWS_CREDENTIALS",
            "region": args.region,
            "model": args.model,
            "live_model": False,
            "paid_calls": 0,
            "checked_at": datetime.now(UTC).isoformat(),
        }
        (output / "live-blocker.json").write_text(json.dumps(record, indent=2) + "\n")
        print(json.dumps(record))
        return 2
    identity = session.client(
        "sts", config=Config(connect_timeout=5, read_timeout=10, retries={"total_max_attempts": 1})
    ).get_caller_identity()
    os.environ.update(
        PH_ALLOW_PAID_BEDROCK="1",
        PH_BEDROCK_MODEL_ID=args.model,
        AWS_REGION=args.region,
        PH_AWS_ACCOUNT_ID=identity["Account"],
    )
    record = {
        "started_at": datetime.now(UTC).isoformat(),
        "model": args.model,
        "region": args.region,
        "source_url": URL,
        "outcome": "started",
        "profile_type": "disclosed synthetic profile",
    }
    ledger.append(record)
    ledger_path.write_text(json.dumps(ledger, indent=2) + "\n")
    started = time.monotonic()
    runtime = None
    try:
        goal, _, _ = scenario()
        goal.description = (
            "Evaluate the real Agents for Humans rules for a synthetic Canadian Python developer."
        )
        goal.profile.age = 30
        runtime = StrandsRuntime(
            configured_bedrock(),
            ResearchTools(retriever=PublicRetriever({ORIGIN}, {ORIGIN}), allowed_urls=[URL]),
        )
        runtime.budget.maximum = 8
        result = run_analysis(goal, [URL], runtime)
        result["verification"] = {
            "level": "LIVE VERIFIED",
            "region": args.region,
            "model": args.model,
            "profile": "CONTROLLED TEST synthetic profile",
            "latency_seconds": round(time.monotonic() - started, 3),
        }
        (output / "live-result.json").write_text(json.dumps(result, indent=2) + "\n")
        (output / "live-drafts.json").write_text(json.dumps(runtime.drafts, indent=2) + "\n")
        usage = dict(runtime.agent.event_loop_metrics.accumulated_usage)
        record.update(
            outcome="LIVE VERIFIED",
            eligibility=result["eligibility"]["overall_status"],
            recommendation=result["fit"]["recommendation"],
            plan_status=result["plan"]["plan_status"],
        )
    except Exception as exc:  # noqa: BLE001 -- preserve exact local failure without claiming a live result.
        record.update(outcome="FAILED", error_type=type(exc).__name__)
        (output / "live-error-private.txt").write_text(str(exc))
        usage = dict(runtime.agent.event_loop_metrics.accumulated_usage) if runtime else {}
    record.update(
        latency_seconds=round(time.monotonic() - started, 3),
        usage=usage,
        model_calls=runtime.budget.calls if runtime else 0,
        tools=runtime.tools.events if runtime else [],
    )
    in_rate, out_rate = RATES[args.model]
    record["estimated_model_cost_usd"] = round(
        (usage.get("inputTokens", 0) * in_rate + usage.get("outputTokens", 0) * out_rate) / 1_000_000, 6
    )
    record["cost_note"] = "Token estimate, not billing data; interrupted calls may be missing."
    ledger_path.write_text(json.dumps(ledger, indent=2) + "\n")
    print(json.dumps(record))
    return 0 if record["outcome"] == "LIVE VERIFIED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
