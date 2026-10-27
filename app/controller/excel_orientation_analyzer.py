from __future__ import annotations

import gc
from dataclasses import dataclass

from PySide6 import QtCore

from app.model.print_job import PrintJob


@dataclass
class ExcelOrientationResult:
    job_id: str
    file_name: str
    recommendation: str
    reason: str

from app.i18n import t



class ExcelOrientationAnalyzer(QtCore.QThread):
    completed = QtCore.Signal(list)
    failed = QtCore.Signal(str)

    def __init__(self, jobs: list[PrintJob]) -> None:
        super().__init__()
        self._jobs = list(jobs)

    def run(self) -> None:
        try:
            import pythoncom  # type: ignore
            import win32com.client  # type: ignore
        except Exception as exc:
            self.failed.emit(t("error_excel_analysis_dependency"))
            return

        results: list[ExcelOrientationResult] = []
        pythoncom.CoInitialize()
        try:
            app = win32com.client.DispatchEx("Excel.Application")
            app.Visible = False
            if hasattr(app, "DisplayAlerts"):
                app.DisplayAlerts = False

            for job in self._jobs:
                workbook = None
                try:
                    workbook = app.Workbooks.Open(job.file_path, ReadOnly=True)
                    sheets = job.excel_sheets or [sheet.Name for sheet in workbook.Worksheets]
                    landscape = 0
                    portrait = 0
                    for name in sheets:
                        sheet = workbook.Worksheets(name)
                        used = sheet.UsedRange
                        width = float(used.Width)
                        height = float(used.Height)
                        if width > height * 1.05:
                            landscape += 1
                        else:
                            portrait += 1
                    recommendation = "landscape" if landscape > portrait else "portrait"
                    reason = f"orientation_{recommendation}_reason"
                    results.append(
                        ExcelOrientationResult(
                            job_id=job.id,
                            file_name=job.file_name,
                            recommendation=recommendation,
                            reason=reason,
                        )
                    )
                except Exception:
                    results.append(
                        ExcelOrientationResult(
                            job_id=job.id,
                            file_name=job.file_name,
                            recommendation="unknown",
                            reason="error_excel_analysis",
                        )
                    )
                finally:
                    if workbook is not None:
                        workbook.Close(False)
            app.Quit()
            del app
        except Exception:
            self.failed.emit(t("error_excel_analysis"))
            return
        finally:
            gc.collect()
            pythoncom.CoUninitialize()

        self.completed.emit(results)
