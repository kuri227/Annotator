from pathlib import Path

from PySide6.QtCore import QTimer, Qt, QUrl, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout, QWidget
)

from .waveform import WaveformWidget


def format_time(milliseconds: int) -> str:
    seconds = max(0, milliseconds // 1000)
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


class ImageViewer(QLabel):
    def __init__(self):
        super().__init__("画像を選択してください")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(500, 400)
        self._pixmap = QPixmap()

    def load(self, path: Path) -> None:
        self._pixmap = QPixmap(str(path))
        self._fit()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._fit()

    def _fit(self) -> None:
        if not self._pixmap.isNull():
            self.setPixmap(self._pixmap.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                               Qt.TransformationMode.SmoothTransformation))


class AudioViewer(QWidget):
    ended = Signal()

    def __init__(self):
        super().__init__()
        self.player = QMediaPlayer(self)
        self.output = QAudioOutput(self)
        self.output.setVolume(0.8)
        self.player.setAudioOutput(self.output)
        self._load_id = 0
        self._autoplay_pending = False

        self.waveform = WaveformWidget()
        self.title = QLabel("音声を選択してください")
        self.title.setObjectName("MediaTitle")
        self.time = QLabel("00:00 / 00:00")
        self.error_label = QLabel()
        self.error_label.setStyleSheet("color:#fca5a5")
        self.error_label.setWordWrap(True)
        self.play = QPushButton("▶  再生 / 一時停止  [Space]")
        self.back = QPushButton("−5秒  [J]")
        self.forward = QPushButton("+5秒  [L]")
        self.position = QSlider(Qt.Orientation.Horizontal)
        self.volume = QSlider(Qt.Orientation.Horizontal)
        self.volume.setRange(0, 100); self.volume.setValue(80)
        self.speed = QComboBox(); self.speed.addItems(["0.75×", "1.0×", "1.25×", "1.5×", "2.0×"])
        self.speed.setCurrentIndex(1)

        controls = QHBoxLayout()
        controls.addWidget(self.back); controls.addWidget(self.play); controls.addWidget(self.forward)
        controls.addWidget(QLabel("速度")); controls.addWidget(self.speed)
        controls.addWidget(QLabel("音量")); controls.addWidget(self.volume)
        layout = QVBoxLayout(self)
        layout.addWidget(self.title); layout.addWidget(self.waveform, 1)
        layout.addWidget(self.position); layout.addWidget(self.time); layout.addWidget(self.error_label); layout.addLayout(controls)

        self.play.clicked.connect(self.toggle)
        self.back.clicked.connect(lambda: self.skip(-5000))
        self.forward.clicked.connect(lambda: self.skip(5000))
        self.volume.valueChanged.connect(lambda value: self.output.setVolume(value / 100))
        self.speed.currentTextChanged.connect(lambda text: self.player.setPlaybackRate(float(text[:-1])))
        self.position.sliderMoved.connect(self.player.setPosition)
        self.waveform.seek_requested.connect(self.seek_ratio)
        self.player.positionChanged.connect(self._position_changed)
        self.player.durationChanged.connect(lambda duration: self.position.setRange(0, duration))
        self.player.mediaStatusChanged.connect(self._status_changed)
        self.player.errorOccurred.connect(self._playback_error)

    def load(self, path: Path, autoplay: bool = False) -> None:
        self._load_id += 1
        load_id = self._load_id
        self.player.stop()
        self.player.setSource(QUrl())
        self._autoplay_pending = autoplay
        self.error_label.clear()
        self.title.setText(path.name)
        self.waveform.set_audio(path)
        # Yield to Qt so the previous decoder can release resources first.
        QTimer.singleShot(0, lambda: self._set_source(load_id, path))

    def _set_source(self, load_id: int, path: Path) -> None:
        if load_id == self._load_id:
            self.player.setSource(QUrl.fromLocalFile(str(path)))

    def clear(self) -> None:
        """Release the media file handle, particularly important on Windows."""
        self.player.stop()
        self._load_id += 1
        self._autoplay_pending = False
        self.player.setSource(QUrl())
        self.title.setText("音声を選択してください")

    def toggle(self) -> None:
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def skip(self, milliseconds: int) -> None:
        self.player.setPosition(max(0, min(self.player.duration(), self.player.position() + milliseconds)))

    def seek_ratio(self, ratio: float) -> None:
        self.player.setPosition(int(self.player.duration() * ratio))

    def _position_changed(self, value: int) -> None:
        duration = self.player.duration()
        if not self.position.isSliderDown(): self.position.setValue(value)
        self.waveform.set_position(value / duration if duration else 0)
        self.time.setText(f"{format_time(value)} / {format_time(duration)}")

    def _status_changed(self, status) -> None:
        if status == QMediaPlayer.MediaStatus.LoadedMedia and self._autoplay_pending:
            self._autoplay_pending = False
            self.player.play()
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.ended.emit()

    def _playback_error(self, error, message: str) -> None:
        self.error_label.setText(f"再生できません: {message or '未対応または破損した音声形式です'}")
        self.play.setEnabled(True)
