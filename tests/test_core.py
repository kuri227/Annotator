import tempfile
import unittest
import wave
import csv
import json
import time
import struct
import os
from pathlib import Path

os.environ["QT_LOGGING_RULES"] = "*.debug=false;qt.multimedia.ffmpeg=false;qt.multimedia.ffmpeg.*=false"

from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest

from annotator.models import MediaType, ProjectConfig
from annotator.models import Session
from annotator.main_window import MainWindow
from annotator.diagnostics import ErrorReporter
from annotator.storage import discover_files, load_annotations, save_annotations
from annotator.waveform import read_waveform
from annotator.file_overview import matching_indices


class CoreTests(unittest.TestCase):
    def test_corrupt_wav_with_huge_declared_size_is_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "corrupt.wav"
            header = (b"RIFF" + struct.pack("<I", 0xFFFFFFF0) + b"WAVEfmt " +
                      struct.pack("<IHHIIHH", 16, 1, 1, 8000, 16000, 2, 16) +
                      b"data" + struct.pack("<I", 0xFFFFFF00) + b"\0\0" * 20)
            path.write_bytes(header)
            started = time.monotonic()
            values = read_waveform(path)
            self.assertLess(time.monotonic() - started, 0.5)
            self.assertLessEqual(len(values), 1200)

    def test_error_reporter_records_exception_without_raising(self):
        with tempfile.TemporaryDirectory() as directory:
            reporter = ErrorReporter(Path(directory))
            try:
                raise RuntimeError("intentional recovery test")
            except RuntimeError as error:
                reporter.report(type(error), error, error.__traceback__, notify=False)
            for handler in reporter.logger.handlers:
                handler.flush()
            self.assertIn("intentional recovery test", reporter.log_path.read_text(encoding="utf-8"))
            reporter.close()

    def test_atomic_save_preserves_previous_file_on_serialization_error(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); path = root / "labels.json"
            path.write_text('{"safe.wav": ["dog"]}', encoding="utf-8")
            config = ProjectConfig(root, root / "raw_data", root / "input_data", path, "audio", ["dog"])
            with self.assertRaises(TypeError):
                save_annotations(config, {"broken.wav": [object()]})
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"safe.wav": ["dog"]})
            self.assertFalse(list(root.glob(".*.tmp")))

    def test_overview_filters_labeled_and_unlabeled_files(self):
        root = Path("project")
        config = ProjectConfig(root, root / "raw_data", root / "input_data", root / "labels.csv", "audio", ["speech"])
        session = Session(config, [root / "raw_data" / "a.wav", root / "raw_data" / "b.wav"], {"a.wav": ["speech"]})
        self.assertEqual(matching_indices(session, "labeled"), [0])
        self.assertEqual(matching_indices(session, "unlabeled"), [1])

    def test_project_config_normalizes_qt_style_string_media_type(self):
        config = ProjectConfig(Path("."), Path("."), Path("."), Path("labels.csv"), "audio", ["speech"])
        self.assertIs(config.media_type, MediaType.AUDIO)

    def test_audio_project_round_trip_and_nested_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = root / "raw_data" / "speaker_a"
            raw.mkdir(parents=True)
            audio = raw / "sample.wav"
            with wave.open(str(audio), "wb") as output:
                output.setparams((1, 2, 8000, 800, "NONE", "not compressed"))
                output.writeframes(b"\x00\x00" * 800)
            config = ProjectConfig(root, root / "raw_data", root / "input_data",
                                   root / "annotations" / "audio.csv", MediaType.AUDIO, ["speech"])
            self.assertEqual(discover_files(config), [audio])
            save_annotations(config, {"speaker_a/sample.wav": ["dog", "cat"]})
            self.assertEqual(load_annotations(config.annotation_file), {"speaker_a/sample.wav": ["dog", "cat"]})
            self.assertTrue((root / "input_data" / "speaker_a" / "sample.wav").exists())
            self.assertTrue(read_waveform(audio))

            with config.annotation_file.open(encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows[0]["filename"], "speaker_a/sample.wav")
            self.assertEqual(json.loads(rows[0]["labels"]), ["dog", "cat"])

    def test_legacy_single_label_csv_is_upgraded_on_load(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "legacy.csv"
            path.write_text("filename,label\nsample.wav,dog\n", encoding="utf-8")
            self.assertEqual(load_annotations(path), {"sample.wav": ["dog"]})


class InterfaceIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _window_with_project(self, root: Path, media_type: MediaType, filename: str) -> MainWindow:
        raw = root / "raw_data"; raw.mkdir(parents=True, exist_ok=True)
        config = ProjectConfig(root, raw, root / "input_data", root / "annotations" / "labels.csv",
                               media_type, ["dog", "cat"])
        window = MainWindow()
        window.session = Session(config, [raw / filename])
        window._rebuild_labels()
        window.viewer_stack.setCurrentIndex(1 if media_type == MediaType.AUDIO else 0)
        window.pages.setCurrentIndex(1)
        return window

    def test_image_viewer_and_multilabel_annotation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); window = self._window_with_project(root, MediaType.IMAGE, "animals.png")
            image = QImage(32, 32, QImage.Format.Format_RGB32); image.fill(0x33AA55)
            self.assertTrue(image.save(str(root / "raw_data" / "animals.png")))
            window._show_current(); window._toggle_label("dog", True); window._toggle_label("cat", True)
            self.assertFalse(window.image_viewer._pixmap.isNull())
            self.assertEqual(window.session.annotations["animals.png"], ["dog", "cat"])
            window.session.dirty = False
            window.close()

    def test_audio_viewer_and_multilabel_annotation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); window = self._window_with_project(root, MediaType.AUDIO, "animals.wav")
            audio = root / "raw_data" / "animals.wav"
            with wave.open(str(audio), "wb") as output:
                output.setparams((1, 2, 8000, 80, "NONE", "not compressed")); output.writeframes(b"\0\0" * 80)
            try:
                window._show_current(); window._toggle_label("dog", True); window._toggle_label("cat", True)
                self.assertTrue(window.audio_viewer.is_loading)
                self.assertFalse(window.audio_viewer.play.isEnabled())
                self.assertFalse(window.audio_viewer.loading_label.isHidden())
                deadline = time.monotonic() + 2
                while (window.audio_viewer.waveform._tasks or window.audio_viewer.is_loading) and time.monotonic() < deadline:
                    QTest.qWait(20)
                self.assertEqual(window.audio_viewer.title.text(), "animals.wav")
                self.assertTrue(window.audio_viewer.waveform._values)
                self.assertFalse(window.audio_viewer.is_loading)
                self.assertTrue(window.audio_viewer.play.isEnabled())
                self.assertEqual(window.session.annotations["animals.wav"], ["dog", "cat"])
            finally:
                window.audio_viewer.clear(); self.app.processEvents()
                window.session.dirty = False; window.close()

    def test_rapid_audio_switch_keeps_ui_responsive(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); window = self._window_with_project(root, MediaType.AUDIO, "first.wav")
            paths = [root / "raw_data" / name for name in ("first.wav", "second.wav")]
            for path in paths:
                with wave.open(str(path), "wb") as output:
                    output.setparams((1, 2, 8000, 800, "NONE", "not compressed")); output.writeframes(b"\0\0" * 800)
            try:
                for index in range(30):
                    window.audio_viewer.load(paths[index % 2], autoplay=False)
                    self.app.processEvents()
                QTest.qWait(300)
                self.assertEqual(window.audio_viewer.title.text(), "second.wav")
                self.assertTrue(window.isEnabled())
            finally:
                window.audio_viewer.clear(); self.app.processEvents(); window.close()

    def test_navigation_while_autoplaying_returns_immediately(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); window = self._window_with_project(root, MediaType.AUDIO, "first.wav")
            raw = root / "raw_data"
            paths = [raw / "first.wav", raw / "second.wav"]
            for path in paths:
                with wave.open(str(path), "wb") as output:
                    output.setparams((1, 2, 8000, 8000, "NONE", "not compressed")); output.writeframes(b"\0\0" * 8000)
            window.session.files = paths
            try:
                window._show_current()
                QTest.qWait(250)
                started = time.monotonic()
                window._move(1)
                self.assertLess(time.monotonic() - started, 0.1)
                self.assertEqual(window.session.current_index, 1)
                self.assertEqual(window.audio_viewer.title.text(), "second.wav")
            finally:
                window.audio_viewer.clear(); self.app.processEvents(); window.close()


if __name__ == "__main__":
    unittest.main()
