"""Checks before solving. Errors block solving; warnings are shown but do not block."""
from dataclasses import dataclass

from . import curriculum as cur_mod
from .model import Project
from .shortform import duplicates, normalise


@dataclass(frozen=True)
class Issue:
    level: str        # "error" or "warning"
    message: str      # Turkish, shown to the user


def _err(msg):
    return Issue("error", msg)


def _warn(msg):
    return Issue("warning", msg)


def validate(p: Project) -> list[Issue]:
    issues: list[Issue] = []
    s = p.school
    teacher_ids = {t.id for t in p.teachers}
    class_ids = {c.id for c in p.classes}

    # School and its parts.
    if not 1 <= s.days <= 7:
        issues.append(_err("Haftalık gün sayısı 1 ile 7 arasında olmalı."))
    if not 1 <= s.max_periods <= 12:
        issues.append(_err("Günlük en fazla ders sayısı 1 ile 12 arasında olmalı."))
    if len(s.bell.periods) < s.max_periods:
        issues.append(_warn("Zil çizelgesinde her ders saati için başlangıç ve bitiş saati girilmemiş."))
    covered = {}
    for part in s.parts:
        if part.curriculum not in cur_mod.load_all():
            issues.append(_err(f"Bilinmeyen okul türü: {part.curriculum}."))
            continue
        if part.grade_from > part.grade_to or part.grade_from < 5 or part.grade_to > 12:
            issues.append(_err(f"Okul türü için sınıf aralığı geçersiz: {part.grade_from}–{part.grade_to}."))
        for g in range(part.grade_from, part.grade_to + 1):
            if g in covered:
                issues.append(_err(f"{g}. sınıf birden fazla okul türünde tanımlanmış."))
            covered[g] = part.curriculum

    # Teachers.
    for owners in duplicates((t.name, t.short) for t in p.teachers).values():
        issues.append(_err(f"Aynı kısaltma birden fazla öğretmende kullanılmış: {', '.join(owners)}."))
    for t in p.teachers:
        if not t.short.strip():
            issues.append(_err(f"{t.name}: kısaltma girilmemiş."))
        bad = [x for x in t.closed if not (1 <= x[0] <= s.days and 1 <= x[1] <= s.max_periods)]
        if bad:
            issues.append(_err(f"{t.name}: kapalı saatlerin bazıları okul takviminin dışında."))

    # Classes.
    labels = [c.label for c in p.classes]
    for lab in {x for x in labels if labels.count(x) > 1}:
        issues.append(_err(f"{lab} sınıfı birden fazla kez tanımlanmış."))
    for c in p.classes:
        name = c.label
        if len(c.daily_hours) != s.days:
            issues.append(_err(f"{name}: günlük ders sayısı {s.days} gün için girilmeli."))
        if any(h < 0 or h > s.max_periods for h in c.daily_hours):
            issues.append(_err(f"{name}: bir günün ders sayısı 0 ile {s.max_periods} arasında olmalı."))
        if covered.get(c.grade) != c.curriculum and s.parts:
            issues.append(_err(f"{name}: okulda {c.grade}. sınıf için bu okul türü tanımlı değil."))
        lessons = p.lessons_of_class(c.id)
        total, day_total = sum(l.hours for l in lessons), sum(c.daily_hours)
        if total != day_total:
            issues.append(_err(f"{name}: derslerin toplamı {total} saat, günlük ders sayılarının toplamı {day_total}. "
                               "İkisi eşit olmalı."))
        try:
            cur = cur_mod.get(c.curriculum)
        except KeyError:
            issues.append(_err(f"{name}: bilinmeyen okul türü {c.curriculum}."))
            continue
        official = cur.weekly_total(c.grade)
        if official is not None and total != official:
            issues.append(_warn(f"{name}: haftalık toplam {total} saat; resmî çizelgede {official} saat."))
        chosen = [(l.name, l.hours) for l in lessons if l.kind == "elective"]
        offered = {n for n, _, _, _ in cur.electives(c.grade)}
        chosen = [(next((o for o in offered if cur_mod.elective_lesson_name(o) == n), n), h) for n, h in chosen]
        for problem in cur_mod.check_electives(cur, c.grade, chosen):
            issues.append((_err if c.elective_rules else _warn)(f"{name}: {problem}"))
        if any(l.kind == "rehberlik" for l in lessons) and not c.rehber:
            issues.append(_err(f"{name}: rehber öğretmen seçilmemiş."))
        if c.rehber and c.rehber not in teacher_ids:
            issues.append(_err(f"{name}: rehber öğretmen listede yok."))
        by_short: dict[str, set] = {}
        for l in lessons:
            by_short.setdefault(normalise(l.short), set()).add(l.name)
        for short, names in by_short.items():
            if len(names) > 1:
                issues.append(_err(f"{name}: '{short}' kısaltması farklı derslerde kullanılmış: {', '.join(sorted(names))}."))

    # Lessons.
    for l in p.lessons:
        c = p.school_class(l.class_id)
        where = f"{c.label if c else '?'} {l.name}"
        if l.class_id not in class_ids:
            issues.append(_err(f"{l.name}: ait olduğu sınıf bulunamadı."))
        if not l.short.strip():
            issues.append(_err(f"{where}: kısaltma girilmemiş."))
        if l.teacher is None:
            issues.append(_err(f"{where}: öğretmen atanmamış."))
        elif l.teacher not in teacher_ids:
            issues.append(_err(f"{where}: atanan öğretmen listede yok."))
        if l.hours < 1:
            issues.append(_err(f"{where}: haftalık ders saati en az 1 olmalı."))
        for fmt in (l.format,) + l.alternatives:
            if sum(fmt) != l.hours or any(b < 1 for b in fmt):
                issues.append(_err(f"{where}: yerleşim biçimi {'+'.join(map(str, fmt))} ders saatiyle ({l.hours}) uyuşmuyor."))
            elif len(fmt) > s.days:
                issues.append(_err(f"{where}: yerleşim biçimi {'+'.join(map(str, fmt))} için {len(fmt)} gün gerekir; "
                                   f"haftada {s.days} gün var."))
            elif c and max(fmt) > max(c.daily_hours, default=0):
                issues.append(_err(f"{where}: {max(fmt)} saatlik blok, sınıfın en uzun gününden uzun."))
    return issues


def errors(p: Project) -> list[Issue]:
    return [i for i in validate(p) if i.level == "error"]
