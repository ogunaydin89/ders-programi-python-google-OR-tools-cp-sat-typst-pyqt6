// Master timetable (çarşaf): all teachers x all day/period slots, A4 landscape.
#import "common.typ": *

#set page(paper: "a4", flipped: true, margin: (x: 7mm, top: 8mm, bottom: 10mm),
  footer: context [#set text(size: 6pt); #h(1fr) Sayfa #counter(page).display() / #counter(page).final().first()])
#set text(font: font, size: 6pt, lang: "tr")

#let days = d.days
#let P = d.periods.len()
#align(center, text(size: 9pt, weight: "bold")[#d.school — ÖĞRETMENLERİN HAFTALIK DERS PROGRAMI])
#v(2pt)

#let w = if days.len() * P > 35 { 5.6mm } else { 6.4mm }
#let day-edge(x) = x >= 3 and calc.rem(x - 3, P) == 0

#table(
  columns: (5mm, 1fr, 5mm) + (w,) * (days.len() * P),
  align: center + horizon,
  inset: (x: 0.6pt, y: 1.2pt),
  stroke: (x, y) => (
    left: if x == 3 or day-edge(x) { thick } else { thin },
    top: thin, bottom: thin, right: thin,
  ),
  table.header(
    repeat: true,
    table.cell(rowspan: 2)[*No*], table.cell(rowspan: 2)[*Öğretmen*], table.cell(rowspan: 2)[*Top.*],
    ..days.map(x => table.cell(colspan: P)[*#x*]),
    ..range(days.len() * P).map(i => [*#(calc.rem(i, P) + 1)*]),
  ),
  ..d.teachers.enumerate().map(((n, t)) => (
    [#(n + 1)],
    align(left)[#t.name],
    [#t.total],
    ..t.cells.map(c => if c == none { [] } else [#c.cls \ #c.short]),
  )).flatten(),
)

#v(6pt)
#signature()
