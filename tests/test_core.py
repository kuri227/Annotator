import tempfile
import unittest
import wave
from pathlib import Path

from annotator.models import MediaType, ProjectConfig
from annotator.storage import discover_files, load_annotations, save_annotations
from annotator.waveform import read_waveform
from annotator.file_overview import matching_indices


class CoreTests(unittest.TestCase):
    def test_overview_filters_labeled_and_unlabeled_files(self):
        root = Path("project")
        config = ProjectConfig(root, root / "raw_data", root / "input_data", root / "labels.csv", "audio", ["speech"])
        from annotator.models import Session
        session = Session(config, [root / "raw_data" / "a.wav", root / "raw_data" / "b.wav"], {"a.wav": "speech"})
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
            save_annotations(config, {"speaker_a/sample.wav": "speech"})
            self.assertEqual(load_annotations(config.annotation_file), {"speaker_a/sample.wav": "speech"})
            self.assertTrue((root / "input_data" / "speaker_a" / "sample.wav").exists())
            self.assertTrue(read_waveform(audio))


if __name__ == "__main__":
    unittest.main()
