"""Sınıflar: add classes (with mandatory day hours), electives, choice lessons, custom lessons."""
from dataclasses import replace

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QGroupBox, QHBoxLayout,
                             QHeaderView, QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton,
                             QScrollArea, QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from .. import curriculum as cm
from ..model import DAY_NAMES, Lesson, SchoolClass, new_id
from ..shortform import lesson_short, normalise
from .widgets import ask, heading, warn


def parse_format(text: str):
    try:
        parts = tuple(int(x) for x in text.replace(" ", "").split("+") if x)
    except ValueError:
        return None
    return parts if parts and all(x > 0 for x in parts) else None


class ElectivePicker(QWidget):
    """Checkbox per offered elective with an hour choice; shows the curriculum's rule problems live."""

    def __init__(self, cur, grade, chosen=()):
        super().__init__()
        self.cur, self.grade = cur, grade
        lay = QVBoxLayout(self)
        need = cur.elective_hours(grade)
        lay.addWidget(QLabel(f"Seçmeli ders saati: {need}"))
        self.rows = []
        groups = cur.elective_groups()
        chosen = dict(chosen)
        box = QWidget()
        bl = QVBoxLayout(box)
        for gid, gname in groups.items():
            items = [e for e in cur.electives(grade) if e[1] == gid]
            if not items:
                continue
            g = QGroupBox(gname)
            gl = QFormLayout(g)
            for name, _, options, _ in items:
                cb = QCheckBox(name)
                hours = QComboBox()
                for o in options:
                    hours.addItem(f"{o} saat", o)
                if name in chosen:
                    cb.setChecked(True)
                    hours.setCurrentIndex(max(0, hours.findData(chosen[name])))
                cb.toggled.connect(self.update)
                hours.currentIndexChanged.connect(self.update)
                gl.addRow(cb, hours)
                self.rows.append((name, cb, hours))
            bl.addWidget(g)
        scroll = QScrollArea()
        scroll.setWidget(box)
        scroll.setWidgetResizable(True)
        lay.addWidget(scroll)
        self.status = QLabel()
        self.status.setWordWrap(True)
        lay.addWidget(self.status)
        self.update()

    def chosen(self):
        return [(name, hours.currentData()) for name, cb, hours in self.rows if cb.isChecked()]

    def problems(self):
        return cm.check_electives(self.cur, self.grade, self.chosen())

    def update(self, *_):
        probs = self.problems()
        self.status.setText("✔ Seçim geçerli." if not probs else "\n".join("✘ " + p for p in probs))
        self.status.setStyleSheet("color: #2e7d32" if not probs else "color: #c62828")


