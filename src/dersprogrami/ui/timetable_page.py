"""Program: çarşaf / class / teacher views. In a class view a lesson can be moved or swapped by hand;
valid target cells turn green, and any move that would break a rule is refused with the reason."""
from dataclasses import replace

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (QComboBox, QHBoxLayout, QHeaderView, QLabel, QPushButton, QTableWidget,
                             QTableWidgetItem, QVBoxLayout, QWidget)

from ..checker import check
from ..model import DAY_NAMES
from .widgets import heading, warn

SELECTED = QColor("#fff59d")
VALID = QColor("#a5d6a7")
LOCKED = QColor("#e3f2fd")
WHITE = QColor("#ffffff")


def move_block(placements, block, day, start, class_blocks):
    """New placements with `block` moved to (day, start); an equal-length block there is swapped back.
    Returns None if the move is not a simple move/swap."""
    if (day, start) == (block.day, block.start):
        return None
    target = [b for b in class_blocks if b.day == day and not (b.start + b.length <= start or
                                                               start + block.length <= b.start)]
    target = [b for b in target if b != block]
    moved = replace(block, day=day, start=start, locked=False)
    if not target:
        others = [x for x in placements if x != block]
        return tuple(others) + (moved,)
    if len(target) == 1 and target[0].length == block.length and target[0].start == start:
        other = target[0]
        if other.locked:
            return None
        rest = [x for x in placements if x not in (block, other)]
        return tuple(rest) + (moved, replace(other, day=block.day, start=block.start))
    return None


