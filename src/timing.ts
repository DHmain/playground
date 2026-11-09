import type { Team, RelayNote } from "./types";
export function relayNoteX(note: RelayNote, now: number, width: number) {
  return width * 0.2 + ((note.at - now) * width * 0.8) / note.travel - 22;
}
export function targetPosition(phase: number) {
  const p = ((phase % 1) + 1) % 1;
  return p < 0.45
    ? (p * 0.425) / 0.45
    : p <= 0.55
      ? 0.425 + (p - 0.45) * 1.5
      : 0.575 + ((p - 0.55) * 0.425) / 0.45;
}
export function ropeClock(t: Team, n: number) {
  const pattern = t.rope_pattern,
    total = pattern.reduce((a, b) => a + b, 0),
    elapsed = Math.max(0, n - t.started),
    cycles = Math.floor(elapsed / total);
  let remaining = elapsed - cycles * total,
    previous = t.started + cycles * total;
  for (let i = 0; i < pattern.length; i++) {
    const period = pattern[i];
    if (remaining < period || i === pattern.length - 1)
      return {
        phase: remaining / period,
        period,
        previous,
        beat: previous + period,
        index: cycles * pattern.length + i,
      };
    remaining -= period;
    previous += period;
  }
  throw new Error("Empty rope pattern");
}
