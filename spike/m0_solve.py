"""M0 spike: solve the anonymised benchmark with CP-SAT and compare against Progmatic.

Throwaway prototype. Usage: .venv/bin/python spike/m0_solve.py [seconds_per_variant]
"""
import collections
import json
import os
import sys
import time
from pathlib import Path

from ortools.sat.python import cp_model

ROOT = Path(__file__).resolve().parent.parent
BENCH = ROOT / "tests" / "fixtures" / "benchmark_anon.json"

# Preference weights (R3 gaps matter most; R9 is Mandatory).
W_GAP, W_NEIGHBOUR, W_SAMEDAY, W_LUNCH, W_BALANCE = 10, 3, 2, 3, 1


def load():
    return json.loads(BENCH.read_text(encoding="utf-8"))


def closed_slots(data, variant):
    closed = {t["id"]: {tuple(s) for s in t["closed"]} for t in data["teachers"]}
    if variant == "progmatic":
        for t, slots in data["variants"]["progmatic"]["open"].items():
            closed[t] -= {tuple(s) for s in slots}
    return closed


def solve(data, variant, seconds):
    days = range(1, data["school"]["days"] + 1)
    lunch = data["school"]["lunch_after_period"]
    hours = {c["id"]: c["daily_hours"] for c in data["classes"]}
    closed = closed_slots(data, variant)
    lessons = data["lessons"]
    m = cp_model.CpModel()

    # x[(lesson, block, day, start)]: block of the lesson's format starts at that period on that day.
    x = {}
    occ = collections.defaultdict(list)          # (lesson, day, period) -> literals covering it
    dayuse = collections.defaultdict(list)       # (lesson, day) -> literals of blocks on that day
    lunch_lits = []
    for l in lessons:
        h = hours[l["class"]]
        dayvars = []
        for j, k in enumerate(l["format"]):
            lits = []
            for d in days:
                for s in range(1, h[d - 1] - k + 2):
                    v = m.NewBoolVar("")
                    x[(l["id"], j, d, s)] = v
                    lits.append(v)
                    dayuse[(l["id"], d)].append(v)
                    for p in range(s, s + k):
                        occ[(l["id"], d, p)].append(v)
                    if k >= 2 and s <= lunch < s + k - 1:
                        lunch_lits.append(v)
            m.AddExactlyOne(lits)                                   # S4/S5: each block placed once
            dv = m.NewIntVar(1, len(days), "")
            m.Add(dv == sum(d * v for (lid, jj, d, s), v in x.items() if lid == l["id"] and jj == j))
            dayvars.append(dv)
        for j in range(len(dayvars) - 1):                           # symmetry: equal blocks in day order
            if l["format"][j] == l["format"][j + 1]:
                m.Add(dayvars[j] < dayvars[j + 1])
        for d in days:
            m.Add(sum(dayuse[(l["id"], d)]) <= 1)                   # S5: at most one block per day

    occ_hours = {l["id"]: range(l["hours"]) for l in lessons}
    by_class = collections.defaultdict(list)
    by_teacher = collections.defaultdict(list)
    for l in lessons:
        by_class[l["class"]].append(l["id"])
        by_teacher[l["teacher"]].append(l["id"])

    # S2 + S3: every class period 1..h filled exactly once, nothing after h.
    for c, lids in by_class.items():
        for d in days:
            for p in range(1, 8):
                cover = [v for lid in lids for v in occ[(lid, d, p)]]
                if p <= hours[c][d - 1]:
                    m.AddExactlyOne(cover)
                else:
                    m.Add(sum(cover) == 0)

    # S1 + S6 and the teacher-side preferences.
    penalties = []
    for t, lids in by_teacher.items():
        for d in days:
            busy = []
            for p in range(1, 8):
                cover = [v for lid in lids for v in occ[(lid, d, p)]]
                b = m.NewBoolVar("")
                if (d, p) in closed[t]:
                    m.Add(sum(cover) == 0)                          # S6
                    m.Add(b == 0)
                else:
                    m.Add(sum(cover) == b)                          # S1 (b is 0/1)
                busy.append(b)
            works = m.NewBoolVar("")
            m.AddMaxEquality(works, busy)
            count = sum(busy)
            for i in range(1, 6):                                   # R3: gap = free period between lessons
                before = m.NewBoolVar("")
                after = m.NewBoolVar("")
                m.AddMaxEquality(before, busy[:i])
                m.AddMaxEquality(after, busy[i + 1:])
                gap = m.NewBoolVar("")
                m.Add(gap >= before + after - 1 - busy[i])
                penalties.append(W_GAP * gap)
            if sum(1 for lid in lids for _ in occ_hours[lid]) >= 2:    # R9 (Mandatory): no one-lesson days
                m.Add(count >= 2).OnlyEnforceIf(works)
        daily = [sum(v for lid in lids for p in range(1, 8) for v in occ[(lid, d, p)]) for d in days]
        peak = m.NewIntVar(0, 7, "")                                # R7: balanced load (lower peak day)
        for e in daily:
            m.Add(peak >= e)
        penalties.append(W_BALANCE * peak)

    by_teacher_class = collections.defaultdict(list)
    for l in lessons:
        by_teacher_class[(l["teacher"], l["class"])].append(l["id"])
        for d in list(days)[:-1]:                                   # R4: blocks on neighbouring days
            nb = m.NewBoolVar("")
            m.Add(nb >= sum(dayuse[(l["id"], d)]) + sum(dayuse[(l["id"], d + 1)]) - 1)
            penalties.append(W_NEIGHBOUR * nb)
    for lids in by_teacher_class.values():                          # R5: one teacher's lessons in a class
        if len(lids) > 1:
            for d in days:
                extra = m.NewIntVar(0, len(lids), "")
                m.Add(extra >= sum(v for lid in lids for v in dayuse[(lid, d)]) - 1)
                penalties.append(W_SAMEDAY * extra)
    penalties += [W_LUNCH * v for v in lunch_lits]                  # R12: no double lesson across lunch

    m.Minimize(sum(penalties))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = seconds
    solver.parameters.num_workers = os.cpu_count() or 8
    first = []

    class FirstSolution(cp_model.CpSolverSolutionCallback):
        def on_solution_callback(self):
            if not first:
                first.append((time.time() - t0, self.ObjectiveValue()))

    t0 = time.time()
    status = solver.Solve(m, FirstSolution())
    if first:
        print(f"first valid timetable after {first[0][0]:.1f}s (objective {first[0][1]:.0f})")
    elapsed = time.time() - t0
    placement = []
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        for (lid, j, d, s), v in x.items():
            if solver.Value(v):
                k = next(l for l in lessons if l["id"] == lid)["format"][j]
                placement += [{"lesson": lid, "day": d, "period": p} for p in range(s, s + k)]
    return solver.StatusName(status), elapsed, solver.ObjectiveValue() if placement else None, \
        solver.BestObjectiveBound(), placement


