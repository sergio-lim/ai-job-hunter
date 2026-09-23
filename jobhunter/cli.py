from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

from jobhunter import __version__
from jobhunter.classify import classify_file, classify_reply
from jobhunter.pipeline import run_pipeline
from jobhunter.score import ScoredJob


def _configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )


def _table(rows: list[ScoredJob]) -> str:
    if not rows:
        return "No matching jobs."
    headers = ("SCORE", "TITLE", "COMPANY", "LOCATION", "SOURCE", "URL")
    table: list[tuple[str, ...]] = [
        (
            str(item.score),
            item.job.title[:42],
            item.job.company[:22],
            (item.job.location or "-")[:18],
            item.job.source,
            item.job.url,
        )
        for item in rows
    ]
    widths = [len(header) for header in headers]
    for row in table:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(cell))

    def fmt(row: tuple[str, ...]) -> str:
        return "  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row))

    rule = "  ".join("-" * width for width in widths)
    lines = [fmt(headers), rule, *[fmt(row) for row in table]]
    return "\n".join(lines)


def _add_run_flags(parser: argparse.ArgumentParser) -> None:
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--demo", action="store_true", help="offline run using data/samples/")
    mode.add_argument("--live", action="store_true", help="fetch public keyless sources")
    parser.add_argument("--min-score", type=int, default=0, help="drop jobs below this score")
    parser.add_argument("--limit", type=int, default=20, help="max jobs to print")
    parser.add_argument("--dry-run", action="store_true", help="do not notify or persist seen ids")
    parser.add_argument("--json", action="store_true", dest="as_json", help="print JSON to stdout")
    parser.add_argument("--profile", type=Path, default=None, help="path to a profile JSON file")
    parser.add_argument("--seen", type=Path, default=None, help="path to the seen-ids JSON file")
    parser.add_argument("--samples", type=Path, default=None, help="override sample jobs path")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="jobhunter",
        description="Collect, verify, and score public job listings.",
    )
    parser.add_argument("--version", action="version", version=f"jobhunter {__version__}")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    run_parser = sub.add_parser("run", help="run the hunt pipeline")
    _add_run_flags(run_parser)

    classify_parser = sub.add_parser("classify", help="classify recruiter replies")
    classify_parser.add_argument("--text", default="", help="raw reply text")
    classify_parser.add_argument("--file", type=Path, help="JSON list of {text} objects")
    classify_parser.add_argument(
        "--llm",
        action="store_true",
        help="use an OpenAI-compatible model when LLM_API_KEY is set",
    )
    classify_parser.add_argument("--json", action="store_true", dest="as_json")
    return parser


def _cmd_run(args: argparse.Namespace) -> int:
    demo = not args.live
    telegram_ready = bool(
        os.environ.get("TELEGRAM_BOT_TOKEN") and os.environ.get("TELEGRAM_CHAT_ID")
    )
    results = run_pipeline(
        demo=demo,
        limit=args.limit,
        min_score=args.min_score,
        dry_run=args.dry_run,
        profile_path=args.profile,
        seen_path=args.seen,
        samples_path=args.samples,
        notify=telegram_ready and not args.dry_run,
    )
    if args.as_json:
        json.dump([item.to_dict() for item in results], sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0
    print(_table(results))
    if results:
        print()
        print(f"{len(results)} job(s)  min_score={args.min_score}  mode={'demo' if demo else 'live'}")
    return 0


def _cmd_classify(args: argparse.Namespace) -> int:
    if args.file:
        rows = classify_file(str(args.file), use_llm=args.llm)
        json.dump(rows, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0
    if not args.text:
        print("provide --text or --file", file=sys.stderr)
        return 2
    result = classify_reply(args.text, use_llm=args.llm)
    if args.as_json:
        json.dump(result.to_dict(), sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        print(f"{result.label}  [{result.method}]  {result.reason}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _configure_logging(args.verbose)
    if args.command == "run":
        return _cmd_run(args)
    if args.command == "classify":
        return _cmd_classify(args)
    parser.print_help()
    return 2
