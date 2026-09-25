import pytest

from dersprogrami import curriculum as cm

# Official totals copied from the charts in sources/ (compulsory incl. Rehberlik and choice lessons).
OFFICIAL = {
    "ortaokul": {"weekly": 35, "compulsory": {5: 30, 6: 30, 7: 30, 8: 29}, "electives": {5: 5, 6: 5, 7: 5, 8: 6}},
    "imam_hatip_ortaokulu": {"weekly": 36, "compulsory": {5: 35, 6: 35, 7: 35, 8: 34},
                             "electives": {5: 1, 6: 1, 7: 1, 8: 2}},
    # Anadolu Lisesi: ortak dersler 32/33/19/15 + Rehberlik 1
    "anadolu_lisesi": {"weekly": 40, "compulsory": {9: 33, 10: 34, 11: 20, 12: 16},
                       "electives": {9: 7, 10: 6, 11: 20, 12: 24}},
    # İmam Hatip: ortak 33/29/12/9 + meslek 6/11/12/10 + Rehberlik 1/0/0/0
    "anadolu_imam_hatip_lisesi": {"weekly": 40, "compulsory": {9: 40, 10: 40, 11: 24, 12: 19},
                                  "electives": {9: 0, 10: 0, 11: 16, 12: 21}},
}


@pytest.mark.parametrize("cid", OFFICIAL)
def test_totals_match_official_charts(cid):
    cur = cm.get(cid)
    off = OFFICIAL[cid]
    for g in cur.grades:
        comp = sum(h for _, _, h, _ in cur.compulsory(g)) + sum(h for _, _, h in cur.choice_lessons(g))
        assert comp == off["compulsory"][g], (cid, g)
        assert cur.elective_hours(g) == off["electives"][g], (cid, g)
        assert comp + cur.elective_hours(g) == off["weekly"] == cur.weekly_total(g)
        assert sum(cur.default_daily_hours(g)) == off["weekly"]


@pytest.mark.parametrize("cid", OFFICIAL)
def test_electives_are_well_formed(cid):
    cur = cm.get(cid)
    groups = cur.elective_groups()
    for g in cur.grades:
        for name, group, options, short in cur.electives(g):
            assert group in groups
            assert options and all(o > 0 for o in options)
            assert short.startswith("S.")


def test_every_curriculum_has_rehberlik_somewhere():
    for cid in OFFICIAL:
        cur = cm.get(cid)
        assert any(is_reh for g in cur.grades for *_, is_reh in cur.compulsory(g))


def test_default_format():
    assert cm.default_format(1) == (1,)
    assert cm.default_format(3) == (2, 1)
    assert cm.default_format(5) == (2, 2, 1)
    assert cm.default_format(6) == (2, 2, 2)
    assert cm.default_format(10) == (2, 2, 2, 2, 2)
    assert cm.default_format(12) == (3, 3, 2, 2, 2)
    for h in range(1, 20):
        f = cm.default_format(h)
        assert sum(f) == h and len(f) <= 5


def test_ortaokul_real_school_choices_are_valid():
    cur = cm.get("ortaokul")
    assert cm.check_electives(cur, 5, [("Okuma Becerileri", 2), ("Ahlak ve Vatandaşlık Eğitimi", 1), ("Müzik", 2)]) == []
    assert cm.check_electives(cur, 7, [("Matematik ve Bilim Uygulamaları", 2), ("Ahlak ve Vatandaşlık Eğitimi", 1),
                                       ("Görgü Kuralları ve Nezaket", 2)]) == []
    assert cm.check_electives(cur, 8, [("Temel Yaşam Becerileri", 2), ("Peygamberimizin Hayatı", 2),
                                       ("Görgü Kuralları ve Nezaket", 2)]) == []


def test_ortaokul_invalid_choices():
    cur = cm.get("ortaokul")
    assert cm.check_electives(cur, 5, [("Okuma Becerileri", 2), ("Robotik Kodlama", 2), ("Müzik", 1)])  # 2x ITB, no DAD
    assert cm.check_electives(cur, 5, [("Okuma Becerileri", 1), ("Ahlak ve Vatandaşlık Eğitimi", 2), ("Müzik", 2)])
    assert cm.check_electives(cur, 7, [("Robotik Kodlama", 2), ("Ahlak ve Vatandaşlık Eğitimi", 1), ("Müzik", 2)])
    assert cm.check_electives(cur, 8, [("Okuma Becerileri", 2)])


def test_lise_group_rules():
    cur = cm.get("anadolu_lisesi")
    ok = [("Seçmeli Matematik", 6), ("Seçmeli Fizik", 4), ("Seçmeli Kimya", 4), ("Seçmeli Biyoloji", 4),
          ("Peygamberimizin Hayatı", 1), ("Spor Eğitimi", 1)]
    assert cm.check_electives(cur, 11, ok) == []
    only_academic = [("Seçmeli Matematik", 6), ("Seçmeli Fizik", 4), ("Seçmeli Kimya", 4), ("Seçmeli Biyoloji", 4),
                     ("Psikoloji", 2)]
    assert any("en az 2" in p for p in cm.check_electives(cur, 11, only_academic))
    nine = [("Astronomi ve Uzay Bilimleri", 2), ("Kur'an-ı Kerim", 2), ("Spor Eğitimi", 3)]
    assert cm.check_electives(cur, 9, nine) == []
    assert cm.check_electives(cur, 9, [("Astronomi ve Uzay Bilimleri", 2), ("Proje Tasarımı ve Uygulamaları", 3),
                                       ("Spor Eğitimi", 2)])


def test_imam_hatip_totals_only():
    assert cm.check_electives(cm.get("anadolu_imam_hatip_lisesi"), 11,
                              [("Seçmeli Matematik", 6), ("Seçmeli Fizik", 4), ("Seçmeli Kimya", 4), ("Ebru", 2)]) == []
    assert cm.check_electives(cm.get("imam_hatip_ortaokulu"), 8, [("Yapay Zeka Uygulamaları", 2)]) == []
    assert cm.check_electives(cm.get("imam_hatip_ortaokulu"), 5, [("Robotik Kodlama", 1), ("Müzik", 1)])


def test_custom_curriculum_has_no_rules():
    assert cm.check_electives(cm.get(cm.CUSTOM_ID), 9, [("Herhangi bir ders", 3)]) == []
