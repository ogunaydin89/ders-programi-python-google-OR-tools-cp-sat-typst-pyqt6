"""The desktop application, driven programmatically without a screen."""
import os
import time
from dataclasses import replace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication

from dersprogrami.checker import check
from dersprogrami.solver import SolveOptions, solve
from dersprogrami.ui import timetable_page
from dersprogrami.ui.app import MainWindow
from dersprogrami.ui.classes_page import ClassDialog

from helpers import load_benchmark


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def win(app, monkeypatch, tmp_path):
    monkeypatch.setattr("dersprogrami.ui.app.recovery_file", lambda: tmp_path / "kurtarma.json")
    from PyQt6.QtCore import QSettings
    monkeypatch.setattr("dersprogrami.ui.app.settings",
                        lambda: QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat))
    w = MainWindow(restore=False)
    yield w
    w.state.dirty = False
    w.close()


def test_all_pages_render_with_benchmark(win, app):
    win.state.apply(load_benchmark("strict"))
    for i in range(win.nav.count()):
        win.nav.setCurrentRow(i)
        app.processEvents()
    assert "*" in win.windowTitle()


def test_undo_redo(win):
    p = load_benchmark("strict")
    win.state.apply(p)
    p2 = replace(p, valid_from="x")
    win.state.apply(p2)
    win.state.undo()
    assert win.state.project == p
    win.state.redo()
    assert win.state.project == p2


def test_add_class_dialog_prefills_and_requires_confirmation(win, monkeypatch):
    from dersprogrami.model import School, SchoolPart
    warned = []
    monkeypatch.setattr("dersprogrami.ui.classes_page.warn", lambda *a: warned.append(a[1]))
    win.state.apply(replace(win.state.project, school=School(name="X", parts=(SchoolPart("imam_hatip_ortaokulu", 5, 8),))))
    ClassDialog(win, win.state.project)
    assert warned and "günlük en fazla 7" in warned[0]           # school still set to 7 periods
    # The Okul page raises the maximum when a school type needs it.
    win.state.apply(replace(win.state.project, school=School(name="X")))
    win.widgets["Okul"].add_part()
    assert win.state.project.school.max_periods == 7
    win.state.apply(replace(win.state.project, school=School(name="X", max_periods=8,
                                                             parts=(SchoolPart("imam_hatip_ortaokulu", 5, 8),))))
    warned.clear()
    dlg = ClassDialog(win, win.state.project)
    assert warned == []
    assert [sp.value() for sp in dlg.days] == [7, 7, 8, 7, 7]      # İHO default: 36 hours
    dlg.accept()
    assert warned and "onay" in warned[0]
    dlg.confirm.setChecked(True)
    dlg.picker.rows[0][1].setChecked(True)                           # one 1-hour elective
    assert dlg.picker.problems() == []
    v = dlg.result_values()
    assert v["grade"] == 5 and sum(v["daily"]) == 36 and len(v["electives"]) == 1


def test_solve_page_end_to_end(win, app):
    win.state.apply(load_benchmark("strict"))
    page = win.widgets["Çöz"]
    page.minutes.setValue(1)
    page.start()
    deadline = time.time() + 120
    while page.job is not None and time.time() < deadline:
        app.processEvents()
        page.poll()
        time.sleep(0.2)
    p = win.state.project
    assert p.placements and check(p, p.placements) == []
    assert "Kalite raporu" in page.report.toHtml()


def test_guided_move_and_refusal(win, app, monkeypatch):
    p = load_benchmark("strict")
    r = solve(p, SolveOptions(time_limit=30, seed=2))
    win.state.apply(replace(p, placements=r.placements))
    page = win.widgets["Program"]
    page.show_view("class", p.classes[0].id)
    assert page.view.currentData()[1] == p.classes[0].id
    warned = []
    monkeypatch.setattr(timetable_page, "warn", lambda *a: warned.append(a[1]))
    # Select the first cell, then try every other cell: valid ones must apply, invalid ones must be refused.
    page.clicked(0, 0)
    assert page.selected is not None
    valid = [k for k, ok in page.valid.items() if ok]
    invalid = [k for k, ok in page.valid.items() if not ok and k != (page.selected.day, page.selected.start)]
    if invalid:
        d, s = invalid[0]
        page.try_move(s - 1, d - 1)
        assert warned
        assert win.state.project.placements == tuple(sorted(r.placements, key=lambda x: (x.lesson, x.day,
                                                                                        x.start))) or \
            win.state.project.placements == r.placements
    if valid:
        page.clicked(0, 0)
        d, s = valid[0]
        page.try_move(s - 1, d - 1)
        new = win.state.project.placements
        assert new != r.placements and check(win.state.project, new) == []
        assert page.view.currentData()[1] == p.classes[0].id            # the view stays on the class


def test_print_page_exports(win, tmp_path, monkeypatch):
    p = load_benchmark("strict")
    r = solve(p, SolveOptions(time_limit=30, seed=2))
    win.state.apply(replace(p, placements=r.placements))
    page = win.widgets["Yazdır"]
    page.folder.setText(str(tmp_path / "pdf"))
    monkeypatch.setattr("dersprogrami.ui.print_page.QDesktopServices.openUrl", lambda *a: None)
    page.export()
    assert len(list((tmp_path / "pdf").glob("*.pdf"))) == 4
