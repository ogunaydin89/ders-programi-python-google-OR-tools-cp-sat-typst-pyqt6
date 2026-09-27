# Findings from real use

Problems found while using the program with a real school. Each is fixed only when the user says so.
Planned-but-unbuilt features are listed separately in PLAN.md, section 14.

## Open

### F2 — Lists are not in Turkish alphabetical order
- **Seen:** 2026-09-26, Öğretmenler page: names starting with Ö and İ appear after S (e.g. after "SEDA …").
- **Cause:** lists are sorted by character codes, which put Ç, Ğ, İ, Ö, Ş, Ü after Z.
- **Where:** every sorted list: teachers, classes, assignment matrix rows, Program view list, class lesson lists.
- **Fix:** one Turkish sort key (alphabet A B C Ç D E F G Ğ H I İ J K L M N O Ö P R S Ş T U Ü V Y Z, case-insensitive)
  used by all lists; a test with the Turkish letters.

### F3 — No visible "Yedek al" (backup) command
- **Seen:** 2026-09-26, the user looked for a backup button and found none.
- **Current behaviour:** backups are automatic but invisible: each save copies the previous version into
  `<project>_yedekler/` (last 10 kept); until the first save, work lives only in the recovery file.
- **Fix:** a "Yedek al…" item in the Dosya menu that saves a dated copy anywhere the user chooses (e.g. a USB stick);
  a "Yedekleri göster" item that opens the backup folder; and a reminder in the title bar/status line while the project
  has never been saved.

## Fixed

### F5 — The last project is not reopened on start
- **Seen:** 2026-09-26: after closing and restarting, the program showed an empty project; the user expected their work.
- **Cause:** the program never remembers the open file; it starts empty unless a file is given on the command line.
- **Fix:** remember the last project and reopen it on start (with a clear message if it was moved or deleted); a
  "Son açılanlar" (recent files) list in the Dosya menu; the file name always visible in the title bar.
- **Fixed:** the last project reopens on start (a moved or deleted file is reported in the status line, no crash);
  Dosya → "Son açılanlar" lists the last 8 projects. Tests: `tests/test_ui_persistence.py`.

### F4 — Work entered after a save was lost ("it does not auto save")
- **Seen:** 2026-09-26: after closing and restarting, the work seemed gone. It was mainly F5 (the program starts with
  an empty project instead of reopening the file); the weak spots below are real nonetheless.
- **Checked:** the autosave timer itself works (reproduced on a copy of the file: an edit was written on the next tick).
- **Weak spots that explain it:**
  1. Text fields (names, short forms, school name, …) are applied only on Enter or leaving the field. Typing and then
     closing the window loses the text, and because the project never became "unsaved", closing asks nothing.
  2. Autosave runs only every 60 s and shows nothing, so the user cannot see whether work is saved.
- **Fix:** apply every text field while typing (or at the latest before save/close/autosave); autosave every ~15 s;
  a status line "Kaydedildi 11:23:05" / "Kaydedilmemiş değişiklik var"; a test that types into each field and closes.
- **Fixed:** typing in any field counts as unsaved immediately and is applied before every save, autosave, open,
  new and close, and when switching to another teacher or lesson; autosave every 15 s (quiet: an invalid value being
  typed is kept, never dropped, and the user is told at save/close); a status line shows "Kaydedildi HH:MM:SS",
  "Kaydedilmemiş değişiklik var" or "Proje henüz bir dosyaya kaydedilmedi". Found while fixing: re-reading unchanged
  fields invented changes, so closing asked to save for nothing; fields are now applied only when something was typed.
  Tests: `tests/test_ui_persistence.py`.

### F1 — The program did not start from the menu
- **Seen:** 2026-09-26, first start from the KDE menu: "No module named dersprogrami".
- **Cause:** the package was never installed into its environment; tests and the self-check added `src/` to the path
  themselves, which hid it. The README install steps had the same gap.
- **Fixed in:** `418d688` (`pip install -e .` in the README, build settings in pyproject, a self-check step and a test
  that start the package without path tricks).
