"""Loopback-only test fixture. Diagnostic routes never exist in server.py.

Uses an injected clock to play an entire 20-player event without waiting for
real event time. Browser sessions still use the production UI and API.
"""
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from game import Game, DIRECTIONS
from game_service import GameService
from server import GameHTTPServer, Handler


def play_stage(server):
    service, clock = server.service, server.test_clock
    g = service._game
    if g.phase != 'playing':
        raise ValueError('Expected a playing stage')
    stage = g.stage
    counts = Counter()

    def action(token, key, at):
        clock[0] = at
        service.action(token, {'action': 'input', 'key': key, 'round': g.round_id})
        counts[token] += 1

    while g.phase == 'playing':
        t = g.teams[g.active_index]
        if stage == 0:
            clock[0] = g.start
            while not t['maze_turn_done']:
                x, y = t['pos']
                key = next(key for key, (dx, dy) in DIRECTIONS.items()
                           if t['distances'].get((x + dx, y + dy)) == t['distances'][(x, y)] - 1)
                slot = next(i for i, role in enumerate(g.roles(len(t['members']))) if key in role)
                action(t['members'][slot], key, clock[0] + .15)
            service.tick()
        elif stage == 1:
            for note in sorted(t['relay_notes'], key=lambda note: note['at']):
                if note['at'] >= g.start + 60:
                    break
                owner = t['members'][t['relay_keys'].index(note['key'])]
                action(owner, note['key'], note['at'])
            clock[0] = g.start + 60
            service.tick()
        elif stage == 2:
            end = t['started'] + 120
            while not t['completed'] and g.rope_beat(t['rope_index'], t) < end:
                at = g.rope_beat(t['rope_index'], t)
                for slot, token in enumerate(t['members']):
                    action(token, t['rope_keys'][slot], at)
                clock[0] = min(end, at + .121)
                service.tick()
            if not t['completed']:
                clock[0] = end
                service.tick()
        else:
            events = []
            for slot, token in enumerate(t['members']):
                first = g.start + ((.5 - slot * .23) % 1) * 2
                events.extend((first + cycle * 2, token) for cycle in range(100))
            for at, token in sorted(events):
                if t['finish'] is not None:
                    break
                action(token, 'S', at)
            service.tick()
    assert g.stage == stage and g.phase == 'results'
    assert all(t['finish'] is not None for t in g.teams)
    assert all(len(t['history']) == stage + 1 for t in g.teams)
    return {'stage': stage, 'inputs': sum(counts.values()), 'players_with_inputs': len(counts),
            'teams_finished': len(g.teams), 'simulated_time': round(clock[0], 2),
            'points': [t['points'] for t in g.teams]}


class PlaytestHandler(Handler):
    def do_POST(self):
        if not self.path.startswith('/__test/'):
            return super().do_POST()
        try:
            body = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))))
            with self.server.service._lock:
                if self.path == '/__test/advance':
                    seconds = body['seconds']
                    if type(seconds) not in (float, int) or not 0 <= seconds <= 65:
                        raise ValueError('Invalid time advance')
                    self.server.test_clock[0] += seconds
                    self.server.service.tick()
                    result = self.server.service.snapshot(self.headers.get('X-Player'))
                elif self.path == '/__test/play_stage':
                    result = play_stage(self.server)
                else:
                    raise ValueError('Unknown diagnostic route')
            self.reply(200, result)
        except (ValueError, KeyError, AssertionError) as error:
            self.reply(400, {'error': str(error)})


if __name__ == '__main__':
    g = Game()
    clock = [0.]
    g.now = lambda: clock[0]
    g.pin = 'TEST20'
    server = GameHTTPServer(('127.0.0.1', 8767), GameService(game=g))
    server.RequestHandlerClass = PlaytestHandler
    server.test_clock = clock
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
