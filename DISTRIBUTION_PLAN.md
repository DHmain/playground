# FOURWARD distribution and development plan

Assessment date: 2026-11-09  
Release decision: suitable for supervised LAN pilots; not ready for general public hosting.  
Scope: game direction, product, engineering, validation, distribution, and operation.

Gameplay update: maze has three rotating, growing courses; relay is a continuous 60-second race with fixed per-player keys, independently moving overtaking notes, maximum 120 BPM arrivals, one-second miss penalties and time-based points; jump rope changes each player’s assigned key every cycle and awards raw successful jumps during 120 seconds; gourd center speed is ×1.5 and health is team size ×300. See README.md for the current scoring rules. Latest verification: 30 Python tests and 3 Playwright tests pass.

## 1. Product direction

FOURWARD is a facilitator-led cooperative party game for classrooms, workshops, and small team events. Players use their own phones or computers while a shared display shows the event. Its strongest differentiator is communication through divided controls, supported by four short competitions.

Recommended initial audience: an adult organizer running a casual event for 4–20 players. Keep small-roster support for practice. Advertise a supported audience and device limit only after field validation.

Recommended release sequence:

1. A reliable downloadable LAN pilot, preserving the existing low-dependency setup.
2. An invite-only hosted beta with separate rooms.
3. A public hosted release after recovery, security, support, and load gates pass.

These are separate release gates. Rooms, hosted organizer identity, and service monitoring are required for the hosted edition, not prerequisites for a supervised single-event LAN pilot. Accounts, billing, public matchmaking, chat, and additional games should wait.

## 2. Verified current state

Reviewed `server.py`, `index.html`, `test_game.py`, launch scripts, and `README.md`.

- Four implemented stages: cooperative maze, rhythm relay, jump rope, and gourd target timing.
- Up to five teams, one to four players per active team; facilitator can play.
- Sequential team turns, scoring, shared standings, pause, reset, and temporary AI players.
- Server-authoritative judgments, participant tokens, role checks, stale-round restrictions, and per-cycle input limits.
- Participant reconnection within the same server lifetime and browser profile.
- No third-party Python dependencies; Windows and Unix launch scripts.
- All 18 existing tests passed, including an HTTP test that creates 20 participant sessions.

Limits of this evidence: no real-device browser run, simultaneous 20-device load test, internet latency study, installation study, or independent security audit was performed. The HTTP test joins sessions sequentially; it does not prove concurrent-event capacity. Passing logic tests does not establish fun, usability, timing fairness, or production reliability.

Current architecture: `game.py` provides the rules; each `GameService` owns a game, lock, detached responses, and stoppable 20 ms ticker. `GameHTTPServer` receives its service explicitly. State remains in memory; browser polling remains every 180 ms. Room routing/lifecycle are not implemented. The frontend has since migrated to Vite and strict TypeScript modules for rendering, networking, sound, timing, animation, and DOM updates. Python serves the bundled `dist/` assets. See `FRONTEND.md` for compatibility checks and remaining limits.

## 3. Game direction backlog

### Rules and event pacing — required before broad distribution

- [ ] Define the intended session duration and default event format through playtests.
- [ ] Measure waiting time and engagement for teams whose turn is inactive. Give them clear upcoming-turn cues and useful spectator information.
- [ ] Review the worst-case duration: five teams × four stages × three minutes is 60 minutes of play limits, plus approximately 80 seconds of preparation, introductions, and results. Decide whether shorter limits or a short-event preset are needed.
- [ ] Add a practice flow for each game with no effect on event scores.
- [ ] Explain controls, assigned responsibilities, success conditions, failure conditions, and scoring before each stage.
- [ ] Define ties, timeout ranking, disconnection, withdrawal, restart, and facilitator intervention in one authoritative rules document.
- [ ] Prevent accidental event reset and make consequential facilitator actions explicit.
- [ ] Define whether AI scores count in real events; identify AI clearly in results.

### Balance and fairness — required before competitive claims

- [ ] Playtest teams of 1, 2, 3, and 4 people separately; record completion rates, retries, duration, and perceived fairness.
- [ ] Recommend equal team sizes until evidence supports stronger balance claims.
- [ ] Evaluate maze difficulty beyond equal shortest-path length: branch count, visibility, role workload, and communication burden.
- [ ] Evaluate relay note readability, runner handoff clarity, retry frustration, and distribution of turns.
- [ ] Evaluate jump-rope cues, acceleration comprehension, shared success feedback, and recovery after misses.
- [ ] Evaluate gourd hit-zone readability and the effect of input delay on narrow scoring windows.
- [ ] Test team-order advantage from watching previous turns; choose whether to rotate order between stages.
- [ ] Separate practice AI from competitive difficulty. Current precise AI inputs should not imply human-level difficulty.
- [ ] Collect player feedback on cooperation and enjoyment, not just completion speed.

