"""Theme + text size: pick Sepia and Dark, bump size, reload -> preferences persist and apply before scripts run."""
import sys, subprocess, time
from playwright.sync_api import sync_playwright
srv = subprocess.Popen([sys.executable, '-m', 'http.server', '8765', '-d', 'site'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
try:
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.goto('http://localhost:8765/ch01.html'); pg.wait_for_timeout(2000)
        bg = lambda: pg.evaluate("getComputedStyle(document.body).backgroundColor")
        fs = lambda: pg.evaluate("getComputedStyle(document.body).fontSize")
        pg.click('#settings-btn'); pg.click('dialog.settings .reading button:has-text("Sepia")'); sepia = bg()
        pg.click('dialog.settings .reading button:has-text("Dark")'); dark = bg()
        for _ in range(3): pg.click('dialog.settings .reading button[title="Larger"]')
        big = fs(); pg.click('dialog.settings button:has-text("Close")')
        pg.goto('http://localhost:8765/index.html'); pg.wait_for_timeout(1000)
        after = (pg.evaluate("document.documentElement.dataset.theme"), bg(), fs())
        pg.screenshot(path='work/dark.png')
        print('sepia bg', sepia, '| dark bg', dark, '| size', big, '| after reload on another page', after, '| errors', errs or 'none')
        assert sepia == 'rgb(244, 236, 216)' and dark == 'rgb(23, 23, 22)' and big == '21px' and after == ('dark', dark, '21px') and not errs
        print('READING E2E OK'); b.close()
finally:
    srv.terminate()
