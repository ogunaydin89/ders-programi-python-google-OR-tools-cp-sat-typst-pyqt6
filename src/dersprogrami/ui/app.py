"""Main window: sidebar pages, file menu, undo/redo, autosave, crash handler."""
import sys
import traceback
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QStandardPaths, QTimer
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import (QApplication, QFileDialog, QHBoxLayout, QListWidget, QMainWindow, QMessageBox,
                             QStackedWidget, QWidget)

from .. import __version__
from ..model import ProjectFileError
from ..storage import load_project, save_project
from .assign_page import AssignPage
from .classes_page import ClassesPage
from .print_page import PrintPage
from .rules_page import RulesPage
from .school_page import SchoolPage
from .solve_page import SolvePage
from .state import ProjectState
from .teachers_page import TeachersPage
from .timetable_page import TimetablePage

AUTOSAVE_MS = 60_000
FILTER = "Ders programı projesi (*.json)"


def data_dir() -> Path:
    d = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation) or Path.home())
    d.mkdir(parents=True, exist_ok=True)
    return d


def recovery_file() -> Path:
    return data_dir() / "kurtarma.json"


class MainWindow(QMainWindow):
    def __init__(self, path=None):
        super().__init__()
        self.state = ProjectState()
        self.resize(1400, 860)
        central = QWidget()
        lay = QHBoxLayout(central)
        self.nav = QListWidget()
        self.nav.setFixedWidth(170)
        self.stack = QStackedWidget()
        self.pages = [("Okul", SchoolPage), ("Öğretmenler", TeachersPage), ("Sınıflar", ClassesPage),
                      ("Ders Atama", AssignPage), ("Kurallar", RulesPage), ("Çöz", SolvePage),
                      ("Program", TimetablePage), ("Yazdır", PrintPage)]
        self.widgets = {}
        for name, cls in self.pages:
            w = cls(self.state)
            self.widgets[name] = w
            self.nav.addItem(name)
            self.stack.addWidget(w)
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.setCurrentRow(0)
        self.widgets["Çöz"].solved.connect(lambda: self.nav.setCurrentRow(6))
        lay.addWidget(self.nav)
        lay.addWidget(self.stack, 1)
        self.setCentralWidget(central)
        self.build_menu()
        self.state.changed.connect(self.update_title)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.autosave)
        self.timer.start(AUTOSAVE_MS)
        if path:
            self.open_path(path)
        else:
            self.offer_recovery()
        self.update_title()

    def build_menu(self):
        m = self.menuBar().addMenu("Dosya")
        for text, key, fn in (("Yeni", QKeySequence.StandardKey.New, self.new),
                              ("Aç…", QKeySequence.StandardKey.Open, self.open),
                              ("Kaydet", QKeySequence.StandardKey.Save, self.save),
                              ("Farklı kaydet…", QKeySequence.StandardKey.SaveAs, self.save_as),
                              ("Çıkış", QKeySequence.StandardKey.Quit, self.close)):
            a = QAction(text, self)
            a.setShortcut(key)
            a.triggered.connect(fn)
            m.addAction(a)
        e = self.menuBar().addMenu("Düzen")
        self.undo_action = QAction("Geri al", self)
        self.undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        self.undo_action.triggered.connect(self.state.undo)
        self.redo_action = QAction("Yinele", self)
        self.redo_action.setShortcuts([QKeySequence.StandardKey.Redo, QKeySequence("Ctrl+Y")])
        self.redo_action.triggered.connect(self.state.redo)
        e.addAction(self.undo_action)
        e.addAction(self.redo_action)

    def update_title(self):
        name = self.state.path.name if self.state.path else "Adsız proje"
        self.setWindowTitle(f"Ders Programı {__version__} — {name}{' *' if self.state.dirty else ''}")
        self.undo_action.setEnabled(self.state.can_undo())
        self.redo_action.setEnabled(self.state.can_redo())

    def busy(self):
        return self.widgets["Çöz"].busy()

    def confirm_discard(self) -> bool:
        if not self.state.dirty:
            return True
        r = QMessageBox.question(self, "Kaydedilmemiş değişiklikler", "Değişiklikler kaydedilsin mi?",
                                 QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard |
                                 QMessageBox.StandardButton.Cancel)
        if r == QMessageBox.StandardButton.Save:
            return self.save()
        return r == QMessageBox.StandardButton.Discard

    def new(self):
        if self.busy():
            return QMessageBox.information(self, "Bilgi", "Çözüm sürerken yeni proje açılamaz.")
        if self.confirm_discard():
            self.state.new()

    def open(self):
        if self.busy() or not self.confirm_discard():
            return
        path, _ = QFileDialog.getOpenFileName(self, "Proje aç", str(Path.home()), FILTER)
        if path:
            self.open_path(path)

    def open_path(self, path):
        try:
            self.state.load(path)
        except ProjectFileError as e:
            QMessageBox.warning(self, "Açılamadı", str(e))

    def save(self) -> bool:
        if not self.state.path:
            return self.save_as()
        try:
            self.state.save()
            recovery_file().unlink(missing_ok=True)
            return True
        except OSError as e:
            QMessageBox.warning(self, "Kaydedilemedi", f"Proje kaydedilemedi: {e.strerror}")
            return False

    def save_as(self) -> bool:
        path, _ = QFileDialog.getSaveFileName(self, "Farklı kaydet", str(Path.home() / "ders_programi.json"), FILTER)
        if not path:
            return False
        if not path.endswith(".json"):
            path += ".json"
        self.state.path = Path(path)
        return self.save()

    def autosave(self):
        if not self.state.dirty:
            return
        try:
            if self.state.path:
                self.state.save()
            else:
                save_project(self.state.project, recovery_file(), backups=0)
        except OSError:
            pass

    def offer_recovery(self):
        f = recovery_file()
        if f.exists():
            when = datetime.fromtimestamp(f.stat().st_mtime).strftime("%d.%m.%Y %H:%M")
            if QMessageBox.question(self, "Kurtarma", f"Kaydedilmemiş bir çalışma bulundu ({when}). Açılsın mı?") \
                    == QMessageBox.StandardButton.Yes:
                try:
                    self.state.project = load_project(f)
                    self.state.dirty = True
                    self.state.changed.emit()
                except ProjectFileError:
                    pass

    def closeEvent(self, event):
        if self.busy():
            QMessageBox.information(self, "Bilgi", "Çözüm sürüyor; önce durdurun.")
            return event.ignore()
        if self.confirm_discard():
            recovery_file().unlink(missing_ok=True)
            event.accept()
        else:
            event.ignore()


def install_crash_handler(window_ref):
    def handler(exc_type, exc, tb):
        text = "".join(traceback.format_exception(exc_type, exc, tb))
        log = data_dir() / "hata.log"
        try:
            with open(log, "a", encoding="utf-8") as f:
                f.write(f"\n--- {datetime.now():%Y-%m-%d %H:%M:%S}\n{text}")
        except OSError:
            pass
        w = window_ref()
        if w is not None:
            try:
                save_project(w.state.project, recovery_file(), backups=0)
            except Exception:
                pass
            QMessageBox.critical(w, "Beklenmeyen hata",
                                 "Beklenmeyen bir hata oluştu. Çalışmanız kurtarma dosyasına kaydedildi.\n"
                                 f"Ayrıntılar: {log}")
    sys.excepthook = handler


def run(path=None) -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("DersProgrami")
    app.setOrganizationName("DersProgrami")
    win = MainWindow(path)
    install_crash_handler(lambda: win)
    win.show()
    return app.exec()
