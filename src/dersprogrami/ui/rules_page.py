"""Kurallar: Off / Preference / Mandatory for R1–R12, with their values."""
from PyQt6.QtWidgets import QComboBox, QGridLayout, QLabel, QSpinBox, QVBoxLayout, QWidget

from ..model import RuleSetting
from .widgets import heading

RULES = [
    ("R1", "Öğretmenin günlük en fazla ders saati", "saat", 1, 12),
    ("R2", "Öğretmenin art arda en fazla ders saati", "saat", 1, 12),
    ("R3", "Öğretmenin boş saatleri (pencere) — zorunluysa haftalık en fazla", "saat", 0, 30),
    ("R4", "Bir dersin blokları art arda günlere gelmesin", None, 0, 0),
    ("R5", "Öğretmenin aynı sınıftaki farklı dersleri farklı günlere", None, 0, 0),
    ("R6", "Aynı ders grubundaki dersler farklı günlere", None, 0, 0),
    ("R7", "Öğretmenin yükü günlere dengeli dağılsın", None, 0, 0),
    ("R8", "Gerekirse alternatif yerleşim biçimleri kullanılabilsin (bölünebilme)", None, 0, 0),
    ("R9", "Öğretmen okula geldiği gün en az", "saat", 1, 7),
    ("R10", "Öğretmenin ilk dersinden son dersine en fazla", "ders", 1, 12),
    ("R11", "Derslerin yasak / tercih edilen saatleri (Ders Atama'da girilir)", None, 0, 0),
    ("R12", "İki saatlik dersler öğle arasıyla bölünmesin", None, 0, 0),
]
LEVELS = [("off", "Kapalı"), ("preference", "Tercih"), ("mandatory", "Zorunlu")]
DEFAULT_VALUES = {"R1": 7, "R2": 4, "R3": 0, "R9": 2, "R10": 6}


class RulesPage(QWidget):
    def __init__(self, state):
        super().__init__()
        self.state = state
        lay = QVBoxLayout(self)
        lay.addWidget(heading("Kurallar"))
        lay.addWidget(QLabel("Zorunlu kurallar her zaman sağlanır; tercihler mümkün olduğunca sağlanır. "
                             "Çakışma, boş ders ve kapalı saat kuralları her zaman geçerlidir."))
        grid = QGridLayout()
        self.widgets = {}
        for r, (rid, text, unit, lo, hi) in enumerate(RULES):
            grid.addWidget(QLabel(f"<b>{rid}</b>"), r, 0)
            grid.addWidget(QLabel(text), r, 1)
            level = QComboBox()
            for key, name in LEVELS:
                if rid == "R8" and key == "mandatory":
                    continue
                level.addItem(name, key)
            grid.addWidget(level, r, 2)
            value = None
            if unit:
                value = QSpinBox(minimum=lo, maximum=hi, suffix=f" {unit}")
                grid.addWidget(value, r, 3)
                value.valueChanged.connect(self.commit)
            level.currentIndexChanged.connect(self.commit)
            self.widgets[rid] = (level, value)
        lay.addLayout(grid)
        lay.addStretch()
        self._loading = False
        state.changed.connect(self.refresh)
        self.refresh()

    def refresh(self):
        self._loading = True
        p = self.state.project
        for rid, (level, value) in self.widgets.items():
            s = p.rule(rid)
            level.setCurrentIndex(max(0, level.findData(s.level)))
            if value:
                value.setValue(s.value if s.value is not None else DEFAULT_VALUES[rid])
        self._loading = False

    def commit(self, *_):
        if self._loading:
            return
        p = self.state.project
        for rid, (level, value) in self.widgets.items():
            p = p.with_rule(rid, RuleSetting(level.currentData(), value.value() if value else None))
        self.state.apply(p, "Kurallar")