# ---------------------------------------------------------------------------
# Independent checker: shares no code with the model above.
# ---------------------------------------------------------------------------
def check(data, placement, closed):
    errors = []
    L = {l["id"]: l for l in data["lessons"]}
    hours = {c["id"]: c["daily_hours"] for c in data["classes"]}
    cells = collections.Counter()
    tcells = collections.Counter()
    per_lesson = collections.defaultdict(lambda: collections.defaultdict(list))
    for pl in placement:
        l = L[pl["lesson"]]
        cells[(l["class"], pl["day"], pl["period"])] += 1
        tcells[(l["teacher"], pl["day"], pl["period"])] += 1
        per_lesson[l["id"]][pl["day"]].append(pl["period"])
        if (pl["day"], pl["period"]) in closed[l["teacher"]]:
            errors.append(f"{l['teacher']} closed slot used: day {pl['day']} period {pl['period']}")
    for c, h in hours.items():
        for d in range(1, 6):
            for p in range(1, 8):
                n = cells[(c, d, p)]
                if p <= h[d - 1] and n != 1:
                    errors.append(f"{c} day {d} period {p}: {n} lessons")
                if p > h[d - 1] and n:
                    errors.append(f"{c} day {d} period {p}: lesson after end of day")
    errors += [f"{t} double-booked day {d} period {p}" for (t, d, p), n in tcells.items() if n > 1]
    load = collections.Counter(l["teacher"] for l in L.values() for _ in range(l["hours"]))
    tdays = collections.Counter((t, d) for (t, d, p), n in tcells.items() if n)
    errors += [f"{t} one-lesson day {d}" for (t, d), n in tdays.items() if n == 1 and load[t] >= 2]
    for lid, l in L.items():
        blocks = []
        for ps in per_lesson[lid].values():
            ps = sorted(ps)
            if ps != list(range(ps[0], ps[0] + len(ps))):
                errors.append(f"{lid} not one consecutive block on a day")
            blocks.append(len(ps))
        if sorted(blocks, reverse=True) != l["format"]:
            errors.append(f"{lid} format {sorted(blocks, reverse=True)} != {l['format']}")
    return errors


