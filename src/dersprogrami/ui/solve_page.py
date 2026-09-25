"""Çöz: validation, solving in a separate process, progress, quality report or explanation."""
from dataclasses import replace

from PyQt6.QtCore import QThread, QTimer, pyqtSignal
from PyQt6.QtWidgets import (QCheckBox, QHBoxLayout, QLabel, QProgressBar, QPushButton, QSpinBox, QTextEdit,
                             QVBoxLayout, QWidget)

from ..checker import check, quality
from ..explain import explain
from ..runner import SolverProcess
from ..validate import validate
from .widgets import heading

QUALITY_NAMES = {"gaps": "Öğretmen boş saatleri", "one_lesson_days": "Tek derslik günler",
                 "neighbouring_days": "Art arda günlere gelen bloklar", "lunch_split": "Öğle arasıyla bölünen dersler",
                 "same_teacher_class_day": "Aynı öğretmen-sınıf dersleri aynı günde",
                 "peak_sum": "Öğretmenlerin en yoğun günlerinin toplamı"}


class ExplainThread(QThread):
    done = pyqtSignal(object)

    def __init__(self, project):
        super().__init__()
        self.project = project

    def run(self):
        try:
            self.done.emit(explain(self.project, budget=90))
        except Exception as e:           # never let the explanation crash the window
            self.done.emit(e)


class SolvePage(QWidget):
    solved = pyqtSignal()

    def __init__(self, state):
        super().__init__()
        self.state = state
        self.job = None
        self.explainer = None
        lay = QVBoxLayout(self)
        lay.addWidget(heading("Programı oluştur"))
        row = QHBoxLayout()
        row.addWidget(QLabel("Arama süresi:"))
        self.minutes = QSpinBox(minimum=1, maximum=120, value=3, suffix=" dk")
        row.addWidget(self.minutes)
        self.keep = QCheckBox("Mevcut programı mümkün olduğunca koru (dönem ortası değişiklik)")
        row.addWidget(self.keep)
        row.addStretch()
        lay.addLayout(row)
        row2 = QHBoxLayout()
        self.go = QPushButton("Çöz")
        self.go.clicked.connect(self.start)
        self.stop = QPushButton("Durdur (en iyisini kullan)")
        self.stop.clicked.connect(self.request_stop)
        self.stop.setEnabled(False)
        row2.addWidget(self.go)
        row2.addWidget(self.stop)
        row2.addStretch()
        lay.addLayout(row2)
        self.bar = QProgressBar()
        self.bar.setTextVisible(True)
        lay.addWidget(self.bar)
        self.status = QLabel("")
        lay.addWidget(self.status)
        self.report = QTextEdit()
        self.report.setReadOnly(True)
        lay.addWidget(self.report, 1)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.poll)

    def busy(self):
        return self.job is not None or (self.explainer is not None and self.explainer.isRunning())

    def start(self):
        p = self.state.project
        issues = validate(p)
        errs = [i.message for i in issues if i.level == "error"]
        warns = [i.message for i in issues if i.level == "warning"]
        if errs:
            self.report.setHtml("<h4>Çözmeden önce düzeltilmesi gerekenler</h4><ul>" +
                                "".join(f"<li>{e}</li>" for e in errs) + "</ul>" +
                                ("<h4>Uyarılar</h4><ul>" + "".join(f"<li>{w}</li>" for w in warns) + "</ul>"
                                 if warns else ""))
            self.status.setText("Veride hata var; program oluşturulmadı.")
            return
        self.report.setHtml("<h4>Uyarılar</h4><ul>" + "".join(f"<li>{w}</li>" for w in warns) + "</ul>"
                            if warns else "")
        self.job = SolverProcess(p, time_limit=self.minutes.value() * 60, minimal_change=self.keep.isChecked())
        self.job.start()
        self.project_at_start = p
        self.best = None
        self.go.setEnabled(False)
        self.stop.setEnabled(True)
        self.bar.setRange(0, self.minutes.value() * 60)
        self.status.setText("Aranıyor…")
        self.timer.start(300)

    def request_stop(self):
        if self.job:
            self.job.request_stop()
            self.status.setText("Durduruluyor, en iyi program alınıyor…")

    def poll(self):
        job = self.job
        if not job:
            return
        import time
        elapsed = int(time.time() - job.started)
        self.bar.setValue(min(elapsed, self.bar.maximum()))
        self.bar.setFormat(f"{elapsed} sn")
        for t, obj, bound, n in job.poll():
            gap = f", en fazla %{100 * (obj - bound) / obj:.0f} daha iyisi olabilir" if obj > 0 else ""
            self.status.setText(f"{t:.0f} sn: {n}. program bulundu (puan {obj:.0f}{gap}).")
        if job.finished:
            self.timer.stop()
            self.job = None
            self.go.setEnabled(True)
            self.stop.setEnabled(False)
            self.finish(job)

    def finish(self, job):
        p = self.project_at_start
        if job.error:
            self.status.setText("Çözücü hatası.")
            self.report.append(f"<pre>{job.error}</pre>")
            return
        r = job.result
        if not r.placements:
            if r.status == "infeasible":
                self.status.setText("Bu kısıtlarla program kurulamıyor. Nedeni aranıyor…")
                self.go.setEnabled(False)
                self.explainer = ExplainThread(p)
                self.explainer.done.connect(self.show_explanation)
                self.explainer.start()
            else:
                self.status.setText("Süre içinde program bulunamadı. Süreyi artırıp tekrar deneyin.")
            return
        problems = check(p, r.placements)
        if problems:
            self.status.setText("Hata: bulunan program bağımsız denetimden geçemedi; kullanılmadı.")
            self.report.append("<ul>" + "".join(f"<li>{x}</li>" for x in problems) + "</ul>")
            return
        if self.state.project != p:
            self.status.setText("Çözüm sürerken veriler değişti; lütfen yeniden çözün.")
            return
        self.state.apply(replace(p, placements=r.placements), "Program oluştur")
        q = quality(p, r.placements)
        state = {"optimal": "en iyi program (kanıtlanmış)", "feasible": "geçerli program"}.get(r.status, r.status)
        extra = ""
        if r.bound is not None and r.objective:
            extra = f" En fazla %{100 * (r.objective - r.bound) / r.objective:.0f} daha iyisi olabilir."
        self.status.setText(f"✔ {state} bulundu ({r.elapsed:.0f} sn).{extra}")
        html = "<h4>Kalite raporu</h4><table>" + "".join(
            f"<tr><td>{QUALITY_NAMES[k]}</td><td><b>{v}</b></td></tr>" for k, v in q.items() if k in QUALITY_NAMES)
        html += "</table>"
        for key, title in (("gaps", "Boş saatler"), ("one_lesson_days", "Tek derslik günler")):
            if q["details"].get(key):
                html += f"<h5>{title}</h5><ul>" + "".join(f"<li>{x}</li>" for x in q["details"][key]) + "</ul>"
        self.report.setHtml(html)
        self.solved.emit()

    def show_explanation(self, e):
        self.go.setEnabled(True)
        if isinstance(e, Exception):
            self.status.setText("Neden bulunurken hata oluştu.")
            self.report.setHtml(f"<pre>{e}</pre>")
            return
        self.status.setText("Program kurulamıyor.")
        html = "<h4>Neden?</h4><ul>" + "".join(f"<li>{s}</li>" for s in e.sentences) + "</ul>"
        if e.fixes:
            html += "<h4>Öneri</h4><ul>" + "".join(f"<li>{f}</li>" for f in e.fixes) + "</ul>"
        self.report.setHtml(html)
