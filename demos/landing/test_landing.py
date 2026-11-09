import importlib.util
from pathlib import Path
import time
import unittest

spec = importlib.util.spec_from_file_location('landing', Path(__file__).with_name('server.py'))
landing = importlib.util.module_from_spec(spec)
spec.loader.exec_module(landing)


class LandingTests(unittest.TestCase):
    def setUp(self):
        landing.reset()
        landing.STATE['status'] = 'playing'

    def hold(self, *roles):
        for role in roles:
            landing.INPUTS[('test', role)] = time.monotonic()

    def test_no_input_falls_and_release_cuts_engine(self):
        landing.STATE['throttle'] = .8
        landing.step(.1)
        self.assertEqual(landing.STATE['throttle'], 0)
        self.assertLess(landing.STATE['vy'], 0)

    def test_two_operators_and_shared_fuel(self):
        self.hold('up')
        landing.step(.1)
        throttle = landing.STATE['throttle']
        self.assertGreater(throttle, 0)
        self.hold('down', 'left')
        fuel = landing.STATE['fuel']
        landing.step(.1)
        self.assertEqual(landing.STATE['throttle'], throttle)
        self.assertLess(landing.STATE['fuel'], fuel)
        self.assertLess(landing.STATE['vx'], 0)

    def test_right_input_moves_right(self):
        self.hold('right')
        landing.step(.1)
        self.assertGreater(landing.STATE['vx'], 0)

    def test_narrow_landing_zone(self):
        landing.STATE.update(x=8, y=0, vx=0, vy=0)
        landing.step(landing.DT)
        self.assertEqual(landing.STATE['status'], 'crashed')
        self.setUp()
        landing.STATE.update(x=3.75, y=0, vx=0, vy=0, stable=1.999)
        landing.step(landing.DT)
        self.assertEqual(landing.STATE['status'], 'landed')
        self.assertEqual(landing.STATE['score'], 50)

    def test_expired_input_and_empty_fuel(self):
        landing.INPUTS[('old', 'up')] = time.monotonic() - 1
        landing.step(.1)
        self.assertFalse(landing.INPUTS)
        self.hold('up', 'left')
        landing.STATE['fuel'] = 0
        landing.step(.1)
        self.assertEqual(landing.STATE['throttle'], 0)
        self.assertEqual(landing.STATE['fuel'], 0)

    def test_safe_center_and_fast_crash(self):
        landing.STATE.update(x=0, y=0, vx=0, vy=0, stable=1.999)
        landing.step(landing.DT)
        self.assertEqual(landing.STATE['status'], 'landed')
        self.assertEqual(landing.STATE['score'], 100)
        self.setUp()
        landing.STATE.update(x=0, y=.01, vy=-10)
        landing.step(landing.DT)
        self.assertEqual(landing.STATE['status'], 'crashed')
        self.assertEqual(landing.STATE['score'], 0)


if __name__ == '__main__':
    unittest.main()
