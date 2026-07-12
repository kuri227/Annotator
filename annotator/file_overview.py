import math

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QDialog, QHBoxLayout, QHeaderView, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from .models import Session


PAGE_SIZE = 20


def relative_name(session: Session, index: int) -> str:
    return str(session.files[index].relative_to(session.config.raw_dir)).replace("\\", "/")


def matching_indices(session: Session, filter_name: str) -> list[int]:
    indices = list(range(len(session.files)))
    if filter_name == "unlabeled":
        return [index for index in indices if relative_name(session, index) not in session.annotations]
    if filter_name == "labeled":
        return [index for index in indices if relative_name(session, index) in session.annotations]
    return indices


class FileOverviewDialog(QDialog):
    file_selected = Signal(int)

    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        self.session = session
        self.page = 0
        self.indices: list[int] = []
        self.setWindowTitle("ファイル一覧・ラベリング状況")
        self.resize(860, 620)

        layout = QVBoxLayout(self)
        heading = QHBoxLayout()
        self.summary = QLabel()
        self.filter = QComboBox()
        self.filter.addItem("すべて", "all")
        self.filter.addItem("未分類のみ", "unlabeled")
        self.filter.addItem("分類済みのみ", "labeled")
        heading.addWidget(self.summary, 1)
        heading.addWidget(QLabel("表示:")); heading.addWidget(self.filter)
        layout.addLayout(heading)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["No.", "状態", "ラベル", "ファイル"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

        paging = QHBoxLayout()
        self.previous = QPushButton("← 前の20件")
        self.page_label = QLabel(); self.page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.next = QPushButton("次の20件 →")
        paging.addWidget(self.previous); paging.addWidget(self.page_label, 1); paging.addWidget(self.next)
        layout.addLayout(paging)

        self.filter.currentIndexChanged.connect(self._filter_changed)
        self.previous.clicked.connect(lambda: self._change_page(-1))
        self.next.clicked.connect(lambda: self._change_page(1))
        self.table.cellDoubleClicked.connect(self._open_row)
        self.refresh()

    def refresh(self) -> None:
        filter_name = self.filter.currentData()
        self.indices = matching_indices(self.session, filter_name)
        page_count = max(1, math.ceil(len(self.indices) / PAGE_SIZE))
        self.page = min(self.page, page_count - 1)
        visible = self.indices[self.page * PAGE_SIZE:(self.page + 1) * PAGE_SIZE]
        self.table.setRowCount(len(visible))
        for row, index in enumerate(visible):
            name = relative_name(self.session, index)
            label = self.session.annotations.get(name)
            values = (str(index + 1), "✓ 分類済み" if label else "○ 未分類", label or "—", name)
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, index)
                if column == 1:
                    item.setForeground(Qt.GlobalColor.green if label else Qt.GlobalColor.yellow)
                self.table.setItem(row, column, item)
        total = len(self.session.files); completed = self.session.completed
        self.summary.setText(f"分類済み {completed}件  •  未分類 {total - completed}件  •  全{total}件")
        self.page_label.setText(f"{self.page + 1} / {page_count} ページ（{len(self.indices)}件）")
        self.previous.setEnabled(self.page > 0)
        self.next.setEnabled(self.page + 1 < page_count)

    def _filter_changed(self) -> None:
        self.page = 0
        self.refresh()

    def _change_page(self, amount: int) -> None:
        self.page += amount
        self.refresh()

    def _open_row(self, row: int, column: int) -> None:
        item = self.table.item(row, 0)
        if item:
            self.file_selected.emit(item.data(Qt.ItemDataRole.UserRole))
            self.accept()
