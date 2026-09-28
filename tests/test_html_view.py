from __future__ import annotations

import re
import unittest
from html import escape

from dempa_site.site.html_view import rendered_public_html


class PublicHTMLViewTest(unittest.TestCase):
    def test_preserves_mathml_and_prose_while_scoping_search(self) -> None:
        math = '<math display="inline"><mrow><mi>α</mi><mo>&lt;</mo><mn>2</mn></mrow></math>'
        source = (
            '<!DOCTYPE html>\n<html xmlns="http://www.w3.org/1999/xhtml" lang="en" xml:lang="en">'
            '<body><header>自動変換のお知らせ</header><article class="ltx_document">'
            '<h1>題名</h1><div class="ltx_authors">著者</div>'
            '<div class="ltx_dates">変換日</div><p>日本語の本文。' + math + 'が成り立つ。</p>'
            '</article></body></html>'
        )
        result = rendered_public_html(source)
        self.assertIn('lang="ja"', result)
        self.assertNotIn('lang="en"', result)
        self.assertIn('<article class="ltx_document" data-pagefind-body>', result)
        self.assertIn('<div class="ltx_authors" data-pagefind-ignore>', result)
        self.assertIn('<div class="ltx_dates" data-pagefind-ignore>', result)
        self.assertIn(math, result)
        self.assertEqual(re.sub('<[^>]+>', '', source), re.sub('<[^>]+>', '', result))
        self.assertIn('<p>日本語の本文。<span class="math-scroll math-inline" tabindex="-1">', result)
        self.assertIn('</span>が成り立つ。</p>', result)

    def test_nested_equation_tables_have_one_keyboard_scroll_region(self) -> None:
        table = ('<table class="ltx_equationgroup"><tr><td><table class="ltx_equation">'
                 '<tr><td><math display="block"><mi>x</mi></math></td></tr>'
                 '</table></td></tr></table>')
        result = rendered_public_html(table)
        self.assertEqual(1, result.count('class="math-scroll"'))
        self.assertIn('tabindex="-1"', result)
        self.assertNotIn('tabindex="0"', result)
        self.assertIn(table, result)
        self.assertTrue(result.endswith('</table></div>'))

    def test_unwrapped_display_math_gets_a_separate_scroll_region(self) -> None:
        source = '<div><math display="block"><mi>x</mi></math></div>'
        result = rendered_public_html(source)
        self.assertIn('<span class="math-scroll" tabindex="-1"', result)
        self.assertIn('</math></span></div>', result)

    def test_search_anchors_preserve_existing_identifiers(self) -> None:
        source = '<body><h1 id="dempa-heading-1">題名</h1><div id="Lemma1"><h6>補題1</h6></div><h2 id="S2">節2</h2></body>'
        result = rendered_public_html(source)
        self.assertIn('<h6 id="dempa-heading-2">補題1</h6>', result)
        self.assertIn('<div id="Lemma1">', result)
        self.assertIn('<h2 id="S2">節2</h2>', result)
        self.assertIn('<script src="/html-reader.js" defer></script>', result)

    def test_search_heading_labels_keep_math_and_escape_metadata(self) -> None:
        math = '<math alttext="p"><mi>p</mi></math>'
        source = ('<html><head></head><body><h2 id="norm">例 2 (' + math + '-ノルム).</h2>'
                  '<h3><math><mn>0</mn></math>次元 &amp; &quot;例&quot;</h3>'
                  '<h4>通常の見出し</h4></body></html>')
        result = rendered_public_html(source)
        self.assertIn('data-pagefind-meta="heading_html_norm[content]" content="' +
                      escape('例 2 (' + math + '-ノルム).', quote=True) + '"', result)
        self.assertIn(escape('<math><mn>0</mn></math>次元 &amp; &quot;例&quot;', quote=True), result)
        self.assertEqual(2, result.count('data-pagefind-meta='))
        self.assertIn(math, result)
        self.assertEqual(re.sub('<[^>]+>', '', source), re.sub('<[^>]+>', '', result))

    def test_search_math_labels_keep_fractions_exponents_and_resolved_references(self) -> None:
        formula = ('<math alttext="\\frac{x^{n+1}}{2}"><mfrac><msup><mi>x</mi>'
                   '<mrow><mi>n</mi><mo>+</mo><mn>1</mn></mrow></msup><mn>2</mn></mfrac></math>')
        reference = ('<math alttext="\\ref{condition}"><mtext><a href="#condition">'
                     '<span>(1)</span></a></mtext></math>')
        source = '<head></head><h2 id="formula">' + formula + '</h2><h3 id="ref">' + reference + '</h3>'
        result = rendered_public_html(source)
        self.assertIn('content="' + escape(formula, quote=True) + '"', result)
        self.assertIn('content="' + escape(reference, quote=True) + '"', result)
        self.assertIn(formula, result)
        self.assertIn(reference, result)


if __name__ == "__main__":
    unittest.main()
