import type { GameState } from "./types";
import { targetPosition, ropeClock, relayNoteX } from "./timing";
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
      const delta = n - S.start;
      const el = document.querySelector<HTMLElement>(`[data-relay="${t.id}"]`);
      if (el)
        el.textContent = delta < 0 ? "준비" : "GO · 담당 키를 계속 확인하세요";
      const width =
        document.querySelector<HTMLElement>(".relay-track")?.clientWidth ?? 0;
      for (const data of t.relay_notes) {
        const note = document.querySelector<HTMLElement>(
          `[data-note="${t.id}-${data.id}"]`,
        );
        if (note) {
          const remaining = data.at - n;
          note.style.transform = `translateX(${relayNoteX(data, n, width)}px)`;
          note.classList.toggle(
            "beat",
            Math.abs(remaining) < S.rules.relay_window,
          );
          note.classList.toggle("hit", data.status === "hit");
          note.classList.toggle(
            "missed",
            data.status === "miss" ||
              (remaining < -S.rules.relay_window && data.status !== "hit"),
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
      const y = n < S.start ? 155 : 155 + 70 * Math.cos(angle);
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
      // Phase zero is the floor contact, matching the server's beat boundaries.
      const impact = document.querySelector<SVGElement>(
        `[data-rope-impact="${t.id}"]`,
      );
      if (impact) {
        const age = n - timing.previous;
        const strength =
          n >= S.start && timing.index > 0 && age < 0.18 ? 1 - age / 0.18 : 0;
        impact.setAttribute("opacity", String(strength));
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
