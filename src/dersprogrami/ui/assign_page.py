"""Ders Atama: matrix of lessons (rows) x classes (columns); pick a teacher per cell. Live teacher totals."""
from dataclasses import replace

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QComboBox, QFormLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QListWidget,
                             QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from ..shortform import normalise
from .classes_page import parse_format
from .widgets import heading, warn


class AssignPage(QWidget):
    def __init__(self, state):
        super().__init__()
        self.state = state
        lay = QHBoxLayout(self)
        left = QVBoxLayout()
        left.addWidget(heading("Ders atama"))
        top = QHBoxLayout()
        top.addWidget(QLabel("Branş filtresi:"))
        self.filter = QComboBox()
        self.filter.currentIndexChanged.connect(self.refresh)
        top.addWidget(self.filter)
        top.addStretch()
        left.addLayout(top)
        self.matrix = QTableWidget()
        self.matrix.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.matrix.currentCellChanged.connect(self.show_detail)
        left.addWidget(self.matrix)
        lay.addLayout(left, 4)

        right = QVBoxLayout()
        right.addWidget(QLabel("<b>Öğretmen yükleri</b>"))
        self.loads = QListWidget()
        right.addWidget(self.loads, 2)
        right.addWidget(QLabel("<b>Seçili ders</b>"))
        self.detail = QLabel("—")
        self.detail.setWordWrap(True)
        right.addWidget(self.detail)
        form = QFormLayout()
        self.fmt = QLineEdit()
        self.alts = QLineEdit()
        self.alts.setPlaceholderText("ör. 1+1 (R8 açıkken kullanılır)")
        self.group = QLineEdit()
        self.group.setPlaceholderText("aynı gruptaki dersler farklı günlere (R6)")
        self.forbid = QLineEdit()
        self.forbid.setPlaceholderText("ör. 1,7 (R11)")
        self.prefer = QLineEdit()
        form.addRow("Yerleşim biçimi", self.fmt)
        form.addRow("Alternatif biçimler", self.alts)
        form.addRow("Ders grubu", self.group)
        form.addRow("Yasak ders saatleri", self.forbid)
        form.addRow("Tercih edilen saatler", self.prefer)
        right.addLayout(form)
        right.addStretch(1)
        lay.addLayout(right, 2)
        for w in (self.fmt, self.alts, self.group, self.forbid, self.prefer):
            w.editingFinished.connect(self.commit_detail)
        self.rows, self.cols = [], []
        self.cell_lesson = {}
        state.changed.connect(self.refresh)
        self.refresh()

    def refresh(self, *_):
        p = self.state.project
        branch = self.filter.currentData()
        self.filter.blockSignals(True)
        self.filter.clear()
        self.filter.addItem("(tümü)", None)
        for b in sorted({t.branch for t in p.teachers if t.branch}):
            self.filter.addItem(b, b)
        self.filter.setCurrentIndex(max(0, self.filter.findData(branch)))
        self.filter.blockSignals(False)
        teachers = sorted(p.teachers, key=lambda t: t.name)
        pick = [t for t in teachers if not branch or t.branch == branch]
        self.cols = sorted(p.classes, key=lambda c: (c.grade, c.section))
        names = {}
        for l in p.lessons:
            names.setdefault(normalise(l.name), l.name)
        self.rows = sorted(names.values(), key=lambda n: n)
        cur = (self.matrix.currentRow(), self.matrix.currentColumn())
        self.matrix.clear()
        self.matrix.setRowCount(len(self.rows))
        self.matrix.setColumnCount(len(self.cols))
        self.matrix.setHorizontalHeaderLabels([c.label for c in self.cols])
        self.matrix.setVerticalHeaderLabels(self.rows)
        self.cell_lesson = {}
        by_key = {(l.class_id, normalise(l.name)): l for l in p.lessons}
        for r, name in enumerate(self.rows):
            for c, cls in enumerate(self.cols):
                l = by_key.get((cls.id, normalise(name)))
                if not l:
                    it = QTableWidgetItem("")
                    it.setFlags(Qt.ItemFlag.NoItemFlags)
                    self.matrix.setItem(r, c, it)
                    continue
                self.cell_lesson[(r, c)] = l.id
                combo = QComboBox()
                combo.addItem(f"— ({l.hours} s)", None)
                shown = pick if l.teacher is None or any(t.id == l.teacher for t in pick) else \
                    pick + [p.teacher(l.teacher)]
                for t in shown:
                    combo.addItem(f"{t.short} ({l.hours} s)", t.id)
                combo.setCurrentIndex(max(0, combo.findData(l.teacher)))
                if l.kind == "rehberlik":
                    combo.setToolTip("Rehberlik dersi sınıfın rehber öğretmenine atanır (Sınıflar sayfası).")
                combo.activated.connect(lambda _i, lid=l.id, cb=combo: self.assign(lid, cb.currentData()))
                self.matrix.setCellWidget(r, c, combo)
        if cur[0] >= 0:
            self.matrix.setCurrentCell(*cur)
        self.loads.clear()
        for t in teachers:
            self.loads.addItem(f"{t.short:8}  {p.teacher_load(t.id):3} saat   {t.name}")
        missing = sum(1 for l in p.lessons if l.teacher is None)
        if missing:
            self.loads.insertItem(0, f"Öğretmeni atanmamış ders: {missing}")
        self.show_detail()

    def assign(self, lesson_id, teacher_id):
        p = self.state.project
        l = p.lesson(lesson_id)
        lessons = tuple(replace(x, teacher=teacher_id) if x.id == lesson_id else x for x in p.lessons)
        classes = p.classes
        if l.kind == "rehberlik":
            classes = tuple(replace(c, rehber=teacher_id) if c.id == l.class_id else c for c in p.classes)
        self.state.apply(replace(p, lessons=lessons, classes=classes), "Öğretmen ata")

    def current_lesson(self):
        lid = self.cell_lesson.get((self.matrix.currentRow(), self.matrix.currentColumn()))
        return self.state.project.lesson(lid) if lid else None

    def show_detail(self, *_):
        l = self.current_lesson()
        for w in (self.fmt, self.alts, self.group, self.forbid, self.prefer):
            w.setEnabled(l is not None)
        if not l:
            self.detail.setText("Bir hücre seçin.")
            return
        c = self.state.project.school_class(l.class_id)
        self.detail.setText(f"{c.label} — {l.name} ({l.hours} saat)")
        self.fmt.setText("+".join(map(str, l.format)))
        self.alts.setText(", ".join("+".join(map(str, a)) for a in l.alternatives))
        self.group.setText(l.lesson_group or "")
        self.forbid.setText(",".join(map(str, sorted(l.forbidden_periods))))
        self.prefer.setText(",".join(map(str, sorted(l.preferred_periods))))

    def commit_detail(self):
        l = self.current_lesson()
        if not l:
            return
        fmt = parse_format(self.fmt.text())
        if not fmt or sum(fmt) != l.hours:
            warn(self, f"Biçim, toplamı {l.hours} olan sayılardan oluşmalı (ör. 2+2+1).")
            return self.show_detail()
        alts = []
        for part in filter(None, (x.strip() for x in self.alts.text().split(","))):
            a = parse_format(part)
            if not a or sum(a) != l.hours:
                warn(self, f"Alternatif biçim '{part}' geçersiz: toplamı {l.hours} olmalı.")
                return self.show_detail()
            alts.append(tuple(sorted(a, reverse=True)))
        try:
            forbid = frozenset(int(x) for x in self.forbid.text().split(",") if x.strip())
            prefer = frozenset(int(x) for x in self.prefer.text().split(",") if x.strip())
        except ValueError:
            warn(self, "Ders saatlerini virgülle ayrılmış sayılar olarak girin (ör. 1,7).")
            return self.show_detail()
        new = replace(l, format=tuple(sorted(fmt, reverse=True)), alternatives=tuple(alts),
                      lesson_group=self.group.text().strip() or None, forbidden_periods=forbid,
                      preferred_periods=prefer)
        p = self.state.project
        self.state.apply(replace(p, lessons=tuple(new if x.id == l.id else x for x in p.lessons)), "Ders ayarı")
