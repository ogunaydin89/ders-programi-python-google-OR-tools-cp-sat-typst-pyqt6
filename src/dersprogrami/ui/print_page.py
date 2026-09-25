"""Yazdır: write the PDFs to a folder the user chooses."""
from dataclasses import replace
from pathlib import Path

from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout,
                             QWidget)

from ..pdf import OUTPUTS, PrintRefused, export_all
from .widgets import heading, warn

DESCRIPTIONS = {
    "carsaf": "Çarşaf: bütün öğretmenlerin haftalık programı (A4 yatay)",
    "teachers": "Öğretmen programları (her öğretmene bir A4 sayfa)",
    "classes": "Sınıf programları (her sınıfa bir A4 sayfa, ders listesiyle)",
    "handouts": "Tebliğ-tebellüğ: A4'e iki kopya A5 öğretmen programı (üst kopya okulda kalır)",
}


class PrintPage(QWidget):
    def __init__(self, state):
        super().__init__()
        self.state = state
        lay = QVBoxLayout(self)
        lay.addWidget(heading("Çıktılar (PDF)"))
        for kind, name in OUTPUTS.items():
            lay.addWidget(QLabel(f"• {DESCRIPTIONS[kind]} — <i>{name}</i>"))
        form = QFormLayout()
        self.valid_from = QLineEdit()
        self.valid_from.setPlaceholderText("ör. 29.09.2026")
        self.valid_from.editingFinished.connect(self.commit)
        form.addRow("Geçerlilik tarihi", self.valid_from)
        row = QHBoxLayout()
        self.folder = QLineEdit()
        pick = QPushButton("Seç…")
        pick.clicked.connect(self.pick)
        row.addWidget(self.folder)
        row.addWidget(pick)
        form.addRow("Kayıt klasörü", row)
        lay.addLayout(form)
        go = QPushButton("PDF'leri oluştur")
        go.clicked.connect(self.export)
        lay.addWidget(go)
        self.result = QLabel()
        self.result.setWordWrap(True)
        lay.addWidget(self.result)
        lay.addStretch()
        state.changed.connect(self.refresh)
        self.refresh()

    def refresh(self):
        self.valid_from.setText(self.state.project.valid_from)
        if not self.folder.text() and self.state.path:
            self.folder.setText(str(Path(self.state.path).parent / "ders_programi_pdf"))

    def commit(self):
        p = self.state.project
        self.state.apply(replace(p, valid_from=self.valid_from.text().strip()), "Geçerlilik tarihi")

    def pick(self):
        d = QFileDialog.getExistingDirectory(self, "PDF'lerin kaydedileceği klasör", self.folder.text())
        if d:
            self.folder.setText(d)

    def export(self):
        if not self.folder.text().strip():
            return warn(self, "Önce bir kayıt klasörü seçin.")
        try:
            paths = export_all(self.state.project, self.folder.text().strip())
        except PrintRefused as e:
            return warn(self, str(e))
        except OSError as e:
            return warn(self, f"PDF'ler kaydedilemedi: {e.strerror}")
        self.result.setText("Kaydedildi:\n" + "\n".join(str(x) for x in paths))
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(paths[0].parent)))