### Presentation and accessibility — required for the supported audience

- [ ] Provide explicit visual success/miss feedback and an explanation of why an attempt failed.
- [ ] Provide visual alternatives to sound cues and persistent mute/volume controls.
- [ ] Test keyboard-only navigation, focus preservation, screen zoom, contrast, and readable text.
- [ ] Distinguish teams and status using labels/shapes as well as colors.
- [ ] Test touch targets, portrait/landscape layouts, safe areas, and browser gesture interference.
- [ ] Offer reduced motion and avoid requiring sound to understand instructions.
- [ ] Clearly state accessibility limits of timing-based play; evaluate a relaxed casual preset.
- [ ] Separate shared-display information from player controls where this improves clarity.
- [ ] Keep Korean as a complete supported language; add localization infrastructure before promising other languages.

## 4. Engineering backlog

### P0: repair and harden the current event loop

- [x] Require the action body to be a JSON object before dispatch; malformed shapes return a controlled error.
- [x] Validate required action-specific fields and types explicitly, including input keys and rounds; reject malformed requests with controlled errors.
- [x] Build detached state and action-result snapshots under the lock, then serialize and write responses outside it.
- [ ] Set request/read/write timeouts and bound connection/resource use.
- [ ] Record unexpected exceptions without exposing participant credentials or internal details.
- [ ] Supervise ticker failures and expose whether the simulation is still advancing.
- [ ] Add facilitator transfer/recovery, removal of departed participants, and a clear withdrawal policy.
- [ ] Release stale lobby capacity safely. Disconnected participants currently remain in the 80-participant registry.
- [ ] Define rejoin behavior after token loss, duplicate tabs, browser sleep, and device changes.
- [ ] Add a version identifier to the UI and server responses for support.

### P0 for hosted beta: room isolation and identities

- [ ] Finish separating room management, persistence, and configuration. Game rules, synchronized service operations, and HTTP transport are already separate modules.
- [ ] Introduce room-scoped game state and locking; eliminate implicit dependence on the global `GAME`.
- [ ] Create, join, close, and expire rooms; define participant, team, spectator, and total room limits.
- [ ] Add shareable join links and QR codes, with collision-resistant room identifiers and bounded join attempts.
- [ ] Scope every participant credential and authorization decision to a room.
- [ ] Separate facilitator credentials from public join codes; provide a private recovery mechanism.
- [ ] Restrict room state access according to the chosen spectator policy. Currently an unauthenticated state request exposes event names and state.
- [ ] Verify room isolation across every read, action, reconnect, export, and recovery path.
- [ ] Add organizer accounts only if needed for ownership/history; guest players should remain easy to join.

### P0 for hosted beta: security and transport

- [ ] Replace `http.server` with a production application serving stack and terminate HTTPS correctly.
- [ ] Configure allowed hosts/origins and trusted proxy behavior explicitly.
- [ ] Rate-limit room creation, joins, PIN/credential attempts, state reads, and gameplay inputs.
- [ ] Protect credentials in transit and storage; define expiry, revocation, and host recovery behavior.
- [ ] Add security headers and a Content Security Policy compatible with the frontend; move inline handlers/scripts as needed.
- [ ] Audit all user-provided text and rendering paths, especially HTML interpolation.
- [ ] Bound payload size, connection count, room count, participant count, and expensive operations.
- [ ] Keep secrets out of URLs where avoidable, logs, exports, and analytics.
- [ ] Test abuse scenarios: lobby exhaustion, PIN guessing, request floods, forged roles, stale credentials, and cross-room actions.

The official Python documentation states that `http.server` is not recommended for production: https://docs.python.org/3/library/http.server.html

### P0: timing, reconnects, and recovery

