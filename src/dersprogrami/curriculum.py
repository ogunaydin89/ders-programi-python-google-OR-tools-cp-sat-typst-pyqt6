"""Official weekly curricula (haftalık ders çizelgeleri): lessons, electives and their rules."""
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from .model import Lesson, SchoolClass, new_id
from .shortform import lesson_short

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
CUSTOM_ID = "diger"
REHBERLIK = "Rehberlik ve Yönlendirme"


@dataclass(frozen=True)
class Curriculum:
    id: str
    name: str
    version: str
    grades: tuple[int, ...]
    raw: dict

    @property
    def custom(self) -> bool:
        return self.id == CUSTOM_ID

    def weekly_total(self, grade: int) -> int | None:
        return self.raw.get("weekly_total", {}).get(str(grade))

    def default_daily_hours(self, grade: int, days: int = 5) -> tuple[int, ...]:
        hours = self.raw.get("default_daily_hours", {}).get(str(grade))
        return tuple(hours) if hours and len(hours) == days else tuple([7] * days)

    def compulsory(self, grade: int):
        """[(name, short, hours, is_rehberlik)] for the grade."""
        out = []
        for c in self.raw.get("compulsory", []):
            h = c["hours"].get(str(grade))
            if h:
                out.append((c["name"], c.get("short") or lesson_short(c["name"]), h, bool(c.get("rehberlik"))))
        return out

    def choice_lessons(self, grade: int):
        """[(choice name, options, hours)] for the grade."""
        return [(c["name"], tuple(c["options"]), c["hours"][str(grade)])
                for c in self.raw.get("choice_lessons", []) if str(grade) in c["hours"]]

    def elective_hours(self, grade: int) -> int:
        return self.raw.get("electives", {}).get("hours", {}).get(str(grade), 0)

    def elective_groups(self) -> dict[str, str]:
        return {g["id"]: g["name"] for g in self.raw.get("electives", {}).get("groups", [])}

    def electives(self, grade: int):
        """[(course name, group id, hour options, short)] offered at the grade."""
        return [(c["name"], c["group"], tuple(c["options"][str(grade)]),
                 c.get("short") or lesson_short(c["name"], elective=True))
                for c in self.raw.get("electives", {}).get("courses", []) if str(grade) in c["options"]]


CUSTOM = Curriculum(CUSTOM_ID, "Diğer / Özel", "", tuple(range(5, 13)), {})


@lru_cache(maxsize=1)
def load_all() -> dict[str, Curriculum]:
    out = {CUSTOM_ID: CUSTOM}
    for path in sorted(DATA_DIR.glob("*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        out[raw["id"]] = Curriculum(raw["id"], raw["name"], raw["version"], tuple(raw["grades"]), raw)
    return out


def get(curriculum_id: str) -> Curriculum:
    try:
        return load_all()[curriculum_id]
    except KeyError:
        raise KeyError(f"Bilinmeyen öğretim programı: {curriculum_id}") from None


def default_format(hours: int, days: int = 5) -> tuple[int, ...]:
    """Progmatic-style default: blocks of 2 plus a single 1 (5 -> 2+2+1); more than 2 per day only if needed."""
    if hours <= 0:
        return ()
    if hours <= 2 * days:
        return tuple([2] * (hours // 2) + [1] * (hours % 2))
    base, extra = divmod(hours, days)
    return tuple(sorted([base + 1] * extra + [base] * (days - extra), reverse=True))


def elective_lesson_name(course: str) -> str:
    return course if course.lower().startswith("seçmeli") else f"Seçmeli {course}"


def check_electives(cur: Curriculum, grade: int, chosen) -> list[str]:
    """Problems (Turkish) with a class's elective choice; chosen = [(course name, hours)]."""
    if cur.custom:
        return []
    problems = []
    offered = {name: (group, options) for name, group, options, _ in cur.electives(grade)}
    groups = cur.elective_groups()
    names = [c for c, _ in chosen]
    for dup in {n for n in names if names.count(n) > 1}:
        problems.append(f"'{dup}' seçmeli dersi birden fazla kez seçilmiş.")
    for course, hours in chosen:
        if course not in offered:
            problems.append(f"'{course}' {grade}. sınıfta seçmeli olarak okutulamaz.")
        elif hours not in offered[course][1]:
            opts = ", ".join(str(o) for o in offered[course][1])
            problems.append(f"'{course}' dersi {grade}. sınıfta {opts} saat olarak seçilebilir, {hours} saat olamaz.")
    total, need = sum(h for _, h in chosen), cur.elective_hours(grade)
    if total != need:
        problems.append(f"Seçmeli derslerin toplamı {need} saat olmalı; şu an {total} saat.")
    by_group: dict[str, int] = {}
    for course, _ in chosen:
        if course in offered:
            by_group[offered[course][0]] = by_group.get(offered[course][0], 0) + 1
    for rule in cur.raw.get("electives", {}).get("rules", []):
        if grade not in rule["grades"]:
            continue
        if "exactly_one_from_each" in rule:
            for g in rule["exactly_one_from_each"]:
                if by_group.get(g, 0) != 1:
                    problems.append(f"'{groups[g]}' grubundan tam olarak bir ders seçilmeli.")
        if "min_groups_covered" in rule:
            r = rule["min_groups_covered"]
            covered = sum(1 for g in r["groups"] if by_group.get(g, 0) > 0)
            if covered < r["min"]:
                names_ = ", ".join(f"'{groups[g]}'" for g in r["groups"])
                problems.append(f"{names_} gruplarının en az {r['min']} tanesinden ders seçilmeli; şu an {covered}.")
    return problems


def build_class_lessons(cur: Curriculum, cls: SchoolClass, electives=(), choices=None, existing_ids=(),
                        days: int = 5) -> tuple[Lesson, ...]:
    """Lessons for a new class: compulsory, choice picks, electives; Rehberlik goes to the rehber teacher.

    electives = [(course name, hours)], choices = {choice name: picked option}.
    """
    choices = choices or {}
    used = set(existing_ids)
    out = []

    def add(name, short, hours, kind, teacher=None, group=None):
        lid = new_id("L", used)
        used.add(lid)
        out.append(Lesson(lid, cls.id, name, short, hours, default_format(hours, days), teacher, kind, group))

    for name, short, hours, is_reh in cur.compulsory(cls.grade):
        add(name, short, hours, "rehberlik" if is_reh else "compulsory", cls.rehber if is_reh else None)
    for name, options, hours in cur.choice_lessons(cls.grade):
        pick = choices.get(name)
        if pick is not None:
            if pick not in options:
                raise ValueError(f"'{name}' için geçersiz seçim: {pick}")
            add(pick, lesson_short(pick), hours, "choice")
    offered = {name: (group, short) for name, group, _, short in cur.electives(cls.grade)}
    for course, hours in electives:
        group, short = offered.get(course, (None, lesson_short(course, elective=True)))
        add(elective_lesson_name(course), short, hours, "elective", group=group)
    return tuple(out)
