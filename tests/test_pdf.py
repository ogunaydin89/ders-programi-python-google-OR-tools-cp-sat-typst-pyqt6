from dataclasses import replace

import pytest

from dersprogrami.pdf import OUTPUTS, PrintRefused, build_data, export_all, render
from dersprogrami.solver import SolveOptions, solve

from helpers import load_benchmark


@pytest.fixture(scope="module")
def solved():
    p = load_benchmark("strict")
    r = solve(p, SolveOptions(time_limit=30, seed=3))
    return replace(p, placements=r.placements, valid_from="01.10.2026")


def test_all_printouts_render(solved, tmp_path):
    paths = export_all(solved, tmp_path)
    assert [x.name for x in paths] == list(OUTPUTS.values())
    for x in paths:
        data = x.read_bytes()
        assert data.startswith(b"%PDF") and len(data) > 5000


def test_carsaf_is_one_landscape_page_for_the_benchmark(solved):
    import typst
    from dersprogrami.pdf import TEMPLATES
    import json
    pages = typst.compile(str(TEMPLATES / "carsaf.typ"), root=str(TEMPLATES), format="svg",
                          sys_inputs={"data": json.dumps(build_data(solved), ensure_ascii=False)},
                          ignore_system_fonts=True)
    pages = pages if isinstance(pages, list) else [pages]
    assert len(pages) == 1
    import re
    w, h = (float(x) for x in re.search(rb'viewBox="0 0 ([\d.]+) ([\d.]+)"', pages[0]).groups())
    assert w > h                                   # landscape


def test_data_matches_timetable(solved):
    d = build_data(solved)
    assert len(d["teachers"]) == 17 and len(d["classes"]) == 8
    assert sum(1 for t in d["teachers"] for c in t["cells"] if c) == 280
    assert sum(1 for c in d["classes"] for x in c["cells"] if x) == 280
    assert [t["total"] for t in d["teachers"]] == [solved.teacher_load(t.id) for t in solved.teachers]


def test_refuses_unsolved_or_invalid(solved):
    with pytest.raises(PrintRefused):
        render(replace(solved, placements=()), "carsaf")
    broken = solved.placements[:-1]
    with pytest.raises(PrintRefused) as e:
        render(replace(solved, placements=broken), "carsaf")
    assert "denetimden geçmedi" in str(e.value)
