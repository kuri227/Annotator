import csv
import json
import shutil
from pathlib import Path

from .models import MediaType, ProjectConfig


def load_annotations(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        if path.suffix.lower() == ".json":
            data = json.loads(path.read_text(encoding="utf-8"))
            return {str(k): str(v) for k, v in data.items()}
        with path.open(encoding="utf-8-sig", newline="") as handle:
            return {row["filename"]: row["label"] for row in csv.DictReader(handle)}
    except (OSError, ValueError, KeyError, TypeError):
        return {}


def save_annotations(config: ProjectConfig, annotations: dict[str, str]) -> None:
    config.annotation_file.parent.mkdir(parents=True, exist_ok=True)
    if config.annotation_file.suffix.lower() == ".json":
        config.annotation_file.write_text(
            json.dumps(annotations, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    else:
        with config.annotation_file.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["filename", "label"])
            writer.writerows(sorted(annotations.items()))

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
