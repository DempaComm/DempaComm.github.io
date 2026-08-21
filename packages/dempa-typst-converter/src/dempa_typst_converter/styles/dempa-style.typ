// Shared Typst style for converted DempaComm manuscripts.
// This file handles presentation only. Invalid Tylax syntax must be corrected first.

#let statement-counter = counter(figure.where(kind: "dempa-statement"))

#let dempa_article(
  title: "",
  author: "",
  date: datetime.today().display(),
  body,
) = {
  set document(title: title, author: author)
  set page(paper: "a4", margin: (x: 24mm, y: 24mm))
  set text(lang: "ja", size: 11pt)
  set par(justify: true, leading: 0.75em)

  align(center)[
    #text(size: 2em, weight: "bold")[#title]
    #v(0.8em)
    #text(size: 1.15em)[#author]
    #v(0.5em)
    #date
  ]
  v(1.5em)
  body
}

#let statement(name, body, title: none) = {
  let title-part = if title == none { [] } else { [（#title）] }
  figure(
    kind: "dempa-statement",
    supplement: name,
    numbering: "1",
    outlined: false,
    align(left)[
      #block(width: 100%, above: 0.8em, below: 0.8em)[
        *#name #context statement-counter.display("1").* #title-part #body
      ]
    ],
  )
}

#let definition(body, title: none) = statement([定義], body, title: title)
#let proposition(body, title: none) = statement([命題], body, title: title)
#let theorem(body, title: none) = statement([定理], body, title: title)
#let lemma(body, title: none) = statement([補題], body, title: title)
#let corollary(body, title: none) = statement([系], body, title: title)
#let fact(body, title: none) = statement([事実], body, title: title)
#let example(body, title: none) = statement([例], body, title: title)

#let proof(body) = block(width: 100%, above: 0.5em, below: 0.8em)[
  *証明.* #body #h(1fr) $square.stroked$
]

#let bibliography-entry(number, body) = block(width: 100%, above: 0.25em, below: 0.25em)[
  #grid(columns: (auto, 1fr), column-gutter: 0.5em, [#number.], body)
]
