from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

from app.i18n import current_language


def apply_ui_font(app: QtWidgets.QApplication) -> None:
    families = {
        "zh": ["Microsoft YaHei UI", "Microsoft YaHei", "Noto Sans CJK SC"],
        "ja": ["Yu Gothic UI", "Meiryo"],
        "ko": ["Malgun Gothic", "Noto Sans CJK KR"],
        "en": ["Segoe UI"],
    }
    available = set(QtGui.QFontDatabase.families())
    font = QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.GeneralFont)
    for family in families.get(current_language(), []):
        if family in available:
            font.setFamily(family)
            break
    font.setPointSize(11)
    app.setFont(font)


def apply_ui_language(app: QtWidgets.QApplication) -> None:
    """Translate Qt's standard buttons as well as the application's own labels."""
    previous = getattr(app, "_raku_qt_translator", None)
    if previous is not None:
        app.removeTranslator(previous)
        previous.deleteLater()
    app._raku_qt_translator = None
    locale_name = {"zh": "zh_CN", "ja": "ja", "ko": "ko"}.get(current_language())
    if locale_name:
        translator = QtCore.QTranslator(app)
        directory = QtCore.QLibraryInfo.path(QtCore.QLibraryInfo.TranslationsPath)
        if translator.load(f"qtbase_{locale_name}", directory):
            app.installTranslator(translator)
            # QCoreApplication does not take ownership of installed translators.
            app._raku_qt_translator = translator
        else:
            translator.deleteLater()
    apply_ui_font(app)
