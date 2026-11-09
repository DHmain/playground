# FOURWARD project context and working guide

## Product and scope

FOURWARD is a Korean-language, facilitator-led cooperative party game for trusted local networks. It supports up to five teams with one to four participants per active team, a host who can also play, spectators, and temporary AI participants.

Support both desktop keyboard/mouse and mobile on-screen controls. The latest product decision preserves mobile support. Do not remove responsive layouts, pointer controls, or mobile checks when improving desktop play.

The current product is a supervised LAN MVP progressing toward distribution. Hosted rooms and public-service readiness are roadmap items, not implemented capabilities.

## Read these documents

- `README.md`: setup, player flow, rules, scoring, and known limitations.
- `FRONTEND.md`: frontend architecture, development commands, and verification coverage.
- `GAME_TEST.md`: interactive testing instructions.
- `DISTRIBUTION_PLAN.md`: release backlog and milestones. Verify recorded progress against code and current tests before selecting work.

## Architecture and file map

- `game.py`: authoritative `Game` rules, validation, and public-state projection, independent of HTTP.
- `game_service.py`: `GameService` owns one game, its lock, detached snapshots/action results, and start/stop ticker lifecycle. Runtime code accesses state through the service.
- `server.py`: HTTP adapter, built-asset serving, and CLI. Each `GameHTTPServer` receives a service explicitly; there is no global game or lock. Event state remains in memory.
- `game_test.py`: starts interactive test mode. The first participant becomes host automatically. The host can choose/restart stages and select zero to three AI teammates. Test mode binds to loopback by default.
- `test_game.py`: automated Python rules and HTTP regression tests. This is different from the playable `game_test.py` launcher.
- `index.html`: Vite source HTML shell.
- `src/main.ts`: state polling, screen orchestration, keyboard/pointer input, delegated UI actions, and frame loop.
- `src/types.ts`: API state, team, participant, action, and key types. Stage-specific fields are supplied only for their corresponding stage; preserve renderer stage guards.
- `src/transport.ts`: HTTP requests, timeouts, response handling, and basic state-envelope validation.
- `src/ui.ts`: HTML escaping, notifications, typed element lookup, and morphdom updates.
- `src/games.ts`: maze, rhythm relay, jump rope, and gourd markup.
- `src/animation.ts`: visual updates driven by requestAnimationFrame.
- `src/timing.ts`: pure target-motion and rope-timing calculations.
- `src/audio.ts`: user-enabled synthesized cues.
- `src/styles.css`: desktop and mobile layouts and visual styling.
- `tests/`: Playwright browser journey and timing tests.
- `dist/`: generated, packaged frontend served by Python. Include it with releases; regenerate rather than editing it manually.
- `vite.config.ts`: frontend development server and `/api` proxy to Python port 8000.
- `playwright.config.ts`: test servers on ports 8765 and 8766.

Frontend stack: Vite, strict TypeScript, HTML/CSS/SVG, and morphdom. Canvas is optional future work. Python has no third-party runtime dependencies; players do not need Node.js when using the bundled build.

## Commands

Development requires Node.js 22.12+ and Python 3.9+.

```sh
npm ci
python3 game_test.py
# In another terminal:
npm run dev
```

Vite normally serves http://127.0.0.1:5173 and proxies API calls to port 8000. Participant tokens are origin-specific; Vite and Python addresses have separate browser sessions.

```sh
npm run build                         # strict type check, then regenerate dist
python3 server.py                     # normal LAN event, host PIN in terminal
python3 game_test.py                  # interactive local testing
python3 game_test.py --port 8080       # alternate port
python3 game_test.py --bind 0.0.0.0    # trusted LAN testing on other devices
```

For packaged play, open http://127.0.0.1:8000 and keep the terminal running. Existing shell/batch launchers wrap these commands.

```sh
npm run typecheck
python3 -B -m unittest -v test_game.py
npx playwright install chromium       # first-time browser setup
npm test
npm run check                         # build + Python suite + Playwright
npm run format
```

HTTP and browser tests need permission to bind local ports. Chromium may need system libraries on clean Linux systems. Use an existing PLAYWRIGHT_BROWSERS_PATH only if that browser installation is available; do not assume a previous session's /tmp cache persists.

## Game invariants

