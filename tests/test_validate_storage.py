import json
from dataclasses import replace

import pytest

from dersprogrami import curriculum as cm
from dersprogrami.model import ProjectFileError, SCHEMA_VERSION, project_from_dict, project_to_dict
from dersprogrami.storage import backup_dir, load_project, save_project
from dersprogrami.validate import errors, validate

from helpers import load_benchmark, small_school


def messages(p):
    return [i.message for i in errors(p)]


def test_small_school_is_valid():
    assert messages(small_school()) == []


def test_build_class_lessons_assigns_rehberlik_and_shorts():
    p = small_school()
    reh = [l for l in p.lessons if l.kind == "rehberlik"]
    assert len(reh) == 1 and reh[0].teacher == "T001"
    shorts = {l.name: l.short for l in p.lessons}
    assert shorts["Türkçe"] == "TÜR" and shorts["Din Kültürü ve Ahlak Bilgisi"] == "DKAB"
    assert shorts["Seçmeli Okuma Becerileri"] == "S.OKU" and shorts["Seçmeli Müzik"] == "S.MÜZ"
    assert sum(l.hours for l in p.lessons) == 35


def test_benchmark_is_valid():
    assert messages(load_benchmark()) == []


def test_missing_teacher_and_hour_mismatch():
    p = small_school()
    l0 = p.lessons[0]
    p2 = replace(p, lessons=(replace(l0, teacher=None, hours=l0.hours + 1),) + p.lessons[1:])
    m = " | ".join(messages(p2))
    assert "öğretmen atanmamış" in m and "İkisi eşit olmalı" in m and "yerleşim biçimi" in m


def test_duplicate_teacher_short():
    p = small_school()
    t = p.teachers
    p2 = replace(p, teachers=(replace(t[0], short=t[1].short),) + t[1:])
    assert any("Aynı kısaltma" in m for m in messages(p2))


def test_elective_rules_switch_turns_errors_into_warnings():
    p = small_school()
    bad = tuple(replace(l, name="Seçmeli Robotik Kodlama") if l.name == "Seçmeli Müzik" else l for l in p.lessons)
    p2 = replace(p, lessons=bad)
    assert any("grubundan tam olarak bir ders" in m for m in messages(p2))
    p3 = replace(p2, classes=(replace(p2.classes[0], elective_rules=False),))
    assert messages(p3) == []
    assert any(i.level == "warning" for i in validate(p3))


def test_missing_rehber_teacher():
    p = small_school()
    p2 = replace(p, classes=(replace(p.classes[0], rehber=None),))
    assert any("rehber öğretmen seçilmemiş" in m for m in messages(p2))


def test_format_needing_too_many_days():
    p = small_school()
    l0 = p.lessons[0]
    p2 = replace(p, lessons=(replace(l0, format=(1,) * l0.hours),) + p.lessons[1:])
    assert any("gün gerekir" in m for m in messages(p2))


def test_roundtrip_is_identical(tmp_path):
    for p in (small_school(), load_benchmark(with_placements=True)):
        path = tmp_path / "okul.json"
        save_project(p, path)
        assert load_project(path) == p
        assert project_from_dict(json.loads(json.dumps(project_to_dict(p)))) == p


def test_atomic_save_and_backups(tmp_path):
    path = tmp_path / "okul.json"
    p = small_school()
    for i in range(14):
        save_project(replace(p, valid_from=str(i)), path, backups=10)
    assert load_project(path).valid_from == "13"
    assert len(list(backup_dir(path).iterdir())) == 10
    assert [f.name for f in tmp_path.iterdir() if f.name.endswith(".tmp")] == []


@pytest.mark.parametrize("content, fragment", [
    ("{not json", "bozuk"),
    ('{"schema_version": 1}', "'school' alanı eksik"),
    (json.dumps({"schema_version": SCHEMA_VERSION + 1}), "daha yeni bir sürümüyle"),
    ('[1, 2, 3]', "beklenen yapı"),
])
def test_damaged_files_give_clear_errors(tmp_path, content, fragment):
    path = tmp_path / "okul.json"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ProjectFileError) as e:
        load_project(path)
    assert fragment in str(e.value)


def test_binary_and_missing_files(tmp_path):
    (tmp_path / "x.json").write_bytes(b"\xff\xfe\x00\x81")
    with pytest.raises(ProjectFileError):
        load_project(tmp_path / "x.json")
    with pytest.raises(ProjectFileError):
        load_project(tmp_path / "yok.json")


def test_school_parts_limit_classes():
    p = small_school()
    p2 = replace(p, classes=(replace(p.classes[0], curriculum="anadolu_lisesi"),))
    assert any("bu okul türü tanımlı değil" in m for m in messages(p2))
    assert cm.get("diger").custom
