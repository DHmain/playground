import { test, expect, type BrowserContext, type Page } from "@playwright/test";

test("20 players: mandatory team landing, role ownership, all four stages", async ({
  browser,
}, testInfo) => {
  test.setTimeout(300000);
  const base = "http://127.0.0.1:8767";
  const roles = ["left", "right", "up", "down"];
  const keys = ["a", "l", "u", "d"];
  const contexts: BrowserContext[] = [];
  const pages: Page[] = [];
  const errors: string[] = [];
  const tokens: string[] = [];
  const reports: unknown[] = [];
  async function post(player: number, path: string, data: object) {
    const response = await contexts[player].request.post(base + path, {
      headers: { "X-Player": tokens[player] },
      data,
    });
    expect(response.ok(), await response.text()).toBe(true);
    return response.json();
  }
  const action = (player: number, data: object) =>
    post(player, "/api/action", data);
  const state = async () =>
    (
      await contexts[0].request.get(base + "/api/state", {
        headers: { "X-Player": tokens[0] },
      })
    ).json();
  try {
    for (let i = 0; i < 20; i++) {
      const context = await browser.newContext({
        viewport:
          i < 10 ? { width: 1280, height: 900 } : { width: 390, height: 844 },
        hasTouch: i >= 10,
      });
      contexts.push(context);
      const page = await context.newPage();
      page.on("pageerror", (error) => errors.push(error.message));
      pages.push(page);
    }
    for (let offset = 0; offset < 20; offset += 4) {
      await Promise.all(
        pages.slice(offset, offset + 4).map(async (page, index) => {
          const player = offset + index;
          await page.goto(base);
          await page.getByLabel("참가자 이름").fill(`Player ${player + 1}`);
          await page.getByRole("button", { name: "대기실 입장" }).click();
          await expect(
            page.getByRole("heading", { name: "우리 팀을 완성하세요" }),
          ).toBeVisible();
          tokens[player] = (await page.evaluate(() =>
            localStorage.getItem("fourward-token"),
          ))!;
        }),
      );
    }
    expect(new Set(tokens).size).toBe(20);
    await action(0, { action: "host", pin: "TEST20" });
    for (let i = 0; i < 20; i++)
      await action(i, { action: "team", team: Math.floor(i / 4) });
    await action(0, { action: "start" });
    expect((await state()).phase).toBe("tutorial");
    const skip = await contexts[0].request.post(base + "/api/action", {
      headers: { "X-Player": tokens[0] },
      data: { action: "start" },
    });
    expect(skip.status()).toBe(400);
    for (let team = 0; team < 5; team++) {
      let current = await state();
      expect(current.active_team).toBe(team);
      expect(current.stage).toBe(-1);
      current = await post(0, "/__test/advance", {
        seconds: current.start - current.now + 0.05,
      });
      const round = current.round;
      const release: Array<() => Promise<void>> = [];
      for (let member = 0; member < 4; member++) {
        const player = team * 4 + member;
        const slot = current.teams[team].members.findIndex((p: {name: string}) => p.name === `Player ${player + 1}`);
        const page = pages[player];
        await expect(page.locator("[data-landing-role]")).toHaveCount(1);
        await expect(page.locator("[data-landing-role]")).toHaveAttribute(
          "data-landing-role",
          roles[slot],
        );
        await action(player, {
          action: "landing_input",
          role: roles[(slot + 1) % 4],
          pressed: true,
          round,
        });
      }
      expect((await state()).landing.active).toEqual([]);
      await action(((team + 1) % 5) * 4, {
        action: "landing_input",
        role: "left",
        pressed: true,
        round,
      });
      await action(team * 4, {
        action: "landing_input",
        role: "left",
        pressed: true,
        round: round - 1,
      });
      expect((await state()).landing.active).toEqual([]);
      for (let member = 0; member < 4; member++) {
        const player = team * 4 + member;
        const slot = current.teams[team].members.findIndex((p: {name: string}) => p.name === `Player ${player + 1}`);
        const page = pages[player];
        if (player < 10) {
          await page.keyboard.down(keys[slot]);
          release.push(() => page.keyboard.up(keys[slot]));
        } else {
          const button = page.locator("[data-landing-role]");
          await button.scrollIntoViewIfNeeded();
          const box = (await button.boundingBox())!;
          const session = await contexts[player].newCDPSession(page);
          await session.send("Input.dispatchTouchEvent", {
            type: "touchStart",
            touchPoints: [
              { x: box.x + box.width / 2, y: box.y + box.height / 2 },
            ],
          });
          release.push(async () => {
            await session.send("Input.dispatchTouchEvent", {
              type: "touchEnd",
              touchPoints: [],
            });
            await session.detach();
          });
        }
      }
      await expect
        .poll(async () => (await state()).landing.active.sort())
        .toEqual([...roles].sort());
      await post(0, "/__test/advance", { seconds: 0.1 });
      expect((await state()).landing.throttle).toBe(0);
      await Promise.all(release.map((fn) => fn()));
      await expect.poll(async () => (await state()).landing.active).toEqual([]);
      current = await post(0, "/__test/advance", { seconds: 61 });
      expect(current.landing.status).toBe("crashed");
      expect(current.teams[team].tutorial_done).toBe(true);
      await post(0, "/__test/advance", { seconds: 3.1 });
    }
    let current = await state();
    expect(current.phase).toBe("playing");
    expect(current.stage).toBe(0);
    expect(
      current.teams.every(
        (team: { tutorial_done: boolean; score: number }) =>
          team.tutorial_done && team.score === 0,
      ),
    ).toBe(true);
    // Every key goes through the real service, with a test-only injected clock.
    for (let stage = 0; stage < 4; stage++) {
      const report = await post(0, "/__test/play_stage", {});
      reports.push(report);
      expect(report.stage).toBe(stage);
      expect(report.teams_finished).toBe(5);
      expect(report.players_with_inputs).toBe(20);
      await Promise.all(
        pages.map((page) =>
          expect(page.locator("table tbody tr")).toHaveCount(5),
        ),
      );
      if (stage < 3) await action(0, { action: "start" });
    }
    current = await state();
    expect(
      current.teams.every(
        (team: { history: unknown[] }) => team.history.length === 4,
      ),
    ).toBe(true);
    for (const page of pages.slice(10)) {
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
      ).toBe(true);
    }
    expect(errors).toEqual([]);
    await testInfo.attach("20-player-report", {
      body: JSON.stringify(
        {
          sessions: 20,
          mobile: 10,
          tutorialTeams: 5,
          browserErrors: errors,
          stages: reports,
        },
        null,
        2,
      ),
      contentType: "application/json",
    });
  } finally {
    await Promise.all(contexts.map((context) => context.close()));
  }
});
