// Shared data and helpers for all printouts.
#let d = json(bytes(sys.inputs.data))
#let font = "Libertinus Serif"
#let thin = 0.3pt + luma(90)
#let thick = 1pt + black

#let signature(width: 100%) = {
  set text(size: 8pt)
  grid(
    columns: (1fr, 1fr),
    align: center,
    gutter: 4pt,
    [#if d.valid_from != "" [Geçerlilik tarihi: #d.valid_from]],
    [
      #d.headmaster_title \
      #if d.headmaster != "" [#d.headmaster \ ]
      #v(10pt)
      İmza
    ],
  )
}

// A days x periods grid: rows = periods (with times), columns = days. Rows grow with their content;
// `pad` sets the vertical padding (the minimum row height). cell(day, period) returns content or none.
#let week-grid(cell, size: 8pt, pad: 6pt) = {
  let days = d.days
  let periods = d.periods
  set text(size: size)
  set par(leading: 0.35em)
  table(
    columns: (auto,) + (1fr,) * days.len(),
    align: center + horizon,
    inset: (x: 3pt, y: pad),
    stroke: thin,
    table.header(
      [*Ders*],
      ..days.map(x => [*#x*]),
    ),
    ..periods.enumerate().map(((i, p)) => (
      [*#(i + 1).* #if p.at(0) != "" [#linebreak() #text(size: size * 0.75)[#p.at(0)–#p.at(1)]]],
      ..range(days.len()).map(j => {
        let c = cell(j, i)
        if c == none { [] } else { c }
      }),
    )).flatten(),
  )
}
