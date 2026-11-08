import threading
import unittest
import urllib.request
import json
import io
import re
from types import SimpleNamespace
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
import server
import game
from game_service import GameService


class GameTest(unittest.TestCase):
    def test_service_instances_isolate_state_credentials_and_actions(self):
        first, second = GameService(game_test=True), GameService(game_test=True)
        token = first.action(None, {'action': 'join', 'name': 'First'})['token']
        self.assertNotEqual(first.host_pin, second.host_pin)
        self.assertFalse(second.snapshot(token)['known'])
        self.assertIsNone(second.snapshot()['host_name'])
        with self.assertRaises(ValueError):
            second.action(token, {'action': 'test_stage', 'stage': 1, 'bots': 0})
        first.action(token, {'action': 'test_stage', 'stage': 1, 'bots': 0})
        self.assertEqual(first.snapshot(token)['stage'], 1)
        self.assertEqual(second.snapshot()['phase'], 'lobby')
        self.assertNotIn(first.host_pin, json.dumps(first.snapshot(token)))

    def test_service_detaches_snapshots_and_serializes_concurrent_actions(self):
        service = GameService()
        with ThreadPoolExecutor(max_workers=8) as pool:
            tokens = list(pool.map(lambda i: service.action(None, {
                'action': 'join', 'name': str(i)})['token'], range(24)))
        self.assertEqual(len(set(tokens)), 24)
        snapshot = service.snapshot(tokens[0])
        self.assertEqual(len(snapshot['waiting']), 24)
        snapshot['waiting'][0]['name'] = 'Changed outside service'
        snapshot['lobby'].clear()
        current = service.snapshot(tokens[0])
        self.assertEqual(current['waiting'][0]['name'], '0')
        self.assertEqual(len(current['lobby']), 5)

    def test_service_rejects_invalid_actions_before_ticking(self):
        g = game.Game()
        service = GameService(game=g)
        with patch.object(g, 'tick') as tick:
            with self.assertRaises(ValueError):
                service.action(None, [])
            tick.assert_not_called()

    def test_service_ticker_start_stop_and_restart(self):
        g = game.Game()
        service = GameService(game=g)
        ticked = threading.Event()
        self.assertFalse(service.running)
        service.stop()
        with patch.object(g, 'tick', side_effect=ticked.set) as tick:
            try:
                service.start()
                service.start()
                self.assertTrue(service.running)
                self.assertTrue(ticked.wait(1), 'Ticker did not advance the game')
                service.stop()
                self.assertFalse(service.running)
                calls = tick.call_count
                ticked.clear()
                self.assertFalse(ticked.wait(.06), 'Stopped ticker kept advancing')
                self.assertEqual(tick.call_count, calls)
                service.start()
                self.assertTrue(ticked.wait(1), 'Ticker did not restart')
            finally:
                service.stop()

    def test_interactive_game_test_mode(self):
        g = game.Game(game_test=True)
        host = g.act(None, {'action': 'join', 'name': 'Tester'})['token']
        guest = g.act(None, {'action': 'join', 'name': 'Guest'})['token']
        self.assertEqual(g.host, host)
        for stage in range(4):
            for bots in (0, 3):
                g.act(host, {'action': 'test_stage', 'stage': stage, 'bots': bots})
                self.assertEqual(g.stage, stage)
                self.assertEqual(g.phase, 'playing')
                self.assertEqual(len(g.teams), 1)
                self.assertEqual(len(g.teams[0]['members']), bots + 1)
                self.assertIn(host, g.teams[0]['members'])
                self.assertIsNone(g.players[guest]['team'])
                self.assertEqual(g.teams[0]['score'], 0)
                if stage == 1:
                    self.assertEqual(g.teams[0]['order'][0], host)
                g.act(host, {'action': 'pause'})
        g.act(host, {'action': 'test_stage', 'stage': 1, 'bots': 0})
        self.assertFalse(g.paused)
        self.assertTrue(g.public(host)['game_test'])
        with self.assertRaises(ValueError):
            g.act(guest, {'action': 'test_stage', 'stage': 0, 'bots': 0})
        with self.assertRaises(ValueError):
            g.act(host, {'action': 'test_stage', 'stage': 4, 'bots': 0})
        normal = game.Game()
        player = normal.act(None, {'action': 'join', 'name': 'Player'})['token']
        normal.act(player, {'action': 'host', 'pin': normal.pin})
        with self.assertRaises(ValueError):
            normal.act(player, {'action': 'test_stage', 'stage': 0, 'bots': 0})

    def test_invalid_action_schemas_do_not_change_players(self):
        g = game.Game()
        invalid = [None, [], 'join', 1, {}, {'action': []},
                   {'action': 'join', 'name': 123},
                   {'action': 'host', 'pin': None},
                   {'action': 'team', 'team': True},
                   {'action': 'count', 'count': '3'},
                   {'action': 'add_ai', 'team': 1.5},
                   {'action': 'remove_ai'},
                   {'action': 'input', 'key': 'X', 'round': 1},
                   {'action': 'input', 'key': 'S', 'round': False}]
        for data in invalid:
            with self.subTest(data=data), self.assertRaises(ValueError):
                g.act(None, data)
        self.assertEqual(g.players, {})

    def test_http_rejects_invalid_bodies_and_origin(self):
        cases = [(b'[]', {}, 400), (b'null', {}, 400),
                 (b'{', {}, 400),
                 (b'{"action":"team","team":true}', {}, 400),
                 (b'{"action":"join","name":"A"}',
                  {'Origin': 'https://other.example'}, 403)]
        for body, headers, expected in cases:
            with self.subTest(body=body, headers=headers):
                handler = server.Handler.__new__(server.Handler)
                handler.path = '/api/action'
                handler.headers = {'Host': 'localhost', 'Content-Length': str(len(body)), **headers}
                handler.rfile = io.BytesIO(body)
                replies = []
                handler.reply = lambda status, result: replies.append((status, result))
                service = GameService()
                handler.server = SimpleNamespace(service=service)
                handler.do_POST()
                self.assertEqual(service.snapshot()['waiting'], [])
                self.assertEqual(replies[0][0], expected)
                self.assertIn('error', replies[0][1])

    def test_http_responses_release_lock_and_detach_state(self):
        g = game.Game()
        token = g.act(None, {'action': 'join', 'name': 'Original'})['token']
        g.act(token, {'action': 'team', 'team': 0})
        g.act(token, {'action': 'host', 'pin': g.pin})
        g.act(token, {'action': 'start'})
        service = GameService(game=g)
        for path in ('/api/state', '/api/action'):
            handler = server.Handler.__new__(server.Handler)
            handler.path = path
            handler.server = SimpleNamespace(service=service)
            body = b'{"action":"pause"}'
            handler.headers = {'X-Player': token, 'Content-Length': str(len(body))}
            handler.rfile = io.BytesIO(body)
            acquired = threading.Event()

            def mutate():
                service.action(None, {'action': 'join', 'name': 'Concurrent'})
                g.teams[0]['pos'][0] = 9
                acquired.set()

            def reply(status, result):
                worker = threading.Thread(target=mutate, daemon=True)
                worker.start()
                available = acquired.wait(1)
                self.assertTrue(available, 'Network reply held the game lock')
                worker.join(1)
                self.assertEqual(status, 200)
                if path == '/api/state':
                    self.assertEqual(result['teams'][0]['pos'], g.teams[0]['maze_start'])

            handler.reply = reply
            if path == '/api/state':
                handler.do_GET()
            else:
                handler.do_POST()

    def ai_lobby(self):
        g = game.Game()
        clock = [0.0]
        g.now = lambda: clock[0]
        host = g.act(None, {'action': 'join', 'name': '사회자'})['token']
        g.act(host, {'action': 'host', 'pin': g.pin})
        return g, clock, host

    def test_ai_complete_all_stages(self):
        g, clock, host = self.ai_lobby()
        for team, size in enumerate((2, 3, 4, 2, 4)):
            for _ in range(size):
                g.act(host, {'action': 'add_ai', 'team': team})
        for p in g.players.values():
            p['seen'] = -100  # AI remains online without browser polling.
        state = g.public(host)
        self.assertTrue(all(p['ai'] and p['online'] for team in state['lobby'] for p in team))
        self.assertFalse(any(k in json.dumps(state) for k in g.players))
        for stage in range(4):
            g.act(host, {'action': 'start'})
            self.assertEqual(g.stage, stage)
            g.tick()  # Countdown must not generate inputs.
            self.assertTrue(all(t['feedback'] == '준비' for t in g.teams))
            clock[0] = g.start
            for _ in range(45001):
                g.tick()
                if g.phase == 'results':
                    break
                clock[0] += .02
            self.assertEqual(g.phase, 'results')
            self.assertTrue(all(t['finish'] is not None for t in g.teams), stage)
            self.assertTrue(all(len(t['history']) == stage + 1 for t in g.teams))
        g.act(host, {'action': 'reset'})
        self.assertEqual(sum(bool(p.get('ai')) for p in g.players.values()), 15)
        g.act(host, {'action': 'clear_ai'})
        self.assertEqual(list(g.players), [host])

    def test_ai_management_limits_and_authority(self):
        g, clock, host = self.ai_lobby()
        user = g.act(None, {'action': 'join', 'name': '사람'})['token']
        for action in ('add_ai', 'remove_ai', 'clear_ai'):
            with self.assertRaises(ValueError):
                g.act(user, {'action': action, 'team': 0})
        for team in (-1, 5):
            with self.assertRaises(ValueError):
                g.act(host, {'action': 'add_ai', 'team': team})
        g.act(user, {'action': 'team', 'team': 0})
        for _ in range(3):
            g.act(host, {'action': 'add_ai', 'team': 0})
        with self.assertRaises(ValueError):
            g.act(host, {'action': 'add_ai', 'team': 0})
        g.act(host, {'action': 'remove_ai', 'team': 0})
        self.assertEqual(len(g.members(0)), 3)
        self.assertIn(user, g.members(0))
        for _ in range(2):
            g.act(host, {'action': 'add_ai', 'team': 1})
        g.act(host, {'action': 'start'})
        for action in ('add_ai', 'remove_ai', 'clear_ai'):
            with self.assertRaises(ValueError):
                g.act(host, {'action': action, 'team': 0})
        clock[0] = g.start + 1
        before = [t['pos'][:] for t in g.teams]
        g.paused = True
        g.tick()
        self.assertEqual([t['pos'] for t in g.teams], before)
        g.paused = False
        g.act(host, {'action': 'reset'})
        g.act(host, {'action': 'clear_ai'})
        g.act(host, {'action': 'add_ai', 'team': 4})
        g.act(host, {'action': 'count', 'count': 2})
        self.assertTrue(any(p['ai'] for p in g.public(host)['waiting']))
        g.act(host, {'action': 'clear_ai'})
        self.assertEqual(set(g.players), {host, user})

    def test_ai_mixed_team_and_shuffle(self):
        g, clock, host = self.ai_lobby()
        g.act(host, {'action': 'count', 'count': 2})
        user = g.act(None, {'action': 'join', 'name': '사람'})['token']
        g.act(user, {'action': 'team', 'team': 0})
        for team in (0, 1, 1):
            g.act(host, {'action': 'add_ai', 'team': team})
        for p in g.players.values():
            if p.get('ai'):
                p['seen'] = -100
        g.act(host, {'action': 'shuffle'})
        self.assertEqual([len(g.members(i)) for i in range(2)], [2, 2])
        # Restore a known mixed team with the human owning U/D.
        g.act(host, {'action': 'clear_ai'})
        g.act(user, {'action': 'team', 'team': 0})
        for team in (0, 1, 1):
            g.act(host, {'action': 'add_ai', 'team': team})
        g.act(host, {'action': 'start'})
        t = g.teams[0]
        # Find a corridor step for each role, independently of maze shape.
        for axis, human_owned in ((('U', 'D'), True), (('L', 'R'), False)):
            x, y, key = next((x, y, k) for (x, y), distance in t['distances'].items()
                             for k, (dx, dy) in game.DIRECTIONS.items()
                             if distance > 2 and k in axis and t['distances'].get((x + dx, y + dy)) == distance - 1)
            t['pos'] = [x, y]
            clock[0] = max(clock[0] + 1, g.start)
            g.tick()
            if human_owned:
                self.assertEqual(t['pos'], [x, y])
                g.input(user, key, g.round_id)
            dx, dy = game.DIRECTIONS[key]
            self.assertEqual(t['pos'], [x + dx, y + dy])

    def setup_game(self, sizes=(4, 4, 4, 4, 4), host_playing=False):
        g = game.Game()
        clock = [0.0]
        g.now = lambda: clock[0]
        host = g.act(None, {'action': 'join', 'name': '사회자'})['token']
        g.act(host, {'action': 'host', 'pin': g.pin})
        if host_playing:
            g.act(host, {'action': 'team', 'team': 0})
        for team, n in enumerate(sizes):
            for i in range(n - (1 if host_playing and team == 0 else 0)):
                k = g.act(None, {'action': 'join', 'name': f'{team}-{i}'})['token']
                g.act(k, {'action': 'team', 'team': team})
        g.begin()
        return g, clock, host

    def test_all_stages_with_20_players(self, host_playing=False, sizes=(4, 4, 4, 4, 4)):
        g, clock, host = self.setup_game(sizes=sizes, host_playing=host_playing)
        self.assertEqual(len(g.players), sum(sizes) + (0 if host_playing else 1))
        self.assertEqual(g.players[host]['team'], 0 if host_playing else None)
        # Humans solve all three mazes in rotating team order.
        turns = []
        while g.phase == 'playing':
            t = g.teams[g.active_index]
            turns.append((g.maze_lap, t['id'], len(t['maze'])))
            clock[0] = g.start
            for _ in range(1000):
                if t['maze_turn_done']:
                    break
                x, y = t['pos']
                key = next(k for k, (dx, dy) in game.DIRECTIONS.items()
                           if t['distances'].get((x+dx,y+dy)) == t['distances'][(x,y)]-1)
                slot = next(i for i,r in enumerate(g.roles(len(t['members']))) if key in r)
                clock[0] += .15
                g.input(t['members'][slot], key, g.round_id)
            self.assertTrue(t['maze_turn_done'])
            g.tick()
        self.assertEqual(turns, [(lap,t['id'],15+lap*4) for lap in range(3) for t in g.teams])
        self.assertTrue(all(t['maze_done']==3 and t['finish'] is not None for t in g.teams))
        # Same input rules drive all remaining stages with precise AI players.
        for player in g.players.values():
            player['ai'] = True
        for stage in (1,2,3):
            g.begin()
            for _ in range(100000):
                clock[0] += .02
                g.tick()
                if g.phase == 'results':
                    break
            self.assertEqual(g.phase, 'results')
            self.assertTrue(all(t['finish'] is not None for t in g.teams))
            if stage == 1:
                self.assertTrue(all(t['finish']==60 and t['points']==120 for t in g.teams))
            if stage == 2:
                self.assertTrue(all(t['finish']==120 and t['points']==t['jump_count'] for t in g.teams))

    def test_host_can_play_all_stages(self):
        self.test_all_stages_with_20_players(host_playing=True)

    def test_start_play_enrolls_host_and_accepts_input(self):
        g, clock, host = self.ai_lobby()
        g.act(host, {'action': 'start_play'})
        self.assertEqual(g.members(0), [host])
        state = g.public(host)
        self.assertEqual(state['my_team'], state['active_team'])
        self.assertEqual(state['my_slot'], 0)
        clock[0] = g.start
        t = g.teams[0]
        x, y = t['pos']
        key = next(k for k, (dx, dy) in game.DIRECTIONS.items()
                   if t['distances'].get((x+dx, y+dy)) == t['distances'][(x, y)]-1)
        g.act(host, {'action': 'input', 'key': key, 'round': g.round_id})
        self.assertNotEqual(t['pos'], [x, y])

    def test_host_can_take_ai_without_resetting_game(self):
        for stage in range(4):
            with self.subTest(stage=stage):
                g, clock, host = self.ai_lobby()
                g.act(host, {'action': 'add_ai', 'team': 0})
                g.act(host, {'action': 'start'})
                g.stage = stage
                t = g.teams[0]
                bot = t['members'][0]
                # Preserve consumed attempts and prior successes at takeover.
                t['used'][bot] = 0
                t['successes'] = [bot]
                old_round, old_start = g.round_id, g.start
                g.act(host, {'action': 'take_ai'})
                self.assertEqual(t['members'], [host])
                self.assertTrue(all(k == host for k in t['order']))
                self.assertEqual(t['successes'], [host])
                self.assertEqual(t['used'][host], 0)
                self.assertNotIn(bot, g.players)
                self.assertEqual((g.round_id, g.start), (old_round, old_start))
                self.assertEqual(g.public(host)['my_slot'], 0)
                with self.assertRaises(ValueError):
                    g.act(host, {'action': 'take_ai'})

    def test_start_play_preserves_roster_when_full(self):
        g, clock, host = self.ai_lobby()
        g.act(host, {'action': 'count', 'count': 2})
        for team in (0, 1):
            for _ in range(4):
                g.act(host, {'action': 'add_ai', 'team': team})
        with self.assertRaises(ValueError):
            g.act(host, {'action': 'start_play'})
        self.assertEqual(g.phase, 'lobby')
        self.assertIsNone(g.players[host]['team'])
        self.assertEqual([len(g.members(i)) for i in (0, 1)], [4, 4])

    def test_small_rosters_complete_all_stages(self):
        # Drive human inputs through every stage, including the participating host.
        for sizes in ((1,), (2,), (3,), (1, 1), (2, 1), (1, 2), (1, 1, 1), (3, 3)):
            with self.subTest(sizes=sizes):
                self.test_all_stages_with_20_players(host_playing=True, sizes=sizes)

    def test_small_roster_shuffle_and_ai(self):
        self.assertEqual(game.Game().roles(1), [['U', 'D', 'L', 'R']])
        for total in (1, 2, 3):
            with self.subTest(total=total):
                g, clock, host = self.ai_lobby()
                with self.assertRaises(ValueError):
                    g.act(host, {'action': 'start'})
                for _ in range(total):
                    g.act(host, {'action': 'add_ai', 'team': 0})
                g.act(host, {'action': 'shuffle'})
                self.assertEqual(sum(len(g.members(i)) for i in range(g.team_count)), total)
                for stage in range(4):
                    g.act(host, {'action': 'start'})
                    for _ in range(30001):
                        g.tick()
                        if g.phase == 'results':
                            break
                        clock[0] += .02
                    self.assertEqual(g.phase, 'results')
                    self.assertTrue(all(t['finish'] is not None for t in g.teams), stage)

    def test_host_team_management_and_authority(self):
        g, clock, host = self.ai_lobby()
        g.act(host, {'action': 'count', 'count': 2})
        g.act(host, {'action': 'team', 'team': 0})
        for team in (0, 1, 1):
            g.act(host, {'action': 'add_ai', 'team': team})
        state = g.public(host)
        self.assertTrue(state['host'])
        self.assertEqual(len(state['lobby'][0]), 2)
        g.act(host, {'action': 'shuffle'})
        self.assertIsNotNone(g.players[host]['team'])
        self.assertEqual([len(g.members(i)) for i in range(2)], [2, 2])
        g.act(host, {'action': 'start'})
        self.assertIsNotNone(g.public(host)['my_slot'])
        g.act(host, {'action': 'pause'})
        self.assertTrue(g.paused)
        g.act(host, {'action': 'pause'})
        self.assertFalse(g.paused)
        g.act(host, {'action': 'reset'})
        g.act(host, {'action': 'spectate'})
        self.assertEqual(g.host, host)
        self.assertIsNone(g.players[host]['team'])
        g.act(host, {'action': 'count', 'count': 3})
        self.assertEqual(g.team_count, 3)
        # Claiming the host seat does not remove an existing team assignment.
        g.host = None
        g.act(host, {'action': 'team', 'team': 0})
        g.act(host, {'action': 'host', 'pin': g.pin})
        self.assertEqual(g.players[host]['team'], 0)

    def test_balancing_and_authority(self):
        g, clock, host = self.setup_game((2, 3, 4))
        self.assertEqual(g.roles(2), [['U','D'],['L','R']])
        self.assertEqual([t['health'] for t in g.teams], [600,900,1200])
        user = g.teams[0]['members'][0]
        with self.assertRaises(ValueError):
            g.act(user, {'action':'reset'})
        with self.assertRaises(ValueError):
            g.act(user, {'action':'team','team':1})
        clock[0] = g.start+1
        before = g.teams[0]['pos'][:]
        g.input(user, 'R', g.round_id)  # this user only owns U/D
        self.assertEqual(before, g.teams[0]['pos'])
        g.stage = 2
        clock[0] = g.rope_beat(0)
        g.input(user, 'S', g.round_id)
        clock[0] += .19
        g.tick()
        self.assertEqual(g.teams[0]['rope_progress'], .5)
        for i in range(len(g.teams)):
            self.assertEqual(g.active_index, i)
            clock[0] = g.start + g.limit + 1
            g.tick()
        self.assertEqual(g.phase, 'results')

    def test_sequential_turns_countdown_and_stale_inputs(self):
        g, clock, host = self.setup_game((2, 2))
        first, second = g.teams
        clock[0] = g.start
        old_round = g.round_id
        # A waiting team cannot play, even with the current round identifier.
        for key in game.DIRECTIONS:
            for player in second['members']:
                g.input(player, key, old_round)
        self.assertEqual(second['pos'], second['maze_start'])
        self.assertEqual(second['moved'], -100)
        self.assertEqual(g.public(host)['active_team'], first['id'])
        # Complete the first team, then give the next team its own full clock.
        first['maze_turn_done'] = True
        clock[0] += 10
        g.tick()
        self.assertEqual(first['maze_done'], 1)
        self.assertEqual(g.phase, 'playing')
        self.assertEqual(g.active_index, 1)
        self.assertEqual(g.start, clock[0] + 4)
        self.assertNotEqual(g.round_id, old_round)
        before = second['pos'][:]
        for player in second['members']:
            for key in game.DIRECTIONS:
                g.input(player, key, g.round_id)
        self.assertEqual(second['pos'], before)
        clock[0] = g.start
        for player in second['members']:
            for key in game.DIRECTIONS:
                g.input(player, key, old_round)
        self.assertEqual(second['moved'], -100)
        second['maze_turn_done'] = True
        g.tick()
        self.assertEqual(g.phase, 'playing')
        self.assertEqual(g.maze_lap, 1)
        self.assertEqual(g.active_index, 0)

    def test_rope_jump_events_only_for_current_team(self):
        g, clock, host = self.setup_game((2, 2))
        g.stage = 2
        first, second = g.teams
        clock[0] = g.rope_beat(0)
        player = first['members'][0]
        g.input(player, 'S', g.round_id)
        jump_time = first['jumps'][0]
        clock[0] += .01
        g.input(player, 'S', g.round_id)
        g.input(second['members'][0], 'S', g.round_id)
        state = g.public(host)
        self.assertEqual(first['jumps'][0], jump_time)
        self.assertEqual(state['teams'][0]['successes'], [0])
        self.assertEqual(second['jumps'], [-100, -100])

    def test_distinct_balanced_courses_and_rope_patterns(self):
        g, clock, host = self.setup_game()
        layouts = [json.dumps(t['maze']) for t in g.teams]
        self.assertEqual(len(set(layouts)), 5)
        lengths = [t['distances'][tuple(t['maze_start'])] for t in g.teams]
        self.assertEqual(len(set(lengths)), 1)
        self.assertGreaterEqual(lengths[0], 64)
        self.assertTrue(all(len(t['maze']) == 15 for t in g.teams))
        patterns = [tuple(t['rope_pattern']) for t in g.teams]
        self.assertEqual(len(set(patterns)), 5)
        self.assertTrue(all(sorted(p) == sorted(patterns[0]) for p in patterns))
        self.assertTrue(all(60 / gap <= 100 for pattern in patterns for gap in pattern))
        for t in g.teams:
            t['started'] = g.start
            self.assertAlmostEqual(g.rope_beat(23, t) - g.start, 18.72)
            for i in range(1, 16):
                self.assertAlmostEqual(g.rope_beat(i, t) - g.rope_beat(i-1, t), t['rope_pattern'][i % 8])

    def test_maze_has_at_most_three_straight_moves(self):
        g = game.Game()
        for seed in range(100):
            maze = g.make_maze(seed)
            self.assertEqual(maze, g.make_maze(seed))
            self.assertEqual(maze[13][13], 0)
            self.assertIn((1, 1), g.distance_map(maze))
            for lines in (maze, list(zip(*maze))):
                for line in lines:
                    run = 0
                    for cell in line:
                        run = run + 1 if cell == 0 else 0
                        self.assertLessEqual(run, 4, f'Straight corridor exceeds three moves: seed {seed}')

    def test_random_maze_corners_change_each_lap_and_preserve_routes(self):
        g, clock, host = self.setup_game((1, 1, 1, 1, 1))
        seen = {t['id']: [] for t in g.teams}
        for lap in range(3):
            if lap:
                g.prepare_courses(lap)
            lengths = []
            for t in g.teams:
                edge = len(t['maze']) - 1
                start, goal = t['maze_start'], t['goal']
                seen[t['id']].append((start[0] == 1, start[1] == 1))
                self.assertEqual(goal, [edge - start[0], edge - start[1]])
                self.assertEqual(t['maze'][start[1]][start[0]], 0)
                self.assertEqual(t['maze'][goal[1]][goal[0]], 0)
                x, y = start
                distance = t['distances'][(x, y)]
                lengths.append(distance)
                for _ in range(distance):
                    dx, dy = next((dx, dy) for dx, dy in game.DIRECTIONS.values()
                                  if t['distances'].get((x + dx, y + dy)) == t['distances'][(x, y)] - 1)
                    x, y = x + dx, y + dy
                    self.assertEqual(t['maze'][y][x], 0)
                self.assertEqual([x, y], goal)
                self.assertEqual(len(set(t['maze_corners'])), 3)
            self.assertEqual(len(set(lengths)), 1)
        self.assertTrue(all(len(set(corners)) == 3 for corners in seen.values()))

    def test_relay_misses_add_one_second_each_and_patterns_change(self):
        g, clock, host = self.setup_game((2,2))
        g.stage = 1
        t = g.teams[0]
        old = t['patterns'][0][:], t['note_times'][:]
        clock[0] = t['turn_start'] + 3 + t['note_times'][-1] + .21
        g.tick()
        self.assertEqual(t['relay_misses'], 7)
        self.assertEqual(t['relay_done'], 1)
        self.assertNotEqual(t['patterns'][1], old[0])
        self.assertNotEqual(t['note_times'], old[1])
        # No future notes due before race finish; seven misses cost seven seconds.
        t['turn_start'] = g.start + 1000
        clock[0] = g.start + 66.9
        g.tick()
        self.assertIsNone(t['finish'])
        clock[0] = g.start + 67
        g.tick()
        self.assertEqual(t['finish'], 67)
        g.teams[1]['finish'] = 70
        g.end()
        self.assertEqual(t['points'], 113)

    def test_relay_space_key_and_tighter_window(self):
        g, clock, host = self.setup_game((2, 2))
        g.stage = 1
        t = g.teams[0]
        self.assertTrue(all(len(p) == 7 and p.count('S') == 2 for p in t['patterns']))
        t['patterns'][0] = ['S', 'U', 'D', 'L', 'R', 'S', 'U']
        runner = t['order'][0]
        clock[0] = t['turn_start'] + 3
        g.input(runner, 'S', g.round_id)
        self.assertEqual(t['relay_hits'], [0])
        clock[0] += t['note_times'][1] + game.RELAY_WINDOW + .01
        g.input(runner, 'U', g.round_id)
        self.assertTrue(t['relay_bad'])
        self.assertEqual(t['relay_hits'], [0])

    def test_rope_runs_full_two_minutes_and_scores_success_count(self):
        g, clock, host = self.setup_game((2, 2))
        g.phase, g.stage = 'results', 1
        g.begin()
        self.assertEqual(g.limit, 120)
        t = g.teams[0]
        for i in range(30):
            clock[0] = g.rope_beat(i, t)
            for token in t['members']:
                g.input(token, 'S', g.round_id)
            clock[0] += game.ROPE_WINDOW + .001
            g.tick()
        self.assertEqual(t['jump_count'], 60)
        self.assertIsNone(t['finish'])
        self.assertEqual(g.active_index, 0)
        clock[0] = g.start + 120
        g.tick()
        self.assertEqual(t['finish'], 120)
        clock[0] = g.start + 120
        g.tick()
        self.assertEqual(t['points'], 60)
        self.assertEqual(g.teams[1]['points'], 0)

    def test_accelerating_target_damage_and_attempt_limit(self):
        def speed(p):
            return (game.target_position(p+.001)-game.target_position(p))/.001
        self.assertAlmostEqual(speed(.49), 1.5)
        self.assertEqual(game.GOURD_HP, 300)
        self.assertAlmostEqual(game.target_position(.5), .5)
        self.assertAlmostEqual(game.target_position(1.5), .5)
        g, clock, host = self.setup_game((2, 2))
        g.stage = 3
        t = g.teams[0]
        player = t['members'][0]
        clock[0] = g.start + .5*game.GOURD_PERIOD
        g.input(player, 'S', g.round_id)
        self.assertEqual(t['health'], 2*game.GOURD_HP-30)
        g.input(player, 'S', g.round_id)
        self.assertEqual(t['health'], 2*game.GOURD_HP-30)
        # A press outside the outer target consumes the next cycle too.
        clock[0] = g.start + 1.2*game.GOURD_PERIOD
        g.input(player, 'S', g.round_id)
        clock[0] = g.start + 1.5*game.GOURD_PERIOD
        g.input(player, 'S', g.round_id)
        self.assertEqual(t['health'], 2*game.GOURD_HP-30)

    def test_http_tokens_and_twenty_sessions(self):
        httpd = server.GameHTTPServer(('127.0.0.1', 0), GameService())
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        url = f'http://127.0.0.1:{httpd.server_port}'
        try:
            self.assertIn(b'FOURWARD', urllib.request.urlopen(url).read())
            html = urllib.request.urlopen(url).read().decode()
            assets = re.findall(r'(?:src|href)="(/assets/[^\"]+)"', html)
            self.assertTrue(assets)
            for asset in assets:
                response = urllib.request.urlopen(url + asset)
                self.assertEqual(response.status, 200)
                self.assertNotIn('text/html', response.headers['Content-Type'])
            for path in ('/server.py', '/assets/%2e%2e/%2e%2e/server.py'):
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    urllib.request.urlopen(url + path)
                self.assertEqual(caught.exception.code, 404)
            tokens=[]
            for i in range(20):
                req=urllib.request.Request(url+'/api/action', data=json.dumps({'action':'join','name':str(i)}).encode(),headers={'Content-Type':'application/json'})
                tokens.append(json.load(urllib.request.urlopen(req))['token'])
            self.assertEqual(len(set(tokens)),20)
            req=urllib.request.Request(url+'/api/state',headers={'X-Player':tokens[0]})
            data=json.load(urllib.request.urlopen(req))
            self.assertEqual(len(data['waiting']),20)
            self.assertNotIn('pin',data)
            self.assertNotIn(tokens[1],json.dumps(data))
        finally:
            httpd.shutdown()
            httpd.server_close()


if __name__ == '__main__':
    unittest.main()
