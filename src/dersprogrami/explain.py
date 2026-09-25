"""Why is there no timetable? Instant arithmetic pre-checks, then a minimal set of conflicting restrictions."""
import collections
import time
from dataclasses import dataclass, field

from ortools.sat.python import cp_model

from .model import DAY_NAMES, Project
from .shortform import normalise
from .solver import ModelBuilder

RULE_TEXT = {
    "R1": "günlük en fazla ders saati kuralı", "R2": "art arda en fazla ders kuralı",
    "R3": "boş saat sınırı", "R4": "blokların art arda günlere gelmemesi kuralı",
    "R5": "aynı öğretmenin bu sınıftaki derslerinin farklı günlere gelmesi kuralı",
    "R6": "ders grubunun farklı günlere gelmesi kuralı", "R7": "yükün günlere dengeli dağılması kuralı",
    "R9": "bir günde en az 2 saat ders kuralı", "R10": "ilk dersten son derse en fazla süre kuralı",
    "R11": "yasak/tercih edilen saatler kuralı", "R12": "blokların öğle arasıyla bölünmemesi kuralı",
}


@dataclass
class Explanation:
    status: str                      # "precheck" | "conflict" | "structural" | "feasible" | "unknown"
    sentences: list = field(default_factory=list)
    fixes: list = field(default_factory=list)


def _names(p: Project):
    classes = {c.id: c for c in p.classes}
    teachers = {t.id: t for t in p.teachers}
    lessons = {l.id: l for l in p.lessons}
    return classes, teachers, lessons


def precheck(p: Project) -> list[str]:
    """Cheap arithmetic checks that already prove there is no timetable."""
    classes, teachers, lessons = _names(p)
    P, D = p.school.max_periods, p.school.days
    out = []
    by_teacher = collections.defaultdict(list)
    for l in p.lessons:
        if l.teacher:
            by_teacher[l.teacher].append(l)

    def open_(t, d, q):
        return (d, q) not in t.closed

    for tid, ls in by_teacher.items():
        t = teachers.get(tid)
        if not t:
            continue
        load = sum(l.hours for l in ls)
        usable = sum(1 for d in range(1, D + 1) for q in range(1, P + 1)
                     if open_(t, d, q) and any(q <= classes[l.class_id].daily_hours[d - 1] for l in ls))
        if load > usable:
            out.append(f"{t.name}: haftalık {load} saat dersi var, ancak kullanılabilir (kapalı olmayan) saati {usable}.")
        if p.rule("R1").level == "mandatory":
            cap = p.rule("R1").value or 7
            room = sum(min(cap, sum(1 for q in range(1, P + 1) if open_(t, d, q))) for d in range(1, D + 1))
            if load > room:
                out.append(f"{t.name}: günde en fazla {cap} saat kuralıyla haftada en çok {room} saat verebilir; "
                           f"dersi {load} saat.")
        if p.rule("R5").level == "mandatory":
            per_class = collections.defaultdict(list)
            for l in ls:
                per_class[l.class_id].append(l)
            for cid, cl in per_class.items():
                if len({normalise(l.name) for l in cl}) > 1:
                    need = sum(len(l.format) for l in cl)
                    if need > D:
                        out.append(f"{t.name}: {classes[cid].label} sınıfındaki dersleri {need} ayrı gün gerektiriyor "
                                   f"(haftada {D} gün); 'farklı günler' kuralı zorunluyken bu mümkün değil.")
        for l in ls:
            c = classes[l.class_id]
            k = max(l.format)
            days_ok = 0
            for d in range(1, D + 1):
                h = c.daily_hours[d - 1]
                run = best = 0
                for q in range(1, h + 1):
                    run = run + 1 if open_(t, d, q) else 0
                    best = max(best, run)
                days_ok += best >= k
            if days_ok < len(l.format):
                fmt = "+".join(map(str, l.format))
                out.append(f"{c.label} {l.name} ({fmt}): {t.name} öğretmeninin {k} saatlik bloğa uygun boş zamanı "
                           f"yalnızca {days_ok} günde var, {len(l.format)} gün gerekiyor.")
    for c in p.classes:
        cl = [l for l in p.lessons if l.class_id == c.id and l.teacher in teachers]
        for d in range(1, D + 1):
            for q in range(1, c.daily_hours[d - 1] + 1):
                if not any(open_(teachers[l.teacher], d, q) for l in cl):
                    out.append(f"{c.label}: {DAY_NAMES[d - 1]} {q}. ders için bu saatte müsait öğretmeni olan ders yok.")
    return out


