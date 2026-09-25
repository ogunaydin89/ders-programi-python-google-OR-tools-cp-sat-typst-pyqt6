"""Independent timetable checker.

Deliberately simple and written without reusing anything from solver.py: every timetable is re-verified
here before it is shown or printed. check() lists broken hard rules; quality() measures preferences.
"""
import collections
import math

from .model import DAY_NAMES, Project
from .shortform import normalise


def _grid(project: Project, placements):
    """lesson -> {day: sorted periods}"""
    g = collections.defaultdict(lambda: collections.defaultdict(list))
    for pl in placements:
        for q in range(pl.start, pl.start + pl.length):
            g[pl.lesson][pl.day].append(q)
    for days in g.values():
        for d in days:
            days[d].sort()
    return g


def _teacher_days(project: Project, grid):
    """teacher -> {day: sorted periods}"""
    lessons = {l.id: l for l in project.lessons}
    td = collections.defaultdict(lambda: collections.defaultdict(list))
    for lid, days in grid.items():
        t = lessons[lid].teacher
        for d, qs in days.items():
            td[t][d].extend(qs)
    for days in td.values():
        for d in days:
            days[d].sort()
    return td


def _runs(qs):
    runs, start = [], None
    for i, q in enumerate(qs):
        if start is None:
            start = q
        if i == len(qs) - 1 or qs[i + 1] != q + 1:
            runs.append((start, q))
            start = None
    return runs


def check(project: Project, placements) -> list[str]:
    """Every broken structural or Mandatory rule, as Turkish sentences. Empty list = valid timetable."""
    p = project
    out = []
    lessons = {l.id: l for l in p.lessons}
    classes = {c.id: c for c in p.classes}
    teachers = {t.id: t for t in p.teachers}
    day = lambda d: DAY_NAMES[d - 1] if 1 <= d <= len(DAY_NAMES) else f"gün {d}"

    def lname(lid):
        l = lessons[lid]
        return f"{classes[l.class_id].label} {l.name}"

    for pl in placements:
        if pl.lesson not in lessons:
            out.append(f"Bilinmeyen ders yerleştirilmiş: {pl.lesson}.")
    placements = [pl for pl in placements if pl.lesson in lessons]
    grid = _grid(p, placements)

    # Lessons: hours, format, one block per day, inside the class day.
    for l in p.lessons:
        days = grid.get(l.id, {})
        blocks = []
        for d, qs in days.items():
            if len(set(qs)) != len(qs):
                out.append(f"{lname(l.id)}: {day(d)} aynı saate iki kez yerleştirilmiş.")
            runs = _runs(sorted(set(qs)))
            if len(runs) > 1:
                out.append(f"{lname(l.id)}: {day(d)} günü birden fazla parçaya bölünmüş.")
            blocks += [b - a + 1 for a, b in runs]
        allowed = {tuple(l.format)}
        if p.rule("R8").level != "off":
            allowed |= {tuple(a) for a in l.alternatives}
        if tuple(sorted(blocks, reverse=True)) not in allowed:
            got = "+".join(map(str, sorted(blocks, reverse=True))) or "hiç"
            out.append(f"{lname(l.id)}: yerleşim {got}, olması gereken {'+'.join(map(str, l.format))}.")

    # Classes: every period 1..h exactly once, nothing after the end of the day.
    cells = collections.Counter()
    for lid, days in grid.items():
        for d, qs in days.items():
            for q in qs:
                cells[(lessons[lid].class_id, d, q)] += 1
    for c in p.classes:
        for d in range(1, p.school.days + 1):
            h = c.daily_hours[d - 1]
            for q in range(1, p.school.max_periods + 1):
                n = cells[(c.id, d, q)]
                if q <= h and n != 1:
                    out.append(f"{c.label}: {day(d)} {q}. ders {'boş' if n == 0 else f'{n} derse verilmiş'}.")
                if q > h and n:
                    out.append(f"{c.label}: {day(d)} {q}. derste ders var ama gün {h} ders.")

    # Same lesson name twice in a class: still different days.
    same = collections.defaultdict(list)
    for l in p.lessons:
        same[(l.class_id, normalise(l.name))].append(l.id)
    for lids in same.values():
        if len(lids) > 1:
            for d in range(1, p.school.days + 1):
                if sum(1 for lid in lids if grid.get(lid, {}).get(d)) > 1:
                    out.append(f"{lname(lids[0])}: aynı ders {day(d)} günü iki kez var.")

    # Teachers: no double booking, closed hours respected.
    td = _teacher_days(p, grid)
    for tid, days in td.items():
        t = teachers.get(tid)
        name = t.name if t else str(tid)
        for d, qs in days.items():
            for q in {q for q in qs if qs.count(q) > 1}:
                out.append(f"{name}: {day(d)} {q}. derste iki sınıfta birden.")
            if t:
                for q in sorted(set(qs)):
                    if (d, q) in t.closed:
                        out.append(f"{name}: kapalı saat kullanılmış ({day(d)} {q}. ders).")

    # Locks.
    have = {(pl.lesson, pl.day, pl.start, pl.length) for pl in placements}
    for pl in p.placements:
        if pl.locked and (pl.lesson, pl.day, pl.start, pl.length) not in have:
            out.append(f"{lname(pl.lesson)}: kilitli yerleşim ({day(pl.day)} {pl.start}. ders) korunmamış.")

    out += _mandatory(p, grid, td, lname, day)
    return out


