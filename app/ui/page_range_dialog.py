from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from app.i18n import t
from app.model.page_range import normalize_page_range
from app.model.print_job import FileType, PrintJob


class PageRangeDialog(QtWidgets.QDialog):
    def __init__(self, jobs: list[PrintJob], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("page_range_title"))
        self.resize(800, 420)
        self._jobs = list(jobs)
        self._selection: dict[str, str] = {}
        self.inputs: dict[str, QtWidgets.QLineEdit] = {}
        layout = QtWidgets.QVBoxLayout(self)
        hint = QtWidgets.QLabel(t("page_range_hint"))
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.table = QtWidgets.QTableWidget(len(jobs), 3)
        self.table.setHorizontalHeaderLabels([t("table_file"), t("table_pages"), t("table_page_range")])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(40)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        for row, job in enumerate(jobs):
            item = QtWidgets.QTableWidgetItem(job.file_name)
            item.setToolTip(job.file_path)
            self.table.setItem(row, 0, item)
            # Excel pagination changes with orientation and the selected sheets.
            count = str(job.page_count) if job.page_count is not None else t("page_range_unknown_count")
            if job.file_type == FileType.EXCEL:
                count = t("page_range_excel_count")
            self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(count))
            editor = QtWidgets.QLineEdit(job.page_range)
            editor.setPlaceholderText(t("page_range_placeholder"))
            editor.setAccessibleName(t("page_range_file_fmt", file=job.file_name))
            self.inputs[job.id] = editor
            self.table.setCellWidget(row, 2, editor)
        layout.addWidget(self.table)
        self.error_label = QtWidgets.QLabel()
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet("color: #c42b1c;")
        layout.addWidget(self.error_label)
        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def accept(self) -> None:
        selection = {}
        for job in self._jobs:
            try:
                total = None if job.file_type == FileType.EXCEL else job.page_count
                selection[job.id] = normalize_page_range(self.inputs[job.id].text(), total)
            except ValueError as exc:
                self.error_label.setText(f"{job.file_name}：{exc}")
                self.inputs[job.id].setFocus()
                return
        self._selection = selection
        super().accept()

    @staticmethod
    def get_ranges(jobs: list[PrintJob], parent=None) -> tuple[dict[str, str], bool]:
        dialog = PageRangeDialog(jobs, parent)
        ok = dialog.exec() == QtWidgets.QDialog.Accepted
        return dialog._selection, ok