def metrics(data, placement):
    L = {l["id"]: l for l in data["lessons"]}
    lunch = data["school"]["lunch_after_period"]
    tday = collections.defaultdict(lambda: collections.defaultdict(list))
    ldays = collections.defaultdict(lambda: collections.defaultdict(list))
    for pl in placement:
        tday[L[pl["lesson"]]["teacher"]][pl["day"]].append(pl["period"])
        ldays[pl["lesson"]][pl["day"]].append(pl["period"])
    gaps = sum(max(ps) - min(ps) + 1 - len(ps) for dd in tday.values() for ps in dd.values())
    lone = sum(1 for dd in tday.values() for ps in dd.values() if len(ps) == 1)
    neighbour = sum(1 for dd in ldays.values() for d in dd if d + 1 in dd)
    lunch_blocks = sum(1 for dd in ldays.values() for ps in dd.values() if lunch in ps and lunch + 1 in ps)
    tc = collections.defaultdict(lambda: collections.defaultdict(set))
    for lid, dd in ldays.items():
        for d in dd:
            tc[(L[lid]["teacher"], L[lid]["class"])][d].add(lid)
    sameday = sum(len(s) - 1 for dd in tc.values() for s in dd.values() if len(s) > 1)
    peak = sum(max(len(ps) for ps in dd.values()) for dd in tday.values())
    return {"gap hours": gaps, "one-lesson days": lone, "blocks on neighbouring days": neighbour,
            "same teacher+class same day": sameday, "double lessons across lunch": lunch_blocks,
            "sum of teachers' peak day": peak}


def main():
    seconds = float(sys.argv[1]) if len(sys.argv) > 1 else 120
    data = load()
    base = metrics(data, data["progmatic_placement"])
    results = {}
    for variant in (sys.argv[2:] or ["progmatic", "strict"]):
        closed = closed_slots(data, variant)
        status, elapsed, obj, bound, placement = solve(data, variant, seconds)
        print(f"\n=== variant '{variant}': {status} in {elapsed:.1f}s, objective {obj}, bound {bound:.0f}")
        if placement:
            errs = check(data, placement, closed)
            print("independent checker:", "PASS" if not errs else f"FAIL ({len(errs)})")
            for e in errs[:20]:
                print("  ", e)
            results[variant] = metrics(data, placement)
    print(f"\n{'measure':32} {'Progmatic':>10} " + " ".join(f"{v:>10}" for v in results))
    for k in base:
        print(f"{k:32} {base[k]:>10} " + " ".join(f"{r[k]:>10}" for r in results.values()))
    pe = check(data, data["progmatic_placement"], closed_slots(data, "strict"))
    print(f"\nProgmatic vs strict wishes: {len(pe)} violation(s)", pe)


if __name__ == "__main__":
    main()
