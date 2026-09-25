"""Test helpers: the anonymised benchmark as a Project, and small sample schools."""
import json
from dataclasses import replace
from pathlib import Path

from dersprogrami import curriculum as cm
from dersprogrami.model import Lesson, Placement, Project, School, SchoolClass, SchoolPart, Teacher
from dersprogrami.shortform import lesson_short

BENCH = Path(__file__).parent / "fixtures" / "benchmark_anon.json"


def load_benchmark(variant: str = "strict", with_placements: bool = False) -> Project:
    d = json.loads(BENCH.read_text(encoding="utf-8"))
    opened = {t: {tuple(s) for s in slots} for t, slots in d["variants"]["progmatic"]["open"].items()} \
        if variant == "progmatic" else {}
    teachers = tuple(Teacher(t["id"], t["id"], t["id"], t["main_subject_in_timetable"],
                             frozenset(tuple(s) for s in t["closed"]) - opened.get(t["id"], set()))
                     for t in d["teachers"])
    rehber = {l["class"]: l["teacher"] for l in d["lessons"] if l["subject"].startswith("REHBERLİK")}
    classes = tuple(SchoolClass(c["id"], "ortaokul", c["grade"], c["section"], tuple(c["daily_hours"]),
                                rehber[c["id"]], elective_rules=False) for c in d["classes"])
    lessons = tuple(Lesson(l["id"], l["class"], l["subject"], lesson_short(l["subject"], l["elective"]), l["hours"],
                           tuple(l["format"]), l["teacher"],
                           "elective" if l["elective"] else
                           "rehberlik" if l["subject"].startswith("REHBERLİK") else "compulsory")
                    for l in d["lessons"])
    school = School(name="Örnek Ortaokulu", parts=(SchoolPart("ortaokul", 5, 8),), days=5, max_periods=7)
    placements = ()
    if with_placements:
        placements = tuple(Placement(p["lesson"], p["day"], p["period"], 1) for p in d["progmatic_placement"])
    return Project(school=school, teachers=teachers, classes=classes, lessons=lessons, placements=placements)


def small_school() -> Project:
    """One ortaokul 5-A class with every lesson assigned to a teacher."""
    cur = cm.get("ortaokul")
    teachers = tuple(Teacher(f"T{i:03d}", f"Öğretmen {i}", f"Ö.{i:02d}") for i in range(1, 14))
    cls = SchoolClass("C001", "ortaokul", 5, "A", cur.default_daily_hours(5), rehber="T001")
    lessons = cm.build_class_lessons(cur, cls, electives=[("Okuma Becerileri", 2), ("Ahlak ve Vatandaşlık Eğitimi", 1),
                                                          ("Müzik", 2)])
    lessons = tuple(l if l.teacher else replace(l, teacher=f"T{(i % 13) + 1:03d}") for i, l in enumerate(lessons))
    return Project(school=School(name="Deneme", parts=(SchoolPart("ortaokul", 5, 8),)),
                   teachers=teachers, classes=(cls,), lessons=lessons)
