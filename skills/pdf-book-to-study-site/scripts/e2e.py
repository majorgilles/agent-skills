"""End-to-end check of progress tracking: mark every exercise of section 1.6 correct -> section Mastered, book % > 0."""
import sys, subprocess, time
from playwright.sync_api import sync_playwright

srv = subprocess.Popen([sys.executable, '-m', 'http.server', '8765', '-d', 'site'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
try:
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page()
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.goto('http://localhost:8765/ch01.html'); pg.wait_for_timeout(3000)
        items = pg.locator('.exercises[data-for="1.6"] li.ex')
        n = items.count()
        for i in range(n):
            li = items.nth(i)
            li.locator('summary').click()
            li.locator('button[title="Mark correct"]').click()
        badge = pg.locator('#s1-6 .lvl-badge').inner_text()
        pg.goto('http://localhost:8765/index.html'); pg.wait_for_timeout(1500)
        overall = pg.locator('.overall .pct').inner_text()
        lvl = pg.locator('[data-sec="s1-6"] .lvl').inner_text()
        ch = pg.locator('.toc-ch[data-slug="ch01"] > .pct').inner_text()
        print(f'marked {n} exercises; section badge={badge!r}; toc level={lvl!r}; chapter={ch}; book={overall}; errors={errs or "none"}')
        assert n == 6 and badge == 'Mastered' and lvl == 'Mastered' and overall != '0%' and not errs
        print('E2E OK')
        b.close()
finally:
    srv.terminate()
