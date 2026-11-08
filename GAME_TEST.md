# FOURWARD — interactive game test

This edition lets you play any stage immediately, solo or with up to three AI teammates. It uses the same game rules and rendering as the normal edition.

The bundled `dist/` frontend must remain next to `server.py`. After editing frontend source, run `npm run build`; see [FRONTEND.md](FRONTEND.md) for development setup.

## Start

Linux / macOS:

```sh
python3 game_test.py
```

Windows: double-click `start_game_test.bat`, or run `py game_test.py`.

Open **http://127.0.0.1:8000** in your browser and keep the server terminal open. If the port is occupied, use `python3 game_test.py --port 8080` and open port 8080 instead.

## Play

1. Enter your name. The first participant automatically becomes host; no PIN is needed.
2. In the GAME TEST panel, leave AI teammates at **0** to control every input yourself.
3. Select any of the four games. The game starts after its preparation countdown.
4. Use the arrow keys and Space, or the on-screen buttons. Enable sound with the existing sound button.
5. Use **현재 게임 다시 시작** to restart, or choose another game at any time. Each selection clears scores and progress and rebuilds your test team.
6. Select 1–3 AI teammates to check cooperative roles. In rhythm relay, you always receive the first turn; subsequent turns include AI.

Normal pause/resume and lobby controls remain available. Closing the server discards the session. Other connected human participants become spectators whenever the host starts a test stage.

## Rhythm relay checklist

- Notes move right-to-left through five horizontal lanes and reach the vertical yellow judgment line at the intended input time.
- With zero AI, all relay patterns belong to you.
- Hit the indicated arrow or Space when its note center reaches the line.
- Deliberately miss a note: the next attempt should use a different key sequence and interval sequence.
- Let a pattern finish: the next pattern should have a fresh sequence and rhythm. Watch the runner above the notes move backward once per missed note; ideal finish is 60 seconds plus penalties.
- Pause and resume: notes should remain synchronized with the game clock.
- Try sound on/off, keyboard, and touch controls; record unclear cues or perceived timing errors.

## Test on a phone

The test edition listens only on this computer by default. For a trusted LAN test, run:

```sh
python3 game_test.py --bind 0.0.0.0
```

Join from the organizer browser first to claim host control, then open the printed LAN address on the phone. To use the phone as host, join there first instead. Test mode grants the first participant control automatically; use the normal `server.py` edition for regular facilitated events.

## Automated checks

`game_test.py` is the playable edition. `test_game.py` is the automated regression suite:

```sh
python3 -B -m unittest -v test_game.py
```
