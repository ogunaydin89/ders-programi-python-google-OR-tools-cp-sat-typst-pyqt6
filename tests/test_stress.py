"""Random schools: the app must never crash, every timetable must pass the checker,
and every 'no timetable' must come with an explanation."""
import random
from dataclasses import replace

import pytest

from dersprogrami import curriculum as cm
from dersprogrami.checker import check
from dersprogrami.explain import explain
from dersprogrami.model import Project, School, SchoolClass, SchoolPart, Teacher
from dersprogrami.solver import SolveOptions, solve
from dersprogrami.validate import errors

ELECTIVES = {
    "ortaokul": {5: [("Okuma Becerileri", 2), ("Ahlak ve Vatandaşlık Eğitimi", 1), ("Müzik", 2)],
                 6: [("Okuma Becerileri", 2), ("Ahlak ve Vatandaşlık Eğitimi", 1), ("Müzik", 2)],
                 7: [("Matematik ve Bilim Uygulamaları", 2), ("Ahlak ve Vatandaşlık Eğitimi", 1),
                     ("Görgü Kuralları ve Nezaket", 2)],
                 8: [("Temel Yaşam Becerileri", 2), ("Peygamberimizin Hayatı", 2), ("Görgü Kuralları ve Nezaket", 2)]},
    "imam_hatip_ortaokulu": {5: [("Robotik Kodlama", 1)], 6: [("Robotik Kodlama", 1)], 7: [("Müzik", 1)],
                             8: [("Müzik", 1), ("Halk Oyunları", 1)]},
}


def random_school(seed: int) -> Project:
    rng = random.Random(seed)
    cid = rng.choice(list(ELECTIVES))
    cur = cm.get(cid)
    classes, lessons = [], []
    for g in (5, 6, 7, 8):
        for sec in "ABC"[:rng.randint(0, 2)]:
            c = SchoolClass(f"C{len(classes) + 1:03d}", cid, g, sec, cur.default_daily_hours(g))
            classes.append(c)
            lessons += cm.build_class_lessons(cur, c, ELECTIVES[cid][g], existing_ids=[l.id for l in lessons])
    if not classes:
        c = SchoolClass("C001", cid, 5, "A", cur.default_daily_hours(5))
        classes.append(c)
        lessons += cm.build_class_lessons(cur, c, ELECTIVES[cid][5])
    # One teacher per lesson name, sometimes two; random closed days/hours (some schools become impossible).
    teachers, by_name = [], {}
    for l in lessons:
        key = l.name if l.kind != "rehberlik" else "REH"
        if key not in by_name or rng.random() < 0.15:
            t = Teacher(f"T{len(teachers) + 1:03d}", f"Öğretmen {len(teachers) + 1}", f"Ö.{len(teachers) + 1:03d}")
            closed = set()
            for d in range(1, 6):
                if rng.random() < 0.2:
                    closed |= {(d, q) for q in range(1, 9)}
                elif rng.random() < 0.3:
                    closed.add((d, rng.randint(1, 7)))
            t = replace(t, closed=frozenset(x for x in closed if x[1] <= 8))
            teachers.append(t)
            by_name.setdefault(key, []).append(t.id)
    lessons = [replace(l, teacher=rng.choice(by_name["REH" if l.kind == "rehberlik" else l.name])) for l in lessons]
    classes = [replace(c, rehber=next(l.teacher for l in lessons if l.class_id == c.id and l.kind == "rehberlik"))
               for c in classes]
    return Project(school=School(name="Rastgele", parts=(SchoolPart(cid, 5, 8),), max_periods=8),
                   teachers=tuple(teachers), classes=tuple(classes), lessons=tuple(lessons))


@pytest.mark.parametrize("seed", range(12))
def test_random_school(seed):
    p = random_school(seed)
    assert errors(p) == [], [i.message for i in errors(p)]
    r = solve(p, SolveOptions(time_limit=8, seed=seed))
    if r.placements:
        assert check(p, r.placements) == []
    elif r.status == "infeasible":
        e = explain(p, budget=30)
        assert e.status in ("precheck", "conflict", "structural", "unknown") and e.sentences
    else:
        assert r.status == "unknown"
