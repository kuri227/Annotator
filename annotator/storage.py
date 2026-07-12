import csv
import json
import shutil
from pathlib import Path

from .models import MediaType, ProjectConfig


def _normalize_labels(value: object) -> list[str]:
    """Normalize new list values and legacy single-label values."""
    if isinstance(value, list):
        return [str(label) for label in value if str(label)]
    if value is None or str(value) == "":
        return []
    return [str(value)]


def load_annotations(path: Path) -> dict[str, list[str]]:
    if not path.exists():
        return {}
    try:
        if path.suffix.lower() == ".json":
            data = json.loads(path.read_text(encoding="utf-8"))
            return {str(k): _normalize_labels(v) for k, v in data.items()}
        with path.open(encoding="utf-8-sig", newline="") as handle:
            annotations = {}
            for row in csv.DictReader(handle):
                if "labels" in row:
                    labels = _normalize_labels(json.loads(row["labels"]))
                else:
                    labels = _normalize_labels(row.get("label"))
                if labels:
                    annotations[row["filename"]] = labels
            return annotations
    except (OSError, ValueError, KeyError, TypeError):
        return {}


def save_annotations(config: ProjectConfig, annotations: dict[str, list[str]]) -> None:
    config.annotation_file.parent.mkdir(parents=True, exist_ok=True)
    if config.annotation_file.suffix.lower() == ".json":
        config.annotation_file.write_text(
            json.dumps(annotations, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    else:
        with config.annotation_file.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["filename", "labels"])
            for filename, labels in sorted(annotations.items()):
                writer.writerow([filename, json.dumps(labels, ensure_ascii=False)])

    config.input_dir.mkdir(parents=True, exist_ok=True)
    for filename in annotations:
        source = config.raw_dir / filename
        if source.is_file():
            destination = config.input_dir / filename
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)


def discover_files(config: ProjectConfig) -> list[Path]:
    media_type = MediaType(config.media_type)
    extensions = {
        "image": {".jpg", ".jpeg", ".png", ".bmp", ".webp"},
        "audio": {".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac"},
    }[media_type.value]
    return sorted(
        (path for path in config.raw_dir.rglob("*") if path.is_file() and path.suffix.lower() in extensions),
        key=lambda path: str(path.relative_to(config.raw_dir)).lower(),
    )
