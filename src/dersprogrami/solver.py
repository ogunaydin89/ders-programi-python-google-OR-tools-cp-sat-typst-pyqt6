"""CP-SAT timetable model: structural rules S1–S7 and rules R1–R12 at Off / Preference / Mandatory.

In diagnose mode every user-controlled restriction (a teacher's closed day, a lesson's format, a lock, each
Mandatory rule instance) is guarded by a switch literal, so explain.py can find which of them conflict.
"""
import collections
import math
import os
import threading
import time
from dataclasses import dataclass, field

from ortools.sat.python import cp_model

from .model import Placement, Project
from .shortform import normalise

WEIGHTS = {"R1": 4, "R2": 2, "R3": 10, "R4": 3, "R5": 2, "R6": 3, "R7": 1, "R8": 5, "R9": 10, "R10": 1,
           "R11": 2, "R12": 3, "change": 50}


@dataclass
class SolveOptions:
    time_limit: float = 120.0
    workers: int = 0                      # 0 = all CPU cores
    seed: int = 0
    minimal_change: bool = False          # keep unlocked existing placements where possible
    alternatives: int = 3                 # how many of the last improving solutions to keep
    stop_event: object = None             # threading/multiprocessing Event: stop and keep the best
    on_progress: object = None            # callable(elapsed, objective, bound, solutions)


@dataclass
class SolveResult:
    status: str                            # optimal | feasible | infeasible | unknown | model_invalid
    placements: tuple = ()
    objective: float | None = None
    bound: float | None = None
    elapsed: float = 0.0
    first_solution_after: float | None = None
    solutions: int = 0
    alternatives: list = field(default_factory=list)
    stopped: bool = False


