from dersprogrami.shortform import duplicates, lesson_short, teacher_short, tr_upper


def test_turkish_upper_case():
    assert tr_upper("istanbul ılgaz") == "İSTANBUL ILGAZ"


def test_lesson_shorts():
    assert lesson_short("Türkçe") == "TÜR"
    assert lesson_short("Fen Bilimleri") == "FEN"
    assert lesson_short("Beden Eğitimi ve Spor") == "BED"
    assert lesson_short("Bilişim Teknolojileri ve Yazılım") == "BİL"
    assert lesson_short("Kur'an-ı Kerim") == "KUR"
    assert lesson_short("Okuma Becerileri", elective=True) == "S.OKU"
    assert lesson_short("Seçmeli Müzik", elective=True) == "S.MÜZ"
    assert lesson_short("Peygamberimizin Hayatı", elective=True) == "S.PEY"


def test_teacher_shorts():
    assert teacher_short("Ayşe Yılmaz") == "A.YIL"
    assert teacher_short("Mehmet Ali Keskin") == "M.KES"
    assert teacher_short("İlker") == "İLK"


def test_duplicates_are_found_case_insensitively():
    found = duplicates([("a", "A.YIL"), ("b", "a.yıl"), ("c", "B.KAR")])
    assert list(found.values()) == [["a", "b"]]
