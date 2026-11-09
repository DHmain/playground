"""Authoritative FOURWARD rules, independent of HTTP and service lifecycle."""
import math
import random
import secrets
import time
from collections import deque
from demos.landing.physics import LandingService, ROLES as LANDING_ROLES

DIRECTIONS = {'U': (0, -1), 'D': (0, 1), 'L': (-1, 0), 'R': (1, 0)}
RELAY_MIN_INTERVAL = .5
RELAY_MAX_BPM = 120
RELAY_WINDOW = .16
ROPE_TARGET = 24
ROPE_WINDOW = .12
GOURD_PERIOD = 2.0
GOURD_HP = 300


def target_position(phase):
    p = phase % 1
    if p < .45:
        return p * .425 / .45
    if p <= .55:
        return .425 + (p - .45) * 1.5
    return .575 + (p - .55) * .425 / .45


NAMES = ['협동 미로', '랜덤 리듬 계주', '변속 줄넘기', '박 터뜨리기']


class Game:
    def __init__(self, game_test=False):
        self.game_test = game_test
        self.pin = secrets.token_hex(3).upper()
        self.players = {}
        self.host = None
        self.team_count = 5
        self.phase = 'lobby'
        self.stage = -1
        self.teams = []
        self.paused = False
        self.pause_start = 0
        self.pause_total = 0
        self.epoch = time.monotonic()
        self.start = 0
        self.limit = 180
        self.round_id = 0
        self.ai_serial = 0
        self.active_index = 0
        self.landing = None
        self.landing_end = None
        self.maze = self.make_maze()
        self.distances = self.distance_map()

    def now(self):
        return (self.pause_start if self.paused else time.monotonic()) - self.epoch - self.pause_total

    def make_maze(self, seed=42, size=15):
        # Carve one cell at a time. Four open cells permit at most three
        # consecutive moves, including paths through junctions.
        rng = random.Random(seed)
        for _ in range(128):
            grid = [[1] * size for _ in range(size)]
            grid[1][1] = 0
            stack = [(1, 1)]
            while stack:
                x, y = stack[-1]
                options = []
                for dx, dy in DIRECTIONS.values():
                    nx, ny = x + dx, y + dy
                    if not (1 <= nx < size - 1 and 1 <= ny < size - 1) or not grid[ny][nx]:
                        continue
                    # Attach to one existing cell to retain a connected tree.
                    if sum(not grid[ny + ey][nx + ex] for ex, ey in DIRECTIONS.values()) != 1:
                        continue
                    valid = True
                    for ax, ay in ((1, 0), (0, 1)):
                        run = 1
                        for sign in (-1, 1):
                            xx, yy = nx + sign * ax, ny + sign * ay
                            while 0 <= xx < size and 0 <= yy < size and not grid[yy][xx]:
                                run += 1
                                xx, yy = xx + sign * ax, yy + sign * ay
                        if run > 4:
                            valid = False
                            break
                    if valid:
                        options.append((nx, ny))
                if not options:
                    stack.pop()
                    continue
                nx, ny = rng.choice(options)
                grid[ny][nx] = 0
                stack.append((nx, ny))
            if not grid[size - 2][size - 2] and (1, 1) in self.distance_map(grid):
                return grid
        raise ValueError('미로 생성에 실패했습니다. 다시 시작하세요.')

    def distance_map(self, maze=None):
        maze = self.maze if maze is None else maze
        goal = len(maze) - 2
        d, q = {(goal, goal): 0}, deque([(goal, goal)])
        while q:
            x, y = q.popleft()
            for dx, dy in DIRECTIONS.values():
                p = (x + dx, y + dy)
                if 0 <= p[0] < len(maze) and 0 <= p[1] < len(maze) and not maze[p[1]][p[0]] and p not in d:
                    d[p] = d[(x, y)] + 1
                    q.append(p)
        return d

    def members(self, team):
        return [token for token, p in self.players.items() if p['team'] == team]

    def assigned(self, token):
        if token not in self.players:
            return None
        t = self.players[token]['team']
        return next((x for x in self.teams if x['id'] == t), None)

    def roles(self, n):
        if n == 1:
            return [['U', 'D', 'L', 'R']]
        return [['U', 'D'], ['L', 'R']] if n == 2 else ([['U', 'D'], ['L'], ['R']] if n == 3 else [['U'], ['D'], ['L'], ['R']])

    def rope_beat(self, index, team=None):
        t = self.teams[self.active_index] if team is None else team
        pattern = t['rope_pattern']
        cycles, offset = divmod(index + 1, len(pattern))
        start = self.start if t['started'] is None else t['started']
        return start + cycles * sum(pattern) + sum(pattern[:offset])

    def prepare_courses(self, lap=0):
        # Equal shortest paths, distinct layouts; no route from another team can be reused.
        buckets = {}
        seed = secrets.randbits(48)
        for attempt in range(5000):
            maze = self.make_maze(seed + attempt, 15 + lap * 4)
            distances = self.distance_map(maze)
            length = distances[(1, 1)]
            branches = sum(sum((x + dx, y + dy) in distances for dx, dy in DIRECTIONS.values()) >= 3 for x, y in distances)
            if 64 + lap * 16 <= length <= 100 + lap * 24 and branches >= 2 + lap:
                bucket = buckets.setdefault(length, [])
                if all(maze != item[0] for item in bucket):
                    bucket.append((maze, distances))
                if len(bucket) == len(self.teams):
                    for t, (grid, distance) in zip(self.teams, bucket):
                        edge = len(grid) - 1
                        start, goal = [1, 1], [edge - 1, edge - 1]
                        if lap == 0:
                            t['maze_corners'] = random.sample(range(4), 3)
                        for _ in range(t['maze_corners'][lap]):
                            grid = [list(row) for row in zip(*grid[::-1])]
                            distance = {(edge - y, x): d for (x, y), d in distance.items()}
                            start = [edge - start[1], start[0]]
                            goal = [edge - goal[1], goal[0]]
                        t.update(maze=grid, distances=distance, maze_start=start, goal=goal)
                    return
        raise ValueError('미로 생성에 실패했습니다. 다시 시작하세요.')

    def begin(self, *, skip_tutorial=False):
        needs_tutorial = self.phase == 'lobby' and not skip_tutorial
        if self.phase == 'lobby':
            active = [i for i in range(self.team_count) if self.members(i)]
            if not active or any(not 1 <= len(self.members(i)) <= 4 for i in active):
                raise ValueError('한 개 이상의 조에 참여해 주세요. 각 조는 1~4명으로 진행할 수 있습니다.')
            self.teams = [{'id': i, 'members': self.members(i), 'score': 0, 'history': []} for i in active]
            self.prepare_courses()
            self.stage = 0
        elif self.phase == 'results' and self.stage < 3:
            self.stage += 1
        else:
            raise ValueError('대기실 또는 스테이지 결과 화면에서 시작하세요.')
        self.phase = 'playing'
        self.limit = 120 if self.stage == 2 else 180
        self.maze_lap = 0
        for t in self.teams:
            t.update(pos=t['maze_start'][:], moved=-100, finish=None, progress=0, feedback='준비', health=GOURD_HP * len(t['members']),
                     used={}, successes=[], rope_index=0, rope_progress=0,
                     maze_done=0, maze_elapsed=0, maze_turn_done=False, relay_misses=0, jump_count=0, completed=False, jumps=[-100.0] * len(t['members']), started=None)
            t['relay_keys'] = list(DIRECTIONS)[:len(t['members'])]
            t['relay_notes'] = []
            t['relay_hit_count'] = 0
            t['rope_keys'] = [random.choice((*DIRECTIONS, 'S')) for _ in t['members']]
        patterns = set()
        for t in self.teams:
            while True:
                pattern = [.60, .60, .72, .72, .84, .84, .96, .96]
                random.shuffle(pattern)
                if tuple(pattern) not in patterns:
                    patterns.add(tuple(pattern))
                    t['rope_pattern'] = pattern
                    break
        self.active_index = 0
        if needs_tutorial:
            self.phase, self.stage, self.limit = 'tutorial', -1, 60
            self.activate_landing()
            return
        self.activate_team()

    def landing_roles(self, size):
        if size == 1:
            return [list(LANDING_ROLES)]
        if size == 2:
            return [['left', 'right'], ['up', 'down']]
        if size == 3:
            return [['left'], ['right'], ['up', 'down']]
        return [[role] for role in LANDING_ROLES]

    def activate_landing(self):
        self.start = self.now() + 4
        self.landing = LandingService(clock=self.now)
        self.landing.last = self.start
        self.landing_end = None
        self.teams[self.active_index]['started'] = self.start
        self.round_id += 1

    def landing_input(self, token, role, pressed, round_id):
        if self.phase != 'tutorial' or self.paused or round_id != self.round_id:
            return
        team = self.assigned(token)
        if (team is not self.teams[self.active_index] or self.now() < self.start
                or self.landing.state['status'] not in ('ready', 'playing')):
            return
        slot = team['members'].index(token)
        if role not in self.landing_roles(len(team['members']))[slot]:
            return
        if pressed:
            self.landing.inputs[(token, role)] = self.now()
        else:
            self.landing.inputs.pop((token, role), None)

    def tick_landing(self):
        now = self.now()
        if now < self.start:
            return
        team = self.teams[self.active_index]
        if self.landing.state['status'] == 'ready':
            self.landing.state['status'] = 'playing'
        self.landing.advance()
        s = self.landing.state
        if s['status'] == 'playing':
            # Practice bots only hold the roles they own, using human inputs.
            target = max(.05, min(.95, (7 + (-3 - s['vy']) * 1.5) / 16))
            desired = {'left': s['vx'] > max(-5, min(5, -s['x'] * .3)) + .4,
                       'right': s['vx'] < max(-5, min(5, -s['x'] * .3)) - .4,
                       'up': s['throttle'] <= target + .02,
                       'down': s['throttle'] >= target - .02}
            for slot, token in enumerate(team['members']):
                if self.players[token].get('ai'):
                    for role in self.landing_roles(len(team['members']))[slot]:
                        self.landing_input(token, role, desired[role], self.round_id)
            return
        if self.landing_end is None:
            self.landing_end = now
            team['tutorial_result'] = dict(s)
            team['completed'] = True
        if now - self.landing_end >= 3:
            if self.active_index + 1 < len(self.teams):
                self.active_index += 1
                self.activate_landing()
            else:
                self.landing = None
                self.phase = 'results'
                self.begin()  # stage -1 -> maze, only after every team played

    def new_relay_stream(self, t):
        # Arrival slots cap the total judgment rate at 120 BPM. Travel time is
        # independent, so sorting by spawn time can reverse arrival order.
        notes, bag = [], []
        at = 4.2
        while at + RELAY_WINDOW < self.limit:
            if not bag:
                bag = t['relay_keys'][:]
                random.shuffle(bag)
            travel = random.uniform(1.2, 4.2)
            notes.append({'key': bag.pop(), 'spawn': self.start + at - travel,
                          'at': self.start + at, 'travel': travel, 'status': 'pending'})
            at += random.choice((RELAY_MIN_INTERVAL, .6, .75, 1.))
        notes.sort(key=lambda note: note['spawn'])
        for index, note in enumerate(notes):
            note['id'] = index
        t['relay_notes'] = notes

    def next_rope_keys(self, t):
        t['rope_keys'] = [random.choice([key for key in (*DIRECTIONS, 'S') if key != old])
                          for old in t['rope_keys']]

    def activate_team(self):
        self.start = self.now() + 4
        t = self.teams[self.active_index]
        t['started'] = self.start
        if self.stage == 0:
            t.update(pos=t['maze_start'][:], moved=-100, maze_turn_done=False)
        if self.stage == 1:
            self.new_relay_stream(t)
        t['feedback'] = '준비'
        self.round_id += 1

    def settle(self, t, now):
        if t['finish'] is not None or now < self.start:
            return
        if self.stage == 1:
            for note in sorted(t['relay_notes'], key=lambda note: note['at']):
                deadline = note['at'] + RELAY_WINDOW
                finish = self.start + 60 + t['relay_misses']
                if deadline >= finish or deadline >= now:
                    break
                if note['status'] == 'pending':
                    note['status'] = 'miss'
                    t['relay_misses'] += 1
                    t['feedback'] = 'MISS +1s'
            elapsed = now - self.start
            t['progress'] = min(1, max(0, (elapsed - t['relay_misses']) / 60))
            if elapsed >= 60 + t['relay_misses']:
                t['finish'] = 60 + t['relay_misses']
        if self.stage == 2:
            while now >= self.rope_beat(t['rope_index'], t) + ROPE_WINDOW and t['finish'] is None:
                hit = len(t['successes'])
                t['rope_progress'] += hit / len(t['members'])
                t['jump_count'] += hit
                t['progress'] = min(1, (now - self.start) / 120)
                t['feedback'] = f'{hit}/{len(t["members"])}명 성공 · +{hit / len(t["members"]):.2f}'
                t['successes'] = []
                t['rope_index'] += 1
                self.next_rope_keys(t)
            # Count an accepted final jump even when its judgment window
            # straddles the two-minute cutoff.
            if now >= self.start + 120 and t['successes']:
                hit = len(t['successes'])
                t['jump_count'] += hit
                t['rope_progress'] += hit / len(t['members'])
                t['successes'] = []

    def tick(self):
        if self.phase == 'tutorial':
            if not self.paused:
                self.tick_landing()
            return
        if self.phase != 'playing' or self.paused:
            return
        now = self.now()
        t = self.teams[self.active_index]
        self.settle(t, min(now, self.start + self.limit))
        if self.start <= now < self.start + self.limit:
            self.play_ai(now)
        if self.stage == 0:
            if t['maze_turn_done'] or now >= self.start + self.limit:
                t['maze_elapsed'] += min(now - self.start, self.limit)
                if t['maze_turn_done']:
                    t['maze_done'] += 1
                t['progress'] = t['maze_done'] / 3
                if self.maze_lap == 2:
                    t['completed'] = True
                    if t['maze_done'] == 3:
                        t['finish'] = t['maze_elapsed']
                if self.active_index + 1 < len(self.teams):
                    self.active_index += 1
                    self.activate_team()
                elif self.maze_lap < 2:
                    self.maze_lap += 1
                    self.prepare_courses(self.maze_lap)
                    self.active_index = 0
                    self.activate_team()
                else:
                    self.end()
            return
        if now >= self.start + self.limit or t['finish'] is not None:
            t['completed'] = True
            if self.stage == 2:
                t['finish'] = 120
            elif t['finish'] is None:
                t['feedback'] = '시간 종료'
            if self.active_index + 1 < len(self.teams):
                self.active_index += 1
                self.activate_team()
            else:
                self.end()

    def play_ai(self, now):
        """Temporary practice players use the same input validation as humans."""
        for t in self.teams[self.active_index:self.active_index + 1]:
            if t['finish'] is not None:
                continue
            bots = [k for k in t['members'] if self.players[k].get('ai')]
            if not bots:
                continue
            if self.stage == 0:
                if now - t['moved'] < .3:
                    continue
                x, y = t['pos']
                key = next((k for k, (dx, dy) in DIRECTIONS.items()
                            if t['distances'].get((x + dx, y + dy)) == t['distances'][(x, y)] - 1), None)
                for k in bots:
                    if key in self.roles(len(t['members']))[t['members'].index(k)]:
                        self.input(k, key, self.round_id)
                        break
            elif self.stage == 1:
                for note in t['relay_notes']:
                    if note['status'] == 'pending' and 0 <= now - note['at'] <= RELAY_WINDOW:
                        owner = t['members'][t['relay_keys'].index(note['key'])]
                        if owner in bots:
                            self.input(owner, note['key'], self.round_id)
            elif self.stage == 2:
                if 0 <= now - self.rope_beat(t['rope_index'], t) <= ROPE_WINDOW:
                    for k in bots:
                        self.input(k, t['rope_keys'][t['members'].index(k)], self.round_id)
            elif self.stage == 3:
                for k in bots:
                    phase = (now - self.start) / GOURD_PERIOD + t['members'].index(k) * .23
                    if .5 <= target_position(phase) <= .55:
                        self.input(k, 'S', self.round_id)

    def end(self):
        def key(t):
            if self.stage == 2:
                return (-t['jump_count'],)
            return (0, round(t['finish'], 1)) if t['finish'] is not None else (1, -round(t['progress'], 6))
        ordered = sorted(self.teams, key=key)
        last, rank = None, 0
        for i, t in enumerate(ordered):
            if key(t) != last:
                rank = i + 1
            if self.stage == 2:
                pts = t['jump_count']
            elif self.stage == 1:
                pts = max(0, round(180 - t['finish'], 1)) if t['finish'] is not None else 0
            else:
                pts = [100, 80, 60, 40, 20][rank - 1]
            t['rank'], t['points'] = rank, pts
            t['score'] += pts
            t['history'].append({'stage': self.stage, 'rank': rank, 'points': pts, 'finish': t['finish']})
            last = key(t)
        self.phase = 'results'

    def input(self, token, key, round_id):
        if self.phase != 'playing' or self.paused or round_id != self.round_id:
            return
        t, now = self.assigned(token), self.now()
        if not t or t is not self.teams[self.active_index] or t['finish'] is not None or now < self.start or now >= self.start + self.limit or (self.stage == 0 and t['maze_turn_done']):
            return
        # All timing is server receipt time; client clocks cannot choose a score.
        if self.stage == 0:
            role = self.roles(len(t['members']))[t['members'].index(token)]
            if key not in role or now - t['moved'] < .12:
                return
            t['moved'] = now
            dx, dy = DIRECTIONS[key]
            x, y = t['pos'][0] + dx, t['pos'][1] + dy
            if not t['maze'][y][x]:
                t['pos'] = [x, y]
                t['progress'] = (t['maze_done'] + max(0, 1 - t['distances'][(x, y)] / t['distances'][tuple(t['maze_start'])])) / 3
                if [x, y] == t['goal']:
                    t['maze_turn_done'] = True
            t['feedback'] = self.players[token]['name'] + ' ' + key
        elif self.stage == 1:
            self.settle(t, now)
            if t['finish'] is not None:
                return
            assigned = t['relay_keys'][t['members'].index(token)]
            if key != assigned:
                return
            candidates = [note for note in t['relay_notes']
                          if note['key'] == assigned and note['status'] == 'pending'
                          and note['spawn'] <= now and abs(now - note['at']) <= RELAY_WINDOW]
            if candidates:
                note = min(candidates, key=lambda note: abs(now - note['at']))
                note['status'] = 'hit'
                t['relay_hit_count'] += 1
                t['feedback'] = 'HIT ' + self.players[token]['name']
        elif self.stage == 2:
            self.settle(t, now)
            idx = t['rope_index']
            if t['used'].get(token) == idx:
                return
            # One attempt per rope cycle, including an early/late miss.
            t['used'][token] = idx
            t['jumps'][t['members'].index(token)] = now
            if key == t['rope_keys'][t['members'].index(token)] and abs(now - self.rope_beat(idx, t)) <= ROPE_WINDOW:
                t['successes'].append(token)
                t['feedback'] = self.players[token]['name'] + ' 점프 성공'
            else:
                t['feedback'] = self.players[token]['name'] + ' MISS'
        elif self.stage == 3 and key == 'S':
            i = t['members'].index(token)
            phase = (now - self.start) / GOURD_PERIOD + i * .23
            cycle = math.floor(phase)
            if t['used'].get(token) == cycle:
                return
            t['used'][token] = cycle
            error = abs(target_position(phase) - .5)
            damage = 30 if error <= .018 else 20 if error <= .05 else 10 if error <= .09 else 0
            t['health'] = max(0, t['health'] - damage)
            t['progress'] = 1 - t['health'] / (GOURD_HP * len(t['members']))
            t['feedback'] = self.players[token]['name'] + (' MISS' if not damage else f' 명중! −{damage}')
            if t['health'] == 0:
                t['finish'] = now - self.start

    def act(self, token, data):
        self.validate_action(data)
        action = data.get('action')
        if action == 'join':
            name = str(data.get('name', '')).strip()[:24]
            if not name:
                raise ValueError('이름을 입력하세요.')
            if len(self.players) >= 80:
                raise ValueError('입장 가능한 인원을 초과했습니다.')
            token = secrets.token_urlsafe(24)
            self.players[token] = {'name': name, 'team': None, 'seen': time.monotonic()}
            if self.game_test and self.host is None:
                self.host = token
                self.players[token]['team'] = 0
            return {'token': token}
        if token not in self.players:
            raise ValueError('다시 입장해 주세요.')
        p = self.players[token]
        if action == 'test_stage':
            if not self.game_test or token != self.host:
                raise ValueError('게임 테스트 모드의 사회자만 사용할 수 있습니다.')
            if not 0 <= data['stage'] <= 3 or not 0 <= data['bots'] <= 3:
                raise ValueError('스테이지 또는 AI 인원이 잘못되었습니다.')
            self.act(token, {'action': 'reset'})
            self.act(token, {'action': 'clear_ai'})
            for player in self.players.values():
                player['team'] = None
            p['team'] = 0
            for _ in range(data['bots']):
                self.act(token, {'action': 'add_ai', 'team': 0})
            self.begin(skip_tutorial=True)
            if data['stage']:
                self.phase = 'results'
                self.stage = data['stage'] - 1
                self.begin()
            return {'ok': True}
        if action == 'host':
            if self.phase != 'lobby' or self.host not in (None, token):
                raise ValueError('사회자는 대기실에서 한 명만 설정할 수 있습니다.')
            if not secrets.compare_digest(str(data.get('pin', '')).upper(), self.pin):
                raise ValueError('사회자 PIN이 일치하지 않습니다.')
            self.host = token
        elif action in ('team', 'spectate'):
            if self.phase != 'lobby':
                raise ValueError('경기 중에는 조를 변경할 수 없습니다.')
            if action == 'spectate':
                p['team'] = None
            else:
                i = int(data['team'])
                if not 0 <= i < self.team_count or (p['team'] != i and len(self.members(i)) >= 4):
                    raise ValueError('해당 조에 참여할 수 없습니다. 빈자리가 있는 조를 선택하세요.')
                p['team'] = i
        elif action in ('shuffle', 'count', 'start', 'start_play', 'take_ai', 'pause', 'reset', 'add_ai', 'remove_ai', 'clear_ai'):
            if token != self.host:
                raise ValueError('사회자만 사용할 수 있습니다.')
            if action in ('shuffle', 'count', 'add_ai', 'remove_ai', 'clear_ai') and self.phase != 'lobby':
                raise ValueError('대기실에서만 변경할 수 있습니다.')
            if action == 'add_ai':
                i = int(data['team'])
                if not 0 <= i < self.team_count or len(self.members(i)) >= 4:
                    raise ValueError('빈자리가 있는 조를 선택하세요.')
                if len(self.players) >= 80:
                    raise ValueError('입장 가능한 인원을 초과했습니다.')
                self.ai_serial += 1
                self.players[secrets.token_urlsafe(24)] = {
                    'name': f'AI {self.ai_serial}', 'team': i, 'seen': time.monotonic(), 'ai': True}
            elif action in ('remove_ai', 'clear_ai'):
                team = int(data['team']) if action == 'remove_ai' else None
                if action == 'remove_ai' and not 0 <= team < self.team_count:
                    raise ValueError('올바른 조를 선택하세요.')
                candidates = [k for k, q in self.players.items()
                              if q.get('ai') and (action == 'clear_ai' or q['team'] == team)]
                for k in (candidates[-1:] if action == 'remove_ai' else candidates):
                    del self.players[k]
            elif action == 'count':
                n = int(data['count'])
                if not 2 <= n <= 5:
                    raise ValueError('2~5개 조를 선택하세요.')
                self.team_count = n
                for q in self.players.values():
                    if q['team'] is not None and q['team'] >= n:
                        q['team'] = None
            elif action == 'shuffle':
                pool = [k for k, q in self.players.items()
                        if (k != self.host or q['team'] is not None)
                        and (q.get('ai') or time.monotonic() - q['seen'] < 15)]
                if not 1 <= len(pool) <= 4 * self.team_count:
                    raise ValueError('배정할 참가자가 필요합니다. 각 조는 1~4명입니다. 사회자도 조에 참여할 수 있습니다.')
                random.shuffle(pool)
                for q in self.players.values():
                    q['team'] = None
                for j, k in enumerate(pool):
                    self.players[k]['team'] = j % self.team_count
            elif action == 'take_ai':
                if self.phase != 'playing' or self.assigned(token) is not None:
                    raise ValueError('경기 중 관전 상태에서만 AI 자리를 넘겨받을 수 있습니다.')
                candidates = [t for t in self.teams if not t['completed']]
                target = next(((t, k) for t in candidates for k in t['members'] if self.players[k].get('ai')), None)
                if target is None:
                    raise ValueError('넘겨받을 AI 자리가 없습니다. 대기실에서 조에 참여해 주세요.')
                t, bot = target
                p['team'] = t['id']
                t['members'] = [token if k == bot else k for k in t['members']]
                t['successes'] = [token if k == bot else k for k in t['successes']]
                if bot in t['used']:
                    t['used'][token] = t['used'].pop(bot)
                del self.players[bot]
                t['feedback'] = p['name'] + ' 참가 · AI 자리 인계'
            elif action in ('start', 'start_play'):
                if self.paused:
                    raise ValueError('일시정지를 먼저 해제하세요.')
                original_team = p['team']
                if action == 'start_play' and self.phase == 'lobby' and original_team is None:
                    available = [i for i in range(self.team_count) if len(self.members(i)) < 4]
                    if not available:
                        raise ValueError('빈자리가 없습니다. AI를 한 명 제거한 뒤 참가해 주세요.')
                    # Prefer an occupied team so the host can cooperate with existing players.
                    p['team'] = next((i for i in available if self.members(i)), available[0])
                try:
                    self.begin()
                except Exception:
                    p['team'] = original_team
                    raise
            elif action == 'pause':
                if self.phase not in ('playing', 'tutorial'):
                    raise ValueError('경기 중에만 일시정지할 수 있습니다.')
                if not self.paused:
                    self.pause_start, self.paused = time.monotonic(), True
                else:
                    self.pause_total += time.monotonic() - self.pause_start
                    self.paused = False
            elif action == 'reset':
                if self.paused:
                    self.pause_total += time.monotonic() - self.pause_start
                    self.paused = False
                self.phase, self.stage, self.teams = 'lobby', -1, []
                self.landing = None
                self.round_id += 1
        elif action == 'input':
            self.input(token, data.get('key'), data.get('round'))
        elif action == 'landing_input':
            self.landing_input(token, data['role'], data['pressed'], data['round'])
        else:
            raise ValueError('알 수 없는 요청입니다.')
        return {'ok': True}

    @staticmethod
    def validate_action(data):
        if not isinstance(data, dict):
            raise ValueError('요청은 JSON 객체여야 합니다.')
        action = data.get('action')
        fields = {
            'join': {'name': str}, 'host': {'pin': str},
            'team': {'team': int}, 'spectate': {}, 'shuffle': {},
            'count': {'count': int}, 'start': {}, 'start_play': {},
            'take_ai': {}, 'pause': {}, 'reset': {},
            'add_ai': {'team': int}, 'remove_ai': {'team': int},
            'clear_ai': {}, 'input': {'key': str, 'round': int},
            'test_stage': {'stage': int, 'bots': int},
            'landing_input': {'role': str, 'pressed': bool, 'round': int},
        }
        if not isinstance(action, str) or action not in fields:
            raise ValueError('알 수 없는 요청입니다.')
        for field, expected in fields[action].items():
            if type(data.get(field)) is not expected:
                raise ValueError(f'요청 필드가 잘못되었습니다: {field}')
        if action == 'input' and (data['key'] not in (*DIRECTIONS, 'S') or data['round'] < 0):
            raise ValueError('입력 키 또는 라운드가 잘못되었습니다.')
        if action == 'landing_input' and (data['role'] not in LANDING_ROLES or data['round'] < 0):
            raise ValueError('착륙 조작 또는 라운드가 잘못되었습니다.')

    def public(self, token):
        self.tick()
        if token in self.players:
            self.players[token]['seen'] = time.monotonic()
        def person(k):
            p = self.players[k]
            return {'name': p['name'], 'online': bool(p.get('ai')) or time.monotonic() - p['seen'] < 5,
                    'ai': bool(p.get('ai')), 'me': k == token}
        out = []
        for t in self.teams:
            d = {k: t[k] for k in ['id', 'score', 'pos', 'progress', 'finish', 'feedback', 'health', 'rope_progress', 'history', 'completed', 'jumps', 'started', 'maze_done', 'relay_misses', 'jump_count']}
            d['status'] = 'done' if t['completed'] else 'active' if self.phase in ('playing', 'tutorial') and t is self.teams[self.active_index] else 'waiting'
            d['members'] = [person(k) for k in t['members']]
            d['tutorial_done'] = 'tutorial_result' in t
            if self.stage == 0:
                d.update(maze_lap=self.maze_lap + 1, maze=t['maze'], maze_start=t['maze_start'], goal=t['goal'], path_length=t['distances'][tuple(t['maze_start'])])
            if self.phase == 'results':
                d.update(rank=t['rank'], points=t['points'])
            if self.stage == 1:
                n = self.now()
                d.update(race_duration=60, relay_keys=t['relay_keys'],
                         relay_hit_count=t['relay_hit_count'],
                         relay_notes=[dict(note) for note in t['relay_notes']
                                      if note['spawn'] <= n <= note['at'] + RELAY_WINDOW + 1.2])
            if self.stage == 2:
                idx = t['rope_index']
                pattern = t['rope_pattern']
                d.update(beat=self.rope_beat(idx, t), beat_index=idx,
                         successes=[t['members'].index(k) for k in t['successes']], rope_keys=t['rope_keys'],
                         rope_pattern=pattern, period=pattern[idx % len(pattern)],
                         bpm=round(60 / pattern[idx % len(pattern)]),
                         next_bpm=round(60 / pattern[(idx + 1) % len(pattern)]), change_in=1)
            out.append(d)
        my = self.assigned(token)
        return {'game_test': self.game_test, 'now': self.now(), 'phase': self.phase, 'stage': self.stage, 'start': self.start, 'limit': self.limit,
                'round': self.round_id, 'paused': self.paused, 'team_count': self.team_count, 'teams': out,
                'active_team': self.teams[self.active_index]['id'] if self.phase in ('playing', 'tutorial') else None,
                'landing': dict(self.landing.state, active=list({role for (_, role), stamp in self.landing.inputs.items() if self.now() - stamp < .65})) if self.phase == 'tutorial' else None,
                'landing_roles': self.landing_roles(len(my['members']))[my['members'].index(token)] if self.phase == 'tutorial' and my and token in my['members'] else [],
                'host': token is not None and token == self.host, 'host_name': self.players[self.host]['name'] if self.host else None,
                'known': token in self.players, 'my_team': self.players.get(token, {}).get('team'),
                'my_slot': my['members'].index(token) if my and token in my['members'] else None,
                'lobby': [[person(k) for k in self.members(i)] for i in range(self.team_count)],
                'rules': {'relay_max_bpm': RELAY_MAX_BPM, 'relay_min_interval': RELAY_MIN_INTERVAL, 'relay_window': RELAY_WINDOW,
                          'rope_target': ROPE_TARGET, 'rope_window': ROPE_WINDOW,
                          'gourd_period': GOURD_PERIOD, 'gourd_hp': GOURD_HP},
                'waiting': [person(k) for k, p in self.players.items() if p['team'] is None and k != self.host]}

