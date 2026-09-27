"""F4 and F5: typed text is never lost, autosave writes it, and the last project reopens on start."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QSettings
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import QApplication

from dersprogrami.storage import load_project, save_project
from dersprogrami.ui import app as app_module
from dersprogrami.ui.app import MainWindow

from helpers import small_school


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def env(qapp, tmp_path, monkeypatch):
    ini = tmp_path / "settings.ini"
    monkeypatch.setattr(app_module, "settings", lambda: QSettings(str(ini), QSettings.Format.IniFormat))
    monkeypatch.setattr(app_module, "recovery_file", lambda: tmp_path / "kurtarma.json")
    path = tmp_path / "okul.json"
    save_project(small_school(), path)
    return tmp_path, path


def type_into(field, text):
    """Send real key events: textEdited fires, editingFinished does not (no Enter, focus stays)."""
    field.setFocus()
    field.selectAll()
    for ch in text:
        for kind in (QKeyEvent.Type.KeyPress, QKeyEvent.Type.KeyRelease):
            QApplication.sendEvent(field, QKeyEvent(kind, 0, Qt.KeyboardModifier.NoModifier, ch))


def test_typing_marks_unsaved_and_autosave_writes_it(env):
    _, path = env
    w = MainWindow(str(path), restore=False)
    school = w.widgets["Okul"]
    type_into(school.name, "Yeni Okul Adı")
    assert w.state.pending and w.state.has_unsaved() and "*" in w.windowTitle()
    assert school.name.text() == "Yeni Okul Adı"            # typing is not wiped by any refresh
    w.autosave()
    assert load_project(path).school.name == "Yeni Okul Adı"
    assert not w.state.has_unsaved() and "Kaydedildi" in w.status.text()
    w.close()


def test_switching_teacher_keeps_typed_name(env):
    _, path = env
    w = MainWindow(str(path), restore=False)
    page = w.widgets["Öğretmenler"]
    w.nav.setCurrentRow(1)
    page.list.setCurrentRow(0)
    first = page.list.currentItem().data(256)
    type_into(page.name, "Ayşe Yılmaz")
    page.list.setCurrentRow(1)                               # switch without pressing Enter
    assert w.state.project.teacher(first).name == "Ayşe Yılmaz"
    w.state.dirty = False
    w.close()


def test_close_asks_when_only_typed(env, monkeypatch):
    _, path = env
    w = MainWindow(str(path), restore=False)
    asked = []
    from PyQt6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: asked.append(1) or QMessageBox.StandardButton.Save)
    type_into(w.widgets["Okul"].headmaster, "Müdür Adı")
    w.close()                                                # asks, saves
    assert asked and load_project(path).school.headmaster == "Müdür Adı"


def test_invalid_short_is_not_lost_by_quiet_autosave(env, monkeypatch):
    _, path = env
    warned = []
    monkeypatch.setattr("dersprogrami.ui.teachers_page.warn", lambda *a: warned.append(a[1]))
    w = MainWindow(str(path), restore=False)
    page = w.widgets["Öğretmenler"]
    page.list.setCurrentRow(0)
    taken = w.state.project.teachers[1].short
    type_into(page.short, taken)                             # duplicate short: invalid for now
    w.autosave()                                             # must not pop up a warning, must not drop the text
    assert page.short.text() == taken and w.state.pending and warned == []   # quiet while typing
    assert not w.flush_pages()                                              # save/close: the user is told
    assert warned and "başka bir öğretmende" in warned[0]
    w.state.dirty = w.state.pending = False
    page.show_teacher()
    w.close()


def test_last_project_reopens_on_start(env):
    _, path = env
    w = MainWindow(str(path), restore=False)
    w.save()
    w.close()
    w2 = MainWindow()                                        # no file given: reopens the last project
    assert w2.state.path == path.resolve() or w2.state.path == path
    assert str(path.resolve()) in app_module.recent_files()
    w2.close()


def test_missing_last_project_is_reported_not_crashing(env):
    tmp, path = env
    w = MainWindow(str(path), restore=False)
    w.close()
    path.unlink()
    w2 = MainWindow()
    assert w2.state.path is None and "bulunamadı" in w2.statusBar().currentMessage()
    w2.close()


def test_never_saved_project_shows_warning(env):
    w = MainWindow(restore=False)
    w.state.apply(small_school())
    assert "henüz bir dosyaya kaydedilmedi" in w.status.text()
    w.state.dirty = False
    w.close()


def test_closing_unchanged_project_never_asks(env, monkeypatch):
    # Regression: re-reading fields on close used to invent changes (e.g. an empty 8th bell row) and ask to save.
    from dataclasses import replace
    from PyQt6.QtWidgets import QMessageBox
    tmp, path = env
    p = load_project(path)
    save_project(replace(p, school=replace(p.school, max_periods=8)), path)
    asked = []
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: asked.append(1) or QMessageBox.StandardButton.Discard)
    w = MainWindow(str(path), restore=False)
    for i in range(w.nav.count()):
        w.nav.setCurrentRow(i)
    w.autosave()
    w.close()
    assert asked == [] and not w.state.has_unsaved()
