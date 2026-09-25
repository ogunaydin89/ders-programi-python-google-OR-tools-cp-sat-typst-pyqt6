"""Development tool: print the chart pages of the official PDFs as text, to compare with data/*.json.

Needs `pdftotext` (poppler). Not used by the application itself.
Usage: python tools/extract_curricula.py
"""
import subprocess
from pathlib import Path

SOURCES = Path(__file__).resolve().parent.parent / "sources"
PAGES = {
    "2025-05_TTK-04_ilkogretim-ortaokul_cizelge.pdf": (2, 3),
    "2025-10_TTK-103_imam-hatip-ortaokulu_cizelge.pdf": (2, 2),
    "2025-05_TTK-05_anadolu-fen-sosyal-lisesi_cizelge.pdf": (2, 2),
    "2025-07_TTK-26_anadolu-imam-hatip-lisesi_cizelge.pdf": (2, 3),
}

for name, (first, last) in PAGES.items():
    print(f"\n===== {name} (pages {first}-{last}) =====")
    out = subprocess.run(["pdftotext", "-layout", "-f", str(first), "-l", str(last), str(SOURCES / name), "-"],
                         capture_output=True, text=True, check=True).stdout
    print("\n".join(line for line in out.splitlines() if line.strip()))
