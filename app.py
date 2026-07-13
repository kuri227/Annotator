"""Production entry point for Annotator."""

import os
import sys

# Qt Multimedia's FFmpeg backend is verbose on Windows.  These settings must be
# applied before importing PySide6 and keep normal production runs silent.
os.environ["QT_LOGGING_RULES"] = "*.debug=false;qt.multimedia.ffmpeg=false;qt.multimedia.ffmpeg.*=false"
os.environ.pop("QT_FFMPEG_DEBUG", None)

from annotator.diagnostics import ErrorReporter, ResilientApplication
from annotator.main_window import MainWindow
from PySide6.QtGui import QFont


def main() -> int:
    reporter = ErrorReporter()
    sys.excepthook = reporter.report
    app = ResilientApplication(sys.argv, reporter)
    app.setApplicationName("Annotator")
    app.setApplicationVersion("5.3.0")
    app.setOrganizationName("Annotator")
    app.setFont(QFont("Segoe UI", 10))
    app.aboutToQuit.connect(reporter.close)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
