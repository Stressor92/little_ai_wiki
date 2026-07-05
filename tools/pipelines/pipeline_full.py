from __future__ import annotations

import argparse
from pathlib import Path

from tools.pipelines.pipeline_base import run_pipeline
from tools.pipelines.pipeline_context import PipelineContext
from tools.pipelines.utils import add_shared_cli_arguments, load_config, stable_execution_id


EXIT_CONFIG = 3
EXIT_INTERRUPT = 4


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Deterministic full pipeline orchestrator")
    add_shared_cli_arguments(parser)
    return parser


def main() -> int:
    try:
        args = _parser().parse_args()

        cfg = load_config(args.config)
        input_path = Path(args.input) if args.input else (Path.cwd() / f"00_raw_{args.domain}")
        output_path = Path(args.output) if args.output else Path.cwd()
        report_path = Path(args.report) if args.report else (output_path / f"pipeline_full_{args.domain}.json")

        execution_id = stable_execution_id("full", args.domain, {**cfg, "workers": args.workers})

        context = PipelineContext(
            domain=args.domain,
            input_path=input_path,
            output_path=output_path,
            dry_run=args.dry_run,
            force=args.force,
            configuration=cfg,
            execution_id=execution_id,
            pipeline="full",
            report_path=report_path,
            workers=args.workers,
            verbose=args.verbose,
        )

        result = run_pipeline(context, mode="full")
        return result.exit_code
    except KeyboardInterrupt:
        return EXIT_INTERRUPT
    except Exception:
        return EXIT_CONFIG


if __name__ == "__main__":
    raise SystemExit(main())
