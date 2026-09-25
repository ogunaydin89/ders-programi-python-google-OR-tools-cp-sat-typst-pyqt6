"""Short forms (kısaltmalar) for lessons and teachers, with Turkish-correct upper case."""
import re

_LETTER = re.compile(r"[^\W\d_]", re.UNICODE)
_ELECTIVE_PREFIX = re.compile(r"^\s*seçmeli\s+", re.IGNORECASE)


def tr_upper(text: str) -> str:
    """Upper case with Turkish dotted/dotless i: 'i' -> 'İ', 'ı' -> 'I'."""
    return text.replace("i", "İ").replace("ı", "I").upper()


def _letters(text: str) -> str:
    return "".join(_LETTER.findall(text))


def lesson_short(name: str, elective: bool = False) -> str:
    """Suggest a lesson short form: first 3 letters (TÜR), electives 'S.' + 3 letters (S.OKU)."""
    base = _ELECTIVE_PREFIX.sub("", name) if elective else name
    words = base.split()
    letters = _letters(words[0]) if words else ""
    if len(letters) < 3:
        letters = _letters(base)
    short = tr_upper(letters[:3])
    return f"S.{short}" if elective else short


def teacher_short(full_name: str) -> str:
    """Suggest a teacher short form: first initial + '.' + first 3 letters of the surname (A.YIL)."""
    words = full_name.split()
    if not words:
        return ""
    if len(words) == 1:
        return tr_upper(_letters(words[0])[:3])
    return f"{tr_upper(_letters(words[0])[:1])}.{tr_upper(_letters(words[-1])[:3])}"


def normalise(short: str) -> str:
    """Comparison key: Turkish upper case, surrounding spaces removed."""
    return tr_upper(short.strip())


def duplicates(items):
    """Given (owner, short) pairs, return {short: [owners]} for every short used by more than one owner."""
    seen: dict[str, list] = {}
    for owner, short in items:
        seen.setdefault(normalise(short), []).append(owner)
    return {s: owners for s, owners in seen.items() if len(owners) > 1}
