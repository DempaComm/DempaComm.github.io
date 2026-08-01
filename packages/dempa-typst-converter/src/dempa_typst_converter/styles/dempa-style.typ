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

#let statement(name, body) = {
  figure(
    kind: "dempa-statement",
    supplement: name,
    numbering: "1",
    outlined: false,
    align(left)[
      #block(width: 100%, above: 0.8em, below: 0.8em)[
        *#name #context statement-counter.display("1").* #body
      ]
    ],
  )
}

#let definition(body) = statement([定義], body)
#let proposition(body) = statement([命題], body)
#let theorem(body) = statement([定理], body)
#let lemma(body) = statement([補題], body)
#let corollary(body) = statement([系], body)
#let example(body) = statement([例], body)

#let proof(body) = block(width: 100%, above: 0.5em, below: 0.8em)[
  *証明.* #body #h(1fr) $square.stroked$
]
