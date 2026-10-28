import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import fitz
from PySide6 import QtCore, QtWidgets

from app.app_context import AppContext, UserSettings
from app.backend.pdf_backend import PdfBackend
from app.backend.pdf_worker import _resolve_payload_pages
from app.backend import pdf_worker
from app.backend.office_page_printing import print_excel_pages, print_word_pages, print_ppt_pages
from app.backend.word_backend import WordBackend
from app.backend.excel_backend import ExcelBackend
from app.backend.ppt_backend import PptBackend
from app.controller.job_manager import JobManager
from app.i18n import set_language
from app.model.page_range import normalize_page_range, resolve_page_indices
from app.model.print_job import PrintJob, FileType, DuplexMode
from app.ui.page_range_dialog import PageRangeDialog
from app.ui.file_list_view import JobTableModel
from app.ui.main_window import MainWindow


def job(file_type=FileType.PDF, **kwargs):
    return PrintJob("中文文档.pdf", file_type, "", 1, DuplexMode.OFF, **kwargs)


def write_pdf(path, labels):
    with fitz.open() as document:
        for label in labels:
            page = document.new_page()
            page.insert_text((72, 72), label)
        document.save(str(path))


class PageRangeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def setUp(self):
        set_language("zh")

    def test_normalization_and_chinese_input(self):
        self.assertEqual(normalize_page_range("８，３－５、1; 4–6"), "1,3-6,8")
        self.assertEqual(normalize_page_range("3,1-2,2,5,4"), "1-5")
        self.assertEqual(normalize_page_range(" \t"), "")
        self.assertEqual(resolve_page_indices("1,3-4", 4), [0, 2, 3])
        self.assertEqual(resolve_page_indices("", 3), [0, 1, 2])

    def test_invalid_ranges_never_become_all_pages(self):
        for text in ["0", "-1", "5-2", "1-", "1,,3", "abc", "1.5", "1/2", "1,", "9" * 100]:
            with self.subTest(text=text), self.assertRaises(ValueError):
                normalize_page_range(text)

    def test_out_of_bounds(self):
        with self.assertRaisesRegex(ValueError, "第 5 页.*共 4 页"):
            resolve_page_indices("1,5", 4)

    def test_worker_rejects_invalid_indices_before_printing(self):
        self.assertEqual(_resolve_payload_pages({"page_indices": [0, 3]}, 4), [0, 3])
        self.assertEqual(_resolve_payload_pages({"page_start": 1, "page_end": 2}, 4), [1, 2])
        for indices in [[], [-1], [4], [True], [1.5], "1,3", None]:
            with self.subTest(indices=indices), self.assertRaises(ValueError):
                _resolve_payload_pages({"page_indices": indices}, 4)

    def test_real_pdf_selection_and_collated_copies(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "中文样本.pdf"
            write_pdf(path, [f"PAGE_{n}" for n in range(1, 16)])
            task = job(page_range="2,4-15")
            task.file_path = str(path)
            task.copies = 2
            backend = PdfBackend(MagicMock(settings=UserSettings()))
            with patch.object(backend, "_run_worker") as worker:
                backend.print(task)
            payloads = [call.args[0] for call in worker.call_args_list]
            indices = [index for payload in payloads for index in payload["page_indices"]]
            self.assertEqual(indices, ([1] + list(range(3, 15))) * 2)
            self.assertTrue(all(payload["copies"] == 1 for payload in payloads))
            with fitz.open(path) as document:
                texts = [document.load_page(index).get_text().strip() for index in indices]
            self.assertEqual(texts[0], "PAGE_2")
            self.assertNotIn("PAGE_1", texts)
            self.assertNotIn("PAGE_3", texts)

    def test_pdf_out_of_bounds_sends_no_jobs(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "two.pdf"
            write_pdf(path, ["one", "two"])
            task = job(page_range="3")
            task.file_path = str(path)
            backend = PdfBackend(MagicMock(settings=UserSettings()))
            with patch.object(backend, "_run_worker") as worker, self.assertRaises(ValueError):
                backend.print(task)
            worker.assert_not_called()

    def test_worker_renders_only_selected_pages_to_pdf_file(self):
        # Exercise the actual drawing loop using Qt's PDF output, never a device.
        from PySide6 import QtPrintSupport
        with tempfile.TemporaryDirectory() as directory:
            source, output = Path(directory) / "source.pdf", Path(directory) / "output.pdf"
            colors = [(1, 1, 1), (1, 0, 0), (0, 1, 0), (0, 0, 1)]
            with fitz.open() as document:
                for color in colors:
                    page = document.new_page()
                    page.draw_rect(page.rect, color=color, fill=color)
                document.save(source)
            printer_type = QtPrintSupport.QPrinter
            def pdf_printer(mode):
                printer = printer_type(mode)
                printer.setOutputFormat(printer_type.PdfFormat)
                printer.setOutputFileName(str(output))
                printer.setResolution(72)
                return printer
            # Preserve the enum attributes used by the worker.
            for name in ["HighResolution", "DuplexNone", "DuplexLongSide", "DuplexShortSide", "DevicePixel"]:
                setattr(pdf_printer, name, getattr(printer_type, name))
            payload = {"file_path": str(source), "page_indices": [1, 3], "dpi": 72}
            with patch.object(pdf_worker, "_read_payload", return_value=payload), \
                 patch.object(pdf_worker.QtWidgets, "QApplication", return_value=self.app), \
                 patch.object(pdf_worker.QtPrintSupport, "QPrinter", new=pdf_printer):
                self.assertEqual(pdf_worker.main(), 0)
            with fitz.open(output) as document:
                self.assertEqual(document.page_count, 2)
                for index, expected in [(0, (255, 0, 0)), (1, (0, 0, 255))]:
                    pixmap = document.load_page(index).get_pixmap()
                    actual = pixmap.pixel(pixmap.width // 2, pixmap.height // 2)
                    self.assertTrue(all(abs(a - b) <= 2 for a, b in zip(actual, expected)), actual)

    def test_pdf_paper_validation_only_checks_requested_pages(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mixed.pdf"
            with fitz.open() as document:
                document.new_page(width=595.28, height=841.89)
                document.new_page(width=841.89, height=1190.55)
                document.save(path)
            task = job(page_range="1", paper_size="A4")
            task.file_path = str(path)
            backend = PdfBackend(MagicMock(settings=UserSettings()))
            with patch.object(backend, "_run_worker") as worker:
                backend.print(task)
            worker.assert_called_once()

    def test_default_pdf_retains_all_pages(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "all.pdf"
            write_pdf(path, ["first", "second"])
            task = job()
            task.file_path = str(path)
            backend = PdfBackend(MagicMock(settings=UserSettings()))
            with patch.object(backend, "_run_worker") as worker:
                backend.print(task)
            self.assertEqual(_resolve_payload_pages(worker.call_args.args[0], 2), [0, 1])

    def test_dialog_validation_is_atomic_and_cancel_keeps_jobs(self):
        first, second = job(page_count=4, page_range="2"), job(page_count=3)
        dialog = PageRangeDialog([first, second])
        dialog.inputs[first.id].setText("1,3")
        dialog.inputs[second.id].setText("4")
        dialog.accept()
        self.assertNotEqual(dialog.result(), QtWidgets.QDialog.Accepted)
        self.assertIn("第 4 页", dialog.error_label.text())
        self.assertEqual(first.page_range, "2")
        dialog.reject()
        self.assertEqual(first.page_range, "2")
        dialog.inputs[second.id].setText("")
        dialog.accept()
        self.assertEqual(dialog._selection, {first.id: "1,3", second.id: ""})

    def test_manager_preserves_per_file_settings_atomically(self):
        manager = JobManager(MagicMock())
        first, second = job(page_count=4), job(page_count=2)
        manager._jobs = [first, second]
        with self.assertRaises(ValueError):
            manager.set_page_ranges({first.id: "2", second.id: "3"})
        self.assertEqual(first.page_range, "")
        manager.set_page_ranges({first.id: "3,1", second.id: "2"})
        self.assertEqual((first.page_range, second.page_range), ("1,3", "2"))
        model = JobTableModel(manager)
        self.assertEqual(model.data(model.index(0, 9)), "1,3")
        self.assertEqual(model.data(model.index(1, 9)), "2")

    def test_excel_count_is_validated_after_final_layout(self):
        task = job(FileType.EXCEL, page_count=1)
        dialog = PageRangeDialog([task])
        dialog.inputs[task.id].setText("3")
        dialog.accept()
        self.assertEqual(dialog._selection[task.id], "3")

    def test_main_window_range_action_and_table(self):
        with tempfile.TemporaryDirectory() as directory, patch("app.app_context._get_app_data_dir", return_value=Path(directory)):
            context = AppContext()
            context.settings.update_check_enabled = False
            manager = JobManager(context)
            first, second = job(page_count=5), job(page_count=5)
            manager._jobs = [first, second]
            with patch("app.ui.main_window.list_printers", return_value=[]), patch("app.ui.main_window.get_default_printer_name", return_value=""):
                window = MainWindow(context, manager)
            self.assertFalse(window.page_range_action.isEnabled())
            window.file_list.selectRow(0)
            self.assertTrue(window.page_range_action.isEnabled())
            with patch.object(PageRangeDialog, "get_ranges", return_value=({first.id: "2-3"}, True)):
                window.page_range_action.trigger()
            self.assertEqual(first.page_range, "2-3")
            self.assertEqual(second.page_range, "")
            window._lock_ui(True)
            self.assertFalse(window.page_range_action.isEnabled())
            window._lock_ui(False)
            window.close()

    def test_office_exports_select_physical_pdf_pages(self):
        context = MagicMock(settings=UserSettings())
        for file_type, exporter in [(FileType.WORD, print_word_pages), (FileType.PPT, print_ppt_pages)]:
            with self.subTest(file_type=file_type):
                office = MagicMock()
                def export(**kwargs):
                    write_pdf(kwargs.get("OutputFileName", kwargs.get("Path")), ["one", "two", "three"])
                office.ExportAsFixedFormat.side_effect = export
                task = job(file_type, page_range="2")
                with patch.object(PdfBackend, "_run_worker") as worker:
                    exporter(context, task, office)
                self.assertEqual(worker.call_args.args[0]["page_indices"], [1])
                self.assertFalse(Path(worker.call_args.args[0]["file_path"]).exists())
                office.PrintOut.assert_not_called()

    def test_excel_selected_sheets_share_one_page_sequence(self):
        workbook = MagicMock()
        sheets = {}
        for name in ["第一页", "第二页"]:
            sheet = MagicMock()
            sheet.ExportAsFixedFormat.side_effect = lambda _type, filename, name=name, **kwargs: write_pdf(filename, [name.encode('unicode_escape').decode()])
            sheets[name] = sheet
        workbook.Worksheets.side_effect = sheets.__getitem__
        task = job(FileType.EXCEL, page_range="2", excel_sheets=list(sheets))
        captured = []
        def capture(payload):
            with fitz.open(payload["file_path"]) as document:
                captured.extend(document.load_page(i).get_text().strip() for i in payload["page_indices"])
        with patch.object(PdfBackend, "_run_worker", side_effect=capture):
            print_excel_pages(MagicMock(settings=UserSettings()), task, workbook)
        self.assertEqual(captured, ["第二页".encode('unicode_escape').decode()])
        workbook.PrintOut.assert_not_called()

    def test_office_backends_route_selected_pages_without_direct_print(self):
        for backend_type, module, file_type, method, helper in [
            (WordBackend, "word", FileType.WORD, "Documents", "print_word_pages"),
            (PptBackend, "ppt", FileType.PPT, "Presentations", "print_ppt_pages"),
            (ExcelBackend, "excel", FileType.EXCEL, "Workbooks", "print_excel_pages"),
        ]:
            with self.subTest(file_type=file_type):
                application = MagicMock()
                application.BackgroundPrintingStatus = 0
                application.PrintStatus = 0
                document = getattr(application, method).Open.return_value
                document.Worksheets.__iter__.return_value = iter([])
                task = job(file_type, page_range="2")
                with patch("win32com.client.DispatchEx", return_value=application), patch(f"app.backend.{module}_backend.{helper}") as export:
                    backend_type(MagicMock(settings=UserSettings())).print(task)
                export.assert_called_once()
                document.PrintOut.assert_not_called()
                document.Close.assert_called()
                application.Quit.assert_called_once()


if __name__ == "__main__":
    unittest.main()
