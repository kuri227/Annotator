import tempfile
import unittest
import wave
import csv
import json
from pathlib import Path

from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from annotator.models import MediaType, ProjectConfig
from annotator.models import Session
from annotator.main_window import MainWindow
from annotator.storage import discover_files, load_annotations, save_annotations
from annotator.waveform import read_waveform
from annotator.file_overview import matching_indices


class CoreTests(unittest.TestCase):
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
            window._show_current(); window._toggle_label("dog", True); window._toggle_label("cat", True)
            self.assertEqual(window.audio_viewer.title.text(), "animals.wav")
            self.assertTrue(window.audio_viewer.waveform._values)
            self.assertEqual(window.session.annotations["animals.wav"], ["dog", "cat"])
            window.audio_viewer.clear(); self.app.processEvents()
            window.session.dirty = False; window.close()


if __name__ == "__main__":
    unittest.main()
