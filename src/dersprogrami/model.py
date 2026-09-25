"""Immutable data model and its JSON form.

Every object is a frozen dataclass: an edit produces a new Project, which makes undo/redo a matter of
keeping previous states. Slots are (day, period) pairs, both starting at 1 (day 1 = Monday).
"""
from dataclasses import dataclass, replace

SCHEMA_VERSION = 1
DAY_NAMES = ("Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar")
RULE_LEVELS = ("off", "preference", "mandatory")
LESSON_KINDS = ("compulsory", "elective", "choice", "custom", "rehberlik")


class ProjectFileError(Exception):
    """A project file that cannot be read; the message is shown to the user (Turkish)."""


@dataclass(frozen=True)
class Bell:
    periods: tuple[tuple[str, str], ...]
    lunch_after: int | None = 4


DEFAULT_BELL = Bell(periods=(("08:30", "09:10"), ("09:25", "10:05"), ("10:25", "11:05"), ("11:20", "12:00"),
                             ("12:50", "13:30"), ("13:45", "14:25"), ("14:40", "15:20")), lunch_after=4)


@dataclass(frozen=True)
class SchoolPart:
    curriculum: str
    grade_from: int
    grade_to: int


@dataclass(frozen=True)
class School:
    name: str = ""
    headmaster: str = ""
    vice_principals: tuple[str, ...] = ()
    parts: tuple[SchoolPart, ...] = ()
    days: int = 5
    max_periods: int = 7
    bell: Bell = DEFAULT_BELL


@dataclass(frozen=True)
class Teacher:
    id: str
    name: str
    short: str
    branch: str = ""
    closed: frozenset[tuple[int, int]] = frozenset()


@dataclass(frozen=True)
class SchoolClass:
    id: str
    curriculum: str
    grade: int
    section: str
    daily_hours: tuple[int, ...]
    rehber: str | None = None
    elective_rules: bool = True

    @property
    def label(self) -> str:
        return f"{self.grade}-{self.section}"


@dataclass(frozen=True)
class Lesson:
    id: str
    class_id: str
    name: str
    short: str
    hours: int
    format: tuple[int, ...]
    teacher: str | None = None
    kind: str = "compulsory"
    group: str | None = None                      # elective group id (ITB, DAD, ...)
    alternatives: tuple[tuple[int, ...], ...] = ()  # R8 fallback formats
    lesson_group: str | None = None               # R6: grouped lessons go on different days
    preferred_periods: frozenset[int] = frozenset()  # R11
    forbidden_periods: frozenset[int] = frozenset()  # R11


@dataclass(frozen=True)
class Placement:
    lesson: str
    day: int
    start: int
    length: int
    locked: bool = False

    def slots(self):
        return [(self.day, p) for p in range(self.start, self.start + self.length)]


@dataclass(frozen=True)
class RuleSetting:
    level: str
    value: int | None = None


DEFAULT_RULES: dict[str, RuleSetting] = {
    "R1": RuleSetting("off", 7), "R2": RuleSetting("off", 4), "R3": RuleSetting("preference"),
    "R4": RuleSetting("preference"), "R5": RuleSetting("preference"), "R6": RuleSetting("off"),
    "R7": RuleSetting("preference"), "R8": RuleSetting("off"), "R9": RuleSetting("mandatory", 2),
    "R10": RuleSetting("off", 6), "R11": RuleSetting("off"), "R12": RuleSetting("preference"),
}


@dataclass(frozen=True)
class Project:
    school: School = School()
    teachers: tuple[Teacher, ...] = ()
    classes: tuple[SchoolClass, ...] = ()
    lessons: tuple[Lesson, ...] = ()
    placements: tuple[Placement, ...] = ()
    rules: tuple[tuple[str, RuleSetting], ...] = tuple(sorted(DEFAULT_RULES.items()))
    curriculum_versions: tuple[tuple[str, str], ...] = ()
    valid_from: str = ""

    def rule(self, rule_id: str) -> RuleSetting:
        return dict(self.rules).get(rule_id, DEFAULT_RULES[rule_id])

    def teacher(self, teacher_id):
        return next((t for t in self.teachers if t.id == teacher_id), None)

    def school_class(self, class_id):
        return next((c for c in self.classes if c.id == class_id), None)

    def lesson(self, lesson_id):
        return next((l for l in self.lessons if l.id == lesson_id), None)

    def lessons_of_class(self, class_id):
        return [l for l in self.lessons if l.class_id == class_id]

    def lessons_of_teacher(self, teacher_id):
        return [l for l in self.lessons if l.teacher == teacher_id]

    def teacher_load(self, teacher_id) -> int:
        return sum(l.hours for l in self.lessons if l.teacher == teacher_id)

    def with_rule(self, rule_id: str, setting: RuleSetting) -> "Project":
        rules = dict(self.rules)
        rules[rule_id] = setting
        return replace(self, rules=tuple(sorted(rules.items())))


