from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence
from PySide6.QtWidgets import (
    QButtonGroup, QComboBox, QFileDialog, QFormLayout, QFrame, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton,
    QProgressBar, QScrollArea, QStackedWidget, QVBoxLayout, QWidget,
)

from .media_widgets import AudioViewer, ImageViewer
from .file_overview import FileOverviewDialog
from .models import MediaType, ProjectConfig, Session
from .storage import discover_files, load_annotations, save_annotations


STYLE = """
QMainWindow, QWidget { background:#0f172a; color:#e2e8f0; font-family:'Segoe UI'; font-size:13px; }
QGroupBox { border:1px solid #334155; border-radius:8px; margin-top:12px; padding:16px 12px 12px; font-weight:600; }
QLineEdit, QComboBox { background:#1e293b; border:1px solid #475569; border-radius:5px; padding:7px; }
QPushButton { background:#334155; border:0; border-radius:5px; padding:9px; font-weight:600; }
QPushButton:hover { background:#475569; } QPushButton:disabled { color:#64748b; }
QPushButton#Primary { background:#0284c7; } QPushButton#Primary:hover { background:#0ea5e9; }
QPushButton#LabelButton { text-align:left; padding:11px; }
QPushButton#LabelButton:checked { background:#0369a1; border:2px solid #38bdf8; }
QLabel#MediaTitle { font-size:18px; font-weight:700; padding:8px; }
QFrame#Sidebar { background:#172033; border-left:1px solid #334155; }
QProgressBar { border:0; background:#1e293b; border-radius:4px; text-align:center; }
QProgressBar::chunk { background:#0ea5e9; border-radius:4px; }
"""


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.session: Session | None = None
        self.label_buttons: list[QPushButton] = []
        self.setWindowTitle("Annotator 5.1")
        self.resize(1280, 820)
        self.setStyleSheet(STYLE)
        self.pages = QStackedWidget()
        self.setCentralWidget(self.pages)
        self._build_setup()
        self._build_workspace()
        self._install_shortcuts()

    def _build_setup(self) -> None:
        page = QWidget(); outer = QVBoxLayout(page)
        outer.setContentsMargins(80, 45, 80, 45)
        title = QLabel("Annotator"); title.setStyleSheet("font-size:30px;font-weight:700")
        subtitle = QLabel("画像・音声の分類教師データを、迷わず高速に作成")
        outer.addWidget(title); outer.addWidget(subtitle)

        box = QGroupBox("プロジェクト設定"); form = QFormLayout(box)
        self.media_type = QComboBox(); self.media_type.addItem("画像分類", MediaType.IMAGE); self.media_type.addItem("音声分類", MediaType.AUDIO)
        self.root_edit = QLineEdit(); self.raw_edit = QLineEdit(); self.input_edit = QLineEdit(); self.label_edit = QLineEdit()
        form.addRow("データ種別", self.media_type)
        for caption, edit, handler in (
            ("プロジェクト", self.root_edit, self._select_project),
            ("raw_data", self.raw_edit, lambda: self._select_directory(self.raw_edit)),
            ("input_data", self.input_edit, lambda: self._select_directory(self.input_edit)),
            ("アノテーション", self.label_edit, self._select_annotation),
        ):
            row = QHBoxLayout(); row.addWidget(edit, 1); button = QPushButton("選択…"); button.clicked.connect(handler); row.addWidget(button)
            form.addRow(caption, row)
        hint = QLabel("推奨構成: project/raw_data → 元データ、project/input_data → 学習用コピー、project/annotations → ラベル")
        hint.setWordWrap(True); hint.setStyleSheet("color:#94a3b8")
        form.addRow("", hint)
        outer.addWidget(box)

        labels = QGroupBox("クラス設定"); labels_layout = QVBoxLayout(labels)
        labels_layout.addWidget(QLabel("1行に1クラス（上から数字キー 1〜9、0 に対応）"))
        self.labels_edit = QLineEdit("Cat, Dog")
        self.labels_edit.setPlaceholderText("例: speech, music, noise")
        labels_layout.addWidget(self.labels_edit); outer.addWidget(labels)
        self.start_button = QPushButton("アノテーションを開始")
        self.start_button.setObjectName("Primary"); self.start_button.setMinimumHeight(48)
        self.start_button.clicked.connect(self._start); outer.addWidget(self.start_button); outer.addStretch()
        self.pages.addWidget(page)

    def _build_workspace(self) -> None:
        page = QWidget(); layout = QHBoxLayout(page); layout.setContentsMargins(0, 0, 0, 0)
        self.viewer_stack = QStackedWidget(); self.image_viewer = ImageViewer(); self.audio_viewer = AudioViewer()
        self.viewer_stack.addWidget(self.image_viewer); self.viewer_stack.addWidget(self.audio_viewer)
        layout.addWidget(self.viewer_stack, 1)

        sidebar = QFrame(); sidebar.setObjectName("Sidebar"); sidebar.setFixedWidth(350)
        side = QVBoxLayout(sidebar); side.setContentsMargins(18, 18, 18, 18)
        back = QPushButton("← プロジェクト設定"); back.clicked.connect(self._back); side.addWidget(back)
        self.position_label = QLabel("現在位置: - / -")
        self.position_label.setStyleSheet("color:#94a3b8;font-weight:600")
        self.file_label = QLabel("-"); self.file_label.setWordWrap(True); self.file_label.setStyleSheet("font-size:16px;font-weight:700")
        self.current_label = QLabel("未分類"); self.current_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.current_label.setWordWrap(True)
        self.current_label.setStyleSheet("background:#1e293b;color:#38bdf8;padding:16px;border-radius:6px;font-size:22px;font-weight:700")
        side.addWidget(self.position_label); side.addWidget(self.file_label); side.addWidget(self.current_label)
        self.progress = QProgressBar(); side.addWidget(self.progress)
        overview = QPushButton("ファイル一覧・未分類を確認")
        overview.clicked.connect(self._show_overview); side.addWidget(overview)
        nav = QHBoxLayout(); prev = QPushButton("← 前へ"); nxt = QPushButton("次へ →"); prev.clicked.connect(lambda: self._move(-1)); nxt.clicked.connect(lambda: self._move(1)); nav.addWidget(prev); nav.addWidget(nxt); side.addLayout(nav)
        side.addWidget(QLabel("クラス（複数選択可）"))
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.label_host = QWidget(); self.label_layout = QVBoxLayout(self.label_host); self.label_layout.setContentsMargins(0, 0, 0, 0)
        scroll.setWidget(self.label_host); side.addWidget(scroll, 1)
        commit_next = QPushButton("選択を確定して次へ  [Enter]")
        commit_next.setObjectName("Primary"); commit_next.clicked.connect(self._confirm_and_next)
        side.addWidget(commit_next)
        self.autoplay = QPushButton("自動再生: ON"); self.autoplay.setCheckable(True); self.autoplay.setChecked(True)
        self.autoplay.clicked.connect(lambda checked: self.autoplay.setText(f"自動再生: {'ON' if checked else 'OFF'}")); side.addWidget(self.autoplay)
        shortcuts = QLabel("数字 ラベル切替  •  Enter 確定して次へ\nSpace 再生/一時停止  •  J/L ±5秒\n←/→ 前後  •  S 保留  •  Ctrl+S 保存")
        shortcuts.setStyleSheet("color:#94a3b8"); side.addWidget(shortcuts)
        save = QPushButton("保存  [Ctrl+S]"); save.setObjectName("Primary"); save.clicked.connect(self._save); side.addWidget(save)
        layout.addWidget(sidebar); self.pages.addWidget(page)

    def _install_shortcuts(self) -> None:
        for key, callback in (("Left", lambda: self._move(-1)), ("Right", lambda: self._move(1)),
                              ("Space", self._toggle_audio), ("J", lambda: self.audio_viewer.skip(-5000)),
                              ("L", lambda: self.audio_viewer.skip(5000)), ("S", self._skip),
                              ("Return", self._confirm_and_next), ("Enter", self._confirm_and_next),
                              ("Ctrl+S", self._save)):
            action = QAction(self); action.setShortcut(QKeySequence(key)); action.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut); action.triggered.connect(callback); self.addAction(action)
        for index, key in enumerate(["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"]):
            action = QAction(self); action.setShortcut(QKeySequence(key)); action.triggered.connect(lambda checked=False, i=index: self._label_by_index(i)); self.addAction(action)

    def _select_project(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, "プロジェクトフォルダ")
        if selected:
            root = Path(selected); self.root_edit.setText(str(root))
            self.raw_edit.setText(str(root / "raw_data")); self.input_edit.setText(str(root / "input_data"))
            media_type = MediaType(self.media_type.currentData())
            self.label_edit.setText(str(root / "annotations" / f"{media_type.value}_labels.csv"))

    def _select_directory(self, edit: QLineEdit) -> None:
        selected = QFileDialog.getExistingDirectory(self, "フォルダを選択", self.root_edit.text())
        if selected: edit.setText(selected)

    def _select_annotation(self) -> None:
        selected, _ = QFileDialog.getSaveFileName(self, "アノテーションファイル", self.label_edit.text() or self.root_edit.text(), "CSV (*.csv);;JSON (*.json)")
        if selected: self.label_edit.setText(selected)

    def _start(self) -> None:
        labels = [item.strip() for item in self.labels_edit.text().replace("\n", ",").split(",") if item.strip()]
        paths = [self.root_edit.text(), self.raw_edit.text(), self.input_edit.text(), self.label_edit.text()]
        if not all(paths) or not labels:
            QMessageBox.warning(self, "設定不足", "フォルダ、保存先、1つ以上のクラスを設定してください。"); return
        if len(labels) > 10 or len(set(labels)) != len(labels):
            QMessageBox.warning(self, "クラス設定", "クラスは重複なしで最大10個までです。"); return
        config = ProjectConfig(
            Path(paths[0]), Path(paths[1]), Path(paths[2]), Path(paths[3]),
            MediaType(self.media_type.currentData()), labels,
        )
        if not config.raw_dir.is_dir():
            QMessageBox.warning(self, "フォルダなし", f"raw_data が見つかりません:\n{config.raw_dir}"); return
        files = discover_files(config)
        if not files:
            QMessageBox.information(self, "対象なし", "対応するファイルが raw_data 内に見つかりませんでした。"); return
        self.session = Session(config, files, load_annotations(config.annotation_file))
        self._rebuild_labels(); self.viewer_stack.setCurrentIndex(1 if config.media_type == MediaType.AUDIO else 0)
        self.pages.setCurrentIndex(1); self._show_current()

    def _rebuild_labels(self) -> None:
        while self.label_layout.count():
            item = self.label_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        assert self.session
        self.label_buttons = []
        for index, label in enumerate(self.session.config.labels):
            key = index + 1 if index < 9 else 0
            button = QPushButton(f"{key}    {label}"); button.setObjectName("LabelButton")
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, value=label: self._toggle_label(value, checked))
            self.label_buttons.append(button); self.label_layout.addWidget(button)
        self.label_layout.addStretch()

    def _show_current(self) -> None:
        if not self.session or not self.session.current_file: return
        path = self.session.current_file; name = str(path.relative_to(self.session.config.raw_dir)).replace("\\", "/")
        self.position_label.setText(f"現在位置: {self.session.current_index + 1} / {len(self.session.files)} 件目")
        selected = self.session.annotations.get(name, [])
        self.file_label.setText(name); self.current_label.setText(" / ".join(selected) or "未分類")
        for button, label in zip(self.label_buttons, self.session.config.labels):
            button.blockSignals(True); button.setChecked(label in selected); button.blockSignals(False)
        self.progress.setMaximum(len(self.session.files)); self.progress.setValue(self.session.completed)
        self.progress.setFormat(f"完了 {self.session.completed} / {len(self.session.files)}")
        if self.session.config.media_type == MediaType.AUDIO:
            self.audio_viewer.load(path)
            if self.autoplay.isChecked(): self.audio_viewer.player.play()
        else: self.image_viewer.load(path)

    def _toggle_label(self, label: str, checked: bool | None = None) -> None:
        if not self.session or not self.session.current_file: return
        name = str(self.session.current_file.relative_to(self.session.config.raw_dir)).replace("\\", "/")
        selected = list(self.session.annotations.get(name, []))
        should_add = label not in selected if checked is None else checked
        if should_add and label not in selected:
            selected.append(label)
        elif not should_add and label in selected:
            selected.remove(label)
        selected.sort(key=self.session.config.labels.index)
        if selected:
            self.session.annotations[name] = selected
        else:
            self.session.annotations.pop(name, None)
        self.session.dirty = True
        self.current_label.setText(" / ".join(selected) or "未分類")
        self.progress.setValue(self.session.completed)
        self.progress.setFormat(f"完了 {self.session.completed} / {len(self.session.files)}")

    def _label_by_index(self, index: int) -> None:
        if self.pages.currentIndex() == 1 and self.session and index < len(self.session.config.labels):
            self._toggle_label(self.session.config.labels[index])
            self.label_buttons[index].blockSignals(True)
            self.label_buttons[index].setChecked(self.session.config.labels[index] in self._current_labels())
            self.label_buttons[index].blockSignals(False)

    def _current_labels(self) -> list[str]:
        if not self.session or not self.session.current_file:
            return []
        name = str(self.session.current_file.relative_to(self.session.config.raw_dir)).replace("\\", "/")
        return self.session.annotations.get(name, [])

    def _confirm_and_next(self) -> None:
        if self.pages.currentIndex() == 1 and self._current_labels():
            self._move(1)

    def _move(self, amount: int) -> None:
        if not self.session or self.pages.currentIndex() != 1: return
        self.session.current_index = (self.session.current_index + amount) % len(self.session.files); self._show_current()

    def _show_overview(self) -> None:
        if not self.session:
            return
        self.audio_viewer.player.pause()
        dialog = FileOverviewDialog(self.session, self)
        dialog.file_selected.connect(self._jump_to_file)
        dialog.exec()

    def _jump_to_file(self, index: int) -> None:
        if self.session and 0 <= index < len(self.session.files):
            self.session.current_index = index
            self._show_current()

    def _skip(self) -> None:
        if self.pages.currentIndex() == 1: self._move(1)

    def _toggle_audio(self) -> None:
        if self.session and self.pages.currentIndex() == 1 and self.session.config.media_type == MediaType.AUDIO: self.audio_viewer.toggle()

    def _save(self) -> None:
        if not self.session: return
        try:
            save_annotations(self.session.config, self.session.annotations); self.session.dirty = False
            QMessageBox.information(self, "保存完了", f"{len(self.session.annotations)}件のアノテーションを保存しました。")
        except OSError as error: QMessageBox.critical(self, "保存エラー", str(error))

    def _back(self) -> None:
        if self._confirm_discard(): self.audio_viewer.clear(); self.pages.setCurrentIndex(0)

    def _confirm_discard(self) -> bool:
        if not self.session or not self.session.dirty: return True
        return QMessageBox.question(self, "未保存の変更", "保存していない変更を破棄しますか？") == QMessageBox.StandardButton.Yes

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._confirm_discard():
            self.audio_viewer.clear()
            event.accept()
        else:
            event.ignore()
