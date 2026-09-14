"""Human readable CLI and JSON. Live mode never activates implicitly."""

import argparse
import json
import sys
from pathlib import Path

from prizehunter_core.evidence import CompetitionEvidenceBundle

from .contracts import Goal
from .demo import NOW, replay_runtime, scenario
from .pipeline import run_analysis
from .retrieval import PublicRetriever, origin
from .runtime import ResearchTools, StrandsRuntime, configured_bedrock
from .watch import run_once


def bounded_json(path):
    data = Path(path).read_bytes()
    if len(data) > 1_000_000:
        raise ValueError("Input file exceeds 1 MB")
    return data.decode()


def report(result, output):
    if output:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if "fit" in result:
        print(
            f"模式：{result['mode']} | 資格：{result['eligibility']['overall_status']} | "
            f"建議：{result['fit']['recommendation']} | 計畫：{result['plan']['plan_status']}",
            file=sys.stderr,
        )
        print(
            f"Strands：{result['execution']['agent_instances']} Agent，"
            f"{result['execution']['model_calls']} 次 model 呼叫；搜尋 live：False",
            file=sys.stderr,
        )
        for item in result["plan"]["actions"]:
            print(f"待人工處理：{item['title']}", file=sys.stderr)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="PrizeHunter AWS Edition — evidence-grounded competition decisions"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ["demo", "watch-once"]:
        command = commands.add_parser(name)
        command.add_argument("--country", choices=["Canada", "Taiwan"], default="Canada")
        command.add_argument("--revision", type=int, choices=[1, 2], default=1)
        command.add_argument("--output")
        if name == "watch-once":
            command.add_argument("--state", required=True)
    analyze = commands.add_parser("analyze")
    analyze.add_argument("--mode", choices=["replay", "live"], default="replay")
    analyze.add_argument("--goal", required=True)
    analyze.add_argument("--evidence")
    analyze.add_argument("--drafts")
    analyze.add_argument("--url", action="append", default=[])
    analyze.add_argument("--official-origin", action="append", default=[])
    analyze.add_argument("--output")
    probe = commands.add_parser("probe")
    probe.add_argument("url")
    probe.add_argument("--official-origin", action="append", default=[])
    probe.add_argument("--output")
    args = parser.parse_args(argv)
    try:
        if args.command in {"demo", "watch-once"}:
            goal, bundle, drafts = scenario(args.country, args.revision)
            result = run_analysis(
                goal, [str(s.source_url) for s in bundle.sources], replay_runtime(bundle, drafts), now=NOW
            )
            if args.command == "watch-once":
                result = run_once(result, args.state)
        elif args.command == "probe":
            result = (
                PublicRetriever({origin(args.url)}, set(args.official_origin))
                .fetch(args.url)
                .model_dump(mode="json")
            )
        else:
            goal = Goal.model_validate_json(bounded_json(args.goal))
            bundle = (
                CompetitionEvidenceBundle.model_validate_json(bounded_json(args.evidence))
                if args.evidence
                else None
            )
            urls = [str(s.source_url) for s in bundle.sources] if bundle else args.url
            if args.mode == "replay":
                if not bundle or not args.drafts:
                    raise ValueError("Replay needs --evidence and explicit synthetic/recorded --drafts")
                runtime = replay_runtime(bundle, json.loads(bounded_json(args.drafts)))
            else:
                if not urls:
                    raise ValueError("Live mode needs approved URLs or saved evidence")
                model = configured_bedrock()
                retriever = PublicRetriever({origin(u) for u in urls}, set(args.official_origin))
                runtime = StrandsRuntime(
                    model, ResearchTools(bundle=bundle, retriever=retriever, allowed_urls=urls)
                )
            result = run_analysis(goal, urls, runtime)
        report(result, args.output)
        return 0
    except Exception as exc:  # noqa: BLE001 -- CLI boundary must return a structured failure.
        error = {
            "status": "failed",
            "error_type": type(exc).__name__,
            "message": str(exc),
            "official_rules_absent": False,
            "live_success_claimed": False,
        }
        report(error, args.output)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
