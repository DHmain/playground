"""Synchronized game operations and ticker lifecycle, independent of HTTP."""
import copy
import logging
import threading

from game import Game


class GameService:
    """Own one game's state and return detached values across its boundary.

    The optional game argument supports deterministic clocks in tests. Once handed
    to a service, a game should only be accessed through that service in runtime
    code. Construction does not start a background thread.
    """

    def __init__(self, *, game_test=False, game=None):
        self._game = game if game is not None else Game(game_test=game_test)
        self._lock = threading.RLock()
        self._lifecycle_lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None

    @property
    def host_pin(self):
        """Private organizer credential for CLI display, never public snapshots."""
        with self._lock:
            return self._game.pin

    def action(self, token, data):
        Game.validate_action(data)
        with self._lock:
            self._game.tick()
            return copy.deepcopy(self._game.act(token, data))

    def snapshot(self, token=None):
        with self._lock:
            return copy.deepcopy(self._game.public(token))

    def tick(self):
        with self._lock:
            self._game.tick()

    @property
    def running(self):
        with self._lifecycle_lock:
            return self._thread is not None and self._thread.is_alive()

    def start(self):
        """Start at most one ticker. A stopped service can be started again."""
        with self._lifecycle_lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop.clear()
            self._thread = threading.Thread(target=self._run, daemon=True,
                                            name='fourward-ticker')
            self._thread.start()

    def stop(self):
        """Stop and join the ticker before returning; safe before start."""
        with self._lifecycle_lock:
            self._stop.set()
            if self._thread is not None:
                self._thread.join()
                self._thread = None

    def _run(self):
        try:
            while not self._stop.wait(.02):
                self.tick()
        except Exception:
            logging.getLogger(__name__).exception('Game ticker stopped unexpectedly')
