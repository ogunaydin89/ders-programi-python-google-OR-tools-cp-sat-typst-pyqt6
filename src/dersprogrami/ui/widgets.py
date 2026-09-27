"""Small shared widgets."""
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QHeaderView, QLabel, QMessageBox, QTableWidget, QTableWidgetItem

from ..model import DAY_NAMES

CLOSED = QColor("#e57373")
OPEN = QColor("#ffffff")


def track(state, *fields):
    """Typing in these fields immediately counts as an unsaved change."""
    for f in fields:
        f.textEdited.connect(lambda *_: state.mark_pending())


def info(parent, text, title="Bilgi"):
    QMessageBox.information(parent, title, text)


def warn(parent, text, title="Uyarı"):
    QMessageBox.warning(parent, title, text)


def ask(parent, text, title="Onay") -> bool:
    return QMessageBox.question(parent, title, text) == QMessageBox.StandardButton.Yes


def heading(text):
    lab = QLabel(f"<h3>{text}</h3>")
    return lab


class AvailabilityGrid(QTableWidget):
    """Days x periods grid; click a cell to close/open an hour, click a day header to close/open the day."""
    toggled = pyqtSignal(frozenset)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.closed = frozenset()
        self.days, self.periods = 5, 7
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.cellClicked.connect(self._cell)
        self.horizontalHeader().sectionClicked.connect(self._day)
        self.verticalHeader().sectionClicked.connect(self._period)

    def set_state(self, days, periods, closed):
        self.days, self.periods, self.closed = days, periods, frozenset(closed)
        self.setColumnCount(days)
        self.setRowCount(periods)
        self.setHorizontalHeaderLabels(list(DAY_NAMES[:days]))
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.setVerticalHeaderLabels([f"{q}. ders" for q in range(1, periods + 1)])
        for d in range(days):
            for q in range(periods):
                it = QTableWidgetItem("kapalı" if (d + 1, q + 1) in self.closed else "")
                it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                it.setBackground(CLOSED if (d + 1, q + 1) in self.closed else OPEN)
                self.setItem(q, d, it)

    def _emit(self, closed):
        self.set_state(self.days, self.periods, closed)
        self.toggled.emit(self.closed)

    def _cell(self, row, col):
        slot = (col + 1, row + 1)
        self._emit(self.closed - {slot} if slot in self.closed else self.closed | {slot})

    def _day(self, col):
        day = {(col + 1, q) for q in range(1, self.periods + 1)}
        self._emit(self.closed - day if day <= self.closed else self.closed | day)

    def _period(self, row):
        per = {(d, row + 1) for d in range(1, self.days + 1)}
        self._emit(self.closed - per if per <= self.closed else self.closed | per)