def _sentence(p: Project, key) -> str:
    classes, teachers, lessons = _names(p)
    kind = key[0]
    if kind == "closed":
        return f"{teachers[key[1]].name} öğretmeninin {DAY_NAMES[key[2] - 1]} günkü kapalı saatleri"
    if kind == "format":
        l = lessons[key[1]]
        return f"{classes[l.class_id].label} {l.name} dersinin {'+'.join(map(str, l.format))} yerleşim biçimi"
    if kind == "lock":
        l = lessons[key[1]]
        return f"{classes[l.class_id].label} {l.name} dersinin {DAY_NAMES[key[2] - 1]} {key[3]}. derse kilitlenmesi"
    rule, who = key[1], key[2:]
    text = RULE_TEXT.get(rule, rule)
    if who and who[0] in teachers:
        extra = f" ({classes[who[1]].label})" if len(who) > 1 and who[1] in classes else ""
        return f"{teachers[who[0]].name}: {text}{extra}"
    if who and who[0] in lessons:
        l = lessons[who[0]]
        return f"{classes[l.class_id].label} {l.name}: {text}"
    return f"'{who[0]}' grubu: {text}" if who else text


def _solve(b: ModelBuilder, keys, budget, workers=8):
    b.m.ClearAssumptions()
    b.m.AddAssumptions([b.switches[k] for k in keys])
    s = cp_model.CpSolver()
    s.parameters.max_time_in_seconds = max(1.0, budget)
    s.parameters.num_workers = workers
    s.parameters.linearization_level = 2
    return s, s.Solve(b.m)


def explain(p: Project, budget: float = 60.0) -> Explanation:
    """Find why no timetable exists. Always returns within roughly `budget` seconds."""
    pre = precheck(p)
    if pre:
        return Explanation("precheck", pre)
    t0 = time.time()
    b = ModelBuilder(p, diagnose=True)
    b.m.ClearObjective()
    keys = list(b.switches)
    left = lambda: budget - (time.time() - t0)
    s, st = _solve(b, keys, left() * 0.4)
    if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return Explanation("feasible", ["Kısıtlamalar birlikte sağlanabiliyor; çözücüye daha fazla süre verin."])
    if st != cp_model.INFEASIBLE:
        return Explanation("unknown", ["Süre içinde nedeni bulunamadı; daha uzun bir süreyle tekrar deneyin."])
    index = {b.switches[k].Index(): k for k in keys}
    core = [index[i] for i in s.SufficientAssumptionsForInfeasibility() if i in index]
    if not core:
        return Explanation("structural", [
            "Hiçbir kapalı saat veya zorunlu kural olmadan bile program kurulamıyor: öğretmen atamaları, "
            "yerleşim biçimleri ve sınıfların günlük ders sayıları birbirine uymuyor."])
    # Shrink to a minimal conflicting set: drop every switch the conflict does not need.
    i = 0
    while i < len(core) and left() > 0:
        trial = core[:i] + core[i + 1:]
        _, st = _solve(b, trial, min(10.0, left()))
        if st == cp_model.INFEASIBLE:
            core = trial
        else:
            i += 1
    sentences = _grouped(p, core)
    fixes = []
    for k in core:
        if left() <= 0:
            break
        _, st = _solve(b, [x for x in keys if x != k], min(10.0, left()))
        if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            fixes.append(f"{_sentence(p, k)} gevşetilirse program kurulabiliyor.")
    if not fixes and left() > 0:
        fixes.append("Tek bir kısıtlamayı gevşetmek yetmiyor; yukarıdakilerden birkaçını birlikte gevşetmek gerekiyor.")
    head = "Şu kısıtlamalar birlikte sağlanamıyor:" if len(core) > 1 else "Şu kısıtlama sağlanamıyor:"
    return Explanation("conflict", [head] + sentences, fixes)


def _grouped(p: Project, core) -> list[str]:
    """One sentence per teacher for closed days; other restrictions one sentence each."""
    _, teachers, _ = _names(p)
    closed = collections.defaultdict(list)
    out = []
    for k in core:
        if k[0] == "closed":
            closed[k[1]].append(k[2])
        else:
            out.append(_sentence(p, k))
    for tid, days in closed.items():
        names = ", ".join(DAY_NAMES[d - 1] for d in sorted(days))
        out.insert(0, f"{teachers[tid].name}: {names} {'günündeki' if len(days) == 1 else 'günlerindeki'} kapalı saatler")
    return out
