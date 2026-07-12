from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class MediaType(str, Enum):
    IMAGE = "image"
    AUDIO = "audio"


@dataclass
class ProjectConfig:
    root: Path
    raw_dir: Path
    input_dir: Path
    annotation_file: Path
    media_type: MediaType
    labels: list[str]

    def __post_init__(self) -> None:
        # Qt may unwrap a ``str``-based Enum stored as QComboBox userData.
        # Normalize at the model boundary so every caller gets one stable type.
        self.media_type = MediaType(self.media_type)


@dataclass
class Session:
    config: ProjectConfig
    files: list[Path] = field(default_factory=list)
    annotations: dict[str, str] = field(default_factory=dict)
    current_index: int = 0
    dirty: bool = False

    @property
    def current_file(self) -> Path | None:
        return self.files[self.current_index] if self.files else None

    @property
    def completed(self) -> int:
        names = {
            str(path.relative_to(self.config.raw_dir)).replace("\\", "/")
            for path in self.files
        }
        return sum(name in self.annotations for name in names)