class ClassDialog(QDialog):
    """New class: type, grade, section, then the day hours must be confirmed; then electives and choices."""

    def __init__(self, parent, project, cls=None):
        super().__init__(parent)
        self.project = project
        self.setWindowTitle("Sınıf" if cls else "Sınıf ekle")
        self.resize(640, 720)
        lay = QVBoxLayout(self)
        form = QFormLayout()
        self.cur = QComboBox()
        parts = project.school.parts or tuple()
        allowed = {x.curriculum for x in parts} or set(cm.load_all())
        for cid, cur in cm.load_all().items():
            if cid in allowed:
                self.cur.addItem(cur.name, cid)
        self.grade = QComboBox()
        self.section = QLineEdit(cls.section if cls else "A")
        form.addRow("Okul türü", self.cur)
        form.addRow("Sınıf", self.grade)
        form.addRow("Şube", self.section)
        lay.addLayout(form)
        hours = QGroupBox("Günlük ders sayıları (bu sınıfın her gün kaç dersi var?)")
        hl = QHBoxLayout(hours)
        self.days = []
        for d in range(project.school.days):
            box = QVBoxLayout()
            box.addWidget(QLabel(DAY_NAMES[d]))
            sp = QSpinBox(minimum=0, maximum=project.school.max_periods)
            sp.valueChanged.connect(self.update_total)
            box.addWidget(sp)
            self.days.append(sp)
            hl.addLayout(box)
        self.total = QLabel()
        hl.addWidget(self.total)
        lay.addWidget(hours)
        self.confirm = QCheckBox("Günlük ders sayılarını kontrol ettim ve onaylıyorum")
        lay.addWidget(self.confirm)
        self.choice_box = QGroupBox("Seçimli dersler")
        self.choice_form = QFormLayout(self.choice_box)
        lay.addWidget(self.choice_box)
        self.picker_holder = QVBoxLayout()
        lay.addLayout(self.picker_holder, 1)
        self.picker = None
        self.rules = QCheckBox("Seçmeli ders kurallarını uygula (kapalıysa kurallar yalnızca uyarı verir)")
        self.rules.setChecked(cls.elective_rules if cls else True)
        lay.addWidget(self.rules)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self.existing = cls
        self.cur.currentIndexChanged.connect(self.fill_grades)
        self.grade.currentIndexChanged.connect(self.fill_grade)
        if cls:
            self.cur.setCurrentIndex(max(0, self.cur.findData(cls.curriculum)))
        self.fill_grades()
        if cls:
            self.grade.setCurrentIndex(max(0, self.grade.findData(cls.grade)))
            for sp, h in zip(self.days, cls.daily_hours):
                sp.setValue(h)
            self.confirm.setChecked(True)
            for w in (self.cur, self.grade, self.section):
                w.setEnabled(False)

    def curriculum(self):
        return cm.get(self.cur.currentData())

    def fill_grades(self, *_):
        self.grade.blockSignals(True)
        self.grade.clear()
        cid = self.cur.currentData()
        ranges = [range(x.grade_from, x.grade_to + 1) for x in self.project.school.parts if x.curriculum == cid]
        grades = sorted({g for r in ranges for g in r}) or list(self.curriculum().grades)
        for g in grades:
            self.grade.addItem(f"{g}. sınıf", g)
        self.grade.blockSignals(False)
        self.fill_grade()

    def fill_grade(self, *_):
        cur, g = self.curriculum(), self.grade.currentData()
        if g is None:
            return
        if not self.existing:
            default = cur.default_daily_hours(g, self.project.school.days)
            for sp, h in zip(self.days, default):
                sp.setValue(min(h, self.project.school.max_periods))
            self.confirm.setChecked(False)
            if max(default) > self.project.school.max_periods:
                warn(self, f"Bu sınıf türünde günde {max(default)} ders var, ancak okulda günlük en fazla "
                           f"{self.project.school.max_periods} ders tanımlı. Okul sayfasından artırın.")
        while self.choice_form.rowCount():
            self.choice_form.removeRow(0)
        self.choices = {}
        current = {l.name for l in self.project.lessons_of_class(self.existing.id)} if self.existing else set()
        for name, options, hours in cur.choice_lessons(g):
            combo = QComboBox()
            for o in options:
                combo.addItem(o, o)
            for o in options:
                if o in current:
                    combo.setCurrentIndex(combo.findData(o))
            self.choice_form.addRow(f"{name} ({hours} saat)", combo)
            self.choices[name] = combo
        self.choice_box.setVisible(bool(self.choices))
        if self.picker:
            self.picker.setParent(None)
        chosen = []
        if self.existing:
            offered = {cm.elective_lesson_name(n): n for n, *_ in cur.electives(g)}
            chosen = [(offered.get(l.name, l.name), l.hours) for l in self.project.lessons_of_class(self.existing.id)
                      if l.kind == "elective"]
        self.picker = ElectivePicker(cur, g, chosen) if cur.elective_hours(g) else None
        if self.picker:
            self.picker_holder.addWidget(self.picker)
        self.update_total()

    def update_total(self, *_):
        total = sum(sp.value() for sp in self.days)
        g = self.grade.currentData()
        official = self.curriculum().weekly_total(g) if g else None
        self.total.setText(f"Toplam: {total}" + (f" (resmî: {official})" if official else ""))

    def accept(self):
        if not self.confirm.isChecked():
            warn(self, "Lütfen günlük ders sayılarını kontrol edip onay kutusunu işaretleyin.")
            return
        if not self.section.text().strip():
            warn(self, "Şube adı boş olamaz.")
            return
        if self.picker and self.rules.isChecked() and self.picker.problems():
            warn(self, "Seçmeli ders seçimi kurallara uymuyor:\n" + "\n".join(self.picker.problems()))
            return
        super().accept()

    def result_values(self):
        return dict(curriculum=self.cur.currentData(), grade=self.grade.currentData(),
                    section=self.section.text().strip().upper(), daily=tuple(sp.value() for sp in self.days),
                    electives=self.picker.chosen() if self.picker else [],
                    choices={n: c.currentData() for n, c in self.choices.items()},
                    rules=self.rules.isChecked())


