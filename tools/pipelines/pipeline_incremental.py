from __future__ import annotations

import argparse
from pathlib import Path

from tools.pipelines.pipeline_base import run_pipeline
from tools.pipelines.pipeline_context import PipelineContext
from tools.pipelines.source_change_detector import detect_source_changes, write_change_report, write_manifest
from tools.pipelines.utils import add_shared_cli_arguments, load_config, stable_execution_id


EXIT_CONFIG = 3
EXIT_INTERRUPT = 4


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Deterministic incremental pipeline orchestrator")
    add_shared_cli_arguments(parser)
    return parser


def main() -> int:
    try:
        args = _parser().parse_args()

        cfg = load_config(args.config)
        input_path = Path(args.input) if args.input else (Path.cwd() / f"00_raw_{args.domain}")
        output_path = Path(args.output) if args.output else Path.cwd()
        report_path = Path(args.report) if args.report else (output_path / f"pipeline_incremental_{args.domain}.json")
        detector_report_path = output_path / ".pipeline_state" / f"source_change_{args.domain}.json"

        execution_id = stable_execution_id("incremental", args.domain, {**cfg, "workers": args.workers})

        detector_result = detect_source_changes(
            domain=args.domain,
            input_path=input_path,
            output_root=output_path,
        )
        write_change_report(detector_result, detector_report_path)

        if not detector_result["changes_detected"] and not args.force:
            print("status=no_changes; incremental pipeline skipped")
            return 0

        context = PipelineContext(
            domain=args.domain,
            input_path=input_path,
            output_path=output_path,
            dry_run=args.dry_run,
            force=args.force,
            configuration=cfg,
            execution_id=execution_id,
            pipeline="incremental",
            report_path=report_path,
            workers=args.workers,
            verbose=args.verbose,
        )

        result = run_pipeline(context, mode="incremental")

        if result.exit_code == 0 and not args.dry_run:
            write_manifest(
                output_root=output_path,
                domain=args.domain,
                manifest=detector_result["current_manifest"],
            )

        return result.exit_code
    except KeyboardInterrupt:
        return EXIT_INTERRUPT
    except Exception:
        return EXIT_CONFIG


if __name__ == "__main__":
    raise SystemExit(main())
