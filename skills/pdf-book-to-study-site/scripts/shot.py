"""Screenshot a page of the local site: python shot.py <path-in-site> <out.png> [width] [scrollY]"""
import sys, subprocess, time
from playwright.sync_api import sync_playwright

srv = subprocess.Popen([sys.executable, '-m', 'http.server', '8765', '-d', 'site'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={'width': int(sys.argv[3]) if len(sys.argv) > 3 else 900, 'height': 1100})
        errors = []
        pg.on('console', lambda m: m.type == 'error' and errors.append(m.text))
        pg.on('pageerror', lambda e: errors.append(str(e)))
        pg.goto('http://localhost:8765/' + sys.argv[1]); pg.wait_for_timeout(4000)
        if len(sys.argv) > 4: pg.evaluate(f'window.scrollTo(0, {sys.argv[4]})'); pg.wait_for_timeout(500)
        pg.screenshot(path=sys.argv[2])
        print('console errors:', errors or 'none')
        b.close()
finally:
    srv.terminate()
