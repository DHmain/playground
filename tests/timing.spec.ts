import { test, expect } from "@playwright/test";
import { targetPosition, ropeClock } from "../src/timing";
import type { Team } from "../src/types";

test("target motion wraps and follows all three speed regions", () => {
  for (const [phase, position] of [
    [0, 0],
    [0.45, 0.425],
    [0.5, 0.5],
    [0.55, 0.575],
    [1, 0],
    [1.5, 0.5],
    [-0.5, 0.5],
  ])
    expect(targetPosition(phase)).toBeCloseTo(position);
  expect(targetPosition(0.51) - targetPosition(0.5)).toBeCloseTo(0.015);
});
test("rope clock follows variable intervals and cycle boundaries", () => {
  const t = { rope_pattern: [0.6, 0.72, 0.84, 0.96], started: 10 } as Team;
  expect(ropeClock(t, 10)).toMatchObject({ index: 0, phase: 0, period: 0.6 });
  expect(ropeClock(t, 10.65).index).toBe(1);
  expect(ropeClock(t, 10.65).beat).toBeCloseTo(11.32);
  expect(ropeClock(t, 13.13).index).toBe(4);
  expect(ropeClock(t, 13.13).previous).toBeCloseTo(13.12);
});
