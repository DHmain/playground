"""Standalone four-role landing prototype. No FOURWARD imports or state."""
import argparse
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from physics import DT, ROLES, LandingService

LOCK = threading.Lock()

_service = LandingService()
STATE = _service.state
INPUTS = _service.inputs
reset = _service.reset
step = _service.step
finish = _service.finish


def ticker():
    previous = time.monotonic()
    accumulator = 0.
    while True:
        now = time.monotonic()
        accumulator += min(.1, now - previous)
        previous = now
        with LOCK:
            while accumulator >= DT:
                step(DT)
                accumulator -= DT
        time.sleep(.008)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def reply(self, code, body, mime='application/json; charset=utf-8'):
        self.send_response(code)
        self.send_header('Content-Type', mime)
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self):
        if self.path == '/api/state':
            with LOCK:
                snapshot = dict(STATE)
                now = time.monotonic()
                snapshot['active'] = list({r for (_, r), stamp in INPUTS.items() if now - stamp < .65})
            self.reply(200, json.dumps(snapshot).encode())
        elif self.path in ('/', '/index.html'):
            self.reply(200, Path(__file__).with_name('index.html').read_bytes(), 'text/html; charset=utf-8')
        elif self.path == '/landing.js':
            self.reply(200, Path(__file__).with_name('landing.js').read_bytes(), 'text/javascript; charset=utf-8')
        else:
            self.reply(404, b'{}')

    def do_POST(self):
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 2048:
                raise ValueError()
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise ValueError()
            with LOCK:
                if self.path == '/api/start':
                    reset()
                    STATE['status'] = 'playing'
                elif self.path == '/api/input':
                    client, role, pressed = body.get('client'), body.get('role'), body.get('pressed')
                    if not isinstance(client, str) or not 1 <= len(client) <= 80 or role not in ROLES or type(pressed) is not bool:
                        raise ValueError()
                    if pressed:
                        if len(INPUTS) >= 100 and (client, role) not in INPUTS:
                            raise ValueError()
                        INPUTS[(client, role)] = time.monotonic()
                    else:
                        INPUTS.pop((client, role), None)
                else:
                    self.reply(404, b'{}')
                    return
            self.reply(200, b'{}')
        except (ValueError, TypeError):
            self.reply(400, b'{"error":"invalid request"}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8010)
    parser.add_argument('--bind', default='127.0.0.1')
    args = parser.parse_args()
    reset()
    threading.Thread(target=ticker, daemon=True).start()
    server = ThreadingHTTPServer((args.bind, args.port), Handler)
    server.daemon_threads = True
    print('Landing demo: http://127.0.0.1:%s · bind %s' % (args.port, args.bind), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
