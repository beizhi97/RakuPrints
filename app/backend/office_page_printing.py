from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import tempfile

from app.backend.pdf_backend import PdfBackend
from app.model.print_job import FileType, PrintJob


def print_exported_pdf(context, job: PrintJob, pdf_path: str) -> None:
    """Apply physical PDF page numbers after Office has finished pagination."""
    pdf_job = replace(
        job, file_path=pdf_path, file_type=FileType.PDF,
        pdf_scale_mode="auto", pdf_scale_percent=100,
        pdf_auto_rotate=False, pdf_center=True,
    )
    PdfBackend(context).print(pdf_job)


def print_excel_pages(context, job: PrintJob, workbook) -> None:
    # Excel has no single multi-range PrintOut argument. Export the final layout
    # before selecting pages, so a range is never repeated separately per sheet.
    with tempfile.TemporaryDirectory(prefix="rakuprint_pages_") as directory:
        output = str(Path(directory) / "workbook.pdf")
        if job.excel_sheets:
            import fitz

            with fitz.open() as combined:
                for index, name in enumerate(job.excel_sheets):
                    part = str(Path(directory) / f"sheet_{index}.pdf")
                    workbook.Worksheets(name).ExportAsFixedFormat(
                        0, part, IgnorePrintAreas=False, OpenAfterPublish=False,
                    )
                    with fitz.open(part) as source:
                        combined.insert_pdf(source)
                combined.save(output)
        else:
            workbook.ExportAsFixedFormat(
                0, output, IgnorePrintAreas=False, OpenAfterPublish=False,
            )
        print_exported_pdf(context, job, output)


def print_word_pages(context, job: PrintJob, document) -> None:
    with tempfile.TemporaryDirectory(prefix="rakuprint_pages_") as directory:
        output = str(Path(directory) / "document.pdf")
        document.ExportAsFixedFormat(OutputFileName=output, ExportFormat=17, OpenAfterExport=False)
        print_exported_pdf(context, job, output)


def print_ppt_pages(context, job: PrintJob, presentation) -> None:
    with tempfile.TemporaryDirectory(prefix="rakuprint_pages_") as directory:
        output = str(Path(directory) / "slides.pdf")
        # One page per slide, including hidden slides, keeps the page numbers
        # consistent with the original slide positions.
        presentation.ExportAsFixedFormat(
            Path=output, FixedFormatType=2, Intent=2,
            OutputType=1, PrintHiddenSlides=-1, PrintRange=None, RangeType=1,
        )
        print_exported_pdf(context, job, output)
