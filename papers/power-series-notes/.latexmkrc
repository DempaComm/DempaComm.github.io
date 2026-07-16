$latex = 'platex -synctex=1 -halt-on-error -interaction=nonstopmode %O %S';
$dvipdf = 'dvipdfmx %O -o %D %S';
$bibtex = q{bibtex %O %B; perl -pi -e 's/error message/warning message/g' %B.blg; true};
$pdf_mode = 3;
