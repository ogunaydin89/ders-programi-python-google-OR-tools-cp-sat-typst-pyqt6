"""Öğretmenler: list, short forms, branş, one-click closed days and hours."""
from dataclasses import replace

from PyQt6.QtWidgets import (QFormLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
                             QPushButton, QVBoxLayout, QWidget)

from ..model import Teacher, new_id
from ..shortform import duplicates, normalise, teacher_short
from .widgets import AvailabilityGrid, ask, heading, warn


class TeachersPage(QWidget):
    def __init__(self, state):
        super().__init__()
        self.state = state
        lay = QHBoxLayout(self)
        left = QVBoxLayout()
        left.addWidget(heading("Öğretmenler"))
        self.list = QListWidget()
        self.list.currentRowChanged.connect(self.show_teacher)
        left.addWidget(self.list)
        row = QHBoxLayout()
        add, rem = QPushButton("Öğretmen ekle"), QPushButton("Sil")
        add.clicked.connect(self.add)
        rem.clicked.connect(self.remove)
        row.addWidget(add)
        row.addWidget(rem)
        left.addLayout(row)
        lay.addLayout(left, 1)

        right = QVBoxLayout()
        form = QFormLayout()
        self.name = QLineEdit()
        self.short = QLineEdit()
        self.short.setPlaceholderText("Zorunlu; ör. A.YIL")
        self.branch = QLineEdit()
        form.addRow("Adı soyadı", self.name)
        form.addRow("Kısaltma", self.short)
        form.addRow("Branş", self.branch)
        right.addLayout(form)
        self.load = QLabel()
        right.addWidget(self.load)
        right.addWidget(QLabel("Kapalı saatler: bir hücreye tıklayınca o saat, gün başlığına tıklayınca bütün gün "
                               "kapanır/açılır."))
        self.grid = AvailabilityGrid()
        self.grid.toggled.connect(self.set_closed)
        right.addWidget(self.grid)
        lay.addLayout(right, 2)
        self.name.editingFinished.connect(self.commit)
        self.short.editingFinished.connect(self.commit)
        self.branch.editingFinished.connect(self.commit)
        state.changed.connect(self.refresh)
        self.refresh()

    def current(self):
        item = self.list.currentItem()
        return self.state.project.teacher(item.data(256)) if item else None

    def refresh(self):
        p = self.state.project
        cur = self.current()
        self.list.blockSignals(True)
        self.list.clear()
        for t in sorted(p.teachers, key=lambda t: t.name):
            it = QListWidgetItem(f"{t.name}  ({t.short}, {p.teacher_load(t.id)} saat)")
            it.setData(256, t.id)
            self.list.addItem(it)
            if cur and t.id == cur.id:
                self.list.setCurrentItem(it)
        self.list.blockSignals(False)
        if self.list.currentItem() is None and self.list.count():
            self.list.setCurrentRow(0)
        self.show_teacher()

    def show_teacher(self, *_):
        t = self.current()
        p = self.state.project
        for w in (self.name, self.short, self.branch):
            w.setEnabled(t is not None)
        self.grid.setEnabled(t is not None)
        if not t:
            return
        self.name.setText(t.name)
        self.short.setText(t.short)
        self.branch.setText(t.branch)
        self.load.setText(f"Haftalık yük: {p.teacher_load(t.id)} saat")
        self.grid.set_state(p.school.days, p.school.max_periods, t.closed)

    def _replace(self, new, label):
        p = self.state.project
        self.state.apply(replace(p, teachers=tuple(new if x.id == new.id else x for x in p.teachers)), label)

    def commit(self):
        t = self.current()
        if not t:
            return
        name = self.name.text().strip() or t.name
        short = self.short.text().strip() or teacher_short(name)
        if name != t.name and t.short.startswith("Ö.") and normalise(short) == normalise(t.short):
            short = teacher_short(name)            # still the placeholder: suggest N.SUR from the new name
        others = [(x.id, x.short) for x in self.state.project.teachers if x.id != t.id]
        if duplicates(others + [(t.id, short)]):
            warn(self, f"'{short}' kısaltması başka bir öğretmende kullanılıyor. Farklı bir kısaltma girin.")
            self.short.setText(t.short)
            return
        self._replace(replace(t, name=name, short=normalise(short), branch=self.branch.text().strip()),
                      "Öğretmen bilgisi")

    def set_closed(self, closed):
        t = self.current()
        if t:
            self._replace(replace(t, closed=frozenset(closed)), "Kapalı saatler")

    def add(self):
        p = self.state.project
        tid = new_id("T", [t.id for t in p.teachers])
        n = len(p.teachers) + 1
        short = f"Ö.{n:02d}"
        while duplicates([(t.id, t.short) for t in p.teachers] + [(tid, short)]):
            n += 1
            short = f"Ö.{n:02d}"
        t = Teacher(tid, f"Yeni Öğretmen {n}", short)
        self.state.apply(replace(p, teachers=p.teachers + (t,)), "Öğretmen ekle")
        for i in range(self.list.count()):
            if self.list.item(i).data(256) == tid:
                self.list.setCurrentRow(i)
        self.name.setFocus()
        self.name.selectAll()

    def remove(self):
        t = self.current()
        if not t:
            return
        p = self.state.project
        used = [l for l in p.lessons if l.teacher == t.id]
        if used and not ask(self, f"{t.name} öğretmeninin {len(used)} dersi var. Silinirse bu dersler öğretmensiz "
                                  "kalır. Devam edilsin mi?"):
            return
        lessons = tuple(replace(l, teacher=None) if l.teacher == t.id else l for l in p.lessons)
        classes = tuple(replace(c, rehber=None) if c.rehber == t.id else c for c in p.classes)
        self.state.apply(replace(p, teachers=tuple(x for x in p.teachers if x.id != t.id), lessons=lessons,
                                 classes=classes), "Öğretmen sil")