class ModelBuilder:
    def __init__(self, project: Project, diagnose: bool = False, previous=()):
        self.p = project
        self.diagnose = diagnose
        self.previous = previous
        self.m = cp_model.CpModel()
        self.penalties = []
        self.switches = {}                         # key -> literal (diagnose mode)
        self.days = list(range(1, project.school.days + 1))
        self.x = {}                                # (lesson, format index, block index, day, start) -> literal
        self.block_size = {}                       # same key -> size
        self.occ = collections.defaultdict(list)   # (lesson, day, period) -> literals
        self.used = collections.defaultdict(list)  # (lesson, day) -> literals of blocks on that day
        self.format_use = {}                       # (lesson, format index) -> literal
        self.formats = {}                          # lesson -> list of formats
        self.busy = {}                             # (teacher, day, period) -> literal
        self._gaps = {}                            # (teacher, day) -> gap literals
        self.build()

    # -- helpers ------------------------------------------------------------
    def switch(self, key):
        if not self.diagnose:
            return None
        if key not in self.switches:
            self.switches[key] = self.m.NewBoolVar(f"sw{len(self.switches)}")
        return self.switches[key]

    @staticmethod
    def enforce(ct, lit):
        if lit is not None:
            ct.OnlyEnforceIf(lit)
        return ct

    def level(self, rule):
        return self.p.rule(rule).level

    def value(self, rule, default):
        v = self.p.rule(rule).value
        return default if v is None else v

    def pen(self, rule, expr, weight=None):
        self.penalties.append((WEIGHTS[rule] if weight is None else weight) * expr)

    # -- model ----------------------------------------------------------------
    def build(self):
        p, m = self.p, self.m
        classes = {c.id: c for c in p.classes}
        lunch = p.school.bell.lunch_after
        r12 = self.level("R12")
        for l in p.lessons:
            c = classes[l.class_id]
            fmts = [tuple(l.format)]
            if self.level("R8") != "off":
                fmts += [tuple(a) for a in l.alternatives if tuple(a) not in fmts]
            relaxed = None
            if self.diagnose and l.hours <= len(self.days) and (1,) * l.hours not in fmts:
                relaxed = len(fmts)
                fmts.append((1,) * l.hours)
            self.formats[l.id] = fmts
            uses = []
            for fi, fmt in enumerate(fmts):
                use = m.NewBoolVar("")
                self.format_use[(l.id, fi)] = use
                uses.append(use)
                dayvars = []
                for j, k in enumerate(fmt):
                    lits, dv = [], []
                    for d in self.days:
                        for s in range(1, c.daily_hours[d - 1] - k + 2):
                            v = m.NewBoolVar("")
                            key = (l.id, fi, j, d, s)
                            self.x[key] = v
                            self.block_size[key] = k
                            lits.append(v)
                            dv.append(d * v)
                            self.used[(l.id, d)].append(v)
                            for q in range(s, s + k):
                                self.occ[(l.id, d, q)].append(v)
                            if k >= 2 and lunch and s <= lunch < s + k - 1:
                                if r12 == "mandatory":
                                    self.enforce(m.Add(v == 0), self.switch(("rule", "R12", l.id)))
                                elif r12 == "preference":
                                    self.pen("R12", v)
                    m.Add(sum(lits) == use)
                    dayvars.append(sum(dv))
                for j in range(len(fmt) - 1):   # equal blocks in day order (symmetry breaking)
                    if fmt[j] == fmt[j + 1]:
                        m.Add(dayvars[j] < dayvars[j + 1]).OnlyEnforceIf(use)
                if fi > 0 and fi != relaxed:
                    self.pen("R8", use)
            m.AddExactlyOne(uses)
            if relaxed is not None:
                self.enforce(m.Add(self.format_use[(l.id, relaxed)] == 0), self.switch(("format", l.id)))
            for d in self.days:
                m.Add(sum(self.used[(l.id, d)]) <= 1)                       # S5: one block per day

        # S5 extension: the same lesson name twice in a class (e.g. two teachers) -> still different days.
        same = collections.defaultdict(list)
        for l in p.lessons:
            same[(l.class_id, normalise(l.name))].append(l.id)
        for lids in same.values():
            if len(lids) > 1:
                for d in self.days:
                    m.Add(sum(v for lid in lids for v in self.used[(lid, d)]) <= 1)

        # S2 + S3: every period 1..h of a class day holds exactly one lesson.
        by_class = collections.defaultdict(list)
        for l in p.lessons:
            by_class[l.class_id].append(l.id)
        for cid, lids in by_class.items():
            for d in self.days:
                for q in range(1, classes[cid].daily_hours[d - 1] + 1):
                    m.AddExactlyOne([v for lid in lids for v in self.occ[(lid, d, q)]])

        # Redundant: each class day's blocks add up to its length (helps the solver find timetables faster).
        lesson_class = {l.id: l.class_id for l in p.lessons}
        day_terms = collections.defaultdict(list)
        for key, v in self.x.items():
            day_terms[(lesson_class[key[0]], key[3])].append(self.block_size[key] * v)
        for (cid, d), terms in day_terms.items():
            m.Add(sum(terms) == classes[cid].daily_hours[d - 1])

        # S7 locks, and minimal-change preference for unlocked previous placements.
        for pl in self.p.placements:
            if pl.locked:
                cands = [v for (lid, fi, j, d, s), v in self.x.items()
                         if lid == pl.lesson and d == pl.day and s == pl.start
                         and self.block_size[(lid, fi, j, d, s)] == pl.length]
                lit = self.switch(("lock", pl.lesson, pl.day, pl.start))
                self.enforce(m.Add(sum(cands) == 1) if cands else m.AddBoolOr([]), lit)
        for pl in self.previous:
            if not pl.locked:
                for d, q in pl.slots():
                    keep = self.occ.get((pl.lesson, d, q))
                    if keep:
                        stay = m.NewBoolVar("")
                        m.Add(sum(keep) >= stay)
                        self.pen("change", 1 - stay)

        self.teacher_rules(by_class)
        self.lesson_rules()
        if self.penalties:
            m.Minimize(sum(self.penalties))

    def teacher_rules(self, by_class):
        p, m = self.p, self.m
        P = p.school.max_periods
        by_teacher = collections.defaultdict(list)
        for l in p.lessons:
            if l.teacher:
                by_teacher[l.teacher].append(l)
        for t in p.teachers:
            lessons = by_teacher.get(t.id)
            if not lessons:
                continue
            load = sum(l.hours for l in lessons)
            open_days = [d for d in self.days if any((d, q) not in t.closed for q in range(1, P + 1))]
            peak = None
            for d in self.days:
                busy = []
                for q in range(1, P + 1):
                    cover = [v for l in lessons for v in self.occ[(l.id, d, q)]]
                    b = m.NewBoolVar("")
                    m.Add(sum(cover) == b)                                   # S1: never two lessons at once
                    if (d, q) in t.closed:
                        self.enforce(m.Add(b == 0), self.switch(("closed", t.id, d)))  # S6
                    self.busy[(t.id, d, q)] = b
                    busy.append(b)
                works = m.NewBoolVar("")
                m.AddMaxEquality(works, busy)
                count = sum(busy)
                self.r1(t, count)
                self.r2(t, busy)
                self.r3(t, d, busy)
                self.r9(t, works, count, load)
                self.r10(t, busy, works)
                if self.level("R7") == "preference":
                    if peak is None:
                        peak = m.NewIntVar(0, P, "")
                        self.pen("R7", peak)
                    m.Add(peak >= count)
                elif self.level("R7") == "mandatory" and open_days:
                    cap = math.ceil(load / len(open_days)) + 1
                    self.enforce(m.Add(count <= cap), self.switch(("rule", "R7", t.id)))
            if self.level("R3") == "mandatory":
                gaps = [g for (tid, _), gl in self._gaps.items() if tid == t.id for g in gl]
                self.enforce(m.Add(sum(gaps) <= self.value("R3", 0)), self.switch(("rule", "R3", t.id)))

        # R5: one teacher's different lessons in the same class on different days.
        lv = self.level("R5")
        if lv != "off":
            groups = collections.defaultdict(list)
            for l in p.lessons:
                if l.teacher:
                    groups[(l.teacher, l.class_id)].append(l)
            for (tid, cid), ls in groups.items():
                if len({normalise(l.name) for l in ls}) < 2:
                    continue
                for d in self.days:
                    total = sum(v for l in ls for v in self.used[(l.id, d)])
                    if lv == "mandatory":
                        self.enforce(m.Add(total <= 1), self.switch(("rule", "R5", tid, cid)))
                    else:
                        extra = m.NewIntVar(0, len(ls), "")
                        m.Add(extra >= total - 1)
                        self.pen("R5", extra)

    def r1(self, t, count):
        lv = self.level("R1")
        cap = self.value("R1", 7)
        if lv == "mandatory":
            self.enforce(self.m.Add(count <= cap), self.switch(("rule", "R1", t.id)))
        elif lv == "preference":
            over = self.m.NewIntVar(0, self.p.school.max_periods, "")
            self.m.Add(over >= count - cap)
            self.pen("R1", over)

    def r2(self, t, busy):
        lv = self.level("R2")
        n = self.value("R2", 4)
        if lv == "off" or n >= len(busy):
            return
        for i in range(len(busy) - n):
            window = sum(busy[i:i + n + 1])
            if lv == "mandatory":
                self.enforce(self.m.Add(window <= n), self.switch(("rule", "R2", t.id)))
            else:
                v = self.m.NewBoolVar("")
                self.m.Add(v >= window - n)
                self.pen("R2", v)

    def r3(self, t, d, busy):
        lv = self.level("R3")
        if lv == "off":
            return
        gaps = []
        for i in range(1, len(busy) - 1):
            before, after, gap = (self.m.NewBoolVar("") for _ in range(3))
            self.m.AddMaxEquality(before, busy[:i])
            self.m.AddMaxEquality(after, busy[i + 1:])
            self.m.Add(gap >= before + after - 1 - busy[i])
            if lv == "mandatory":   # make gap exact so the weekly limit counts real gaps
                self.m.AddImplication(gap, before)
                self.m.AddImplication(gap, after)
                self.m.AddImplication(gap, busy[i].Not())
            else:
                self.pen("R3", gap)
            gaps.append(gap)
        self._gaps[(t.id, d)] = gaps

    def r9(self, t, works, count, load):
        lv = self.level("R9")
        n = self.value("R9", 2)
        if lv == "off" or load < n:
            return
        mine = [l for l in self.p.lessons if l.teacher == t.id]
        if len(mine) == 1 and min(mine[0].format) < n:   # one lesson with a short block: unavoidable
            return
        if lv == "mandatory":
            lit = self.switch(("rule", "R9", t.id))
            self.m.Add(count >= n).OnlyEnforceIf([works] + ([lit] if lit is not None else []))
        else:
            short = self.m.NewIntVar(0, n, "")
            self.m.Add(short >= n * works - count)
            self.pen("R9", short)

    def r10(self, t, busy, works):
        lv = self.level("R10")
        n = self.value("R10", 6)
        if lv == "off" or n >= len(busy):
            return
        P = len(busy)
        first = self.m.NewIntVar(1, P, "")
        last = self.m.NewIntVar(1, P, "")
        for q, b in enumerate(busy, 1):
            self.m.Add(first <= q).OnlyEnforceIf(b)
            self.m.Add(last >= q).OnlyEnforceIf(b)
        span = last - first + 1
        if lv == "mandatory":
            lit = self.switch(("rule", "R10", t.id))
            self.m.Add(span <= n).OnlyEnforceIf([works] + ([lit] if lit is not None else []))
        else:
            over = self.m.NewIntVar(0, P, "")
            self.m.Add(over >= span - n)
            self.pen("R10", over)

    def lesson_rules(self):
        p, m = self.p, self.m
        # R4: blocks of one lesson not on neighbouring days.
        lv = self.level("R4")
        if lv != "off":
            for l in p.lessons:
                if len(l.format) < 2:
                    continue
                for d in self.days[:-1]:
                    pair = sum(self.used[(l.id, d)]) + sum(self.used[(l.id, d + 1)])
                    if lv == "mandatory":
                        self.enforce(m.Add(pair <= 1), self.switch(("rule", "R4", l.id)))
                    else:
                        nb = m.NewBoolVar("")
                        m.Add(nb >= pair - 1)
                        self.pen("R4", nb)
        # R6: lessons in the same user-defined group on different days.
        lv = self.level("R6")
        if lv != "off":
            groups = collections.defaultdict(list)
            for l in p.lessons:
                if l.lesson_group:
                    groups[l.lesson_group].append(l.id)
            for g, lids in groups.items():
                for d in self.days:
                    total = sum(v for lid in lids for v in self.used[(lid, d)])
                    if lv == "mandatory":
                        self.enforce(m.Add(total <= 1), self.switch(("rule", "R6", g)))
                    else:
                        extra = m.NewIntVar(0, len(lids), "")
                        m.Add(extra >= total - 1)
                        self.pen("R6", extra)
        # R11: forbidden and preferred periods per lesson.
        lv = self.level("R11")
        if lv != "off":
            for l in p.lessons:
                bad = set(l.forbidden_periods)
                if l.preferred_periods:
                    bad |= set(range(1, p.school.max_periods + 1)) - set(l.preferred_periods)
                for d in self.days:
                    for q in bad:
                        for v in self.occ.get((l.id, d, q), []):
                            if lv == "mandatory":
                                self.enforce(m.Add(v == 0), self.switch(("rule", "R11", l.id)))
                            else:
                                self.pen("R11", v)

    # -- reading a solution ---------------------------------------------------------
    def placements(self, value) -> tuple:
        locked = {(pl.lesson, pl.day, pl.start) for pl in self.p.placements if pl.locked}
        out = []
        for key, v in self.x.items():
            if value(v):
                lid, fi, j, d, s = key
                out.append(Placement(lid, d, s, self.block_size[key], (lid, d, s) in locked))
        return tuple(sorted(out, key=lambda x: (x.lesson, x.day, x.start)))


