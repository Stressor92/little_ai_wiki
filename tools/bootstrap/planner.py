from dataclasses import dataclass
from pathlib import Path

from tools.bootstrap.constants import GLOBAL_FOLDERS, LAYERS, SEED_FILES, layer_folder_name


@dataclass
class PlanFile:
    path: Path
    kind: str
    layer_id: str
    folder: str
    purpose: str = ""
    seed_name: str = ""


class Plan:

    def __init__(self):
        self.directories = []
        self.files = []

    def pretty(self):

        lines = ["Bootstrap Plan", ""]

        lines.append("Directories:")

        for d in self.directories:
            lines.append(f"  + {d}")

        lines.append("")
        lines.append("Files:")

        for f in self.files:
            lines.append(f"  + {f.path} ({f.kind})")

        return "\n".join(lines)


def create_plan(root, domain, topic="", with_seeds=False):

    plan = Plan()

    for layer in LAYERS:
        folder = layer_folder_name(layer, domain)
        folder_path = root / folder

        plan.directories.append(folder_path)
        plan.files.append(
            PlanFile(
                path=folder_path / "INDEX.md",
                kind="index",
                layer_id=layer["id"],
                folder=folder,
                purpose=layer["purpose"],
            )
        )

        if with_seeds and layer["id"] in SEED_FILES:
            for seed_name in SEED_FILES[layer["id"]]:
                plan.files.append(
                    PlanFile(
                        path=folder_path / seed_name,
                        kind="seed",
                        layer_id=layer["id"],
                        folder=folder,
                        seed_name=seed_name,
                    )
                )

    for folder in GLOBAL_FOLDERS:
        global_path = root / folder
        plan.directories.append(global_path)

        if with_seeds and folder == "personas":
            for seed_name in SEED_FILES.get("personas", []):
                plan.files.append(
                    PlanFile(
                        path=global_path / seed_name,
                        kind="seed",
                        layer_id="100",
                        folder=folder,
                        seed_name=seed_name,
                    )
                )

    return plan