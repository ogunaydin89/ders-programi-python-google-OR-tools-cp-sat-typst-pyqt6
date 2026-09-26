# Ders Programı

*Türk ortaokul ve liseleri için ders dağıtım (haftalık ders programı) hazırlama programı.*

A desktop timetabler for Turkish middle and high schools (grades 5–12), built as a modern replacement for Alfabe Progmatic: the same lesson-distribution model (2+2+1 formats, closed hours, teacher preferences), plus a plain-Turkish explanation whenever no timetable is possible.

- **Solver:** Google OR-Tools CP-SAT
- **PDF output:** Typst
- **User interface:** PyQt6 (Turkish)
- **Built-in curricula (2025–2026):** Ortaokul, İmam Hatip Ortaokulu, Anadolu Lisesi, Anadolu İmam Hatip Lisesi, plus "Diğer / Özel" for anything else

The full design and every decision behind it are in [PLAN.md](PLAN.md).

## Status

Work in progress. Milestones (see PLAN.md, section 11):

- [x] M0: solver test run on a real school (anonymised benchmark)
- [x] M1: data model, curriculum files, validation, save/load
- [x] M2: solver core
- [x] M3: all rules (R1–R12), minimal-change re-solve
- [x] M4: "why no solution" explanations, quality report
- [x] M5: PDF output
- [x] M6: desktop application
- [x] M7: polish (see PLAN.md section 14 for known gaps)

## Install (Windows 11, Linux, macOS)

Requirements: **Python 3.10 or newer** (tested with 3.14) and **git**.

```bash
git clone https://codeberg.org/helinesca/ders-programi-python-google-OR-tools-cp-sat-typst-pyqt6.git
cd ders-programi-python-google-OR-tools-cp-sat-typst-pyqt6
python -m venv .venv
```

Windows:

```bat
.venv\Scripts\pip install -r requirements-dev.txt
.venv\Scripts\pip install -e .
.venv\Scripts\python -m pytest
```

Linux / macOS:

```bash
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/pip install -e .
.venv/bin/python -m pytest
```

### Start the application

Windows: `.venv\Scripts\python -m dersprogrami`  ·  Linux / macOS: `.venv/bin/python -m dersprogrami`

Command line (optional): `python -m dersprogrami solve okul.json --time 180`, `python -m dersprogrami check okul.json`,
`python -m dersprogrami pdf okul.json cikti_klasoru`.

### Check a new installation

`.venv\Scripts\python tools\selfcheck.py` (Windows) or `.venv/bin/python tools/selfcheck.py` (Linux / macOS) checks the
libraries, solves the benchmark school, verifies the result and writes the PDFs. It takes about a minute and ends with
*"her şey çalışıyor."* when everything works.

## Kısa kullanım (Türkçe)

1. **Okul:** okul adını ve okul türlerini sınıf aralıklarıyla girin (karma okullarda birden fazla satır).
2. **Öğretmenler:** öğretmenleri ekleyin; kısaltma otomatik önerilir. Kapalı gün ve saatleri tabloya tıklayarak işaretleyin.
3. **Sınıflar:** "Sınıf ekle" ile sınıfları oluşturun; günlük ders sayılarını onaylayın, seçmeli dersleri seçin.
4. **Ders Atama:** tabloda her derse öğretmen seçin; sağda öğretmen yükleri anında güncellenir.
5. **Kurallar:** kuralları Kapalı / Tercih / Zorunlu olarak ayarlayın.
6. **Çöz:** programı oluşturun. Program kurulamıyorsa nedeni Türkçe açıklanır.
7. **Program:** sınıf görünümünde bir derse, sonra yeşil bir hücreye tıklayarak elle düzeltin; dersleri kilitleyin.
8. **Yazdır:** çarşaf, öğretmen, sınıf ve A5 tebliğ-tebellüğ çıktılarını PDF olarak kaydedin.

**Windows note:** use `git clone` as shown. A ZIP downloaded from the website carries Windows' "downloaded from the internet" mark, and SmartScreen may then block its scripts; if you do use the ZIP, right-click it → Properties → *Unblock* before extracting.

**Gentoo / distributions that package PyQt6:** create the environment with `python -m venv --system-site-packages .venv` and install everything except PyQt6 with pip, so the system's PyQt6 is used; then run `pip install --no-deps -e .`.

## Privacy

Project files contain teachers' real names. Keep them outside this folder; they are never part of the repository. The benchmark in `tests/fixtures/` is anonymised (teachers T01–T17, no names).

## Licence

GPL-3.0-or-later (required by PyQt6). See [LICENSE](LICENSE). The official curriculum charts in `sources/` are public documents of the Turkish Ministry of National Education (MEB).