- [ ] Measure latency, jitter, server tick delay, and actual input-to-feedback time on supported networks and devices.
- [ ] State a supported network envelope based on measurements; provide a preflight connection check and degraded-connection notice.
- [ ] Choose a timing policy: receipt-time casual play, bounded latency compensation, or relaxed windows. Document the tradeoff between fairness and forged client timestamps.
- [ ] Do not trust client timestamps without limits and replay/sequence protection.
- [ ] Evaluate WebSockets or another push transport using measured requirements. Changing transport alone does not remove network delay.
- [ ] Use versioned snapshots/events and sequence numbers if introducing push transport; resynchronize after missed updates.
- [ ] Define disconnect handling per stage, including pause, grace period, withdrawal, and whether a team can continue.
- [ ] Persist completed results and room metadata; choose explicitly whether active games resume or return to a safe checkpoint.
- [ ] Store recoverable durations/state rather than assuming process-local monotonic timestamps survive restart.
- [ ] Define behavior for deployment during an event, server crash, storage failure, and corrupted snapshots.
- [ ] Test backup restoration and schema migrations before relying on saved results.

### Architecture recommendation

Keep the existing Python game rules and browser client. Make the game clock injectable for repeatable tests. Separate frontend modules for transport, state, input, rendering, and audio; a frontend framework is optional.

For an initial hosted beta, use one authoritative application process managing multiple isolated rooms with durable storage. Set and test a capacity limit. Do not start multiple independent workers against process-local state: clients would see different games. Introduce explicit room ownership/routing and shared infrastructure only when scale requires it. A database alone does not establish authoritative simulation ownership.

## 5. Organizer and player experience

- [ ] Organizer flow: launch/create room → invite players → device check → teams → practice → event → export results → close room.
- [ ] Player flow: open link/scan QR → enter display name → choose/receive team → learn role → ready → play → reconnect if needed.
- [ ] Provide a readiness indicator before starting and visible next-team warnings.
- [ ] Provide useful errors for room full/closed, expired credentials, unavailable host, and unsupported browser features.
- [ ] Provide clear event progress, remaining stages, final standings, and a replay/new-event action.
- [ ] Export a readable score summary; exclude secret tokens and unnecessary participant data.
- [ ] Add device/audio checks, browser compatibility guidance, and a fallback when optional APIs are unavailable.
- [ ] Decide duplicate-name policy and provide facilitator tools for disruptive or mistaken entries.

## 6. Validation plan and release evidence

### Automated checks

- [ ] Preserve all existing 18 tests and run them in CI on supported Python versions.
- [ ] Add focused regression tests for malformed JSON bodies, invalid fields, disallowed origins, and authorization failures.
- [ ] Add room isolation, expiry, credential revocation, and capacity tests when rooms are implemented.
- [ ] Add persistence, restart, migration, and restore tests for promised recovery behavior.
- [ ] Add browser end-to-end coverage for join, host, team assignment, practice, all stages, results, refresh, and reconnect.
- [ ] Verify pause/resume, stage transitions, duplicate/reordered inputs, and delayed requests under the chosen transport.
- [ ] Load-test the advertised concurrent rooms and participants plus agreed headroom; publish observed limits internally.
- [ ] Soak-test at full target load for at least twice the intended maximum event duration.

### Field validation

- [ ] Test Windows and macOS organizer setup; include Linux if advertised.
- [ ] Test current supported Chrome/Edge, Safari on iPhone, and Chrome on Android; record exact versions and devices.
- [ ] Run a real 20-player/5-team event, including mixed input devices and a shared display.
- [ ] Test Wi-Fi congestion, blocked peer access, device sleep, screen rotation, backgrounding, refresh, temporary disconnection, and host loss.
- [ ] Run at least three complete pilot events, including one led by an organizer unfamiliar with the code.
- [ ] Record onboarding problems, waiting time, completion rates, timing complaints, crashes, and recovery success.
- [ ] Agree measurable targets before pilots; use observed results to set supported network and capacity claims.

### Proposed launch acceptance criteria

These are release targets, not verified properties of the current build.

- Every advertised game and roster size works under the documented rules.
- No open defects involving unauthorized control, cross-room data exposure, event corruption, or unrecoverable advertised flows.
- A new organizer completes setup and one full event using only the shipped instructions.
- Disconnection and restart behave exactly as documented, without silent score changes.
- Target-load and soak tests pass within a performance budget agreed before testing.
- Supported devices complete the full event without blocking control, audio, layout, or navigation failures.
- Backups, rollback, and recovery have been exercised for hosted releases.
- All remaining known issues have an owner, severity, workaround, and explicit release decision.

## 7. Packaging, rights, and release operations

### Both editions