def new_id(prefix: str, existing) -> str:
    """Next free id like T001, C001, L0001."""
    width = 4 if prefix == "L" else 3
    used = {e for e in existing}
    n = 1
    while f"{prefix}{n:0{width}d}" in used:
        n += 1
    return f"{prefix}{n:0{width}d}"


# ---------------------------------------------------------------------------
# JSON form
# ---------------------------------------------------------------------------
def project_to_dict(p: Project) -> dict:
    s = p.school
    return {
        "schema_version": SCHEMA_VERSION,
        "curriculum_versions": dict(p.curriculum_versions),
        "valid_from": p.valid_from,
        "school": {
            "name": s.name, "headmaster": s.headmaster, "vice_principals": list(s.vice_principals),
            "parts": [{"curriculum": x.curriculum, "grade_from": x.grade_from, "grade_to": x.grade_to}
                      for x in s.parts],
            "days": s.days, "max_periods": s.max_periods,
            "bell": {"periods": [list(x) for x in s.bell.periods], "lunch_after": s.bell.lunch_after},
        },
        "teachers": [{"id": t.id, "name": t.name, "short": t.short, "branch": t.branch,
                      "closed": sorted([list(x) for x in t.closed])} for t in p.teachers],
        "classes": [{"id": c.id, "curriculum": c.curriculum, "grade": c.grade, "section": c.section,
                     "daily_hours": list(c.daily_hours), "rehber": c.rehber, "elective_rules": c.elective_rules}
                    for c in p.classes],
        "lessons": [{"id": l.id, "class": l.class_id, "name": l.name, "short": l.short, "hours": l.hours,
                     "format": list(l.format), "teacher": l.teacher, "kind": l.kind, "group": l.group,
                     "alternatives": [list(a) for a in l.alternatives], "lesson_group": l.lesson_group,
                     "preferred_periods": sorted(l.preferred_periods),
                     "forbidden_periods": sorted(l.forbidden_periods)} for l in p.lessons],
        "placements": [{"lesson": x.lesson, "day": x.day, "start": x.start, "length": x.length, "locked": x.locked}
                       for x in p.placements],
        "rules": {k: {"level": v.level, "value": v.value} for k, v in p.rules},
    }


def _need(d, key, kind, where):
    if not isinstance(d, dict) or key not in d:
        raise ProjectFileError(f"Proje dosyası bozuk: {where} içinde '{key}' alanı eksik.")
    v = d[key]
    if kind is int and (not isinstance(v, int) or isinstance(v, bool)):
        raise ProjectFileError(f"Proje dosyası bozuk: {where} içinde '{key}' bir sayı olmalı.")
    if kind is not int and kind is not None and not isinstance(v, kind):
        raise ProjectFileError(f"Proje dosyası bozuk: {where} içinde '{key}' alanının türü hatalı.")
    return v


def _ints(v, where):
    if not isinstance(v, list) or not all(isinstance(x, int) and not isinstance(x, bool) for x in v):
        raise ProjectFileError(f"Proje dosyası bozuk: {where} bir sayı listesi olmalı.")
    return tuple(v)


def _slots(v, where):
    if not isinstance(v, list) or not all(isinstance(x, list) and len(x) == 2 for x in v):
        raise ProjectFileError(f"Proje dosyası bozuk: {where} [gün, ders] çiftlerinden oluşmalı.")
    return frozenset(tuple(_ints(x, where)) for x in v)


