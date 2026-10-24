"""End-to-end check of answer grading through the OpenAI-compatible path, against a local mock LLM."""
import sys, json, subprocess, time, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from playwright.sync_api import sync_playwright

seen = {}
class Mock(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', '*'); self.send_header('Access-Control-Allow-Headers', '*')
    def do_OPTIONS(self):
        self.send_response(204); self._cors(); self.end_headers()
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        seen['req'] = body
        reply = {'choices': [{'message': {'content': '{"verdict":"correct","feedback":"Right: \\\\(\\\\{-1,4,9\\\\}\\\\) pattern."}'}}]}
        self.send_response(200); self._cors(); self.send_header('content-type', 'application/json'); self.end_headers()
        self.wfile.write(json.dumps(reply).encode())
    def log_message(self, *a): pass

mock = HTTPServer(('127.0.0.1', 8766), Mock); threading.Thread(target=mock.serve_forever, daemon=True).start()
srv = subprocess.Popen([sys.executable, '-m', 'http.server', '8765', '-d', 'site'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
try:
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page()
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.goto('http://localhost:8765/ch01.html'); pg.wait_for_timeout(3000)
        pg.click('#settings-btn')
        pg.select_option('dialog.settings select', 'custom')
        pg.fill('dialog.settings input[placeholder="Base URL"]', 'http://127.0.0.1:8766/v1')
        pg.fill('dialog.settings input[placeholder="model name"]', 'mock-model')
        pg.click('dialog.settings button:has-text("Save")')
        li = pg.locator('#ex-1\\.1-1')
        li.locator('summary').click()
        li.locator('textarea').fill('\\{\\ldots,-11,-6,-1,4,9,14,\\ldots\\}')
        li.locator('button:has-text("Check answer")').click()
        pg.wait_for_timeout(2500)
        result = li.locator('.result').inner_text()
        state = li.get_attribute('data-s')
        sol_btn = li.locator('button:has-text("Show book solution")').is_visible()
        user_msg = seen.get('req', {}).get('messages', [{}, {}])[1].get('content', '')
        print('result:', result[:80].replace('\n', ' '), '| state:', state, '| solution button:', sol_btn, '| errors:', errs or 'none')
        print('grader saw exercise text:', 'Exercise 1:' in user_msg, '| saw book solution:', 'Official solution' in user_msg,
              '| saw group instruction:', 'listing their elements' in user_msg)
        assert state == 'correct' and sol_btn and 'Official solution' in user_msg and 'Exercise 1:' in user_msg and not errs
        print('GRADING E2E OK')
        b.close()
finally:
    srv.terminate(); mock.shutdown()
