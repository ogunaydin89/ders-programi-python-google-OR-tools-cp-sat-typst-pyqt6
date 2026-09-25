"""PDF output with Typst: master timetable (çarşaf), teacher, class and A5 handout printouts.

Only a timetable that passes the independent checker is ever printed.
"""
import json
from pathlib import Path

import typst

from ..checker import check
from ..model import DAY_NAMES, Project

TEMPLATES = Path(__file__).resolve().parent / "templates"
OUTPUTS = {
    "carsaf": "carsaf.pdf",
    "teachers": "ogretmen_programlari.pdf",
    "classes": "sinif_programlari.pdf",
    "handouts": "ogretmen_teblig_A5.pdf",
}


class PrintRefused(Exception):
    """The timetable is incomplete or failed the checker; nothing is printed."""


def build_data(p: Project) -> dict:
    lessons = {l.id: l for l in p.lessons}
    classes = {c.id: c for c in p.classes}
    teachers = {t.id: t for t in p.teachers}
    D, P = p.school.days, p.school.max_periods
    tcells = {t.id: [None] * (D * P) for t in p.teachers}
    ccells = {c.id: [None] * (D * P) for c in p.classes}
    for pl in p.placements:
        l = lessons[pl.lesson]
        c = classes[l.class_id]
        t = teachers.get(l.teacher)
        for q in range(pl.start, pl.start + pl.length):
            i = (pl.day - 1) * P + (q - 1)
            if t:
                tcells[t.id][i] = {"cls": c.label, "short": l.short, "name": l.name}
            ccells[c.id][i] = {"name": l.name, "short": l.short,
                               "teacher_short": t.short if t else "", "teacher": t.name if t else ""}
    load = {t.id: p.teacher_load(t.id) for t in p.teachers}
    periods = [list(x) for x in p.school.bell.periods[:P]]
    periods += [["", ""]] * (P - len(periods))
    return {
        "school": p.school.name,
        "headmaster": p.school.headmaster,
        "headmaster_title": "Okul Müdürü",
        "valid_from": p.valid_from,
        "days": list(DAY_NAMES[:D]),
        "periods": periods,
        "teachers": [{"name": t.name, "short": t.short, "total": load[t.id], "cells": tcells[t.id]}
                     for t in p.teachers if load[t.id] > 0],
        "classes": [{"label": c.label, "cells": ccells[c.id],
                     "lessons": [{"name": l.name, "hours": l.hours,
                                  "teacher": teachers[l.teacher].name if l.teacher in teachers else ""}
                                 for l in p.lessons_of_class(c.id)]}
                    for c in sorted(p.classes, key=lambda c: (c.grade, c.section))],
    }


def render(p: Project, kind: str) -> bytes:
    """One printout as PDF bytes. Raises PrintRefused if the timetable is not complete and valid."""
    if not p.placements:
        raise PrintRefused("Henüz ders programı oluşturulmamış.")
    problems = check(p, p.placements)
    if problems:
        raise PrintRefused("Program denetimden geçmedi; yazdırılmadı:\n" + "\n".join(problems[:10]))
    data = json.dumps(build_data(p), ensure_ascii=False)
    return typst.compile(str(TEMPLATES / f"{kind}.typ"), root=str(TEMPLATES), sys_inputs={"data": data},
                         ignore_system_fonts=True)


def export_all(p: Project, outdir) -> list[Path]:
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    paths = []
    for kind, name in OUTPUTS.items():
        path = outdir / name
        path.write_bytes(render(p, kind))
        paths.append(path)
    return paths
