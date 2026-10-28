"""Smoke-test a frozen Windows build without submitting printer jobs.

Usage: python scripts/verify_windows_package.py dist/RakuPrint/RakuPrint.exe
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

import fitz
import win32api
import win32con
import win32gui
import win32process


def main() -> None:
    executable = Path(sys.argv[1]).resolve(strict=True)
    version = win32api.GetFileVersionInfo(str(executable), "\\")
    assert version["FileVersionLS"] == (4 << 16), version
    assert (executable.parent / "_internal/PySide6/translations/qtbase_zh_CN.qm").is_file()
    assert (executable.parent / "_internal/LICENSE").is_file()
    assert not (executable.parent / "_internal/icuuc.dll").exists(), "Do not bundle a third-party ICU DLL over Windows ICU"

    with tempfile.TemporaryDirectory(prefix="rakuprint_package_") as directory:
        isolated = Path(directory)
        settings = isolated / "RakuPrint/config/user_settings.json"
        settings.parent.mkdir(parents=True)
        settings.write_text(json.dumps({"language_mode": "zh", "update_check_enabled": False}), encoding="utf-8")
        environment = os.environ.copy()
        environment["LOCALAPPDATA"] = str(isolated)
        environment.pop("QT_QPA_PLATFORM", None)
        environment.pop("PYTHONPATH", None)
        environment.pop("PYTHONHOME", None)
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = win32con.SW_HIDE
        process = subprocess.Popen([str(executable)], cwd=directory, env=environment, startupinfo=startup, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        windows: list[int] = []
        try:
            deadline = time.monotonic() + 25
            while time.monotonic() < deadline:
                assert process.poll() is None, f"Application exited early: {process.returncode}"
                windows.clear()

                def collect(handle: int, _context: object) -> None:
                    if win32process.GetWindowThreadProcessId(handle)[1] == process.pid:
                        if win32gui.GetWindowText(handle) == "RakuPrints 乐印":
                            windows.append(handle)

                win32gui.EnumWindows(collect, None)
                if windows:
                    break
                time.sleep(0.2)
            if not windows:
                diagnostics: list[str] = []

                def diagnose(handle: int, _context: object) -> None:
                    if win32process.GetWindowThreadProcessId(handle)[1] == process.pid:
                        diagnostics.append(win32gui.GetWindowText(handle))
                        win32gui.EnumChildWindows(handle, lambda child, _: diagnostics.append(win32gui.GetWindowText(child)), None)

                win32gui.EnumWindows(diagnose, None)
                raise AssertionError(f"Chinese main window did not appear; windows: {diagnostics}")
            assert win32gui.IsWindowEnabled(windows[0]), "Main window is blocked by a modal dialog"
            print("PASS: frozen EXE opens the Chinese main window from an unrelated directory")
            win32gui.PostMessage(windows[0], win32con.WM_CLOSE, 0, 0)
            assert process.wait(timeout=10) == 0, "Application did not close cleanly"
            print("PASS: main window closes cleanly")
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=10)
            output, errors = process.communicate()
            if output or errors:
                print("Startup diagnostics:", output, errors)

        document_path = isolated / "worker-input.pdf"
        with fitz.open() as document:
            document.new_page()
            document.save(document_path)
        # Validation happens before QPrinter creation; no device printing occurs.
        for payload, expected_code, expected_error in [
            ({"file_path": str(isolated / "missing.pdf")}, 2, "File not found"),
            ({"file_path": str(document_path), "page_indices": [99]}, 10, "Invalid page indices"),
        ]:
            result = subprocess.run(
                [str(executable), "--pdf-worker"], input=json.dumps(payload), text=True,
                capture_output=True, cwd=directory, env=environment, timeout=20,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            assert result.returncode == expected_code, (result.returncode, result.stdout, result.stderr)
            assert expected_error in result.stderr, (result.stdout, result.stderr)
        print("PASS: frozen PDF worker starts, loads PyMuPDF, and rejects invalid pages before printing")


if __name__ == "__main__":
    main()
