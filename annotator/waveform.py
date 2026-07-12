import audioop
import wave
from pathlib import Path

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget


def read_waveform(path: Path, points: int = 1200) -> list[float]:
    """Return normalized peak values for PCM WAV without loading the whole file."""
    if path.suffix.lower() != ".wav":
        return []
    try:
        with wave.open(str(path), "rb") as source:
            width = source.getsampwidth()
            frames = source.getnframes()
            channels = source.getnchannels()
            block_frames = max(1, frames // points)
            result = []
            while len(result) < points:
                chunk = source.readframes(block_frames)
                if not chunk:
                    break
                peak = audioop.max(chunk, width)
                maximum = float((1 << (8 * width - 1)) - 1)
                result.append(min(1.0, peak / maximum))
            return result
    except (wave.Error, OSError, EOFError):
        return []


class WaveformWidget(QWidget):
    seek_requested = Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._values: list[float] = []
        self._position = 0.0
        self._message = "音声を選択すると波形を表示します"
        self.setMinimumHeight(230)

    def set_audio(self, path: Path) -> None:
        self._values = read_waveform(path)
        self._position = 0.0
        self._message = "この形式は再生できます（波形表示はPCM WAVに対応）"
        self.update()

    def set_position(self, ratio: float) -> None:
        self._position = max(0.0, min(1.0, ratio))
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.width():
            self.seek_requested.emit(event.position().x() / self.width())

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#111827"))
        center = self.height() / 2
        if not self._values:
            painter.setPen(QColor("#94a3b8"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._message)
        else:
            path = QPainterPath(QPointF(0, center))
            step = self.width() / max(1, len(self._values) - 1)
            for index, value in enumerate(self._values):
                path.lineTo(index * step, center - value * (center - 18))
            for index in range(len(self._values) - 1, -1, -1):
                path.lineTo(index * step, center + self._values[index] * (center - 18))
            path.closeSubpath()
            painter.fillPath(path, QColor("#38bdf8"))
        x = int(self._position * self.width())
        painter.setPen(QPen(QColor("#f59e0b"), 2))
        painter.drawLine(x, 0, x, self.height())
