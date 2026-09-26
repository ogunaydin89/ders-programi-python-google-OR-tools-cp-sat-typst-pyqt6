"""Self-check for a new machine (e.g. the school's Windows 11 PC): run it after installing.

    Windows:        .venv\\Scripts\\python tools\\selfcheck.py
    Linux / macOS:  .venv/bin/python tools/selfcheck.py

It checks the libraries, solves the anonymised benchmark school in a separate process, verifies the
result independently and writes the four PDFs into a temporary folder. Takes about a minute.
"""
import platform
import sys
import tempfile
import time
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tests")]


def step(name, fn):
    t0 = time.time()
    try:
        detail = fn()
    except Exception as e:  # report every failure, never crash the check itself
        print(f"[HATA]  {name}: {type(e).__name__}: {e}")
        return False
    print(f"[TAMAM] {name} ({time.time() - t0:.1f} sn){' — ' + detail if detail else ''}")
    return True


def main():
    print(f"Python {platform.python_version()} · {platform.system()} {platform.release()} · {platform.machine()}")
    ok = True
    state = {}

    def libs():
        import ortools
        import typst  # noqa: F401
        from PyQt6.QtCore import QT_VERSION_STR
        return f"OR-Tools {ortools.__version__}, Qt {QT_VERSION_STR}"

    def installed():
        # The way the application is really started: no path tricks, from another folder.
        import os
        import subprocess
        env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
        out = subprocess.run([sys.executable, "-c", "import dersprogrami.ui.app; print('ok')"],
                             cwd=tempfile.gettempdir(), env=env, capture_output=True, text=True)
        if out.stdout.strip() != "ok":
            raise RuntimeError("paket kurulu değil; proje klasöründe 'pip install -e .' çalıştırın. " + out.stderr[-300:])
        return "python -m dersprogrami ile başlatılabilir"

    def solve():
        from dersprogrami.runner import SolverProcess
        from helpers import load_benchmark
        p = load_benchmark("strict")
        job = SolverProcess(p, time_limit=60)
        job.start()
        r = job.wait()
        if job.error:
            raise RuntimeError(job.error)
        if not r.placements:
            raise RuntimeError(f"çözüm bulunamadı ({r.status})")
        state["project"] = replace(p, placements=r.placements)
        return f"{r.status}, ilk program {r.first_solution_after:.1f} sn"

    def verify():
        from dersprogrami.checker import check, quality
        p = state["project"]
        problems = check(p, p.placements)
        if problems:
            raise RuntimeError(problems[0])
        q = quality(p, p.placements)
        return f"boş saat {q['gaps']}, tek derslik gün {q['one_lesson_days']}"

    def pdfs():
        from dersprogrami.pdf import export_all
        with tempfile.TemporaryDirectory(prefix="dersprogrami_") as out:   # deleted afterwards
            paths = export_all(state["project"], out)
            sizes = [x.stat().st_size for x in paths]
        if min(sizes) < 5000:
            raise RuntimeError("PDF dosyası beklenenden küçük")
        return f"{len(paths)} PDF oluşturuldu ve silindi"

    def gui():
        from PyQt6.QtWidgets import QApplication
        from dersprogrami.ui.app import MainWindow
        app = QApplication.instance() or QApplication([])
        w = MainWindow()
        w.state.dirty = False
        w.close()
        return "pencere açılıp kapandı"

    for name, fn in (("Kütüphaneler", libs), ("Program kurulumu", installed), ("Çözüm (ayrı süreçte)", solve), ("Bağımsız denetim", verify),
                     ("PDF çıktıları", pdfs), ("Program penceresi", gui)):
        ok = step(name, fn) and ok
        if not ok and name.startswith("Çözüm"):
            break
    print("\nSONUÇ:", "her şey çalışıyor." if ok else "sorun var; yukarıdaki [HATA] satırlarına bakın.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