- [ ] Choose a distribution license and clarify ownership of code and contributed assets.
- [ ] Inventory fonts, sounds, images, dependencies, and brand references; record provenance and required notices.
- [ ] Review the game name and public marketing claims before public promotion.
- [ ] Document supported operating systems, browsers, networks, and participant limits.
- [ ] Add versioning, changelog, release notes, issue reporting, and a support contact.
- [ ] Stop tracking generated `__pycache__` files; add appropriate ignore rules.
- [ ] Maintain a release checklist and reproducible artifacts from a tagged revision.
- [ ] Document data collected, where it is stored, retention, deletion, and export behavior.
- [ ] Obtain appropriate policy review for the intended audience and launch regions, particularly if targeting schools or minors. Do not claim compliance without review.

### Downloadable LAN edition

- [ ] Offer a tested archive and, if removing the Python prerequisite, platform-specific executable builds.
- [ ] Validate installation on clean machines and document signing/security prompts for each platform.
- [ ] Provide a launcher showing address, port, version, host access, and connection diagnostics.
- [ ] Explain trusted-network/firewall setup without requesting broad firewall disablement.
- [ ] Include local result storage/export, upgrade instructions, and recovery limitations.
- [ ] Test port conflicts, missing runtime, path spaces, non-ASCII paths, and launcher error visibility.

### Hosted edition

- [ ] Add container/build configuration, environment settings, CI/CD, and isolated staging.
- [ ] Configure domain, HTTPS renewal, secrets, durable storage, and backups.
- [ ] Add liveness/readiness checks, structured logs, error reporting, and operational dashboards.
- [ ] Monitor active rooms, connections, tick delay, action latency, error rate, and storage health.
- [ ] Define alerts, incident owner, support hours, maintenance policy, and a restore/rollback runbook.
- [ ] Drain active rooms during deployments or provide a tested safe handover policy.
- [ ] Measure cost per event and set hosting quotas before opening unrestricted signup.
- [ ] Publish appropriate terms, privacy information, retention settings, and abuse reporting.
- [ ] If charging later, implement entitlement, refunds/cancellation, payment failure handling, and customer support before accepting payments.

## 8. Prioritized delivery milestones

| Milestone | Deliverable | Exit gate |
| --- | --- | --- |
| M1: Reliable local event | Request hardening, lock fix, host recovery/transfer, participant removal, practice, result export | Complete event survives documented disconnect scenarios; new regression tests pass |
| M2: LAN release candidate | Versioned package, launcher/docs, supported-device checks, pacing/balance adjustments | Three complete pilots; unfamiliar organizer succeeds; no release-blocking defects |
| M3: Hosted private beta | Isolated rooms, facilitator ownership, production serving, HTTPS, limits, persistence, monitoring | Two independent groups complete events concurrently with no shared state or access |
| M4: Public hosted release | Capacity evidence, tested restore/rollback, policies, support, onboarding polish | All hosted launch acceptance criteria met and reviewed |
| M5: Commercial expansion | Validated pricing, organizational features, optional billing and new content | Repeat use and willingness to pay demonstrated by pilot organizers |

Sequence can overlap where safe, but do not open public hosting before M3/M4 controls are complete. No delivery-date estimate is committed: estimate work after the first refactor and pilot expose the remaining scope.

Optional lobby cooperation tutorial: can landing is packaged with the main game, shares a practice flight among visitors, and does not affect event scores or teams. It does not replace per-stage practice or field validation.

## 9. What to do next

Progress: request validation, response-lock fixes, the interactive test edition, frontend migration, and HTTP-independent service extraction are implemented. Four new service tests cover isolation, concurrency/snapshot detachment, validation before ticking, and ticker lifecycle. Full verification passed after extraction: strict TypeScript, production build, all 27 Python tests, and all 3 Playwright tests. Remaining M1 work starts with host transfer/recovery.

Start M1. The next implementation batch should be small and reviewable:

1. Completed: extract an HTTP-independent game service boundary while preserving rules and existing tests.
2. Completed: validate action bodies/fields and move response writes outside the game lock using detached snapshots.
3. Completed: add regression coverage for validation, response locking, and service ownership/lifecycle.
4. Implement facilitator transfer/recovery and departed-player removal with explicit mid-game rules.
5. Add completed-event result export and version information.
6. Run a small device pilot, then a full 20-player event; use those observations to finalize practice, pacing, and timing changes.

The immediate developer task is step 4. The immediate game-director task is to write a one-page pilot script and feedback sheet covering role comprehension, waiting time, timing fairness, and enjoyment. After that, implement the rest of M1 and release a LAN candidate before expanding to hosted rooms.

Definition of the next major success: an organizer can run and finish an event without developer intervention, preserve its results, and recover from the documented connection failures.
