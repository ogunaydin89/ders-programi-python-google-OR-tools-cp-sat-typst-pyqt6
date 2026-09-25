// One A4 page per teacher.
#import "common.typ": *

#set page(paper: "a4", margin: 15mm)
#set text(font: font, size: 9pt, lang: "tr")

#for (n, t) in d.teachers.enumerate() {
  if n > 0 { pagebreak() }
  align(center, text(size: 12pt, weight: "bold")[#d.school])
  align(center, text(size: 11pt)[#t.name — Haftalık Ders Programı (#t.total saat)])
  v(8pt)
  week-grid((day, period) => {
    let c = t.cells.at(day * d.periods.len() + period)
    if c != none [*#c.cls* \ #c.name]
  }, size: 9pt, pad: 9pt)
  v(12pt)
  signature()
}
