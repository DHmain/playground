import type { GameState } from "./types";
import { targetPosition, ropeClock } from "./timing";
export function animate(S: GameState | null, n: number) {
  if (!S || S.phase !== "playing") return;
  const clock = document.getElementById("clock");
  if (clock)
    clock.textContent = S.paused
      ? "PAUSED"
      : n < S.start
        ? "시작 " + Math.ceil(S.start - n)
        : Math.max(0, Math.ceil(S.start + S.limit - n)) + "s";
  for (const t of S.teams) {
    if (S.stage === 1 && t.id === S.active_team && t.finish === null) {
      const runner = document.querySelector<HTMLElement>(
        `[data-runner="${t.id}"]`,
      );
      if (runner)
        runner.style.left = `${Math.min(94, Math.max(0, (n - S.start - t.relay_misses) / 60) * 94)}%`;
      const delta = n - t.turn_start;
      const el = document.querySelector<HTMLElement>(`[data-relay="${t.id}"]`);
      if (el)
        el.textContent =
          delta < 0 ? "준비" : delta < 3 ? String(Math.ceil(3 - delta)) : "GO";
      const width =
        document.querySelector<HTMLElement>(".relay-track")?.clientWidth ?? 0;
      for (let i = 0; i < t.pattern.length; i++) {
        const note = document.querySelector<HTMLElement>(
          `[data-note="${t.id}-${i}"]`,
        );
        if (note) {
          const remaining = t.turn_start + 3 + t.note_times[i] - n;
          // Travel from the right edge to the 20% hit line in 2.5 seconds.
          note.style.transform = `translateX(${width * 0.2 + (remaining * width * 0.8) / 2.5 - 24}px)`;
          note.classList.toggle(
            "beat",
            Math.abs(remaining) < S.rules.relay_window,
          );
          note.classList.toggle("hit", t.hits.includes(i));
          note.classList.toggle(
            "missed",
            remaining < -S.rules.relay_window && !t.hits.includes(i),
          );
        }
      }
    }
    if (S.stage === 2 && t.id === S.active_team) {
      const timing = ropeClock(t, n);
      const angle = timing.phase * Math.PI * 2;
      document
        .querySelectorAll("[data-rope-note]")
        .forEach((el, i) => el.classList.toggle("on", i === timing.index % 8));
      const y = n < S.start ? 155 : 155 + 60 * Math.cos(angle);
      const path = `M55 155 Q300 ${2 * y - 155} 545 155`;
      for (const side of ["back", "front"]) {
        const el = document.querySelector<HTMLElement>(
          `[data-rope-${side}="${t.id}"]`,
        );
        if (el) {
          el.setAttribute("d", path);
          el.style.visibility =
            (side === "front") === y >= 155 ? "visible" : "hidden";
        }
      }
      t.members.forEach((p, i) => {
        const el = document.querySelector<HTMLElement>(
          `[data-jumper="${t.id}-${i}"]`,
        );
        if (!el) return;
        const age = n - t.jumps[i];
        const lift =
          age >= 0 && age < 0.5 ? Math.sin((age / 0.5) * Math.PI) * 40 : 0;
        el.setAttribute("transform", `translate(0,${-lift})`);
        el.classList.toggle(
          "hit",
          age >= 0 && age < 0.5 && t.successes.includes(i),
        );
      });
    }
  }
  document.querySelectorAll<HTMLElement>("[data-target-slot]").forEach((el) => {
    const phase =
      Math.max(0, n - S.start) / S.rules.gourd_period +
      Number(el.dataset.targetSlot) * 0.23;
    el.style.left = targetPosition(phase) * 100 + "%";
  });
  const needle = document.getElementById("needle");
  if (needle && S.my_slot !== null) {
    const phase =
      Math.max(0, n - S.start) / S.rules.gourd_period + S.my_slot * 0.23;
    needle.style.left = targetPosition(phase) * 100 + "%";
  }
}