def project_from_dict(d: dict) -> Project:
    if not isinstance(d, dict):
        raise ProjectFileError("Proje dosyası bozuk: beklenen yapı bulunamadı.")
    version = _need(d, "schema_version", int, "dosya")
    if version > SCHEMA_VERSION:
        raise ProjectFileError("Bu proje dosyası programın daha yeni bir sürümüyle kaydedilmiş. Lütfen programı güncelleyin.")
    sd = _need(d, "school", dict, "dosya")
    bell = _need(sd, "bell", dict, "okul")
    periods = _need(bell, "periods", list, "zil")
    if not all(isinstance(x, list) and len(x) == 2 and all(isinstance(y, str) for y in x) for x in periods):
        raise ProjectFileError("Proje dosyası bozuk: zil saatleri [başlangıç, bitiş] biçiminde olmalı.")
    school = School(
        name=_need(sd, "name", str, "okul"), headmaster=_need(sd, "headmaster", str, "okul"),
        vice_principals=tuple(_need(sd, "vice_principals", list, "okul")),
        parts=tuple(SchoolPart(_need(x, "curriculum", str, "okul türü"), _need(x, "grade_from", int, "okul türü"),
                               _need(x, "grade_to", int, "okul türü")) for x in _need(sd, "parts", list, "okul")),
        days=_need(sd, "days", int, "okul"), max_periods=_need(sd, "max_periods", int, "okul"),
        bell=Bell(tuple(tuple(x) for x in periods), bell.get("lunch_after")),
    )
    teachers = tuple(Teacher(_need(t, "id", str, "öğretmen"), _need(t, "name", str, "öğretmen"),
                             _need(t, "short", str, "öğretmen"), t.get("branch", ""),
                             _slots(t.get("closed", []), "öğretmen kapalı saatleri"))
                     for t in _need(d, "teachers", list, "dosya"))
    classes = tuple(SchoolClass(_need(c, "id", str, "sınıf"), _need(c, "curriculum", str, "sınıf"),
                                _need(c, "grade", int, "sınıf"), _need(c, "section", str, "sınıf"),
                                _ints(_need(c, "daily_hours", list, "sınıf"), "sınıfın günlük ders sayıları"),
                                c.get("rehber"), bool(c.get("elective_rules", True)))
                    for c in _need(d, "classes", list, "dosya"))
    lessons = []
    for l in _need(d, "lessons", list, "dosya"):
        kind = l.get("kind", "compulsory")
        if kind not in LESSON_KINDS:
            raise ProjectFileError(f"Proje dosyası bozuk: bilinmeyen ders türü '{kind}'.")
        lessons.append(Lesson(
            _need(l, "id", str, "ders"), _need(l, "class", str, "ders"), _need(l, "name", str, "ders"),
            _need(l, "short", str, "ders"), _need(l, "hours", int, "ders"),
            _ints(_need(l, "format", list, "ders"), "ders yerleşim biçimi"), l.get("teacher"), kind,
            l.get("group"), tuple(_ints(a, "alternatif biçim") for a in l.get("alternatives", [])),
            l.get("lesson_group"), frozenset(_ints(l.get("preferred_periods", []), "tercih edilen saatler")),
            frozenset(_ints(l.get("forbidden_periods", []), "yasak saatler"))))
    placements = tuple(Placement(_need(x, "lesson", str, "yerleşim"), _need(x, "day", int, "yerleşim"),
                                 _need(x, "start", int, "yerleşim"), _need(x, "length", int, "yerleşim"),
                                 bool(x.get("locked", False)))
                       for x in d.get("placements", []))
    rules = dict(DEFAULT_RULES)
    for k, v in d.get("rules", {}).items():
        if k not in DEFAULT_RULES or not isinstance(v, dict) or v.get("level") not in RULE_LEVELS:
            raise ProjectFileError(f"Proje dosyası bozuk: kural '{k}' okunamadı.")
        rules[k] = RuleSetting(v["level"], v.get("value"))
    cv = d.get("curriculum_versions", {})
    return Project(school=school, teachers=teachers, classes=classes, lessons=tuple(lessons),
                   placements=placements, rules=tuple(sorted(rules.items())),
                   curriculum_versions=tuple(sorted(cv.items())) if isinstance(cv, dict) else (),
                   valid_from=d.get("valid_from", ""))

