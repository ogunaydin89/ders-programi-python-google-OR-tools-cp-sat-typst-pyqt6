# Ders Programı — Plan

A desktop school timetabler for Turkish middle and high schools (grades 5–12), meant to replace Alfabe Progmatic: same lesson-distribution power, plus a plain-Turkish explanation whenever no timetable is possible.

Status: **M0–M7 built** (see section 14 for build notes and known gaps). Every decision marked *locked* below was made by the user; do not change it without asking.

---

## 1. Locked decisions

| Topic | Decision |
|---|---|
| Grades | **5–12.** Grades 1–4 are out of scope (class teachers build those timetables themselves). |
| Solver | Google OR-Tools **CP-SAT**. Quality over speed: slower is fine if the result is better. |
| GUI | **PyQt6** desktop app (same toolkit as Comfy Studio, XTTS Studio, EmergePDF). **No browser UI.** |
| PDF | **Typst** templates. |
| Language | Python. App UI in **Turkish only** (no language toggle). |
| Paper | Every printout A4, except teacher handouts: an A5 timetable printed twice on one A4 sheet (upper half and an identical lower half, with a cut line). |
| Teacher load | No daily-hour cap by default. Keep each teacher's lessons as close together as possible (few gaps) while spreading their load evenly across their working days. |
| Hosting | Local folder only (`~/Code/ders-programi-python-google-OR-tools-cp-sat-typst-pyqt6`). Pushed to Codeberg only when mature. |
| Platforms | **Windows 11 is the real target** (school computers). Developed on Gentoo, but tested on Windows 11 from M2 onward. **Delivered as source code only** (no .exe installer: Defender, SmartScreen and Core Isolation block unsigned installers); the README gives exact install and run steps. Linux and macOS keep working. |
| Short forms | **Mandatory for every lesson and teacher**, entered when the lesson or teacher is added. Auto-suggested, freely editable (any form the user prefers), must be unique (section 3). |
| Manual edits | A manual placement that breaks a structural or Mandatory rule is **refused**, with the reason shown. |
| Built-in curricula | Ortaokul (5–8), İmam Hatip Ortaokulu (5–8), Anadolu Lisesi (9–12), Anadolu İmam Hatip Lisesi (9–12), plus **Diğer / Özel** (no built-in lessons; everything entered by hand) for schools running program variants. |
| Elective rules | Enforced by default; a per-class switch turns them into warnings (for program-variant classes). |
| Grades 11–12 electives | Each şube takes one elective package. Students mixed across şubes for electives cannot be modelled (known, accepted limit). |
| School setup | The school settings page asks for school name, headmaster and vice principal names, **school type(s)** and the **grade range** of each type. Mixed schools (e.g. an Anadolu İmam Hatip Lisesi with integrated İmam Hatip Ortaokulu sections) have one entry per type. |
| Custom lessons | The user can add **any lesson with any name and hours to any grade or class.** |
| Electives | Treated exactly like any other lesson (no cross-grade elective blocks, no student-level grouping). |
| Split lessons | **None.** One teacher per lesson; no group splitting (Kur'an-ı Kerim split rules are not used). |
| Free days | **No automatic free-day rule.** A teacher gets a day off only on request, entered as a closed day. Never add a free-day constraint. |
| Distribution | Replicate Progmatic's lesson-distribution model (section 5). |
| Curriculum updates | Handled in later releases (v2+). |
| Good timetable | Every enabled constraint satisfied. |

## 2. Scope

**v1 does:**
- School setup: name, headmaster, vice principal(s), school type(s) and grade range per type.
- Grades and sections (şube) added manually; each class has a curriculum and a grade, limited to the school's types and grade ranges.
- Per class, per weekday: the number of lesson hours that day (e.g. 7-7-7-7-7, 7-7-8-7-7 or 8-8-8-8-8). **Adding a class forces this step:** the daily hours are pre-filled with the default for that curriculum and grade, and the class is not created until the user confirms or changes them.
- Compulsory lessons filled in automatically from the chosen curriculum.
- Elective selection per class, validated against that curriculum's rules (section 4).
- Choice lessons (e.g. "Görsel Sanatlar/Müzik"): the class picks one of the options.
- Custom lessons of any name and hours, for any grade or class.
- Rehberlik ve Yönlendirme auto-assigned to the class's rehber teacher.
- Teacher ↔ lesson ↔ class assignment through an **assignment matrix** (section 7), with each teacher's running hour total and a branş filter.
- One-click closing of any teacher's day or single hour.
- Progmatic-style distribution rules (section 5).
- Explanation of infeasibility (section 6).
- Manual placement and locking of lessons, then solving around them, with guided editing (section 7).
- Minimal-change re-solve for mid-year changes (section 5.3).
- Post-solve quality report and solve controls (section 6).
- Undo/redo, autosave and automatic backups.
- PDF output: master, teacher and class timetables, and A5 teacher handouts with a tebliğ-tebellüğ copy (section 8).

**v1 does not:** grades 1–4, hazırlık (prep) classes as a built-in curriculum, the İmam Hatip program/project variants (B-group programs; İmam Hatip Ortaokulu 40-hour, hafızlık, music and sport programs), Fen and Sosyal Bilimler Lisesi charts, rooms/labs/shared facilities, merged classes (birleştirme), double shifts (sabahçı/öğlenci), split or co-taught lessons, tracking electives across years, importing Progmatic files, web/browser UI, online sync, school-wide closed slots, new-year rollover, nöbet (duty roster), substitution helper, Excel/CSV import, e-Okul export, ek ders calculations, a "max N days, solver picks" teacher rule, boarding-school study hours (etüt), an English UI, student-level elective groups across şubes. Anything missing from the curricula can still be entered with custom lessons.

## 3. Data model

- **School settings:** school name, headmaster name, vice principal name(s), school parts (each = curriculum or Diğer / Özel + grade range, e.g. İmam Hatip Ortaokulu 5–8 and Anadolu İmam Hatip Lisesi 9–12), weekdays (default Mon–Fri), maximum periods per day (default from the school parts: 7 or 8; editable). One shared bell for the whole school: start and end time of each period (printed on the PDFs) and which break is the lunch break (used by R12). Pre-filled default, taken from the user's school (editable):

| Period | Time |
|---|---|
| 1 | 08:30–09:10 |
| 2 | 09:25–10:05 |
| 3 | 10:25–11:05 |
| 4 | 11:20–12:00 |
| Öğle arası | 12:00–12:50 |
| 5 | 12:50–13:30 |
| 6 | 13:45–14:25 |
| 7 | 14:40–15:20 |

An 8th period, when a school has one, is added by the user.
- **Short forms (mandatory):** nothing can be added without one; the app suggests it, the user can edit it, and duplicates are refused. The master printout (çarşaf) uses them.
  - Lessons: first 3 letters in Turkish upper case (Türkçe → TÜR, Matematik → MAT), with fixed exceptions stored in the curriculum files (Din Kültürü ve Ahlak Bilgisi → DKAB). Yabancı Dil uses the language (İngilizce → İNG).
  - Electives: `S.` + first 3 letters (Okuma Becerileri → S.OKU, Peygamberimizin Hayatı → S.PEY). Clashes (Temel Dinî Bilgiler and Temel Yaşam Becerileri both → S.TEM) must be resolved before saving.
  - Teachers: first initial + `.` + first 3 letters of the surname (Ayşe Yılmaz → A.YIL). The suggestion is only a default; any other form is accepted (e.g. first 3 letters of the name + surname initial, AYŞ.Y) as long as it is unique.
  - Classes: grade + section (5-A), automatic.
- **Class (sınıf/şube):** curriculum, grade, section letter, daily hours per weekday, rehber teacher, elective choices, choice-lesson picks, custom lessons.
- **Teacher:** display name, short form, branş (used to filter the assignment matrix), closed slots (per day or per hour), optional per-teacher rule overrides. Teachers with 0 hours stay in the list but are skipped by the solver and the PDFs.
- **Lesson (ders ataması):** class, subject, teacher, weekly hours, distribution format (e.g. `2+2+1`), allowed alternative formats (splitting), optional lesson group.
- **Placement:** lesson block → day + starting period; may be *locked*.
- **Project file:** one human-readable JSON file per school/year, saved and loaded by the app. It contains real names, so it is saved **outside the program folder** (wherever the user chooses) and never enters the repository. It records the curriculum files' version it was built with, so a later curriculum update never silently changes an existing project.
- **Curriculum files:** one data file per curriculum in `data/` (not hard-coded), so later releases only swap files. Each file also holds the default daily hours per grade (e.g. ortaokul 7-7-7-7-7, lise 8-8-8-8-8), used to pre-fill the add-class step.

Validation before solving:
- each class's lesson hours must equal the sum of its daily hours (**error**);
- a class total that differs from the official weekly total (35 ortaokul, 36 İmam Hatip Ortaokulu, 40 lise) is a **warning** only, because custom lessons may change it;
- every lesson must have a teacher;
- every elective choice must satisfy its curriculum's rules (an **error**, or a **warning** for classes whose elective-rules switch is off);
- every class with a Rehberlik lesson must have a rehber teacher.

## 4. Built-in curricula

Official sources (copies in `sources/`):
- Ortaokul: Talim ve Terbiye Kurulu karar no. 04, 09/05/2025 — <https://ttkb.meb.gov.tr/meb_iys_dosyalar/2025_05/16094742_4nolukararilkogretimkurumlariilkokulveortaokulhaftalikderscizelgesi.pdf>
- İmam Hatip Ortaokulu: karar no. 103, 14/10/2025 — <https://dogm.meb.gov.tr/pdf/DersCizelgeleri/IHO_HDC_2025-103_KurulKarari_Uygulamali.pdf>
- Anadolu Lisesi: karar no. 05, 09/05/2025 — <https://ttkb.meb.gov.tr/meb_iys_dosyalar/2025_05/20144001_202505.pdf>
- Anadolu İmam Hatip Lisesi: karar no. 26, 23/07/2025 — <https://ttkb.meb.gov.tr/meb_iys_dosyalar/2025_08/05103624_202526.pdf>

All in force from 2025–2026. Hour notation below: `2` = fixed hours; `1/2`, `2/4`, `3/5` … = the class chooses one of the listed hour options.

### 4.1 Ortaokul (grades 5–8)

**Compulsory lessons**

| Lesson | 5 | 6 | 7 | 8 |
|---|---|---|---|---|
| Türkçe | 6 | 6 | 5 | 5 |
| Matematik | 5 | 5 | 5 | 5 |
| Fen Bilimleri | 4 | 4 | 4 | 4 |
| Sosyal Bilgiler | 3 | 3 | 3 | |
| T.C. İnkılap Tarihi ve Atatürkçülük | | | | 2 |
| Yabancı Dil | 3 | 3 | 4 | 4 |
| Din Kültürü ve Ahlak Bilgisi | 2 | 2 | 2 | 2 |
| Görsel Sanatlar | 1 | 1 | 1 | 1 |
| Müzik | 1 | 1 | 1 | 1 |
| Beden Eğitimi ve Spor | 2 | 2 | 2 | 2 |
| Teknoloji ve Tasarım | | | 2 | 2 |
| Bilişim Teknolojileri ve Yazılım | 2 | 2 | | |
| Rehberlik ve Yönlendirme | 1 | 1 | 1 | 1 |
| **Compulsory total** | 30 | 30 | 30 | 29 |
| Electives | 5 | 5 | 5 | 6 |
| **Weekly total** | 35 | 35 | 35 | 35 |

**Electives**

*İnsan, Toplum ve Bilim*

| Elective | 5 | 6 | 7 | 8 |
|---|---|---|---|---|
| Matematik ve Bilim Uygulamaları | | 2 | 2 | |
| Okuma Becerileri | 2 | 2 | | |
| Yazarlık ve Yazma Becerileri | 1/2 | 1/2 | 1/2 | 2 |
| Yaşayan Diller ve Lehçeler | 2 | 2 | 2 | 2 |
| Yabancı Dil | 2 | 2 | 2 | 2 |
| Çevre Eğitimi ve İklim Değişikliği | | 2 | 2 | 2 |
| "Şehrimiz ..." | 1/2 | 1/2 | 1/2 | 2 |
| Hukuk ve Adalet | | 2 | 2 | 2 |
| Düşünme Eğitimi | | | 1/2 | 2 |
| Robotik Kodlama | 2 | 2 | | |
| Yapay Zeka Uygulamaları | | | 2 | 2 |
| Proje Tasarımı ve Uygulamaları | 1/2 | 1/2 | 1/2 | |
| Okul Temelli Sosyal Sorumluluk Çalışmaları | | 2 | 2 | 2 |
| Medya Okuryazarlığı | | | 2 | 2 |
| Afet Bilinci | 1/2 | 1/2 | 1/2 | |
| Temel Yaşam Becerileri | 1/2 | 1/2 | 1/2 | 2 |
| Türk Sosyal Hayatında Aile | 2 | 2 | 2 | 2 |

*Din, Ahlak ve Değer*

| Elective | 5 | 6 | 7 | 8 |
|---|---|---|---|---|
| Kur'an-ı Kerim | 2 | 2 | 2 | 2 |
| Peygamberimizin Hayatı | 2 | 2 | 2 | 2 |
| Temel Dinî Bilgiler | 2 | 2 | 2 | 2 |
| Kültür ve Medeniyetimize Yön Verenler | 2 | 2 | 2 | 2 |
| Ahlak ve Vatandaşlık Eğitimi | 1/2 | 1/2 | 1/2 | 2 |

*Kültür, Sanat ve Spor*

| Elective | 5 | 6 | 7 | 8 |
|---|---|---|---|---|
| Görgü Kuralları ve Nezaket | 2 | 2 | 2 | 2 |
| Müzik | 1/2 | 1/2 | 1/2 | 2 |
| Spor ve Fizikî Etkinlikler | 2 | 2 | 2 | 2 |
| Oyun ve Oyun Etkinlikleri | 1/2 | 1/2 | 1/2 | |
| Dijital Sanatlar | | 1/2 | 1/2 | |
| Masal ve Destanlarımız | 1/2 | 1/2 | 1/2 | 2 |
| Geleneksel Sanatlar | | 1/2 | 1/2 | |
| Halk Oyunları | 2 | 2 | 2 | 2 |

**Chooser (mandatory, per class)**
- Exactly one elective from each of the three groups.
- Grades 5–7: **2 + 2 + 1** hours. The 1-hour elective must be one marked `1/2` at that grade; any group may supply it.
- Grade 8: **2 + 2 + 2** hours.
- Only electives offered at the class's grade can be chosen.

### 4.2 İmam Hatip Ortaokulu (grades 5–8)

**Compulsory lessons**

| Lesson | 5 | 6 | 7 | 8 |
|---|---|---|---|---|
| Türkçe | 6 | 6 | 5 | 5 |
| Matematik | 5 | 5 | 5 | 5 |
| Fen Bilimleri | 4 | 4 | 4 | 4 |
| Sosyal Bilgiler | 3 | 3 | 3 | |
| T.C. İnkılap Tarihi ve Atatürkçülük | | | | 2 |
| Yabancı Dil | 3 | 3 | 4 | 4 |
| Din Kültürü ve Ahlak Bilgisi | 2 | 2 | 2 | 2 |
| Görsel Sanatlar | 1 | 1 | 1 | 1 |
| Müzik | 1 | 1 | 1 | 1 |
| Beden Eğitimi ve Spor | 2 | 1 | 1 | 1 |
| Teknoloji ve Tasarım | | | 1 | 2 |
| Bilişim Teknolojileri ve Yazılım | 1 | 1 | | |
| Rehberlik ve Yönlendirme | 1 | 1 | 1 | 1 |
| Kur'an-ı Kerim | 2 | 2 | 2 | 2 |
| Arapça | 2 | 2 | 2 | 2 |
| Peygamberimizin Hayatı | 2 | 2 | 2 | 2 |
| Temel Dinî Bilgiler | | 1 | 1 | |
| **Compulsory total** | 35 | 35 | 35 | 34 |
| Electives | 1 | 1 | 1 | 2 |
| **Weekly total** | 36 | 36 | 36 | 36 |

**Electives:** the same three groups and mostly the same courses as the ortaokul list, but almost all at 1 hour (a few offer `1/2` in grade 8). The full list is transcribed into the data file at M1 and checked against the PDF.

**Chooser rules:** electives add up exactly to 1 hour (grades 5–7) or 2 hours (grade 8); only electives offered at that grade, with a listed hour option. The chart sets no per-group minimum.

Default daily hours for 36: the pre-filled default puts the one 8th period on Wednesday (7-7-8-7-7); the user can move it.

### 4.3 Anadolu Lisesi (grades 9–12)

**Compulsory lessons (ortak dersler)**

| Lesson | 9 | 10 | 11 | 12 |
|---|---|---|---|---|
| Türk Dili ve Edebiyatı | 5 | 5 | 5 | 5 |
| Din Kültürü ve Ahlak Bilgisi | 2 | 2 | 2 | 2 |
| Tarih | 2 | 2 | 2 | |
| T.C. İnkılap Tarihi ve Atatürkçülük | | | | 2 |
| Coğrafya | 2 | 2 | | |
| Matematik | 6 | 6 | | |
| Fizik | 2 | 2 | | |
| Kimya | 2 | 2 | | |
| Biyoloji | 2 | 2 | | |
| Felsefe | | 2 | 2 | |
| Birinci Yabancı Dil | 4 | 4 | 4 | 4 |
| Beden Eğitimi ve Spor | 2 | 2 | 2 | |
| Görsel Sanatlar / Müzik *(choice)* | 2 | 2 | 2 | |
| Beden Eğitimi ve Spor / Görsel Sanatlar / Müzik *(choice)* | | | | 2 |
| Sağlık Bilgisi ve Trafik Kültürü | 1 | | | |
| **Compulsory total** | 32 | 33 | 19 | 15 |
| Electives | 7 | 6 | 20 | 24 |
| Rehberlik ve Yönlendirme | 1 | 1 | 1 | 1 |
| **Weekly total** | 40 | 40 | 40 | 40 |

**Electives:** four groups — Akademik Çalışmalar (grades 11–12 only), İnsan–Toplum–Bilim, Din–Ahlak–Değer, Kültür–Sanat–Spor. The full elective list with hour options per grade is long; it is transcribed from the source PDF into the curriculum data file at M1 and checked line by line against the PDF, not copied here.

**Chooser rules:**
- The class's electives must add up exactly to the elective hours for its grade (7 / 6 / 20 / 24).
- Grades 9–10: at least one elective from each of İnsan–Toplum–Bilim, Din–Ahlak–Değer and Kültür–Sanat–Spor.
- Grades 11–12: at least one elective from at least two of those three groups.
- Only electives offered at that grade, with one of their listed hour options.
- The elective Birinci Yabancı Dil and İkinci Yabancı Dil must be different languages from each other (enter the language as part of the lesson name).

### 4.4 Anadolu İmam Hatip Lisesi (grades 9–12, standard İmam Hatip Programı)

**Compulsory lessons (ortak dersler)**

| Lesson | 9 | 10 | 11 | 12 |
|---|---|---|---|---|
| Türk Dili ve Edebiyatı | 5 | 5 | 5 | 5 |
| Tarih | 2 | 2 | 2 | |
| T.C. İnkılap Tarihi ve Atatürkçülük | | | | 2 |
| Coğrafya | 2 | 2 | | |
| Matematik | 6 | 6 | | |
| Fizik | 2 | 2 | | |
| Kimya | 2 | 2 | | |
| Biyoloji | 2 | 2 | | |
| Felsefe | | 2 | 2 | |
| Yabancı Dil | 5 | 2 | 2 | 2 |
| Beden Eğitimi ve Spor / Görsel Sanatlar / Müzik *(choice)* | 2 | 1 | 1 | |
| Sağlık Bilgisi ve Trafik Kültürü | 1 | | | |
| Arapça | 4 | 3 | | |
| **Compulsory total** | 33 | 29 | 12 | 9 |

**Vocational lessons (meslek dersleri)**

| Lesson | 9 | 10 | 11 | 12 |
|---|---|---|---|---|
| Kur'an-ı Kerim | 5 | 4 | 4 | 3 |
| Mesleki Arapça | | | 3 | 2 |
| Temel Dinî Bilgiler | 1 | | | |
| Siyer | | 2 | | |
| Fıkıh | | 2 | | |
| Tefsir | | | 2 | |
| Dinler Tarihi | | | | 1 |
| Hadis | | 2 | | |
| Akaid | | | 1 | |
| Kelam | | | | 2 |
| Hitabet ve Mesleki Uygulama | | | 2 | |
| İslam Kültür ve Medeniyeti | | | | 2 |
| Osmanlı Türkçesi | | 1 | | |
| **Vocational total** | 6 | 11 | 12 | 10 |

| | 9 | 10 | 11 | 12 |
|---|---|---|---|---|
| Electives (A group) | | | 16 | 21 |
| Rehberlik ve Yönlendirme | 1 | | | |
| **Weekly total** | 40 | 40 | 40 | 40 |

**Electives:** A group only (the standard program may not use B group). Groups: Temel İslam Bilimleri, Türk İslam Sanatları, Akademik Çalışmalar, İnsan–Toplum–Bilim, Kültür–Sanat–Spor. Full list transcribed into the data file at M1 and checked against the PDF.

**Chooser rules:** electives must add up exactly to 16 (grade 11) / 21 (grade 12); only electives offered at that grade, with a listed hour option. The chart sets no per-group minimum.

Program/project variants (Fen ve Sosyal Bilimler, Musiki, Spor, Hafızlık etc.) change several hours and add B-group electives; they are not built in; such schools use the Diğer / Özel type or custom lessons with the class's elective-rules switch off.

## 5. Constraints

### 5.1 Structural (always on)

- **S1** A teacher teaches at most one lesson per period.
- **S2** A class has at most one lesson per period.
- **S3** Class day shape: on each day, a class has lessons in exactly periods 1…h (h = that class's hours for the day), with no holes.
- **S4** Every lesson gets exactly its weekly hours.
- **S5** Distribution format: a lesson's hours are placed as the blocks of its format (e.g. `2+2+1`); each block is consecutive periods on one day; at most one block of a lesson per day. The same applies when a class has the same subject as two lesson records (e.g. Yabancı Dil shared by two teachers): all their blocks go on different days. "Same lesson" means an **identical lesson name**: e.g. Türk Dili ve Edebiyatı and Seçmeli Türk Dili ve Edebiyatı are different lessons (the regulation assesses them separately), otherwise grades 11–12 could not fit.
- **S6** Closed teacher slots (day or hour) are never used.
- **S7** Locked placements are kept.

### 5.2 Progmatic-parity rules

Based on the Progmatic 2.1 manual. Each rule has a level: **Off / Preference / Mandatory**. Mandatory rules are hard constraints (and take part in the explanation, section 6); Preference rules are penalties the solver minimises.

- **R1** Teacher maximum hours per day (per-teacher or global value). **Default: Off.**
- **R2** Teacher maximum consecutive hours. **Default: Off.**
- **R3** Teacher gaps (boş saat/pencere): maximum per day and per week; minimise as a preference. **Default: Preference** (keep lessons close together).
- **R4** Blocks of the same lesson not on consecutive days. **Default: Preference.**
- **R5** One teacher's different subjects in the same class on different days. **Default: Preference** (tried, but not forced).
- **R6** Lesson groups: lessons the user groups together go on different days. **Default: Off** (no groups until the user makes them).
- **R7** Balanced daily load for teachers across their working days. **Default: Preference** (spread the load evenly). R3 and R7 pull in slightly different directions; their weights are tuned on the benchmark.
- **R8** Splitting (bölünebilme): a lesson may list alternative formats (e.g. `2` → `1+1`, `4+4+2` → `4+3+3`). The main format is preferred; an alternative is used only when needed and costs a penalty. **Default: Off** (enabled per lesson).

Additional rules (from FET's constraint set; same Off / Preference / Mandatory levels):

- **R9** Teacher minimum hours on a working day: if a teacher comes in, they teach at least N hours (avoids 1-hour days). **Default: Mandatory, N = 2** (one-lesson days must not exist). Exempt automatically, because for them the rule can never be met: teachers whose whole weekly load is below N, and teachers with a single lesson whose format has a block shorter than N (e.g. only one 3-hour lesson as 2+1).
- **R10** Teacher maximum span per day: from their first to their last lesson, at most N periods. **Default: Off.**
- **R11** Preferred or forbidden periods for a lesson or a subject (e.g. BES not in period 1). **Default: Off** (set per lesson).
- **R12** Blocks do not straddle the lunch break. **Default: Preference.**

Default formats by weekly hours (the user can override per lesson): 1 → `1`, 2 → `2`, 3 → `2+1`, 4 → `2+2`, 5 → `2+2+1`, 6 → `2+2+2`, 7 → `2+2+2+1`, 8 → `2+2+2+2`.

### 5.3 Minimal-change re-solve

For mid-year changes (a teacher leaves, a new teacher arrives, hours change): the user starts from the current timetable, makes the change, and asks for a re-solve that **moves as few lessons as possible**. The solver minimises the number of placements that differ from the previous timetable, subject to all rules, and the app shows which lessons moved.

## 6. Explaining "no solution" (key feature; Progmatic lacks it)

Two stages, both reported in plain Turkish:

1. **Pre-check (instant arithmetic, before the solver):**
   - class lesson hours ≠ sum of its daily hours;
   - a teacher's load > their open slots, or > open days × daily cap;
   - a format has more blocks than the class has days, or a block longer than the class's day;
   - a teacher's open slots do not overlap enough with a class's lesson periods;
   - R5 set to Mandatory but a teacher's lessons in one class need more distinct days than the class has (e.g. Türkçe 2+2+2 + Okuma 2 + Yazarlık 1 + Rehberlik 1 = 6 days).
   Example: *"T05: haftalık 21 saat dersi var, ancak kapatılmamış saati 18."*
2. **Solver conflict analysis:** every user-controlled rule instance (each closed slot, each format, each Mandatory rule per teacher/class, each lock) gets an on/off switch (CP-SAT assumption literal). If the model is infeasible, CP-SAT returns a subset of switches responsible; the app shrinks it to a **minimal conflicting set** by re-solving with one switch removed at a time, then lists those rules as sentences and, where possible, which single relaxation fixes it. Example: *"7-A Matematik 2+2+1 yerleşemiyor; 1+1 bölünmeye izin verilirse çözüm var."*

If the time limit runs out before the solver proves either result, the app says so honestly rather than guessing.

Performance note: on large schools, testing thousands of switches one at a time is slow. Test whole rule families first (e.g. all closures of one teacher, all formats of one class), then narrow down inside the guilty families.

**After a successful solve — quality report:** list every Preference-level rule that was not fully met (e.g. "T07: 3 boş saat", "T12: Pazartesi 1 saat"), so a valid timetable can still be judged.

**Solve controls:** time limit; "stop and keep the best so far"; use all CPU cores; keep several alternative solutions and compare them side by side.

## 7. User interface (PyQt6, Turkish)

- **Okul (first page):** school name, headmaster name, vice principal name(s); school type(s), each with its grade range (add another type for mixed schools); weekdays and maximum periods.
- **Sınıflar:** add/remove classes. The add-class dialog asks for curriculum, grade and section, then shows the per-day hours pre-filled with that grade's default and requires confirmation before creating the class. Also per-day hours editing later; rehber teacher; elective chooser and choice-lesson picks with live validation; custom lessons.
- **Öğretmenler:** list; availability grid where clicking a cell closes/opens an hour and clicking a day header closes/opens the whole day; per-teacher overrides.
- **Ders Atama:** an **assignment matrix**: classes across, lessons down, a teacher picked in each cell (list filtered by branş); every teacher's weekly total updates live as cells are filled. Per lesson: format, alternatives, group.
- **Kurallar:** Off / Preference / Mandatory for R1–R12 and their values.
- **Çöz:** solve button, solve controls (section 6), progress, result / quality report / explanation panel, minimal-change re-solve.
- **Program:** master / teacher / class grids. Guided manual editing: when a lesson is picked up, valid cells are highlighted; a move or swap that breaks a structural or Mandatory rule is refused and the reason named; breaking a Preference is allowed and shows up in the quality report; cells can be locked.
- **Yazdır:** PDF export.
- Everywhere: undo/redo, autosave, automatic backups of the project file.

## 8. PDF output (Typst)

- **Master timetable (çarşaf):** all teachers × all day/period slots on A4 landscape, like the Progmatic printout: title "<Okul adı> — ÖĞRETMENLERİN HAFTALIK DERS PROGRAMI", a row number and weekly total hours next to each teacher, each cell showing class and lesson short forms. It continues on a second page only if the teacher rows do not fit.
- **Teacher timetables:** A4, one per teacher.
- **Teacher handouts:** A5 teacher timetable, printed twice on one A4 portrait sheet with a dashed cut line: the lower half goes to the teacher, the identical upper half is the tebliğ-tebellüğ copy (signature and date line for the teacher) that the school keeps.
- **Class timetables:** A4, one per class.
- Every printout shows the period times (from the bell settings) and a "valid from" date entered at export.
- Precise alignment and spacing, embedded font with full Turkish character support.
- Headers show the school name. Signature lines show the title ("Okul Müdürü", "Müdür Yardımcısı") and, if entered on the Okul page, the name. Name fields are optional; left empty, only the title is printed.

## 9. Benchmark and tests

- **Benchmark:** the user's school's current Progmatic timetable (ortaokul, 8 sections 5A–8B, 17 teachers with lessons, 5 days × 7 periods, 280 lesson hours). **Source: the live school pano** (`CLASS_TIMETABLES` in `js/data.js` of the deployed Firebase site, which carries the Progmatic result cell by cell; the Codeberg copy of the pano is an older backup and must not be used). Extracted by script into an **anonymised** project file (teachers T01–T17; no real names in the repo). Progmatic's own placement is kept alongside for comparison (e.g. how often it puts blocks of one lesson on neighbouring days). Success = the solver places all 280 hours with the same assignments and formats, satisfying every enabled rule. Progmatic cannot export its data, so the teachers' closed days/hours (e.g. teachers shared with other schools, requested days off) must be listed by the user; without them the benchmark is easier than the real problem.
- A synthetic high-school instance (Anadolu Lisesi, 40 hours) to test 8-period days and the high-school choosers.
- A synthetic **mixed school**: Anadolu İmam Hatip Lisesi 9–12 (8-8-8-8-8) with integrated İmam Hatip Ortaokulu 5–8 (7-7-8-7-7), teachers shared across both, some teaching both 5th and 12th grades.
- A deliberately broken copy of the benchmark tests the explanations (e.g. over-closed teacher, impossible format).
- Unit tests: curriculum loading, curriculum totals match the official charts, elective chooser rules, validation, pre-checks, PDF generation.
- **Windows 11 check at every milestone:** a short script (install, run tests, one sample solve, one PDF) that the user or an agent runs on the school computer, since Windows cannot be tested from the Gentoo machine.

## 10. Proposed layout

```text
PLAN.md
README.md            install and run steps for any OS (written when code exists)
requirements.txt
sources/             official MEB PDFs the curriculum files are built from
data/
    ortaokul_2025.json
    imam_hatip_ortaokulu_2025.json
    anadolu_lisesi_2025.json
    anadolu_imam_hatip_lisesi_2025.json
src/dersprogrami/
    model.py         data classes, JSON load/save
    curriculum.py    curriculum files, elective and choice-lesson rules
    validate.py      validation and pre-checks
    solver.py        CP-SAT model
    explain.py       conflict analysis → Turkish sentences
    pdf/             Typst templates and export
    ui/              PyQt6 windows
tests/
    fixtures/benchmark_anon.json
```

Virtualenvs, caches and generated PDFs stay out of version control.

## 11. Milestones

0. ✔ **M0 Solver test run:** a throwaway prototype (`spike/`) solves the benchmark (S1–S7 plus the default Preference rules) in both variants, checks the result with an independent checker and compares it with Progmatic's baseline.
1. ✔ **M1 Data:** data model, school setup, the four curriculum files (text extracted from the PDFs in `sources/` by script, then every grade's totals checked automatically against the official totals), electives and choice lessons, custom lessons, validation, JSON save/load.
2. ✔ **M2 Solver core:** S1–S7 on the benchmark, run from the command line.
3. ✔ **M3 Rules:** R1–R12 with Off/Preference/Mandatory; minimal-change re-solve.
4. ✔ **M4 Explanations:** pre-checks, minimal conflict sets, quality report, solve controls.
5. ✔ **M5 PDFs:** master (çarşaf), teacher, class and A5 handout templates.
6. ✔ **M6 PyQt6 UI:** including guided manual editing, undo/redo, autosave and backups.
7. ✔ **M7 Polish:** README with exact install and run steps for Windows 11 (primary), Linux and macOS; then consider Codeberg.

## 12. Reliability

No plan guarantees bug-free software; these rules make sure bugs cannot lose data, freeze the app or produce a timetable that looks valid but is not.

- **Prove the core first (M0):** the real benchmark is solved by a throwaway prototype before anything else is built on the solver.
- **Independent checker:** every timetable the solver produces is re-verified by a separate, deliberately simple checker (written independently of the solver) against every rule before it is shown or printed. If they disagree, printing is refused and the disagreement is reported as a bug.
- **No hangs:** the solver runs in a separate process with a time limit and can always be stopped; every slow step (solving, conflict analysis, PDF export) has a time budget and reports "could not decide in time" instead of waiting forever. The window never freezes.
- **No data loss:** atomic saves (write a temporary file, then swap it in), autosave and backups, validation of every project file on load, and a global crash handler that saves work, writes a log file and shows a Turkish message.
- **Testing:** unit tests; known-answer tests (the benchmark, the mixed İHO + AİHL school, deliberately broken variants); random stress tests (hundreds of generated schools, small, huge, mixed and impossible: the app must never crash, every timetable must pass the checker, and every "no solution" must really have none); the Windows 11 check at every milestone.

## 13. Open questions

- Installing OR-Tools and Typst on the Gentoo machine: prebuilt pip packages vs building from source (decide at M2; show exact commands first). Checked: OR-Tools 9.15, Typst 0.15 and PyQt6 6.11 all publish packages for Python 3.14 on Windows, Linux and macOS.
- README note for Windows: a ZIP downloaded from Codeberg carries the "downloaded from the internet" mark and SmartScreen may block its scripts; use `git clone`, or Properties → Unblock before extracting.
- Class timetable printout of the benchmark school, for cross-checking the transcription.
- Licence note: PyQt6 is GPL, so a shared app must be GPL; PySide6 (LGPL) has a near-identical API if that ever matters.

## 14. Build notes and known gaps

**Decisions made while building** (within the plan, recorded for review):
- PDFs use Typst's built-in Libertinus Serif font with system fonts ignored, so printouts are identical on every OS and nothing extra has to be installed.
- R9 exemption: besides teachers with less than N weekly hours, a teacher whose only lesson has a block shorter than N (e.g. a single 3-hour lesson as 2+1) is exempt, because for them the rule can never be met.
- Adding a school type on the Okul page raises the daily maximum to what that type needs (İHO and lise: 8); the add-class dialog warns if a default day still does not fit.
- Solver speed: redundant "class day total" constraints and CP-SAT linearization level 2. On the benchmark the first valid timetable now comes after 5–18 s in 10 of 10 runs (before: 9–55 s, sometimes none within 60 s).
- Manual editing is click-based (select a lesson, then a green cell); a lesson can move to free cells or swap with a lesson of the same length. Locked lessons never move.

**Known gaps** (planned but not built yet):
- Per-teacher rule overrides (e.g. a different daily maximum for one teacher); rule values are school-wide.
- Side-by-side comparison of alternative timetables in the UI (the solver already keeps the last improving solutions).
- Class day lengths are not yet among the switches the explanation can blame (closed hours, formats, locks and Mandatory rules are).
- Windows 11: not yet run on a real Windows machine; use `tools/selfcheck.py` on the school PC.

