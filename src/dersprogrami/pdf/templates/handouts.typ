// Teacher handouts: the same A5 timetable twice on one A4 sheet. The upper copy is kept by the
// school (tebliğ-tebellüğ), the lower copy goes to the teacher. Cut along the dashed line.
#import "common.typ": *

#set page(paper: "a4", margin: (x: 12mm, y: 8mm))
#set text(font: font, size: 7.5pt, lang: "tr")

#let copy(t) = block(height: 136mm, width: 100%, {
  align(center, text(size: 9.5pt, weight: "bold")[#d.school])
  align(center, text(size: 9pt)[#t.name — Haftalık Ders Programı (#t.total saat)])
  v(4pt)
  week-grid((day, period) => {
    let c = t.cells.at(day * d.periods.len() + period)
    if c != none [*#c.cls* #c.short]
  }, size: 8pt, pad: 3.5pt)
  v(4pt)
  set text(size: 7.5pt)
  grid(
    columns: (1fr, 1fr),
    align: center,
    [
      *Tebliğ Eden* \
      #d.headmaster_title \
      #if d.headmaster != "" [#d.headmaster]
    ],
    [
      *Tebellüğ Eden* \
      #t.name \
      Tarih: ...../...../.......... #h(6pt) İmza:
    ],
  )
})

#for (n, t) in d.teachers.enumerate() {
  if n > 0 { pagebreak() }
  copy(t)
  v(1fr)
  line(length: 100%, stroke: (paint: luma(120), thickness: 0.5pt, dash: "dashed"))
  v(1fr)
  copy(t)
}
