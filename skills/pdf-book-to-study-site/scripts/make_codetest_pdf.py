"""Synthetic one-page 'coding book' PDF for testing code-block extraction and the in-browser runner.
  python make_codetest_pdf.py work/codetest.pdf
  BOOK_PDF=work/codetest.pdf python tools/convert.py codetest 0 0 && python e2e_code.py   (remove content/codetest.html after)"""
import sys, pymupdf

d = pymupdf.open(); p = d.new_page(width=504, height=720); y = 100; cw = 0.6 * 9.5   # Courier char width at 9.5 pt


def line(x, s, font='tiro', size=10.9, dy=14):
    global y
    p.insert_text((x, y), s, fontname=font, fontsize=size); y += dy


line(54, 'The following function computes the sum of squares.')
for s in ['def sum_squares(n):', '    total = 0', '    for k in range(1, n + 1):', '        total += k * k', '    return total',
          'print(sum_squares(3))']:
    line(54, s, 'cour', 9.5)                                 # indentation as space characters
y += 10; line(54, 'Calling it with 3 prints 14.'); y += 20
line(54, 'Exercises for Section 1.1', 'tibo', 10.9, 16)
p.insert_text((70, y), '1.', fontname='tibo', fontsize=10); line(88, 'Write a function cube(n) that returns n cubed.', size=10, dy=15)
p.insert_text((70, y), '2.', fontname='tibo', fontsize=10); line(88, 'What does this print?', size=10)
for ind, s in [(0, 'for i in range(2):'), (4, 'print(i % 2)')]:
    line(88 + ind * cw, s, 'cour', 9.5)                      # indentation as x offsets (how real PDFs do it)
d.save(sys.argv[1] if len(sys.argv) > 1 else 'work/codetest.pdf')
