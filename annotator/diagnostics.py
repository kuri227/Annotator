"""Last-resort error boundary and private, rotating diagnostics."""

import logging
import sys
import tempfile
from logging.handlers import RotatingFileHandler
from pathlib import Path
from types import TracebackType

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMessageBox


class ErrorReporter:
    def __init__(self, log_dir: Path | None = None):
        base = log_dir or Path.home() / "AppData" / "Local" / "Annotator" / "logs"
        try:
            base.mkdir(parents=True, exist_ok=True)
        except OSError:
            base = Path(tempfile.gettempdir()) / "Annotator" / "logs"
            base.mkdir(parents=True, exist_ok=True)
        self.log_path = base / "annotator.log"
        self.logger = logging.getLogger(f"annotator.{id(self)}")
        self.logger.setLevel(logging.ERROR)
        self.logger.propagate = False
        handler = RotatingFileHandler(self.log_path, maxBytes=1_000_000, backupCount=2, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        self.logger.addHandler(handler)
        self._notification_pending = False

    def close(self) -> None:
        for handler in list(self.logger.handlers):
            handler.close()
            self.logger.removeHandler(handler)

    def report(self, exc_type: type[BaseException], error: BaseException,
               traceback: TracebackType | None, notify: bool = True) -> None:
        try:
            self.logger.error("Unhandled application error", exc_info=(exc_type, error, traceback))
        except Exception:
            pass  # Diagnostics must never become a second failure.
        if notify and QApplication.instance() and not self._notification_pending:
            self._notification_pending = True
            QTimer.singleShot(0, self._show_recovery_message)

    def _show_recovery_message(self) -> None:
        try:
            QMessageBox.warning(
                None, "処理エラー",
                "処理中にエラーが発生しましたが、アプリは継続できます。\n"
                "現在の操作をやり直すか、先にアノテーションを保存してください。",
            )
        finally:
            self._notification_pending = False


class ResilientApplication(QApplication):
    """Keep the Qt event loop alive when a Python event handler fails."""

    def __init__(self, arguments: list[str], reporter: ErrorReporter):
        super().__init__(arguments)
        self.reporter = reporter

    def notify(self, receiver, event) -> bool:
        try:
            return super().notify(receiver, event)
        except Exception:
            exc_type, error, traceback = sys.exc_info()
            self.reporter.report(exc_type, error, traceback)
            return False