def _mandatory(p, grid, td, lname, day):
    out = []
    lessons = {l.id: l for l in p.lessons}
    teachers = {t.id: t for t in p.teachers}
    lv = lambda r: p.rule(r).level == "mandatory"
    val = lambda r, d: d if p.rule(r).value is None else p.rule(r).value
    load = collections.Counter()
    count = collections.Counter()
    shortest = {}
    for l in p.lessons:
        load[l.teacher] += l.hours
        count[l.teacher] += 1
        shortest[l.teacher] = min(l.format)
    r9_exempt = {t for t in load if load[t] < val("R9", 2) or (count[t] == 1 and shortest[t] < val("R9", 2))}
    for tid, days in td.items():
        name = teachers[tid].name if tid in teachers else str(tid)
        gaps_week = 0
        for d, qs in days.items():
            qs = sorted(set(qs))
            if not qs:
                continue
            gaps = qs[-1] - qs[0] + 1 - len(qs)
            gaps_week += gaps
            if lv("R1") and len(qs) > val("R1", 7):
                out.append(f"{name}: {day(d)} {len(qs)} saat ders (en fazla {val('R1', 7)}).")
            if lv("R2") and max(b - a + 1 for a, b in _runs(qs)) > val("R2", 4):
                out.append(f"{name}: {day(d)} art arda {val('R2', 4)} saatten fazla ders.")
            if lv("R9") and tid not in r9_exempt and len(qs) < val("R9", 2):
                out.append(f"{name}: {day(d)} yalnızca {len(qs)} saat ders için okula geliyor.")
            if lv("R10") and qs[-1] - qs[0] + 1 > val("R10", 6):
                out.append(f"{name}: {day(d)} ilk dersten son derse {qs[-1] - qs[0] + 1} saat.")
        if lv("R3") and gaps_week > val("R3", 0):
            out.append(f"{name}: haftada {gaps_week} boş saat (en fazla {val('R3', 0)}).")
        if lv("R7"):
            t = teachers.get(tid)
            open_days = [d for d in range(1, p.school.days + 1)
                         if not t or any((d, q) not in t.closed for q in range(1, p.school.max_periods + 1))]
            cap = math.ceil(load[tid] / max(1, len(open_days))) + 1
            for d, qs in days.items():
                if len(set(qs)) > cap:
                    out.append(f"{name}: {day(d)} {len(set(qs))} saat, günlere dengesiz dağılmış.")
    lunch = p.school.bell.lunch_after
    for l in p.lessons:
        days = sorted(grid.get(l.id, {}))
        if lv("R4") and len(l.format) > 1 and any(b - a == 1 for a, b in zip(days, days[1:])):
            out.append(f"{lname(l.id)}: blokları art arda günlerde.")
        if lv("R12") and lunch:
            for d in days:
                qs = grid[l.id][d]
                if lunch in qs and lunch + 1 in qs:
                    out.append(f"{lname(l.id)}: {day(d)} öğle arasıyla bölünmüş.")
        if lv("R11"):
            bad = set(l.forbidden_periods)
            if l.preferred_periods:
                bad |= set(range(1, p.school.max_periods + 1)) - set(l.preferred_periods)
            for d in days:
                for q in grid[l.id][d]:
                    if q in bad:
                        out.append(f"{lname(l.id)}: {day(d)} {q}. ders bu ders için yasak.")
    if lv("R5"):
        groups = collections.defaultdict(list)
        for l in p.lessons:
            groups[(l.teacher, l.class_id)].append(l)
        for ls in groups.values():
            if len({normalise(l.name) for l in ls}) > 1:
                for d in range(1, p.school.days + 1):
                    names = {normalise(l.name) for l in ls if grid.get(l.id, {}).get(d)}
                    if len(names) > 1:
                        out.append(f"{lname(ls[0].id)}: aynı öğretmenin bu sınıftaki dersleri {day(d)} aynı günde.")
    if lv("R6"):
        groups = collections.defaultdict(list)
        for l in p.lessons:
            if l.lesson_group:
                groups[l.lesson_group].append(l)
        for g, ls in groups.items():
            for d in range(1, p.school.days + 1):
                if sum(1 for l in ls if grid.get(l.id, {}).get(d)) > 1:
                    out.append(f"'{g}' ders grubundan iki ders {day(d)} aynı günde.")
    return out