class ClassesPage(QWidget):
    COLS = ["Ders", "Kısaltma", "Saat", "Biçim", "Tür"]

    def __init__(self, state):
        super().__init__()
        self.state = state
        lay = QHBoxLayout(self)
        left = QVBoxLayout()
        left.addWidget(heading("Sınıflar"))
        self.list = QListWidget()
        self.list.currentRowChanged.connect(self.show_class)
        left.addWidget(self.list)
        row = QHBoxLayout()
        for text, fn in (("Sınıf ekle", self.add), ("Düzenle", self.edit), ("Sil", self.remove)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            row.addWidget(b)
        left.addLayout(row)
        lay.addLayout(left, 1)
        right = QVBoxLayout()
        self.title = QLabel()
        right.addWidget(self.title)
        form = QFormLayout()
        self.rehber = QComboBox()
        self.rehber.activated.connect(self.set_rehber)
        form.addRow("Rehber öğretmen", self.rehber)
        right.addLayout(form)
        self.table = QTableWidget(0, len(self.COLS))
        self.table.setHorizontalHeaderLabels(self.COLS)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.itemChanged.connect(self.edit_lesson)
        right.addWidget(self.table)
        row2 = QHBoxLayout()
        for text, fn in (("Özel ders ekle", self.add_custom), ("Seçili dersi sil", self.remove_lesson)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            row2.addWidget(b)
        row2.addStretch()
        right.addLayout(row2)
        lay.addLayout(right, 3)
        state.changed.connect(self.refresh)
        self.refresh()

    def current(self):
        it = self.list.currentItem()
        return self.state.project.school_class(it.data(256)) if it else None

    def refresh(self):
        p = self.state.project
        cur = self.current()
        self.list.blockSignals(True)
        self.list.clear()
        for c in sorted(p.classes, key=lambda c: (c.grade, c.section)):
            total = sum(l.hours for l in p.lessons_of_class(c.id))
            it = QListWidgetItem(f"{c.label}  ({cm.get(c.curriculum).name}, {total} saat)")
            it.setData(256, c.id)
            self.list.addItem(it)
            if cur and cur.id == c.id:
                self.list.setCurrentItem(it)
        self.list.blockSignals(False)
        if self.list.currentItem() is None and self.list.count():
            self.list.setCurrentRow(0)
        self.show_class()

    def show_class(self, *_):
        c = self.current()
        p = self.state.project
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        self.rehber.clear()
        if not c:
            self.title.setText("Henüz sınıf yok. 'Sınıf ekle' ile başlayın.")
            self.table.blockSignals(False)
            return
        hours = " · ".join(f"{DAY_NAMES[i][:3]} {h}" for i, h in enumerate(c.daily_hours))
        self.title.setText(f"<b>{c.label}</b> — {cm.get(c.curriculum).name} — günlük ders: {hours}")
        self.rehber.addItem("(seçilmedi)", None)
        for t in sorted(p.teachers, key=lambda t: t.name):
            self.rehber.addItem(t.name, t.id)
        self.rehber.setCurrentIndex(max(0, self.rehber.findData(c.rehber)))
        kinds = {"compulsory": "zorunlu", "elective": "seçmeli", "choice": "seçimli", "custom": "özel",
                 "rehberlik": "rehberlik"}
        for l in p.lessons_of_class(c.id):
            r = self.table.rowCount()
            self.table.insertRow(r)
            vals = [l.name, l.short, str(l.hours), "+".join(map(str, l.format)), kinds[l.kind]]
            for col, v in enumerate(vals):
                it = QTableWidgetItem(v)
                it.setData(256, l.id)
                if col == 4 or (col == 0 and l.kind != "custom"):
                    it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(r, col, it)
        self.table.blockSignals(False)

    def set_rehber(self, *_):
        c = self.current()
        if not c:
            return
        p = self.state.project
        tid = self.rehber.currentData()
        lessons = tuple(replace(l, teacher=tid) if l.class_id == c.id and l.kind == "rehberlik" else l
                        for l in p.lessons)
        classes = tuple(replace(x, rehber=tid) if x.id == c.id else x for x in p.classes)
        self.state.apply(replace(p, classes=classes, lessons=lessons), "Rehber öğretmen")

    def edit_lesson(self, item):
        p = self.state.project
        l = p.lesson(item.data(256))
        if not l:
            return
        col, text = item.column(), item.text().strip()
        new = l
        if col == 0 and text:
            new = replace(l, name=text)
        elif col == 1:
            if not text:
                warn(self, "Kısaltma boş olamaz.")
                return self.show_class()
            clash = [x for x in p.lessons_of_class(l.class_id)
                     if normalise(x.short) == normalise(text) and normalise(x.name) != normalise(l.name)]
            if clash:
                warn(self, f"'{text}' kısaltması bu sınıfta '{clash[0].name}' dersinde kullanılıyor.")
                return self.show_class()
            new = replace(l, short=normalise(text))
        elif col == 2:
            if not text.isdigit() or int(text) < 1:
                warn(self, "Ders saati 1 veya daha büyük bir sayı olmalı.")
                return self.show_class()
            new = replace(l, hours=int(text), format=cm.default_format(int(text), p.school.days))
        elif col == 3:
            fmt = parse_format(text)
            if not fmt or sum(fmt) != l.hours:
                warn(self, f"Biçim, toplamı {l.hours} olan sayılardan oluşmalı (ör. 2+2+1).")
                return self.show_class()
            new = replace(l, format=tuple(sorted(fmt, reverse=True)))
        self.state.apply(replace(p, lessons=tuple(new if x.id == l.id else x for x in p.lessons)), "Ders düzenle")

    def _class_values(self, dlg):
        return dlg.result_values()

    def add(self):
        p = self.state.project
        if not p.school.parts and not ask(self, "Okul sayfasında okul türü tanımlanmamış. Yine de sınıf eklensin mi?"):
            return
        dlg = ClassDialog(self, p)
        if not dlg.exec():
            return
        v = dlg.result_values()
        if any(c.grade == v["grade"] and c.section == v["section"] for c in p.classes):
            warn(self, f"{v['grade']}-{v['section']} sınıfı zaten var.")
            return
        cls = SchoolClass(new_id("C", [c.id for c in p.classes]), v["curriculum"], v["grade"], v["section"],
                          v["daily"], elective_rules=v["rules"])
        lessons = cm.build_class_lessons(cm.get(v["curriculum"]), cls, v["electives"], v["choices"],
                                         [l.id for l in p.lessons], p.school.days)
        versions = dict(p.curriculum_versions)
        versions[v["curriculum"]] = cm.get(v["curriculum"]).version
        self.state.apply(replace(p, classes=p.classes + (cls,), lessons=p.lessons + lessons,
                                 curriculum_versions=tuple(sorted(versions.items()))), "Sınıf ekle")

    def edit(self):
        c = self.current()
        if not c:
            return
        p = self.state.project
        dlg = ClassDialog(self, p, c)
        if not dlg.exec():
            return
        v = dlg.result_values()
        cls = replace(c, daily_hours=v["daily"], elective_rules=v["rules"])
        fresh = cm.build_class_lessons(cm.get(c.curriculum), cls, v["electives"], v["choices"],
                                       [l.id for l in p.lessons], p.school.days)
        old = [l for l in p.lessons if l.class_id == c.id]
        keep = [l for l in old if l.kind in ("compulsory", "rehberlik", "custom")]
        by_name = {normalise(l.name): l for l in old}
        new_parts = []
        for l in fresh:
            if l.kind in ("elective", "choice"):
                prev = by_name.get(normalise(l.name))
                new_parts.append(replace(l, teacher=prev.teacher, short=prev.short) if prev else l)
        lessons = tuple(l for l in p.lessons if l.class_id != c.id) + tuple(keep) + tuple(new_parts)
        dropped = {l.id for l in old} - {l.id for l in lessons}
        placements = tuple(x for x in p.placements if x.lesson not in dropped)
        self.state.apply(replace(p, classes=tuple(cls if x.id == c.id else x for x in p.classes), lessons=lessons,
                                 placements=placements), "Sınıf düzenle")

    def remove(self):
        c = self.current()
        if not c or not ask(self, f"{c.label} sınıfı ve bütün dersleri silinsin mi?"):
            return
        p = self.state.project
        gone = {l.id for l in p.lessons if l.class_id == c.id}
        self.state.apply(replace(p, classes=tuple(x for x in p.classes if x.id != c.id),
                                 lessons=tuple(l for l in p.lessons if l.id not in gone),
                                 placements=tuple(x for x in p.placements if x.lesson not in gone)), "Sınıf sil")

    def add_custom(self):
        c = self.current()
        if not c:
            return
        name, ok = QInputDialog.getText(self, "Özel ders", "Dersin adı:")
        if not ok or not name.strip():
            return
        hours, ok = QInputDialog.getInt(self, "Özel ders", "Haftalık ders saati:", 1, 1, 40)
        if not ok:
            return
        p = self.state.project
        short = lesson_short(name)
        taken = {normalise(l.short) for l in p.lessons_of_class(c.id)}
        n = 1
        base = short
        while normalise(short) in taken:
            short = f"{base}{n}"
            n += 1
        l = Lesson(new_id("L", [x.id for x in p.lessons]), c.id, name.strip(), short, hours,
                   cm.default_format(hours, p.school.days), kind="custom")
        self.state.apply(replace(p, lessons=p.lessons + (l,)), "Özel ders ekle")

    def remove_lesson(self):
        r = self.table.currentRow()
        if r < 0:
            return
        lid = self.table.item(r, 0).data(256)
        p = self.state.project
        l = p.lesson(lid)
        if l and ask(self, f"{l.name} dersi bu sınıftan silinsin mi?"):
            self.state.apply(replace(p, lessons=tuple(x for x in p.lessons if x.id != lid),
                                     placements=tuple(x for x in p.placements if x.lesson != lid)), "Ders sil")
