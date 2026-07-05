import json
from pathlib import Path


def write_report(report, output):

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf8") as f:
        json.dump(
            report,
            f,
            indent=2,
            ensure_ascii=False
        )