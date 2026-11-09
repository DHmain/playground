"""Shared landing physics, isolated from main-event rules and scores."""
import math
import threading
import time

DT = 1 / 60
LANDING_HALF_WIDTH = 7.5
ROLES = ('left', 'right', 'up', 'down')


class LandingService:
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.state = {}
        self.inputs = {}
        self.lock = threading.RLock()
        self.reset()
        self.last = self.clock()
        self.accumulator = 0.

    def advance(self):
        now = self.clock()
        if now < self.last:
            return
        self.accumulator += min(65., now - self.last)
        self.last = now
        while self.accumulator >= DT:
            self.step(DT)
            self.accumulator -= DT

    def snapshot(self):
        with self.lock:
            self.advance()
            result = dict(self.state)
            now = self.clock()
            result['active'] = list({r for (_, r), stamp in self.inputs.items() if now - stamp < .65})
            return result

    def action(self, operation, body):
        if not isinstance(body, dict):
            raise ValueError('Expected an object')
        if operation == 'input':
            client, role, pressed = body.get('client'), body.get('role'), body.get('pressed')
            if not isinstance(client, str) or not 1 <= len(client) <= 80 or role not in ROLES or type(pressed) is not bool:
                raise ValueError('Invalid input')
        elif operation != 'start':
            raise ValueError('Unknown action')
        with self.lock:
            self.advance()
            if operation == 'start':
                self.reset()
                self.state['status'] = 'playing'
            elif pressed:
                if len(self.inputs) >= 100 and (client, role) not in self.inputs:
                    raise ValueError('Input capacity exceeded')
                self.inputs[(client, role)] = self.clock()
            else:
                self.inputs.pop((client, role), None)
            return {}

    def reset(self):
        self.state.clear()
        self.state.update(x=-22., y=105., vx=0., vy=0., fuel=50., throttle=0.,
                     elapsed=0., stable=0., status='ready', score=0, reason='', wind=0.)
        self.inputs.clear()


    def step(self, dt):
        s = self.state
        if s['status'] != 'playing':
            return
        now = self.clock()
        for key, stamp in list(self.inputs.items()):
            if now - stamp >= .65:
                del self.inputs[key]
        active = {role for (_, role), stamp in self.inputs.items() if now - stamp < .65}
        s['elapsed'] += dt
        t = s['elapsed']
        s['wind'] = 1.25 * math.sin(t * .38) + .55 * math.sin(t * .91)
        up, down = 'up' in active, 'down' in active
        if not up and not down:
            s['throttle'] = 0.
        elif up != down:
            s['throttle'] = max(0., min(1., s['throttle'] + (1 if up else -1) * .8 * dt))
        if s['fuel'] <= 0:
            s['throttle'] = 0.
            active.clear()
        left, right = 'left' in active, 'right' in active
        burn = s['throttle'] * 3.2 + (left + right) * .55
        fraction = min(1., s['fuel'] / (burn * dt)) if burn else 1.
        s['fuel'] = max(0., s['fuel'] - burn * dt)
        s['vx'] += (s['wind'] + (right - left) * 5.5 * fraction - s['vx'] * .12) * dt
        s['vy'] += (16 * s['throttle'] * fraction - 7) * dt
        s['x'] += s['vx'] * dt
        s['y'] += s['vy'] * dt
        if s['y'] <= 0:
            if abs(s['x']) > LANDING_HALF_WIDTH:
                self.finish('착륙장 밖에 착륙했습니다.')
            elif abs(s['vy']) > 5 or abs(s['vx']) > 3:
                self.finish('충돌 속도 초과 · 수직 5 / 수평 3 m/s 이하로 착륙하세요.')
            else:
                s['y'] = 0.
                s['vy'] = 0.
                s['vx'] *= max(0., 1 - 4 * dt)
                s['stable'] += dt
                if s['stable'] >= 2:
                    s['score'] = round(100 * max(0., 1 - abs(s['x']) / LANDING_HALF_WIDTH))
                    s['status'] = 'landed'
                    s['reason'] = '안정 착륙! 중앙에서 %.1f m' % abs(s['x'])
        else:
            s['stable'] = 0.
        if s['status'] == 'playing' and (abs(s['x']) > 65 or s['y'] > 155 or t >= 60):
            self.finish('비행 구역 이탈' if t < 60 else '60초 제한시간 초과')


    def finish(self, reason):
        self.state.update(status='crashed', reason=reason, score=0)
        self.state['y'] = max(0., self.state['y'])


