import audioop
import wave
from pathlib import Path

from PySide6.QtCore import QObject, QPointF, QRunnable, QThreadPool, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget


def read_waveform(path: Path, points: int = 1200) -> list[float]:
    """Return normalized peak values for PCM WAV without loading the whole file."""
    if path.suffix.lower() != ".wav":
        return []
    try:
        with wave.open(str(path), "rb") as source:
            width = source.getsampwidth()
            channels = source.getnchannels()
            if width not in (1, 2, 3, 4) or not 1 <= channels <= 32:
                return []
            bytes_per_frame = width * channels
            # Corrupt headers sometimes claim billions of frames. Bound work and
            # memory by the real file size, then sample small windows.
            physical_limit = max(0, path.stat().st_size // bytes_per_frame)
            frames = min(source.getnframes(), physical_limit)
            if frames <= 0:
                return []
            sample_count = min(points, frames)
            block_frames = max(1, min(2048, frames // sample_count))
            result = []
            for index in range(sample_count):
                source.setpos(min(frames - 1, index * frames // sample_count))
                chunk = source.readframes(block_frames)
                if not chunk:
                    result.append(0.0)
                    continue
                peak = audioop.max(chunk, width)
                maximum = float((1 << (8 * width - 1)) - 1)
                result.append(min(1.0, peak / maximum))
            return result
    except (wave.Error, OSError, EOFError, ValueError, OverflowError):
        return []


class _WaveformSignals(QObject):
    finished = Signal(int, object)


class _WaveformTask(QRunnable):
    def __init__(self, request_id: int, path: Path):
        super().__init__()
        self.setAutoDelete(False)
        self.request_id = request_id
        self.path = path
        self.signals = _WaveformSignals()

    def run(self) -> None:
        self.signals.finished.emit(self.request_id, read_waveform(self.path))


class WaveformWidget(QWidget):
    seek_requested = Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._values: list[float] = []
        self._position = 0.0
        self._message = "音声を選択すると波形を表示します"
        self._request_id = 0
        self._tasks: set[_WaveformTask] = set()
        self.setMinimumHeight(230)

    def set_audio(self, path: Path) -> None:
        self._request_id += 1
        self._position = 0.0
        self._values = []
        self._message = "この形式は再生できます（波形表示はPCM WAVに対応）"
        if path.suffix.lower() != ".wav":
            self.update()
            return
        self._message = "波形を読み込み中…"
        task = _WaveformTask(self._request_id, path)
        self._tasks.add(task)
        task.signals.finished.connect(lambda request_id, values, current=task: self._waveform_ready(request_id, values, current))
        QThreadPool.globalInstance().start(task)
        self.update()

    def _waveform_ready(self, request_id: int, values: list[float], task: _WaveformTask) -> None:
        self._tasks.discard(task)
        if request_id != self._request_id:
            return
        self._values = values
        self._message = "波形を読み込めませんでした" if not values else ""
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
