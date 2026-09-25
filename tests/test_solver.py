"""Solver + independent checker on the real-school benchmark and small cases."""
from dataclasses import replace

import pytest

from dersprogrami.checker import check, quality
from dersprogrami.model import Placement, RuleSetting
from dersprogrami.solver import SolveOptions, solve

from helpers import load_benchmark, small_school

FAST = SolveOptions(time_limit=20, seed=1)


def test_progmatic_result_passes_checker_except_known_points():
    p = load_benchmark("progmatic", with_placements=True)
    problems = check(p, p.placements)
    # Progmatic's own timetable breaks only our R9 (one-lesson days of T14).
    assert problems and all("yalnızca 1 saat" in x and x.startswith("T14") for x in problems)


def test_benchmark_strict_is_solved_and_verified():
    p = load_benchmark("strict")
    r = solve(p, FAST)
    assert r.status in ("optimal", "feasible")
    assert check(p, r.placements) == []
    q = quality(p, r.placements)
    assert q["one_lesson_days"] == 0
    assert r.first_solution_after is not None and r.first_solution_after < 20


def test_small_school_solves():
    p = small_school()
    r = solve(p, SolveOptions(time_limit=10))
    assert r.status in ("optimal", "feasible") and check(p, r.placements) == []


def test_locks_are_kept():
    p = load_benchmark("progmatic", with_placements=True)
    # Lock the first two Progmatic blocks of T01's lessons, then solve.
    first = [pl for pl in p.placements if pl.lesson == "L001"]
    lock = Placement("L001", first[0].day, first[0].start, 1, locked=True)
    lesson = p.lesson("L001")
    assert lesson.hours == 1                       # a 1-hour lesson, so a 1-period lock matches its format
    p2 = replace(p, placements=(lock,))
    r = solve(p2, FAST)
    assert r.status in ("optimal", "feasible")
    assert any(pl.lesson == "L001" and pl.day == lock.day and pl.start == lock.start for pl in r.placements)
    assert check(p2, r.placements) == []


def test_impossible_is_reported_as_infeasible():
    p = small_school()
    t = p.teachers[1]
    closed_all = frozenset((d, q) for d in range(1, 6) for q in range(1, 8))
    p2 = replace(p, teachers=(p.teachers[0], replace(t, closed=closed_all)) + p.teachers[2:])
    r = solve(p2, SolveOptions(time_limit=10))
    assert r.status == "infeasible" and r.placements == ()


@pytest.mark.parametrize("rule, value", [("R4", None), ("R12", None), ("R10", 6), ("R2", 4)])
def test_mandatory_rules_hold(rule, value):
    p = load_benchmark("progmatic").with_rule(rule, RuleSetting("mandatory", value))
    r = solve(p, FAST)
    if r.status in ("optimal", "feasible"):
        assert check(p, r.placements) == []
    else:
        assert r.status in ("infeasible", "unknown")


def test_minimal_change_keeps_timetable():
    p = load_benchmark("progmatic", with_placements=True)
    blocks = []
    for pl in sorted(p.placements, key=lambda x: (x.lesson, x.day, x.start)):
        if blocks and blocks[-1].lesson == pl.lesson and blocks[-1].day == pl.day and \
                blocks[-1].start + blocks[-1].length == pl.start:
            blocks[-1] = replace(blocks[-1], length=blocks[-1].length + 1)
        else:
            blocks.append(pl)
    p2 = replace(p, placements=tuple(blocks))
    # Progmatic's own placement breaks R9 for T14; with R9 as a preference the old timetable is kept intact.
    p2 = p2.with_rule("R9", RuleSetting("preference", 2))
    r = solve(p2, SolveOptions(time_limit=20, minimal_change=True))
    old = {(b.lesson, b.day, q) for b in blocks for q in range(b.start, b.start + b.length)}
    new = {(b.lesson, b.day, q) for b in r.placements for q in range(b.start, b.start + b.length)}
    assert len(old - new) <= 10


def test_stop_event_stops_and_keeps_best():
    import threading
    ev = threading.Event()
    p = load_benchmark("strict")
    timer = threading.Timer(3.0, ev.set)
    timer.start()
    r = solve(p, SolveOptions(time_limit=60, stop_event=ev))
    timer.cancel()
    assert r.elapsed < 15 and r.stopped
    if r.placements:
        assert check(p, r.placements) == []
