import csv
import json
import shutil
import os
import tempfile
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


def save_annotations(config: ProjectConfig, annotations: dict[str, list[str]]) -> list[str]:
    """Atomically save labels and copy data; return non-fatal copy failures."""
    config.annotation_file.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{config.annotation_file.name}.", suffix=".tmp",
        dir=config.annotation_file.parent,
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        if config.annotation_file.suffix.lower() == ".json":
            temporary.write_text(json.dumps(annotations, ensure_ascii=False, indent=2), encoding="utf-8")
        else:
            with temporary.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["filename", "labels"])
                for filename, labels in sorted(annotations.items()):
                    writer.writerow([filename, json.dumps(labels, ensure_ascii=False)])
        os.replace(temporary, config.annotation_file)
    finally:
        temporary.unlink(missing_ok=True)

    failures = []
    config.input_dir.mkdir(parents=True, exist_ok=True)
    for filename in annotations:
        try:
            source = config.raw_dir / filename
            if not source.is_file():
                failures.append(f"{filename}: 元ファイルがありません")
                continue
            destination = config.input_dir / filename
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        except OSError as error:
            failures.append(f"{filename}: {error}")
    return failures


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
