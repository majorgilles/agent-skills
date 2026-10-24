"""End-to-end check of coding-book support on the synthetic codetest page (needs network for Pyodide/MathJax)."""
import sys, json, shutil, threading, subprocess, time, pathlib
from http.server import BaseHTTPRequestHandler, HTTPServer
from playwright.sync_api import sync_playwright
sys.path.insert(0, 'tools'); import build

out = pathlib.Path('work/codesite'); shutil.rmtree(out, ignore_errors=True); shutil.copytree('site/assets', out / 'assets')
src = pathlib.Path('content/codetest.html').read_text(encoding='utf-8')
js = src.replace('<p>Calling it with 3 prints 14.</p>',
                 '<p>JS:</p><pre class="code" data-lang="javascript"><code>console.log([1, 2, 3].map(x =&gt; x * 2))</code></pre>')
page = build.PAGE.format(title='Code test', book='Code Test Book', book_id='codetest', slug='codetest', prev='', next='', home='', code=build.code_attr(src),
                         body=js.split('\n', 1)[1], license='')
(out / 'codetest.html').write_text(page, encoding='utf-8')
(out / 'outline.json').write_text(json.dumps([build.outline('codetest', src)]), encoding='utf-8')
(out / 'solutions.json').write_text('{}', encoding='utf-8')

seen = {}
class Mock(BaseHTTPRequestHandler):
    def _cors(self): self.send_header('Access-Control-Allow-Origin', '*'); self.send_header('Access-Control-Allow-Headers', '*')
    def do_OPTIONS(self): self.send_response(204); self._cors(); self.end_headers()
    def do_POST(self):
        seen['req'] = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        self.send_response(200); self._cors(); self.send_header('content-type', 'application/json'); self.end_headers()
        self.wfile.write(json.dumps({'choices': [{'message': {'content': '{"verdict":"correct","feedback":"Works."}'}}]}).encode())
    def log_message(self, *a): pass
mock = HTTPServer(('127.0.0.1', 8766), Mock); threading.Thread(target=mock.serve_forever, daemon=True).start()
srv = subprocess.Popen([sys.executable, '-m', 'http.server', '8765', '-d', str(out)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
try:
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.goto('http://localhost:8765/codetest.html'); pg.wait_for_timeout(2000)
        py_block = pg.locator('pre.code[data-lang="python"]').first
        pg.locator('.run-bar button').first.click()
        pg.wait_for_function("document.querySelector('pre.run-out') && /\\d/.test(document.querySelector('pre.run-out').textContent)", timeout=120000)
        block_out = pg.locator('pre.run-out').first.inner_text()
        pg.locator('.run-bar button').nth(1).click(); pg.wait_for_timeout(1500)
        js_out = pg.locator('pre.run-out').nth(1).inner_text()
        li = pg.locator('#ex-1\\.1-1'); li.locator('summary').click()
        is_code = 'code-input' in (li.locator('textarea').get_attribute('class') or '')
        li.locator('textarea').fill('def cube(n):\n    return n ** 3\nprint(cube(3))')
        li.locator('button.run').click(); pg.wait_for_function("document.querySelector('#ex-1\\\\.1-1 pre.run-out').textContent.includes('27')", timeout=30000)
        li.locator('textarea').fill('while True:\n    pass')
        li.locator('button.run').click(); pg.wait_for_function("document.querySelector('#ex-1\\\\.1-1 pre.run-out').textContent.includes('Stopped')", timeout=30000)
        loop_out = li.locator('pre.run-out').inner_text()
        pg.click('#settings-btn'); pg.select_option('dialog.settings select', 'custom')
        pg.fill('dialog.settings input[placeholder="Base URL"]', 'http://127.0.0.1:8766/v1'); pg.fill('dialog.settings input[placeholder="model name"]', 'm')
        pg.click('dialog.settings button:has-text("Save")')
        li.locator('textarea').fill('def cube(n):\n    return n ** 3\nprint(cube(3))')
        li.locator('button:has-text("Check answer")').click()
        pg.wait_for_function("document.querySelector('#ex-1\\\\.1-1').dataset.s === 'correct'", timeout=60000)
        msg = seen['req']['messages'][1]['content']
        print('block:', block_out.strip(), '| js:', js_out.strip(), '| code editor:', is_code, '| loop:', loop_out.strip())
        print('grader got execution result:', 'Actual execution result:\n27' in msg, '| book name in prompt:', 'Code Test Book' in seen['req']['messages'][0]['content'], '| errors:', errs or 'none')
        assert block_out.strip() == '14' and js_out.strip() == '[2,4,6]' and is_code and 'Stopped' in loop_out and 'Actual execution result:\n27' in msg and not errs
        print('CODE E2E OK'); b.close()
finally:
    srv.terminate(); mock.shutdown()
