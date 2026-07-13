from pathlib import Path

from PySide6.QtCore import QTimer, Qt, QUrl, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QProgressBar, QPushButton, QSlider,
    QVBoxLayout, QWidget
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
        self._expected_source = QUrl()
        self._loading_seconds = 0
        self.is_loading = False

        self.waveform = WaveformWidget()
        self.title = QLabel("音声を選択してください")
        self.title.setObjectName("MediaTitle")
        self.time = QLabel("00:00 / 00:00")
        self.error_label = QLabel()
        self.error_label.setStyleSheet("color:#fca5a5")
        self.error_label.setWordWrap(True)
        self.loading_label = QLabel("音声を読み込み中…")
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_label.setStyleSheet("color:#7dd3fc;font-weight:700;padding:6px")
        self.loading_progress = QProgressBar()
        self.loading_progress.setRange(0, 0)
        self.loading_progress.setTextVisible(False)
        self.loading_label.hide(); self.loading_progress.hide()
        self.loading_timer = QTimer(self)
        self.loading_timer.setInterval(1000)
        self.loading_timer.timeout.connect(self._update_loading_elapsed)
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
        layout.addWidget(self.title); layout.addWidget(self.loading_label); layout.addWidget(self.loading_progress)
        layout.addWidget(self.waveform, 1)
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
        self.player.bufferProgressChanged.connect(self._buffer_progress_changed)

    def load(self, path: Path, autoplay: bool = False) -> None:
        self._load_id += 1
        load_id = self._load_id
        self._autoplay_pending = autoplay
        self._expected_source = QUrl.fromLocalFile(str(path))
        self.error_label.clear()
        self.title.setText(path.name)
        self._begin_loading()
        self.waveform.set_audio(path)
        # Never call stop() while FFmpeg is decoding. On some malformed/junk-
        # prefixed files that call can block the GUI thread. setSource() performs
        # the supported source transition itself on the next event-loop turn.
        QTimer.singleShot(0, lambda: self._set_source(load_id, path))

    def _set_source(self, load_id: int, path: Path) -> None:
        if load_id == self._load_id:
            self.player.setSource(self._expected_source)

    def clear(self) -> None:
        """Release the media file handle, particularly important on Windows."""
        self._load_id += 1
        self._autoplay_pending = False
        self._expected_source = QUrl()
        self._end_loading(show_ready=False)
        self.player.setSource(QUrl())
        self.title.setText("音声を選択してください")

    def toggle(self) -> None:
        if self.is_loading:
            return
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def skip(self, milliseconds: int) -> None:
        if self.is_loading:
            return
        self.player.setPosition(max(0, min(self.player.duration(), self.player.position() + milliseconds)))

    def seek_ratio(self, ratio: float) -> None:
        if self.is_loading:
            return
        self.player.setPosition(int(self.player.duration() * ratio))

    def _position_changed(self, value: int) -> None:
        duration = self.player.duration()
        if not self.position.isSliderDown(): self.position.setValue(value)
        self.waveform.set_position(value / duration if duration else 0)
        self.time.setText(f"{format_time(value)} / {format_time(duration)}")

    def _status_changed(self, status) -> None:
        # Ignore delayed status signals belonging to the previously selected file.
        if self.player.source() != self._expected_source:
            return
        if status in (QMediaPlayer.MediaStatus.LoadedMedia, QMediaPlayer.MediaStatus.BufferedMedia):
            self._end_loading(show_ready=True)
        if status == QMediaPlayer.MediaStatus.LoadedMedia and self._autoplay_pending:
            self._autoplay_pending = False
            self.player.play()
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.ended.emit()

    def _playback_error(self, error, message: str) -> None:
        if self.player.source() != self._expected_source:
            return
        self._autoplay_pending = False
        self._end_loading(show_ready=False)
        self.error_label.setText(f"再生できません: {message or '未対応または破損した音声形式です'}")

    def _begin_loading(self) -> None:
        self.is_loading = True
        self._loading_seconds = 0
        self.loading_label.setText("音声を読み込み中…  前後ボタンでスキップできます")
        self.loading_progress.setRange(0, 0)
        self.loading_label.show(); self.loading_progress.show(); self.loading_timer.start()
        self._set_media_controls_enabled(False)

    def _end_loading(self, show_ready: bool) -> None:
        self.is_loading = False
        self.loading_timer.stop()
        self._set_media_controls_enabled(True)
        if show_ready:
            load_id = self._load_id
            self.loading_progress.setRange(0, 100); self.loading_progress.setValue(100)
            self.loading_label.setText("再生準備完了")
            QTimer.singleShot(800, lambda: self._hide_ready(load_id))
        else:
            self.loading_label.hide(); self.loading_progress.hide()

    def _hide_ready(self, load_id: int) -> None:
        if load_id == self._load_id and not self.is_loading:
            self.loading_label.hide(); self.loading_progress.hide()

    def _update_loading_elapsed(self) -> None:
        self._loading_seconds += 1
        self.loading_label.setText(
            f"音声を読み込み中… {self._loading_seconds}秒  前後ボタンでスキップできます"
        )

    def _buffer_progress_changed(self, progress: float) -> None:
        if self.is_loading and self.player.source() == self._expected_source and 0 < progress < 1:
            self.loading_progress.setRange(0, 100)
            self.loading_progress.setValue(round(progress * 100))
            self.loading_progress.setFormat("%p%")
            self.loading_progress.setTextVisible(True)

    def _set_media_controls_enabled(self, enabled: bool) -> None:
        for widget in (self.play, self.back, self.forward, self.position, self.speed):
            widget.setEnabled(enabled)
