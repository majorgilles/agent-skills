import sys, subprocess, time
from playwright.sync_api import sync_playwright
srv = subprocess.Popen([sys.executable, '-m', 'http.server', '8765', '-d', 'site'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
try:
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page(viewport={'width': 900, 'height': 900})
        pg.add_init_script(f"localStorage.setItem('bop-reader-v1', JSON.stringify({{theme: '{sys.argv[2]}', fs: 20}}))")
        pg.goto('http://localhost:8765/' + sys.argv[1]); pg.wait_for_timeout(3500)
        pg.evaluate(f'window.scrollTo(0, {sys.argv[3]})'); pg.wait_for_timeout(400)
        pg.screenshot(path=sys.argv[4]); b.close()
finally:
    srv.terminate()
