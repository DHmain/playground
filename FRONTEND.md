# Frontend development and compatibility

FOURWARD uses a Vite + strict TypeScript frontend and the existing Python game server. The optional landing tutorial at `/demos/landing/index.html` uses a separate module script and per-server physics service through `/api/tutorial/landing/*`, preserving main-event state. Gameplay renders with HTML/CSS and SVG; Canvas is not required for the current note density. Rendering is isolated so a later Canvas renderer can reuse the transport and timing code.

## Play the packaged build

The `dist/` directory is included with this version. Keep it alongside `server.py`.

```sh
python3 game_test.py
# or: python3 server.py
```

Open http://127.0.0.1:8000. Players do not need Node.js. Existing Windows and Unix launchers still work. Do not open the source `index.html` as a file.

## Develop

Use Node.js 22.12 or later and Python 3.9 or later.

```sh
npm ci
python3 game_test.py
```

In a second terminal:

```sh
npm run dev
```

Open the Vite address (normally http://127.0.0.1:5173). Vite proxies `/api` to Python on port 8000, keeping API calls on the same browser origin. If changing the backend port, update `vite.config.ts`. Browser participant tokens are scoped to the frontend origin, so the Vite and packaged addresses have separate sessions.

```sh
npm run build
```

This type-checks the client, tests, and configuration, then replaces `dist/` with the production build. Rebuild after source changes. Python serves only files inside `dist/`; it does not expose source files or node_modules. Include the complete generated `dist/` in downloadable releases.

## Modules

| Module | Responsibility | Verification |
| --- | --- | --- |
| `src/main.ts` | State polling, screen selection, delegated actions, keyboard/pointer input, animation loop | Browser journeys in test and normal modes |
| `src/types.ts` | API state, participants, teams, keys, action names | Strict TypeScript build; stage fields accessed by stage-selected renderers |
| `src/transport.ts` | HTTP calls, timeouts, errors, basic state envelope checks | Live Python API, invalid host PIN, disconnect/reconnect |
| `src/ui.ts` | Escaping, notifications, DOM patching, form preservation | Join/lobby controls and persistent relay note DOM nodes |
| `src/games.ts` | Maze, relay, rope, gourd markup | All four live stages, narrow viewport |
| `src/animation.ts` | Frame-driven relay notes, rope, jumps, target bars | All stages, pause/resume, persistent scene nodes |
| `src/timing.ts` | Pure target and rope timing calculations | Boundary and variable-interval tests |
| `src/audio.ts` | User-enabled synthesized timing cues | Browser audio toggle and error monitoring; audible quality requires a human check |
| `game.py` | Game rules, validation, and state projection | Full rules regression suite |
| `game_service.py` | Per-service state/lock, detached results, ticker lifecycle | Isolation, concurrent joins, snapshot detachment, validation, and ticker restart tests |
| `server.py` | HTTP adapter, explicit service injection, safe built-asset serving | HTTP, asset MIME and traversal tests, browser integration |
| `game_test.py` | Interactive local test launcher | Browser test server and all stage selectors |

No inline HTML event handlers or implicit window globals are needed. The DOM is patched instead of replacing the complete game subtree on each update. Animation uses `requestAnimationFrame`; polling remains at 180 ms. Server receipt time still determines scores. This migration does not implement network latency compensation or an audio-clock scheduler.

Verified on 2026-11-09 after the tutorial and stage 2/3 changes: strict TypeScript and production build passed; all 33 main Python tests, 6 landing physics tests, and all 5 Playwright tests passed in Chromium.

## Verification commands

```sh
npx playwright install chromium
npm run check
```

`check` builds the frontend, runs the Python suite, then runs Playwright. The browser suite starts isolated test-mode and normal-mode servers on ports 8765 and 8766. Those ports must be free. Chromium system dependencies may be required on a clean Linux machine.

The browser journey checks join, stage selection, keyboard and pointer input dispatch, continuous relay spawn/variable speed, note-node preservation, pause/resume, AI count and fixed relay ownership, refresh, mobile-width layout, lobby/reset/team management, sound toggle, invalid host PIN, connection recovery, and final-results rendering. Final-results rendering uses a fixture based on live state; complete game/scoring behavior is exercised by the Python suite.

Limits: automated coverage does not prove every possible input combination or real-device behavior. iOS Safari, Android browsers, Windows/macOS launchers, audible synchronization, touch latency, accessibility, and 20 physical devices still require release testing. The optional landing tutorial uses Canvas and is packaged as a second Vite HTML entry; the main stages continue to render with HTML/CSS/SVG. WebSockets, host recovery, and multi-room hosting remain separate roadmap work.
