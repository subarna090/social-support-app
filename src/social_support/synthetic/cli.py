"""``social-support-data``: generate synthetic applicant packs and seed the app (contracts/cli.md).

Console output never contains names, Emirates IDs, addresses or incomes.
"""

import argparse
import sys
from datetime import date
from pathlib import Path

from social_support.domain.models import Outcome
from social_support.services.tracing import configure_logging
from social_support.synthetic.profile import SamplingError
from social_support.synthetic.run import (
    INCONSISTENCY_TYPES,
    GenerationRequest,
    RequestError,
    generate,
)
from social_support.synthetic.seeding import seed_run
from social_support.ui.client import UNREACHABLE, ApiClient


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:  # argparse would exit; we return 2 instead
        raise RequestError(message)


def _types(raw: str) -> tuple[str, ...]:
    names = [name.strip() for name in raw.split(",") if name.strip()]
    for name in names:
        if name not in INCONSISTENCY_TYPES:
            expected = ", ".join(INCONSISTENCY_TYPES)
            raise RequestError(f"unknown inconsistency type: {name} (expected: {expected})")
    return tuple(INCONSISTENCY_TYPES[name] for name in names)


def _mix(raw: str) -> dict[str, int]:
    message = "outcome mix must be three percentages that add up to 100"
    try:
        values = [int(part) for part in raw.split(",")]
    except ValueError:
        raise RequestError(message) from None
    if len(values) != 3:
        raise RequestError(message)
    order = (Outcome.APPROVE, Outcome.SOFT_DECLINE, Outcome.NEEDS_HUMAN_REVIEW)
    return {outcome.value: value for outcome, value in zip(order, values, strict=True)}


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="social-support-data", description="Synthetic applicant packs.")
    commands = parser.add_subparsers(dest="command", required=True, parser_class=_Parser)

    gen = commands.add_parser("generate", help="generate a batch of applicant packs")
    gen.add_argument("--count", type=int, required=True)
    gen.add_argument("--seed", type=int, required=True)
    gen.add_argument("--inconsistency-rate", type=int, default=0)
    gen.add_argument("--inconsistency-types", default=",".join(INCONSISTENCY_TYPES))
    gen.add_argument("--outcome-mix", default=None)
    gen.add_argument("--as-of", type=date.fromisoformat, default=None)
    gen.add_argument("--out", type=Path, default=Path("data/synthetic"))
    gen.add_argument("--overwrite", action="store_true")

    seed = commands.add_parser("seed", help="submit a generated run to the running application")
    seed.add_argument("--run", type=Path, required=True)
    seed.add_argument("--limit", type=int, default=None)
    seed.add_argument("--api-base-url", default=None)
    return parser


def _generate(args: argparse.Namespace) -> int:
    request = GenerationRequest(
        count=args.count,
        seed=args.seed,
        inconsistency_rate_pct=args.inconsistency_rate,
        inconsistency_types=_types(args.inconsistency_types),
        outcome_mix_pct=_mix(args.outcome_mix) if args.outcome_mix else None,
        output_root=args.out,
        overwrite=args.overwrite,
        **({"as_of": args.as_of} if args.as_of else {}),
    )
    run = generate(request)
    counts = run.counts
    eligibility = ", ".join(f"{k} {v}" for k, v in counts["eligibility"].items())
    total = sum(counts["inconsistencies"].values())
    detail = ", ".join(f"{k} {v}" for k, v in counts["inconsistencies"].items() if v)
    print(f"Generated {counts['packs']} packs in {run.folder}")
    print(f"Eligibility: {eligibility}")
    print(f"Inconsistencies: {total}" + (f" ({detail})" if detail else ""))
    print(f"Policy: {run.policy_version_id}")
    return 0


def _seed(args: argparse.Namespace) -> int:
    # Default address: API_BASE_URL from the environment, then .env, then localhost (ApiClient).
    summary = seed_run(args.run, ApiClient(args.api_base_url), limit=args.limit)
    if summary.unreachable:
        print(UNREACHABLE, file=sys.stderr)
        print(
            f"Submitted {summary.submitted} of {summary.total} packs before stopping.",
            file=sys.stderr,
        )
        return 1
    if summary.rejected:
        print(f"Rejected by the application: {summary.rejected} (see the report)")
    differed = summary.submitted - summary.matched
    print(
        f"Seeded {summary.submitted} packs: {summary.matched} matched the eligibility outcome, "
        f"{differed} differed. Report: {summary.report_path}"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    configure_logging()  # JSON records on stderr; per-pack records are DEBUG, so hidden by default
    try:
        args = build_parser().parse_args(argv)
        if args.command == "generate":
            return _generate(args)
        if args.command == "seed":
            return _seed(args)
    except RequestError as exc:
        print(f"social-support-data: error: {exc}", file=sys.stderr)
        return 2
    except SamplingError as exc:
        print(f"social-support-data: {exc}", file=sys.stderr)
        return 1
    return 2
