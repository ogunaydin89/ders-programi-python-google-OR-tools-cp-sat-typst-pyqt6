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

## Fixed

### F1 — The program did not start from the menu
- **Seen:** 2026-09-26, first start from the KDE menu: "No module named dersprogrami".
- **Cause:** the package was never installed into its environment; tests and the self-check added `src/` to the path
  themselves, which hid it. The README install steps had the same gap.
- **Fixed in:** `418d688` (`pip install -e .` in the README, build settings in pyproject, a self-check step and a test
  that start the package without path tricks).