def quality(project: Project, placements) -> dict:
    """Preference measures, with per-teacher/lesson details for the quality report."""
    p = project
    lessons = {l.id: l for l in p.lessons}
    classes = {c.id: c for c in p.classes}
    teachers = {t.id: t for t in p.teachers}
    grid = _grid(p, placements)
    td = _teacher_days(p, grid)
    lunch = p.school.bell.lunch_after
    details = collections.defaultdict(list)
    gaps = lone = 0
    peak = 0
    for tid, days in td.items():
        name = teachers[tid].name if tid in teachers else str(tid)
        g_t = 0
        for d, qs in days.items():
            qs = sorted(set(qs))
            g = qs[-1] - qs[0] + 1 - len(qs)
            g_t += g
            if len(qs) == 1:
                lone += 1
                details["one_lesson_days"].append(f"{name}: {DAY_NAMES[d - 1]} tek ders")
        if g_t:
            details["gaps"].append(f"{name}: {g_t} boş saat")
        gaps += g_t
        peak += max(len(set(qs)) for qs in days.values())
    neighbour = lunch_split = 0
    for lid, days in grid.items():
        l = lessons[lid]
        label = f"{classes[l.class_id].label} {l.name}"
        ds = sorted(days)
        n = sum(1 for a, b in zip(ds, ds[1:]) if b - a == 1)
        if n:
            neighbour += n
            details["neighbouring_days"].append(label)
        for d in ds:
            if lunch and lunch in days[d] and lunch + 1 in days[d]:
                lunch_split += 1
                details["lunch_split"].append(f"{label}: {DAY_NAMES[d - 1]}")
    sameday = 0
    groups = collections.defaultdict(list)
    for l in p.lessons:
        groups[(l.teacher, l.class_id)].append(l)
    for ls in groups.values():
        for d in range(1, p.school.days + 1):
            names = {normalise(l.name) for l in ls if grid.get(l.id, {}).get(d)}
            if len(names) > 1:
                sameday += len(names) - 1
    return {"gaps": gaps, "one_lesson_days": lone, "neighbouring_days": neighbour, "lunch_split": lunch_split,
            "same_teacher_class_day": sameday, "peak_sum": peak, "details": dict(details)}
