// One A4 page per class, with the lesson list underneath.
#import "common.typ": *

#set page(paper: "a4", margin: 15mm)
#set text(font: font, size: 9pt, lang: "tr")

#for (n, c) in d.classes.enumerate() {
  if n > 0 { pagebreak() }
  align(center, text(size: 12pt, weight: "bold")[#d.school])
  align(center, text(size: 11pt)[#c.label Sınıfı — Haftalık Ders Programı])
  v(8pt)
  week-grid((day, period) => {
    let x = c.cells.at(day * d.periods.len() + period)
    if x != none [*#x.name* \ #text(size: 7pt)[#x.teacher_short]]
  }, size: 8pt, pad: 5pt)
  v(8pt)
  table(
    columns: (1fr, auto, 1fr),
    stroke: thin,
    align: (left, center, left),
    table.header([*Ders*], [*Saat*], [*Öğretmen*]),
    ..c.lessons.map(l => ([#l.name], [#l.hours], [#l.teacher])).flatten(),
  )
  v(8pt)
  signature()
}