class TimetablePage(QWidget):
    def __init__(self, state):
        super().__init__()
        self.state = state
        self.selected = None
        self.valid = {}
        lay = QVBoxLayout(self)
        lay.addWidget(heading("Ders programı"))
        row = QHBoxLayout()
        row.addWidget(QLabel("Görünüm:"))
        self.view = QComboBox()
        self.view.currentIndexChanged.connect(self.render)
        row.addWidget(self.view, 1)
        self.lock = QPushButton("Seçili dersi kilitle / kilidi aç")
        self.lock.clicked.connect(self.toggle_lock)
        row.addWidget(self.lock)
        lay.addLayout(row)
        self.info = QLabel()
        self.info.setWordWrap(True)
        lay.addWidget(self.info)
        self.grid = QTableWidget()
        self.grid.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.grid.cellClicked.connect(self.clicked)
        lay.addWidget(self.grid, 1)
        state.changed.connect(self.refresh)
        self.refresh()

    def refresh(self):
        p = self.state.project
        key = self.view.currentData()
        self.view.blockSignals(True)
        self.view.clear()
        self.view.addItem("Çarşaf (bütün öğretmenler)", ("all", None))
        for c in sorted(p.classes, key=lambda c: (c.grade, c.section)):
            self.view.addItem(f"Sınıf: {c.label}", ("class", c.id))
        for t in sorted(p.teachers, key=lambda t: t.name):
            self.view.addItem(f"Öğretmen: {t.name}", ("teacher", t.id))
        self.view.setCurrentIndex(max(0, self.index_of(key)))
        self.view.blockSignals(False)
        self.selected = None
        self.valid = {}
        self.render()

    def index_of(self, key) -> int:
        """Position of a view key such as ("class", "C001"); Qt's findData cannot compare Python tuples."""
        for i in range(self.view.count()):
            if key is not None and tuple(self.view.itemData(i)) == tuple(key):
                return i
        return -1

    def show_view(self, kind, ref=None):
        self.view.setCurrentIndex(max(0, self.index_of((kind, ref))))

    # -- drawing -------------------------------------------------------------
    def render(self, *_):
        p = self.state.project
        kind, ref = self.view.currentData() or ("all", None)
        D, P = p.school.days, p.school.max_periods
        lessons = {l.id: l for l in p.lessons}
        classes = {c.id: c for c in p.classes}
        teachers = {t.id: t for t in p.teachers}
        self.grid.clear()
        self.cell_block = {}
        if not p.placements:
            self.info.setText("Henüz program yok. 'Çöz' sayfasından program oluşturun.")
        else:
            problems = check(p, p.placements)
            self.info.setText("⚠ Program güncel değil veya kurallara uymuyor: " + problems[0] +
                              (f" (+{len(problems) - 1})" if len(problems) > 1 else "")
                              if problems else "Sınıf görünümünde bir derse, sonra yeşil bir hücreye tıklayarak "
                                               "dersi taşıyabilir veya yer değiştirebilirsiniz.")
        if kind == "all":
            rows = [t for t in sorted(p.teachers, key=lambda t: t.name) if p.teacher_load(t.id)]
            self.grid.setRowCount(len(rows))
            self.grid.setColumnCount(D * P)
            self.grid.setVerticalHeaderLabels([f"{t.short}" for t in rows])
            self.grid.setHorizontalHeaderLabels([f"{DAY_NAMES[d][:3]} {q}" for d in range(D) for q in range(1, P + 1)])
            index = {t.id: r for r, t in enumerate(rows)}
            for b in p.placements:
                l = lessons.get(b.lesson)
                if not l or l.teacher not in index:
                    continue
                for q in range(b.start, b.start + b.length):
                    it = QTableWidgetItem(f"{classes[l.class_id].label}\n{l.short}")
                    it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.grid.setItem(index[l.teacher], (b.day - 1) * P + q - 1, it)
            self.grid.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
            self.grid.resizeRowsToContents()
            return
        self.grid.setRowCount(P)
        self.grid.setColumnCount(D)
        self.grid.setHorizontalHeaderLabels(list(DAY_NAMES[:D]))
        bell = p.school.bell.periods
        self.grid.setVerticalHeaderLabels([f"{q}. ders\n{bell[q - 1][0]}" if q <= len(bell) else f"{q}. ders"
                                           for q in range(1, P + 1)])
        self.grid.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        for b in p.placements:
            l = lessons.get(b.lesson)
            if not l:
                continue
            if (kind == "class" and l.class_id != ref) or (kind == "teacher" and l.teacher != ref):
                continue
            for q in range(b.start, b.start + b.length):
                if kind == "class":
                    t = teachers.get(l.teacher)
                    text = f"{l.name}\n{t.short if t else ''}"
                else:
                    text = f"{classes[l.class_id].label}\n{l.name}"
                it = QTableWidgetItem(("🔒 " if b.locked else "") + text)
                it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                colour = SELECTED if b == self.selected else LOCKED if b.locked else WHITE
                it.setBackground(colour)
                self.grid.setItem(q - 1, b.day - 1, it)
                self.cell_block[(q - 1, b.day - 1)] = b
        for (d, s), ok in self.valid.items():
            if ok:
                for q in range(s, s + self.selected.length):
                    it = self.grid.item(q - 1, d - 1)
                    if it is None:
                        it = QTableWidgetItem("")
                        self.grid.setItem(q - 1, d - 1, it)
                    it.setBackground(VALID)
        self.grid.resizeRowsToContents()

    # -- editing ------------------------------------------------------------------
    def class_blocks(self, class_id):
        p = self.state.project
        ids = {l.id for l in p.lessons if l.class_id == class_id}
        return [b for b in p.placements if b.lesson in ids]

    def clicked(self, row, col):
        kind, ref = self.view.currentData() or ("all", None)
        if kind != "class":
            return
        p = self.state.project
        block = self.cell_block.get((row, col))
        if self.selected and (col + 1, row + 1) in self.valid or \
                (self.selected and block != self.selected and self._target_start(row, col) is not None):
            return self.try_move(row, col)
        if block is None:
            return
        self.selected = block
        before = set(check(p, p.placements))
        self.valid = {}
        cb = self.class_blocks(ref)
        c = p.school_class(ref)
        for d in range(1, p.school.days + 1):
            for s in range(1, c.daily_hours[d - 1] - block.length + 2):
                new = move_block(p.placements, block, d, s, cb)
                self.valid[(d, s)] = new is not None and not (set(check(p, new)) - before)
        self.render()

    def _target_start(self, row, col):
        block = self.cell_block.get((row, col))
        if block is not None and block.length == self.selected.length:
            return block.start
        return None

    def try_move(self, row, col):
        p = self.state.project
        kind, ref = self.view.currentData()
        target = self.cell_block.get((row, col))
        start = target.start if target is not None and target.length == self.selected.length else row + 1
        new = move_block(p.placements, self.selected, col + 1, start, self.class_blocks(ref))
        if new is None:
            warn(self, "Bu hücreye taşınamaz: yalnızca aynı uzunluktaki bir dersle yer değiştirilebilir "
                       "(kilitli dersler yer değiştirmez).")
        else:
            added = set(check(p, new)) - set(check(p, p.placements))
            if added:
                warn(self, "Bu taşıma kurallara aykırı olduğu için yapılmadı:\n\n" + "\n".join(sorted(added)[:8]))
            else:
                self.selected = None
                self.valid = {}
                self.state.apply(replace(p, placements=tuple(sorted(new, key=lambda x: (x.lesson, x.day,
                                                                                       x.start)))), "Ders taşı")
                return
        self.selected = None
        self.valid = {}
        self.render()

    def toggle_lock(self):
        if not self.selected:
            warn(self, "Önce sınıf görünümünde bir derse tıklayın.")
            return
        p = self.state.project
        b = self.selected
        new = tuple(replace(x, locked=not x.locked) if x == b else x for x in p.placements)
        self.selected = None
        self.valid = {}
        self.state.apply(replace(p, placements=new), "Kilit")
