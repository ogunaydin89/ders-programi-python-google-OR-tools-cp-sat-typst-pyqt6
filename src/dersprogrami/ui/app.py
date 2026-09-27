"""Main window: sidebar pages, file menu, undo/redo, autosave, crash handler."""
import sys
import traceback
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QSettings, QStandardPaths, QTimer
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import (QAbstractItemView, QApplication, QFileDialog, QHBoxLayout, QLabel, QListWidget,
                             QMainWindow, QMessageBox, QStackedWidget, QWidget)

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

AUTOSAVE_MS = 15_000
RECENT_MAX = 8
FILTER = "Ders programı projesi (*.json)"


def data_dir() -> Path:
    d = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation) or Path.home())
    d.mkdir(parents=True, exist_ok=True)
    return d


def recovery_file() -> Path:
    return data_dir() / "kurtarma.json"


def settings() -> QSettings:
    """Remembered between runs: last project and recent files."""
    return QSettings(QSettings.Format.IniFormat, QSettings.Scope.UserScope, "DersProgrami", "DersProgrami")


def recent_files() -> list[str]:
    value = settings().value("recent", [])
    return [value] if isinstance(value, str) else list(value or [])


class MainWindow(QMainWindow):
    def __init__(self, path=None, restore=True):
        super().__init__()
        self.state = ProjectState()
        self.saved_at = None
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
        self.status = QLabel()
        self.statusBar().addWidget(self.status, 1)
        self.state.changed.connect(self.update_title)
        self.state.status_changed.connect(self.update_title)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.autosave)
        self.timer.start(AUTOSAVE_MS)
        if path:
            self.open_path(path)
        elif restore and not self.offer_recovery():
            self.reopen_last()
        self.update_title()

    def build_menu(self):
        m = self.menuBar().addMenu("Dosya")
        for text, key, fn in (("Yeni", QKeySequence.StandardKey.New, self.new),
                              ("Aç…", QKeySequence.StandardKey.Open, self.open),
                              ("Kaydet", QKeySequence.StandardKey.Save, self.save),
                              ("Farklı kaydet…", QKeySequence.StandardKey.SaveAs, self.save_as),
                              ("Çıkış", QKeySequence.StandardKey.Quit, self.close)):
            if text == "Çıkış":
                self.recent_menu = m.addMenu("Son açılanlar")
                self.recent_menu.aboutToShow.connect(self.fill_recent)
                m.addSeparator()
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
        unsaved = self.state.has_unsaved()
        self.setWindowTitle(f"Ders Programı {__version__} — {name}{' *' if unsaved else ''}")
        self.undo_action.setEnabled(self.state.can_undo())
        self.redo_action.setEnabled(self.state.can_redo())
        if not self.state.path:
            empty = not (self.state.project.teachers or self.state.project.classes)
            self.status.setText("" if empty and not unsaved else
                                "⚠ Proje henüz bir dosyaya kaydedilmedi — Ctrl+S ile kaydedin.")
        elif unsaved:
            self.status.setText(f"Kaydedilmemiş değişiklik var (birkaç saniye içinde otomatik kaydedilir) — "
                                f"{self.state.path}")
        else:
            when = f" {self.saved_at:%H:%M:%S}" if self.saved_at else ""
            self.status.setText(f"✔ Kaydedildi{when} — {self.state.path}")

    # -- pending typing -------------------------------------------------------
    def flush_pages(self, quiet=False) -> bool:
        """Apply text that was typed but not yet confirmed (Enter / leaving the field)."""
        focus = QApplication.focusWidget()
        if focus is not None:
            parent = focus.parent()
            while parent is not None and not isinstance(parent, QAbstractItemView):
                parent = parent.parent()
            if parent is not None:          # an open table cell editor: leaving it commits the cell
                focus.clearFocus()
        if not self.state.pending:          # nothing typed: re-reading every field could only add noise
            return True
        ok = True
        for w in self.widgets.values():
            if hasattr(w, "flush"):
                ok = w.flush(quiet) and ok
        self.state.pending = not ok
        self.update_title()
        return ok

    # -- remembered files ----------------------------------------------------
    def remember(self, path):
        path = str(Path(path).resolve())
        s = settings()
        s.setValue("last_project", path)
        s.setValue("recent", [path] + [p for p in recent_files() if p != path][:RECENT_MAX - 1])
        s.sync()

    def fill_recent(self):
        self.recent_menu.clear()
        files = recent_files()
        if not files:
            self.recent_menu.addAction("(boş)").setEnabled(False)
        for f in files:
            a = self.recent_menu.addAction(f)
            a.setEnabled(Path(f).exists())
            a.triggered.connect(lambda _=False, f=f: self.open_recent(f))

    def open_recent(self, path):
        if self.busy() or not self.confirm_discard():
            return
        self.open_path(path)

    def reopen_last(self):
        last = settings().value("last_project", "")
        if not last:
            return
        if Path(last).exists():
            self.open_path(last)
        else:
            self.statusBar().showMessage(f"Son açılan proje bulunamadı (taşınmış veya silinmiş olabilir): {last}",
                                         20_000)

    def busy(self):
        return self.widgets["Çöz"].busy()

    def confirm_discard(self) -> bool:
        self.flush_pages()
        if not self.state.has_unsaved():
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
            return
        self.saved_at = None
        self.remember(path)
        self.update_title()

    def save(self) -> bool:
        if not self.flush_pages():
            return False
        if not self.state.path:
            return self.save_as()
        try:
            self.state.save()
            recovery_file().unlink(missing_ok=True)
            self.saved_at = datetime.now()
            self.remember(self.state.path)
            self.update_title()
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
        if self.state.pending:
            self.flush_pages(quiet=True)    # quiet: never pop up a warning while the user is typing
        if not self.state.dirty:
            return
        try:
            if self.state.path:
                self.state.save()
                self.saved_at = datetime.now()
            else:
                save_project(self.state.project, recovery_file(), backups=0)
        except OSError as e:
            self.statusBar().showMessage(f"Otomatik kayıt başarısız: {e.strerror}", 15_000)
        self.update_title()

    def offer_recovery(self) -> bool:
        """Offer the recovery file of an unsaved session; True if it was opened."""
        f = recovery_file()
        if f.exists():
            when = datetime.fromtimestamp(f.stat().st_mtime).strftime("%d.%m.%Y %H:%M")
            if QMessageBox.question(self, "Kurtarma", f"Kaydedilmemiş bir çalışma bulundu ({when}). Açılsın mı?") \
                    == QMessageBox.StandardButton.Yes:
                try:
                    self.state.project = load_project(f)
                    self.state.dirty = True
                    self.state.changed.emit()
                    return True
                except ProjectFileError:
                    pass
        return False

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
