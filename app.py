"""Production entry point for Annotator."""

import os
import sys

# Qt Multimedia's FFmpeg backend is verbose on Windows.  These settings must be
# applied before importing PySide6 and keep normal production runs silent.
os.environ.setdefault("QT_LOGGING_RULES", "*.debug=false;qt.multimedia.ffmpeg.*=false")
os.environ.setdefault("QT_FFMPEG_DEBUG", "0")

from annotator.diagnostics import ErrorReporter, ResilientApplication
from annotator.main_window import MainWindow


def main() -> int:
    reporter = ErrorReporter()
    sys.excepthook = reporter.report
    app = ResilientApplication(sys.argv, reporter)
    app.setApplicationName("Annotator")
    app.setApplicationVersion("5.2.0")
    app.setOrganizationName("Annotator")
    app.aboutToQuit.connect(reporter.close)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
