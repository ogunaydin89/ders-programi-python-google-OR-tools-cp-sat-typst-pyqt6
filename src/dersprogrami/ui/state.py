"""The open project: undo/redo history, dirty flag, save/load. Every edit goes through apply()."""
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal

from ..model import Project
from ..storage import load_project, save_project

HISTORY = 200


class ProjectState(QObject):
    changed = pyqtSignal()

    def __init__(self, project: Project | None = None, path=None):
        super().__init__()
        self.project = project or Project()
        self.path = Path(path) if path else None
        self._undo: list[tuple[Project, str]] = []
        self._redo: list[tuple[Project, str]] = []
        self.dirty = False

    def apply(self, new: Project, label: str = ""):
        if new == self.project:
            return
        self._undo.append((self.project, label))
        del self._undo[:-HISTORY]
        self._redo.clear()
        self.project = new
        self.dirty = True
        self.changed.emit()

    def can_undo(self):
        return bool(self._undo)

    def can_redo(self):
        return bool(self._redo)

    def undo(self):
        if self._undo:
            prev, label = self._undo.pop()
            self._redo.append((self.project, label))
            self.project = prev
            self.dirty = True
            self.changed.emit()

    def redo(self):
        if self._redo:
            nxt, label = self._redo.pop()
            self._undo.append((self.project, label))
            self.project = nxt
            self.dirty = True
            self.changed.emit()

    def new(self):
        self.project, self.path = Project(), None
        self._undo.clear()
        self._redo.clear()
        self.dirty = False
        self.changed.emit()

    def load(self, path):
        self.project = load_project(path)
        self.path = Path(path)
        self._undo.clear()
        self._redo.clear()
        self.dirty = False
        self.changed.emit()

    def save(self, path=None):
        path = Path(path) if path else self.path
        save_project(self.project, path)
        self.path = path
        self.dirty = False
        self.changed.emit()
