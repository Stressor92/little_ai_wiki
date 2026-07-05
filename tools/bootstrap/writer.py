from tools.bootstrap.constants import BOOTSTRAP_MARKER
from tools.bootstrap.templates import index_template, seed_template


def execute_plan(plan, domain, topic="", force=False):

    report = {
        "created_directories": [],
        "created_files": [],
        "skipped_existing": [],
        "warnings": [],
        "errors": [],
        "recommendations": [],
    }

    for directory in plan.directories:

        if directory.exists():
            report["skipped_existing"].append(str(directory))
        else:
            directory.mkdir(parents=True)
            report["created_directories"].append(str(directory))

    for file in plan.files:
        file_path = file.path

        if file_path.exists() and not force:
            report["skipped_existing"].append(str(file_path))
            continue

        if file_path.exists() and force:
            existing = file_path.read_text(encoding="utf8")
            if BOOTSTRAP_MARKER not in existing:
                report["warnings"].append(
                    f"Skipped non-bootstrap file in force mode: {file_path}"
                )
                report["skipped_existing"].append(str(file_path))
                continue

        if file.kind == "index":
            text = index_template(
                folder=file.folder,
                layer_id=file.layer_id,
                domain=domain,
                topic=topic,
                purpose=file.purpose,
            )
        else:
            text = seed_template(
                folder=file.folder,
                seed_name=file.seed_name,
                domain=domain,
                topic=topic,
            )

        file_path.write_text(text, encoding="utf8")
        report["created_files"].append(str(file_path))

    return report