- Server receipt time determines judgments. Client animation predicts visuals; it does not determine scores.
- Teams play sequentially, with preparation countdowns and a 120-second jump-rope window and 180-second safety limits for other turns. Waiting teams cannot submit effective gameplay inputs.
- Preserve host authorization, participant-token privacy, stale-round rejection, pause behavior, and duplicate/per-cycle input limits.
- Each team receives three randomly ordered, nonrepeating maze starting corners; rotate the grid, start, opposite exit, and distance map together. Future corner assignments remain server-side.
- Maze straight corridors allow at most three consecutive moves (four open cells) before turning. Maze roles depend on team size. Generated team mazes have equal shortest-path length, which does not guarantee identical human difficulty.
- Stage 2: every player owns one fixed arrow key (U/D/L/R by roster slot; smaller teams only receive owned keys). Notes stream continuously until the 60-second race finishes, with +1 second per missed note and a ±0.16-second window. Notes have independent 1.2–4.2-second travel times and can overtake. Arrival gaps are randomized 0.5/0.6/0.75/1 seconds (maximum 120 BPM); spawn order is not arrival order. Only spawned notes are public.
- No relay attempts, seven-note patterns, or runner handoffs remain. Relay points are max(0, 180 minus finish seconds), DNF scores zero.
- Stage 3: each player receives one random U/D/L/R/Space key for the current rope cycle. After that cycle’s judgment window, every player receives a different random key; future keys are not exposed. A wrong key consumes the cycle attempt, as does an early input. Jump rope is capped at 100 BPM: shuffled 0.60/0.72/0.84/0.96-second intervals, twice each. Jump rope runs for 120 seconds, awarding one point per successful player jump. Gourd target cycles last 2.0 seconds, center slope is 1.5, and health is team size times 300.
- AI and human judgments use the same rules; practice AI is deliberately precise.
- Changes to timing formulas must remain consistent across Python rules, TypeScript visuals/audio, and tests.

## Implementation and verification rules

- Edit frontend source, rebuild dist, and keep the packaged Python launch flow operational.
- Preserve DOM nodes during state updates; avoid rebuilding the entire active scene or disrupting focused inputs on each poll.
- Keep actions in module-owned listeners; do not introduce inline event handlers or implicit window globals.
- Keep network serialization/writes outside the game lock. Detach mutable response state while holding the lock.
- Validate action bodies and fields before dispatch. Keep API and TypeScript contracts aligned.
- Escape user-provided text before HTML interpolation. Serve assets only from dist and retain traversal protection.
- Preserve desktop keyboard input, mobile pointer input, sound opt-in, and visual timing cues.
- Add focused regression coverage for meaningful rule, transport, or recovery changes. Run checks appropriate to the change; documentation-only edits need link/content checks rather than full gameplay tests.
- Report actual checks and limitations. Browser tests do not establish audible synchronization, real touch latency, fairness, or twenty-device capacity.
- Preserve unrelated working-tree changes. Generated bytecode has historically been tracked; do not treat its presence as intentional source work.

## Current state and next work

Last recorded verification after the stage redesign: production build and strict type checks passed, 30 Python tests passed, and 3 Playwright tests passed. These are historical results; rerun relevant checks after changes.

Implemented: four games, scoring, host play, AI, request hardening, detached response snapshots, interactive stage testing, continuous fixed-key relay with overtaking notes, random per-cycle rope keys, modular TypeScript frontend, and bundled asset serving.

Verification after tutorial integration and stage 2/3 rule updates: strict types and production build passed, 33 main Python tests plus 6 landing physics tests passed, and all 5 Playwright tests passed in Chromium. Real multi-device touch latency and audible synchronization still require human testing.

Optional lobby tutorial: can landing at `/demos/landing/index.html`, built by Vite from `demos/landing/index.html` and `landing.js`. Each HTTP server owns a separate `LandingService` (`demos/landing/physics.py`), accessed via `/api/tutorial/landing/{state,start,input}`. It shares one practice flight among tutorial visitors, allows practice restart by any visitor, and never changes main-event teams, stages, or scores. Fuel starts at 50 and the landing zone is 15m wide. The standalone demo launcher remains usable.

The HTTP-independent game service boundary is extracted. Next implement host transfer/recovery, departed-player handling with explicit mid-game rules, and result export. Align changes with the release roadmap.

Remaining distribution gaps include restart recovery, persistent results, packaging validation, real-device pilots, multi-room isolation, production serving, rate limits, and operations. Do not claim public hosting is ready. Do not add multiple independent workers around process-local game state without an explicit room-ownership design.

Current stage rules: maze teams rotate after each of three courses (15/19/23 cells square), with equal shortest-path lengths per lap and at least 2/3/4 branch vertices. Maze points use rank based on aggregate play time; unfinished teams rank by completed mazes.
