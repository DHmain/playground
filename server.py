"""LAN HTTP adapter and CLI. Python 3.9+, no third-party dependencies."""
import argparse
import json
import mimetypes
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

from game_service import GameService
from demos.landing.physics import LandingService

ROOT = Path(__file__).resolve().parent


class GameHTTPServer(ThreadingHTTPServer):
    """Each HTTP server owns an explicitly supplied independent game service."""

    def __init__(self, address, service):
        self.service = service
        self.landing = LandingService()
        super().__init__(address, Handler)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def reply(self, status, obj):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        try:
            if self.path == '/api/tutorial/landing/state':
                self.reply(200, self.server.landing.snapshot())
            elif self.path == '/api/state':
                snapshot = self.server.service.snapshot(self.headers.get('X-Player'))
                self.reply(200, snapshot)
            else:
                path = unquote(urlsplit(self.path).path)
                relative = 'index.html' if path in ('/', '/index.html') else path.lstrip('/')
                root = (ROOT / 'dist').resolve()
                asset = (root / relative).resolve()
                if root not in asset.parents or not asset.is_file():
                    self.reply(404, {'error': '찾을 수 없습니다. 프런트엔드 빌드를 확인하세요.'})
                    return
                body = asset.read_bytes()
                mime = mimetypes.guess_type(asset.name)[0] or 'application/octet-stream'
                self.send_response(200)
                self.send_header('Content-Type', mime)
                self.send_header('Cache-Control', 'no-store')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_POST(self):
        tutorial = self.path in ('/api/tutorial/landing/start', '/api/tutorial/landing/input')
        if self.path != '/api/action' and not tutorial:
            self.reply(404, {'error': '찾을 수 없습니다.'})
            return
        try:
            # Reject browser requests initiated from a different web origin.
            origin = self.headers.get('Origin')
            if origin and origin not in ('http://' + self.headers.get('Host', ''), 'https://' + self.headers.get('Host', '')):
                self.reply(403, {'error': '다른 출처의 요청은 허용하지 않습니다.'})
                return
            length = int(self.headers.get('Content-Length', 0))
            if not 0 < length <= 8192:
                raise ValueError('요청 크기가 잘못되었습니다.')
            data = json.loads(self.rfile.read(length))
            if tutorial:
                result = self.server.landing.action(self.path.rsplit('/', 1)[1], data)
            else:
                result = self.server.service.action(self.headers.get('X-Player'), data)
            self.reply(200, result)
        except (ValueError, KeyError, TypeError, IndexError) as e:
            self.reply(400, {'error': str(e)})
        except (BrokenPipeError, ConnectionResetError):
            pass


def main(game_test=False):
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--game-test', action='store_true', default=game_test)
    parser.add_argument('--bind', default=None)
    args = parser.parse_args()
    service = GameService(game_test=args.game_test)
    bind = args.bind or ('127.0.0.1' if args.game_test else '0.0.0.0')
    server = GameHTTPServer((bind, args.port), service)
    addresses = {'127.0.0.1'}
    try:
        addresses.update(socket.gethostbyname_ex(socket.gethostname())[2])
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(('192.0.2.1', 80))  # route selection only; no packet is sent
            addresses.add(s.getsockname()[0])
    except OSError:
        pass
    if bind != '0.0.0.0':
        addresses = {bind}
    print('\n=== FOURWARD / ' + ('GAME TEST' if args.game_test else '4인 협동 운동회') + ' ===', flush=True)
    for ip in sorted(addresses):
        print(f'접속 주소: http://{ip}:{args.port}', flush=True)
    print(f'사회자 PIN: {service.host_pin}\n같은 공유기의 참가자는 서버 PC의 LAN IP로 접속하세요. 종료: Ctrl+C\n', flush=True)
    try:
        service.start()
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        service.stop()
        server.server_close()


if __name__ == '__main__':
    main()
