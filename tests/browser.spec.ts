import { test, expect } from "@playwright/test";

test("built client: all stages, inputs, pause, AI, reconnect, mobile, normal edition", async ({
  page,
  browser,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await page.getByLabel("참가자 이름").fill("Browser Tester");
  await page.getByRole("button", { name: "대기실 입장" }).click();
  await expect(page.getByText("GAME TEST · 직접 플레이 테스트")).toBeVisible();
  const state = () =>
    page.evaluate(
      async () =>
        await (
          await fetch("/api/state", {
            headers: {
              "X-Player": localStorage.getItem("fourward-token") || "",
            },
          })
        ).json(),
    );
  const games = [
    "협동 미로 탈출",
    "랜덤 리듬 계주",
    "변속 단체 줄넘기",
    "박 터뜨리기",
  ];
  for (let stage = 0; stage < 4; stage++) {
    await page.getByRole("button", { name: games[stage], exact: true }).click();
    await expect.poll(async () => (await state()).stage).toBe(stage);
    await expect(page.locator(".controller .key").first()).toBeVisible();
    await page.waitForTimeout(4300);
    await page.keyboard.press(stage === 0 ? "ArrowUp" : "Space");
    await page.locator(".controller .key").first().dispatchEvent("pointerdown");
    if (stage === 1) {
      await expect(page.locator(".relay-note")).toHaveCount(7);
      await expect(page.locator(".runner-race")).toBeVisible();
      await expect(page.locator(".relay-runner")).toBeVisible();
      await expect(page.locator(".relay-note .note-arrow")).toHaveCount(5);
      await expect(page.locator(".relay-note .note-space")).toHaveCount(2);
      expect(
        await page
          .locator(".relay-runner")
          .evaluate((el) => getComputedStyle(el).transform),
      ).toBe("matrix(-1, 0, 0, 1, 0, 0)");
      const square = await page.locator(".relay-note").first().boundingBox();
      expect(square!.width).toBe(square!.height);
      const note = await page.locator(".relay-note").first().elementHandle();
      const before = await note!.boundingBox();
      await page.waitForTimeout(300);
      const after = await note!.boundingBox();
      expect(after!.x).toBeLessThan(before!.x);
      expect(after!.y).toBeCloseTo(before!.y);
      expect(await note!.evaluate((el) => el.isConnected)).toBe(true);
      const old = (await state()).teams[0];
      await expect
        .poll(async () => (await state()).teams[0].attempt, { timeout: 12000 })
        .toBeGreaterThan(old.attempt);
      const fresh = (await state()).teams[0];
      expect(fresh.pattern).not.toEqual(old.pattern);
      expect(fresh.note_times).not.toEqual(old.note_times);
    }
    if (stage === 2) {
      await expect
        .poll(
          async () =>
            Number(await page.locator(".rope-impact").getAttribute("opacity")),
          { intervals: [20], timeout: 3000 },
        )
        .toBeGreaterThan(0);
      const current = (await state()).teams[0];
      expect(current.rope_pattern.every((gap: number) => 60 / gap <= 100)).toBe(
        true,
      );
      expect(current.bpm).toBeLessThanOrEqual(100);
      expect((await state()).limit).toBe(120);
    }
    if (stage === 3) {
      expect((await state()).rules.gourd_period).toBe(2);
      expect((await state()).rules.gourd_hp).toBe(300);
    }
    await page.getByRole("button", { name: "일시정지" }).click();
    await expect(page.locator("#clock")).toHaveText("PAUSED");
    await page.getByRole("button", { name: "재개" }).click();
    await expect.poll(async () => (await state()).paused).toBe(false);
  }
  await page.getByRole("button", { name: "박자 소리 켜기" }).click();
  await expect(
    page.getByRole("button", { name: "박자 소리 끄기" }),
  ).toBeVisible();
  const musicResponse = page.waitForResponse((response) =>
    response.url().endsWith("/audio/happy-adventure.mp3"),
  );
  await page.getByRole("button", { name: "BGM 켜기", exact: true }).click();
  expect((await musicResponse).ok()).toBe(true);
  await expect(
    page.getByRole("button", { name: "BGM 끄기", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await page.getByRole("button", { name: "BGM 끄기", exact: true }).click();
  await page.getByLabel("AI 팀원").selectOption("3");
  await page.getByRole("button", { name: games[1], exact: true }).click();
  await expect
    .poll(async () => (await state()).teams[0].members.length)
    .toBe(4);
  expect((await state()).teams[0].mine).toBe(true);
  await page.reload();
  await expect(page.getByText("GAME TEST · 직접 플레이 테스트")).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.locator(".relay-track")).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  page.on("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "대기실로", exact: true }).click();
  await expect.poll(async () => (await state()).phase).toBe("lobby");
  await page.getByRole("button", { name: "임시 AI 전체 제거" }).click();
  await page
    .getByRole("button", { name: "＋ 임시 AI", exact: true })
    .first()
    .click();
  await page
    .getByRole("button", { name: "AI 1명 제거", exact: true })
    .first()
    .click();
  await page.getByLabel("조 수").selectOption("2");
  await page.getByRole("button", { name: "랜덤 섞기" }).click();
  await page.getByRole("button", { name: "우리 조로 경기 시작" }).click();
  await expect.poll(async () => (await state()).phase).toBe("playing");
  const finished = await state();
  finished.phase = "results";
  finished.stage = 3;
  finished.active_team = null;
  finished.teams.forEach((team: Record<string, unknown>) =>
    Object.assign(team, {
      rank: 1,
      points: 100,
      score: 400,
      completed: true,
      finish: 10,
    }),
  );
  await page.route("**/api/state", (route) =>
    route.fulfill({ json: finished }),
  );
  await expect(page.getByText("종합 우승:", { exact: false })).toBeVisible();
  await expect(page.locator("table tbody tr")).toHaveCount(
    finished.teams.length,
  );
  await page.unroute("**/api/state");
  await page.route("**/api/state", (route) => route.abort());
  await expect(page.locator("#connection")).toContainText("서버 연결 끊김");
  await page.unroute("**/api/state");
  await expect(page.locator("#connection")).toContainText("연결됨");
  expect(errors).toEqual([]);
  const normal = await browser.newPage();
  normal.on("pageerror", (error) => errors.push(error.message));
  await normal.goto("http://127.0.0.1:8766");
  await normal.getByLabel("참가자 이름").fill("Normal Player");
  await normal.getByRole("button", { name: "대기실 입장" }).click();
  await expect(normal.getByText("사회자석", { exact: true })).toBeVisible();
  await normal.getByLabel("사회자 PIN").fill("WRONG");
  await normal
    .getByRole("button", { name: "사회자로 참여", exact: true })
    .click();
  await expect(normal.locator("#toast")).toContainText("PIN");
  await normal
    .getByRole("button", { name: "＋ 참여", exact: true })
    .first()
    .click();
  await expect(
    normal.locator(".slot").filter({ hasText: "Normal Player" }),
  ).toBeVisible();
  await normal.getByRole("button", { name: "조에서 나가기 / 대기로" }).click();
  await expect(normal.getByText("대기 인원 · 1명")).toBeVisible();
  expect(errors).toEqual([]);
  await normal.close();
});
