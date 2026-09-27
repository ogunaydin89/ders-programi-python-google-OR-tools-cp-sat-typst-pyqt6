"""Okul: school name, administration, school types with grade ranges, week and bell times."""
from dataclasses import replace

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QComboBox, QFormLayout, QGroupBox, QHBoxLayout, QLineEdit, QPushButton, QSpinBox,
                             QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from .. import curriculum as cm
from ..model import Bell, SchoolPart
from .widgets import heading, track, warn


def needed_periods(part) -> int:
    """Longest default school day of a school type within its grade range (e.g. 8 for İHO and lise)."""
    cur = cm.get(part.curriculum)
    return max((max(cur.default_daily_hours(g)) for g in range(part.grade_from, part.grade_to + 1)
                if g in cur.grades), default=1)


class SchoolPage(QWidget):
    def __init__(self, state):
        super().__init__()
        self.state = state
        self._loading = False
        lay = QVBoxLayout(self)
        lay.addWidget(heading("Okul bilgileri"))
        form = QFormLayout()
        self.name = QLineEdit()
        self.headmaster = QLineEdit()
        self.headmaster.setPlaceholderText("İsteğe bağlı; boş bırakılırsa çıktılarda yalnızca unvan yazılır")
        self.vices = QLineEdit()
        self.vices.setPlaceholderText("İsteğe bağlı; birden fazlaysa virgülle ayırın")
        form.addRow("Okul adı", self.name)
        form.addRow("Okul müdürü", self.headmaster)
        form.addRow("Müdür yardımcıları", self.vices)
        lay.addLayout(form)

        parts = QGroupBox("Okul türleri ve sınıf aralıkları (karma okullarda birden fazla satır)")
        pl = QVBoxLayout(parts)
        self.parts = QTableWidget(0, 3)
        self.parts.setHorizontalHeaderLabels(["Okul türü", "İlk sınıf", "Son sınıf"])
        self.parts.horizontalHeader().setStretchLastSection(True)
        pl.addWidget(self.parts)
        row = QHBoxLayout()
        add, rem = QPushButton("Okul türü ekle"), QPushButton("Seçili türü kaldır")
        add.clicked.connect(self.add_part)
        rem.clicked.connect(self.remove_part)
        row.addWidget(add)
        row.addWidget(rem)
        row.addStretch()
        pl.addLayout(row)
        lay.addWidget(parts)

        week = QGroupBox("Hafta ve zil saatleri")
        wl = QHBoxLayout(week)
        wf = QFormLayout()
        self.days = QSpinBox(minimum=1, maximum=7)
        self.periods = QSpinBox(minimum=1, maximum=12)
        self.lunch = QSpinBox(minimum=0, maximum=12)
        self.lunch.setSpecialValueText("yok")
        wf.addRow("Haftalık gün sayısı", self.days)
        wf.addRow("Günlük en fazla ders", self.periods)
        wf.addRow("Öğle arası şu dersten sonra", self.lunch)
        wl.addLayout(wf)
        self.bell = QTableWidget(0, 2)
        self.bell.setHorizontalHeaderLabels(["Başlangıç", "Bitiş"])
        wl.addWidget(self.bell)
        lay.addWidget(week)
        lay.addStretch()

        for w in (self.name, self.headmaster, self.vices):
            w.editingFinished.connect(self.commit)
        track(state, self.name, self.headmaster, self.vices)
        for w in (self.days, self.periods, self.lunch):
            w.valueChanged.connect(self.commit)
        self.bell.itemChanged.connect(self.commit)
        state.changed.connect(self.refresh)
        self.refresh()

    def _part_row(self, r, part):
        combo = QComboBox()
        for cid, cur in cm.load_all().items():
            combo.addItem(cur.name, cid)
        combo.setCurrentIndex(max(0, combo.findData(part.curriculum)))
        lo, hi = QSpinBox(minimum=5, maximum=12), QSpinBox(minimum=5, maximum=12)
        lo.setValue(part.grade_from)
        hi.setValue(part.grade_to)
        self.parts.setCellWidget(r, 0, combo)
        self.parts.setCellWidget(r, 1, lo)
        self.parts.setCellWidget(r, 2, hi)
        combo.currentIndexChanged.connect(self.commit)
        lo.valueChanged.connect(self.commit)
        hi.valueChanged.connect(self.commit)

    def refresh(self):
        self._loading = True
        s = self.state.project.school
        self.name.setText(s.name)
        self.headmaster.setText(s.headmaster)
        self.vices.setText(", ".join(s.vice_principals))
        self.parts.setRowCount(len(s.parts))
        for r, part in enumerate(s.parts):
            self._part_row(r, part)
        self.days.setValue(s.days)
        self.periods.setValue(s.max_periods)
        self.lunch.setValue(s.bell.lunch_after or 0)
        self.bell.blockSignals(True)
        self.bell.setRowCount(s.max_periods)
        self.bell.setVerticalHeaderLabels([f"{q}. ders" for q in range(1, s.max_periods + 1)])
        for q in range(s.max_periods):
            start, end = s.bell.periods[q] if q < len(s.bell.periods) else ("", "")
            self.bell.setItem(q, 0, QTableWidgetItem(start))
            self.bell.setItem(q, 1, QTableWidgetItem(end))
        self.bell.blockSignals(False)
        self._loading = False

    def flush(self, quiet=False) -> bool:
        self.commit()
        return True

    def commit(self, *_):
        if self._loading:
            return
        p = self.state.project
        parts = []
        for r in range(self.parts.rowCount()):
            combo, lo, hi = (self.parts.cellWidget(r, c) for c in range(3))
            if combo:
                parts.append(SchoolPart(combo.currentData(), lo.value(), hi.value()))
        periods = []
        for q in range(self.bell.rowCount()):
            a, b = self.bell.item(q, 0), self.bell.item(q, 1)
            periods.append(((a.text() if a else "").strip(), (b.text() if b else "").strip()))
        n = max([self.periods.value()] + [needed_periods(x) for x in parts])
        periods = (periods + [("", "")] * n)[:n]
        days = self.days.value()
        if days != p.school.days and p.classes:
            warn(self, "Gün sayısı değişti: sınıfların günlük ders sayılarını Sınıflar sayfasında kontrol edin.")
        school = replace(p.school, name=self.name.text().strip(), headmaster=self.headmaster.text().strip(),
                         vice_principals=tuple(x.strip() for x in self.vices.text().split(",") if x.strip()),
                         parts=tuple(parts), days=days, max_periods=n,
                         bell=Bell(tuple(periods), self.lunch.value() or None))
        self.state.apply(replace(p, school=school), "Okul bilgileri")

    def add_part(self):
        p = self.state.project
        used = {g for x in p.school.parts for g in range(x.grade_from, x.grade_to + 1)}
        lo = next((g for g in range(5, 13) if g not in used), 5)
        part = SchoolPart("ortaokul" if lo <= 8 else "anadolu_lisesi", lo, 8 if lo <= 8 else 12)
        school = replace(p.school, parts=p.school.parts + (part,))
        n = max(school.max_periods, needed_periods(part))
        periods = tuple((list(school.bell.periods) + [("", "")] * n)[:n])
        school = replace(school, max_periods=n, bell=replace(school.bell, periods=periods))
        self.state.apply(replace(p, school=school), "Okul türü ekle")

    def remove_part(self):
        r = self.parts.currentRow()
        p = self.state.project
        if 0 <= r < len(p.school.parts):
            parts = p.school.parts[:r] + p.school.parts[r + 1:]
            self.state.apply(replace(p, school=replace(p.school, parts=parts)), "Okul türü kaldır")