class _Callback(cp_model.CpSolverSolutionCallback):
    def __init__(self, builder, options, t0):
        super().__init__()
        self.b, self.o, self.t0 = builder, options, t0
        self.first = None
        self.count = 0
        self.best = []

    def on_solution_callback(self):
        now = time.time() - self.t0
        self.count += 1
        if self.first is None:
            self.first = now
        self.best.append(self.b.placements(self.BooleanValue))
        self.best = self.best[-max(1, self.o.alternatives):]
        if self.o.on_progress:
            self.o.on_progress(now, self.ObjectiveValue(), self.BestObjectiveBound(), self.count)


STATUS = {cp_model.OPTIMAL: "optimal", cp_model.FEASIBLE: "feasible", cp_model.INFEASIBLE: "infeasible",
          cp_model.UNKNOWN: "unknown", cp_model.MODEL_INVALID: "model_invalid"}


def solve(project: Project, options: SolveOptions | None = None) -> SolveResult:
    """Solve; the caller must check the result with checker.check before showing or printing it."""
    o = options or SolveOptions()
    previous = project.placements if o.minimal_change else ()
    b = ModelBuilder(project, previous=previous)
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = o.time_limit
    solver.parameters.num_workers = o.workers or os.cpu_count() or 8
    solver.parameters.random_seed = o.seed
    solver.parameters.linearization_level = 2      # measured: much faster first timetables on tight schools
    t0 = time.time()
    cb = _Callback(b, o, t0)
    stopped = threading.Event()
    watcher = None
    if o.stop_event is not None:
        def watch():
            while not stopped.is_set():
                if o.stop_event.is_set():
                    solver.StopSearch()
                    return
                time.sleep(0.1)
        watcher = threading.Thread(target=watch, daemon=True)
        watcher.start()
    status = solver.Solve(b.m, cb)
    stopped.set()
    elapsed = time.time() - t0
    has = status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    return SolveResult(
        status=STATUS.get(status, "unknown"),
        placements=b.placements(solver.BooleanValue) if has else (),
        objective=solver.ObjectiveValue() if has and b.penalties else (0.0 if has else None),
        bound=solver.BestObjectiveBound() if has and b.penalties else (0.0 if has else None),
        elapsed=elapsed, first_solution_after=cb.first, solutions=cb.count,
        alternatives=cb.best[:-1] if has else [],
        stopped=bool(o.stop_event is not None and o.stop_event.is_set()),
    )
