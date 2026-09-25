from dataclasses import replace

from dersprogrami.checker import check
from dersprogrami.explain import explain, precheck
from dersprogrami.runner import SolverProcess

from helpers import load_benchmark, small_school


def _close(p, tid, slots):
    return replace(p, teachers=tuple(replace(t, closed=frozenset(slots)) if t.id == tid else t for t in p.teachers))


def test_precheck_catches_overloaded_teacher():
    p = load_benchmark("strict")
    t12 = p.teacher("T12")
    p2 = _close(p, "T12", t12.closed | {(2, 1), (2, 2)})   # 8 lessons, only Monday's 7 periods left
    msgs = precheck(p2)
    assert any(m.startswith("T12:") and "haftalık 8 saat" in m for m in msgs)
    assert explain(p2).status == "precheck"


def test_benchmark_has_no_precheck_problems():
    assert precheck(load_benchmark("strict")) == []


def test_conflict_between_two_teachers_is_found():
    from dersprogrami.model import Teacher
    p = small_school()
    # Two teachers who teach only Türkçe (6 h, 2+2+2) and Matematik (5 h, 2+2+1) in this class.
    p = replace(p, teachers=p.teachers + (Teacher("T100", "Türkçe Öğretmeni", "T.ÖĞR"),
                                          Teacher("T101", "Matematik Öğretmeni", "M.ÖĞR")),
                lessons=tuple(replace(l, teacher={"Türkçe": "T100", "Matematik": "T101"}.get(l.name, l.teacher))
                              for l in p.lessons))
    tur = next(l for l in p.lessons if l.name == "Türkçe")
    mat = next(l for l in p.lessons if l.name == "Matematik")
    only_mornings = {(d, q) for d in range(1, 6) for q in range(1, 8)} - {(d, q) for d in (1, 2, 3) for q in (1, 2)}
    p2 = _close(_close(p, tur.teacher, only_mornings), mat.teacher, only_mornings)
    assert precheck(p2) == []                                      # not visible by arithmetic alone
    e = explain(p2, budget=60)
    assert e.status == "conflict"
    text = " ".join(e.sentences)
    assert tur.teacher in text or p2.teacher(tur.teacher).name in text
    assert p2.teacher(mat.teacher).name in text
    assert e.fixes


def test_runner_solves_in_separate_process():
    p = load_benchmark("strict")
    job = SolverProcess(p, time_limit=45)
    job.start()
    r = job.wait()
    assert job.error is None and r.placements and check(p, r.placements) == []


def test_runner_stop_keeps_best():
    import time
    p = load_benchmark("strict")
    job = SolverProcess(p, time_limit=120)
    job.start()
    time.sleep(8)
    job.request_stop()
    r = job.wait()
    assert job.error is None and time.time() - job.started < 40
    assert r.stopped
