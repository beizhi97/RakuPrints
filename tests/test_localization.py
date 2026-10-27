import ast
import os
from pathlib import Path
import string
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from urllib.error import HTTPError

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtCore, QtGui, QtWidgets

from app import i18n
from app.app_context import AppContext, UserSettings
from app.backend.pdf_backend import PdfBackend, _assert_pdf_paper_matches
from app.backend.excel_backend import _assert_excel_paper_matches
from app.controller.job_manager import JobManager
from app.controller.excel_orientation_analyzer import ExcelOrientationAnalyzer
from app.controller.update_manager import UpdateChecker
from app.model.print_job import PrintJob, FileType, DuplexMode
from app.ui.excel_orientation_dialog import ExcelOrientationDialog
from app.ui.language import apply_ui_language
from app.ui.main_window import MainWindow
from app.ui.settings_panel import SettingsPanel


class LocalizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def setUp(self):
        i18n.set_language("zh")
        apply_ui_language(self.app)

    def tearDown(self):
        i18n.set_language("en")
        apply_ui_language(self.app)

    def test_translation_keys_and_placeholders_match(self):
        formatter = string.Formatter()
        reference = i18n.TRANSLATIONS["ja"]
        for language, translations in i18n.TRANSLATIONS.items():
            with self.subTest(language=language):
                self.assertEqual(set(reference), set(translations))
                for key, value in translations.items():
                    fields = lambda text: {field for _, field, _, _ in formatter.parse(text) if field}
                    self.assertEqual(fields(reference[key]), fields(value), (language, key))
                    self.assertTrue(value.strip(), (language, key))

    def test_all_literal_translation_calls_exist(self):
        for path in Path("app").rglob("*.py"):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "t":
                    if node.args and isinstance(node.args[0], ast.Constant):
                        self.assertIn(node.args[0].value, i18n.TRANSLATIONS["zh"], str(path))

    def test_qt_buttons_and_font_follow_language(self):
        button = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Cancel)
        self.assertIn("取消", button.button(QtWidgets.QDialogButtonBox.Cancel).text())
        if "Microsoft YaHei UI" in QtGui.QFontDatabase.families():
            self.assertEqual(self.app.font().family(), "Microsoft YaHei UI")
        i18n.set_language("en")
        apply_ui_language(self.app)
        english = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Cancel)
        self.assertIn("Cancel", english.button(QtWidgets.QDialogButtonBox.Cancel).text())

    def test_file_dialog_and_live_language_switch(self):
        with tempfile.TemporaryDirectory() as directory, patch("app.app_context._get_app_data_dir", return_value=Path(directory)):
            context = AppContext()
            context.settings.update_check_enabled = False
            manager = JobManager(context)
            with patch("app.ui.main_window.list_printers", return_value=[]), patch("app.ui.main_window.get_default_printer_name", return_value=""):
                window = MainWindow(context, manager)
            with patch.object(QtWidgets.QFileDialog, "getOpenFileNames", return_value=([], "")) as picker:
                window._on_add_files()
                self.assertTrue(picker.call_args.args[3].startswith("可打印的文件"))
            window._on_language_changed("en")
            self.assertEqual(window.add_files_action.text(), "Add Files")
            window._on_language_changed("zh")
            self.assertEqual(window.add_files_action.text(), "添加文件")
            self.assertEqual(context.settings.language_mode, "zh")
            self.assertEqual(self.app.font().pointSize(), 11)
            window.close()

    def test_chinese_filename_missing_pdf_error(self):
        job = PrintJob("不存在的目录/中文文件.pdf", FileType.PDF, "", 1, DuplexMode.OFF)
        with self.assertRaisesRegex(RuntimeError, "找不到文件"):
            PdfBackend(MagicMock()).print(job)

    def test_retranslation_preserves_settings_without_emitting_changes(self):
        panel = SettingsPanel()
        panel.retranslate()
        for combo, value in [(panel.language_combo, "zh"), (panel.theme_combo, "dark"),
                             (panel.duplex_combo, DuplexMode.SHORT_EDGE.value),
                             (panel.excel_orientation_combo, "ask"), (panel.pdf_scale_mode_combo, "fit")]:
            combo.setCurrentIndex(combo.findData(value))
        changes = []
        for signal in [panel.language_changed, panel.theme_changed, panel.duplex_changed,
                       panel.excel_orientation_mode_changed, panel.pdf_scale_mode_changed]:
            signal.connect(changes.append)
        i18n.set_language("en")
        panel.retranslate()
        self.assertEqual(changes, [])
        self.assertEqual(panel.language_combo.currentData(), "zh")
        self.assertEqual(panel.duplex_combo.currentData(), DuplexMode.SHORT_EDGE.value)
        self.assertEqual(panel.theme_combo.currentData(), "dark")

    def test_pdf_paper_mismatch_has_chinese_page_details(self):
        doc = MagicMock(page_count=1)
        doc.load_page.return_value.rect.width = 595.28
        doc.load_page.return_value.rect.height = 841.89
        with self.assertRaisesRegex(RuntimeError, "第 1 页：A4，所选：A3"):
            _assert_pdf_paper_matches(doc, "A3")

    def test_excel_missing_sheet_has_chinese_name(self):
        workbook = MagicMock()
        workbook.Worksheets.side_effect = KeyError("missing")
        with self.assertRaisesRegex(RuntimeError, "找不到工作表：中文工作表"):
            _assert_excel_paper_matches(workbook, ["中文工作表"], 9)

    def test_error_summaries_are_localized(self):
        for key, expected in [
            ("error_pdf_dependency", "summary_pdf_dependency"),
            ("error_paper_unsupported", "error_paper_unsupported"),
            ("error_file_missing", "error_file_missing"),
        ]:
            self.assertEqual(JobManager._summarize_message(i18n.t(key)), i18n.t(expected))
        message = i18n.t("error_paper_mismatch", application="Word")
        self.assertEqual(JobManager._summarize_message(message), i18n.t("summary_paper_mismatch"))

    def test_excel_orientation_codes_survive_translation(self):
        job = PrintJob("中文工作簿.xlsx", FileType.EXCEL, "", 1, DuplexMode.OFF)
        sheet = MagicMock(Name="工作表")
        sheet.UsedRange.Width = 200
        sheet.UsedRange.Height = 100
        workbook = MagicMock()
        workbook.Worksheets = MagicMock(return_value=sheet)
        workbook.Worksheets.__iter__.return_value = iter([sheet])
        excel = MagicMock()
        excel.Workbooks.Open.return_value = workbook
        analyzer = ExcelOrientationAnalyzer([job])
        results = []
        analyzer.completed.connect(results.extend)
        with patch("win32com.client.DispatchEx", return_value=excel):
            analyzer.run()
        self.assertEqual(results[0].recommendation, "landscape")
        dialog = ExcelOrientationDialog([(job.id, job.file_name, results[0].recommendation, results[0].reason)])
        self.assertEqual(dialog.table.item(0, 0).text(), "中文工作簿.xlsx")
        self.assertEqual(dialog.table.item(0, 1).text(), "横向")
        self.assertEqual(dialog.selected_job_ids(), [job.id])
        dialog._clear_all()
        self.assertEqual(dialog.selected_job_ids(), [])

    def test_saved_duplex_values_remain_compatible(self):
        for mode in DuplexMode:
            restored = UserSettings.from_dict({"duplex": mode.value, "language_mode": "zh"})
            self.assertEqual(restored.duplex, mode)
            self.assertEqual(restored.to_dict()["language_mode"], "zh")

    def test_fork_without_release_is_not_an_update_error(self):
        checker = UpdateChecker()
        result = []
        checker.checked.connect(lambda info, error: result.append((info, error)))
        with patch("app.controller.update_manager.urlopen", side_effect=HTTPError("https://api.github.com", 404, "Not Found", {}, None)) as request:
            checker.run()
        self.assertEqual(result, [(None, "")])
        self.assertIn("beizhi97/RakuPrints", request.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
