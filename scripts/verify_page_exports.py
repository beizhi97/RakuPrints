"""Verify native Office export and page selection; physical printing is blocked."""
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import fitz
import pythoncom
import win32com.client
from app.app_context import UserSettings
from app.backend.office_page_printing import print_word_pages, print_excel_pages, print_ppt_pages
from app.backend.pdf_backend import PdfBackend
from app.model.print_job import PrintJob, FileType, DuplexMode

if len(sys.argv) != 2 or sys.argv[1] not in {'word', 'excel', 'ppt'}:
    raise SystemExit('Usage: python scripts/verify_page_exports.py word|excel|ppt')
kind = sys.argv[1]
context = SimpleNamespace(settings=UserSettings())
captured = []
def capture(payload):
    with fitz.open(payload['file_path']) as document:
        captured.extend(document.load_page(index).get_text() for index in payload['page_indices'])

pythoncom.CoInitialize()
application = document = None
try:
    application = win32com.client.DispatchEx({'word': 'Word.Application', 'excel': 'Excel.Application', 'ppt': 'PowerPoint.Application'}[kind])
    print(f'Native application: {application.Name}, version: {application.Version}', flush=True)
    if kind == 'word':
        application.Visible = False
        application.DisplayAlerts = 0
        document = application.Documents.Add()
        document.Content.Text = 'WORD_PAGE_1\fWORD_PAGE_2\fWORD_PAGE_3'
        task = PrintJob('native.docx', FileType.WORD, '', 1, DuplexMode.OFF, page_range='2')
        with patch.object(PdfBackend, '_run_worker', side_effect=capture):
            print_word_pages(context, task, document)
        expected = 'WORD_PAGE_2'
    elif kind == 'excel':
        application.Visible = False
        application.DisplayAlerts = False
        document = application.Workbooks.Add()
        first = document.Worksheets(1)
        first.Name = '中文工作表一'
        second = document.Worksheets.Add(After=first)
        second.Name = '中文工作表二'
        for index, sheet in enumerate([first, second], 1):
            sheet.Range('A1').Value = f'EXCEL_SHEET_{index}'
            sheet.PageSetup.PrintArea = '$A$1:$C$3'
        task = PrintJob('native.xlsx', FileType.EXCEL, '', 1, DuplexMode.OFF, page_range='2', excel_sheets=[first.Name, second.Name])
        with patch.object(PdfBackend, '_run_worker', side_effect=capture):
            print_excel_pages(context, task, document)
        expected = 'EXCEL_SHEET_2'
        assert len(captured) == 1 and expected in captured[0], captured
        captured.clear()
        task.excel_sheets = []
        expected = str(document.Worksheets(2).Range('A1').Value)
        with patch.object(PdfBackend, '_run_worker', side_effect=capture):
            print_excel_pages(context, task, document)
    else:
        document = application.Presentations.Add(WithWindow=False)
        for index in range(1, 4):
            slide = document.Slides.Add(index, 12)
            slide.Shapes.AddTextbox(1, 72, 72, 500, 200).TextFrame.TextRange.Text = f'PPT_SLIDE_{index}'
            if index == 2:
                slide.SlideShowTransition.Hidden = -1
        task = PrintJob('native.pptx', FileType.PPT, '', 1, DuplexMode.OFF, page_range='2')
        with patch.object(PdfBackend, '_run_worker', side_effect=capture):
            print_ppt_pages(context, task, document)
        expected = 'PPT_SLIDE_2'
    assert len(captured) == 1, captured
    assert expected in captured[0], captured
    print(f'PASS {kind}: selected only page 2 ({expected}); no physical print calls.', flush=True)
finally:
    if document is not None:
        if kind == 'ppt':
            document.Saved = True
            document.Close()
        else:
            document.Close(False)
    if application is not None:
        application.Quit()
    pythoncom.CoUninitialize()

