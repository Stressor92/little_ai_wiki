#!/usr/bin/env python3

from pathlib import Path
import argparse
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.bootstrap.planner import create_plan
from tools.bootstrap.writer import execute_plan
from tools.bootstrap.validator import validate_domain_name, validate_structure
from tools.bootstrap.report import write_report


def parse_args():
    parser = argparse.ArgumentParser(
        description="Bootstrap a new knowledge domain."
    )

    parser.add_argument("--domain", required=True)
    parser.add_argument("--input", default="")
    parser.add_argument("--output", default="")
    parser.add_argument("--report", default="")
    parser.add_argument("--config", default="")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--topic", default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--with-seeds", action="store_true")
    parser.add_argument("--output-report", default="")

    return parser.parse_args()


def main():

    args = parse_args()

    validate_domain_name(args.domain)

    root = Path(args.output or args.input or Path.cwd()).resolve()

    plan = create_plan(
        root=root,
        domain=args.domain,
        topic=args.topic,
        with_seeds=args.with_seeds
    )

    if args.dry_run:
        print(plan.pretty())
        return 0

    report = execute_plan(
        plan,
        domain=args.domain,
        topic=args.topic,
        force=args.force
    )

    validation = validate_structure(root, args.domain)

    report["validation_findings"] = validation

    report_path = args.report or args.output_report
    if report_path:
        write_report(report, report_path)

    print(
        f"""
Created Directories : {len(report["created_directories"])}
Created Files       : {len(report["created_files"])}
Skipped             : {len(report["skipped_existing"])}
Warnings            : {len(report["warnings"])}
Errors              : {len(report["errors"])}
"""
    )

    if report["errors"]:
        return 2

    if validation:
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())