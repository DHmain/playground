import "./styles.css";
import type { GameState, Team, Person, Key, ActionName } from "./types";
import { app, element, e, arrows, toast, mount as patchMount } from "./ui";
import { maze, relay, rope, gourd } from "./games";
import { animate } from "./animation";
import { ropeClock } from "./timing";
import { beep, updateAudio } from "./audio";
import { fetchState, postAction } from "./transport";
import { landingScreen, animateLanding } from "./landing";
import type { LandingRole } from "./types";

("use strict");
const titles = [
  "협동 미로 탈출",
  "랜덤 리듬 계주",
  "변속 단체 줄넘기",
  "박 터뜨리기",
];
const desc = [
  "15×15 → 19×19 → 23×23 미로를 조별로 순환! 담당 방향을 협동해 출구를 찾으세요. 직선은 최대 3칸이며 최단 경로 길이는 동일합니다.",
  "각자 담당 키 하나로 연속 노트를 처리하세요. 노트별 속도가 달라 추월 가능 · 최대 120 BPM · MISS마다 +1초 · ±0.16초 판정.",
  "줄이 넘어갈 때마다 바뀌는 내 키를 확인하세요! 최대 100 BPM · ±0.12초 판정 · 120초 동안 성공한 점프마다 1점.",
  "중앙에서 가속하는 타겟 바! 2초 주기 · 좁아진 중앙을 정확히 노리세요.",
];

let token = localStorage.getItem("fourward-token") || "",
  S: GameState = null!,
  lastSignature = "",
  selectedTeam: number | null = null,
  baseTime = 0,
  basePerf = 0,
  rtt = 0,
  online = false;
let busy = false;

async function act(action: ActionName, data: Record<string, unknown> = {}) {
  try {
    const result = await postAction(token, action, data);
    if (result.token) {
      token = result.token;
      localStorage.setItem("fourward-token", token);
      lastSignature = "";
    }
    await poll();
    return true;
  } catch (err) {
    toast(err instanceof Error ? err.message : "연결을 확인하세요.");
    return false;
  }
}
function serverNow() {
  return S?.paused ? S.now : baseTime + (performance.now() - basePerf) / 1000;
}
async function poll() {
  if (busy) return;
  busy = true;
  try {
    const before = performance.now();
    const data = await fetchState(token);
    rtt = performance.now() - before;
    baseTime = data.now + rtt / 2000;
    basePerf = performance.now();
    if (
      S &&
      (data.phase !== "tutorial" || data.round !== S.round || data.paused)
    )
      clearLandingInputs();
    S = data;
    online = true;
    element("connection").textContent = `연결됨 · ${Math.round(rtt)}ms`;
    element("connection").className = "connection";
    if (token && !S.known) {
      token = "";
      localStorage.removeItem("fourward-token");
      toast("서버가 재시작되었습니다. 다시 입장하세요.");
    }
    const sig = JSON.stringify({
      ...S,
      now: 0,
      waiting: S.waiting,
      lobby: S.lobby,
    });
    if (sig !== lastSignature) {
      lastSignature = sig;
      render();
    }
  } catch (err) {
    online = false;
    clearLandingInputs();
    element("connection").textContent = "서버 연결 끊김 · 재연결 중";
    element("connection").className = "connection offline";
    if (!S) joinScreen();
  } finally {
    busy = false;
  }
}
function joinScreen() {
  if (app.querySelector("#name")) return;
  mount(
    `<section class="card join"><div class="eyebrow">TEAMWORK MAKES THE FINISH LINE</div><h1>같이 눌러야,<br>함께 도착합니다.</h1><p class="muted">협동 미로부터 박 터뜨리기까지.<br>이름을 입력하고 우리 조에 합류하세요.</p><form id="joinForm"><label for="name">참가자 이름</label><input id="name" name="name" maxlength="24" required placeholder="김싸피" class="wide" autocomplete="nickname"><button class="primary wide" style="margin-top:12px">대기실 입장 →</button></form><div class="notice small">${S?.game_test ? "GAME TEST · 이름을 입력하면 첫 참가자가 자동으로 사회자가 됩니다." : "서버 PC와 같은 네트워크에서 접속해 주세요. 사회자도 먼저 이름으로 입장합니다."}</div></section>`,
  );
  element<HTMLFormElement>("joinForm").onsubmit = (ev) => {
    ev.preventDefault();
    act("join", { name: element<HTMLInputElement>("name").value });
  };
}
function people(list: Person[]) {
  return list
    .map(
      (p) =>
        `<span class="badge ${p.online ? "" : "offline"}">${e(p.name)}${p.ai ? " · AI" : ""}${p.me ? " · 나" : ""}${p.online ? "" : " · 연결 끊김"}</span>`,
    )
    .join(" ");
}
let testBots = 0;
function testPanel() {
  return `<section class="card"><div class="eyebrow">GAME TEST · 직접 플레이 테스트</div><p>게임을 선택하면 점수와 진행을 초기화하고 바로 시작합니다. 혼자 플레이하면 모든 입력을 직접 확인할 수 있습니다.</p><label>AI 팀원 <select data-test-bots>${[0, 1, 2, 3].map((n) => `<option value="${n}" ${n === testBots ? "selected" : ""}>${n}명${n === 0 ? " · 혼자 플레이" : ""}</option>`).join("")}</select></label><div class="row" style="margin-top:12px">${titles.map((name, stage) => `<button data-action="test_stage" data-stage="${stage}">${name}</button>`).join("")}${S.stage >= 0 ? `<button class="primary" data-action="test_stage" data-stage="${S.stage}">현재 게임 다시 시작</button>` : ""}</div><p class="small muted">방향키 / SPACE 또는 화면 버튼 · 계주는 고정 키·연속 노트, 줄넘기는 매 회차 새 키 · 소리는 상단 버튼으로 켜세요.</p></section>`;
}
function render() {
  if (!token || !S?.known) {
    joinScreen();
    return;
  }
  if (S.phase === "tutorial") {
    mount(landingScreen(S));
    animateLanding(S, serverNow());
  } else if (S.phase === "lobby") lobby();
  else match();
}
function landingTutorialCard() {
  return `<section class="card"><div class="eyebrow">필수 협동 튜토리얼</div><h2>깡통 착륙 → 1스테이지</h2><p class="muted">경기를 시작하면 각 조가 차례로 착륙을 체험합니다. 4인 팀은 A(왼쪽) · L(오른쪽) · U(출력 증가) · D(출력 감소)를 한 명씩 맡습니다. 모든 조의 비행이 끝나면 미로가 자동 시작됩니다. 연료 50 · 연습 점수는 본경기에 미반영.</p></section>`;
}
function lobby() {
  const focus = document.activeElement?.id;
  const pin = document.querySelector<HTMLInputElement>("#pin")?.value || "";
  mount(
    `${landingTutorialCard()}<div class="row between"><div><div class="eyebrow">LOBBY / TEAM SELECTION</div><h1>우리 팀을 완성하세요</h1><p class="muted">빈자리의 ＋ 버튼으로 참여하세요. 사회자도 조에 들어가 함께 플레이할 수 있습니다.</p></div><span class="badge">사회자: ${e(S.host_name || "아직 없음")}</span></div><section class="card"><div class="row between"><div><h2>대기 인원 · ${S.waiting.length}명</h2><div class="row">${people(S.waiting) || '<span class="muted">대기 중인 참가자가 없습니다.</span>'}</div></div><button data-action="spectate">조에서 나가기 / 대기로</button></div></section><div class="row between"><h2>조 편성 <span class="muted small">각 1~4명 · 1개 조부터 진행 가능</span></h2>${S.host ? `<div class="row"><select aria-label="조 수" data-team-count>${[2, 3, 4, 5].map((n) => `<option ${S.team_count === n ? "selected" : ""}>${n}</option>`).join("")}</select><button data-action="shuffle">⤨ 랜덤 섞기</button><button data-action="clear_ai">임시 AI 전체 제거</button><button class="primary" data-action="start_play">${S.my_team === null ? "플레이어로 참가하고 시작 →" : "우리 조로 경기 시작 →"}</button>${S.my_team === null ? '<button data-action="start">관전으로 시작</button>' : ""}</div>` : ""}</div><div class="teams" style="--cols:${S.team_count}">${S.lobby.map((list, i) => `<section class="teamcard" style="--team:var(--c${i})"><div class="row between"><h2>${i + 1}조</h2><span class="badge">${list.length}/4</span></div>${[0, 1, 2, 3].map((j) => (list[j] ? `<div class="slot">${e(list[j].name)} ${list[j].ai ? "· AI " : ""}${list[j].me ? "(나)" : ""}<span class="small muted">${list[j].online ? "" : " · 오프라인"}</span></div>` : `<div class="slot empty"><button class="wide" data-action="team" data-team="${i}">＋ 참여</button></div>`)).join("")}${S.host ? `<div class="row" style="margin-top:10px"><button ${list.length >= 4 ? "disabled" : ""} data-action="add_ai" data-team="${i}">＋ 임시 AI</button><button ${list.some((p) => p.ai) ? "" : "disabled"} data-action="remove_ai" data-team="${i}">AI 1명 제거</button></div>` : ""}</section>`).join("")}</div>${S.host ? '<div class="notice small">임시 AI는 테스트용 자동 참가자입니다. 한 조에 본인 또는 AI 한 명만 있어도 시작할 수 있습니다. 총 2~3명도 조를 나눠 경기할 수 있습니다. 직접 플레이하려면 빈자리의 ＋ 참여를 누르세요. 미로에서는 AI 담당 방향만 자동으로 움직입니다. 대기실에서 제거할 수 있으며 서버 종료 시 사라집니다.</div>' : ""}${!S.host && !S.host_name ? `<section class="card" style="margin-top:20px"><h2>사회자석</h2><p class="small muted">서버 실행 창에 표시된 PIN을 입력하세요. 현재 조를 유지하며 사회자와 플레이어를 겸할 수 있습니다.</p><div class="row"><input type="password" id="pin" aria-label="사회자 PIN" placeholder="사회자 PIN" value="${e(pin)}"><button data-action="host">사회자로 참여</button></div></section>` : ""}<details><summary>진행 및 인원 보정 규칙</summary><div class="card"><p>미로: 1명은 모든 방향, 3명은 한 명이 상하, 2명은 상하/좌우를 나눠 맡습니다. 계주: 각자 고정 키 하나 · 무작위 속도의 연속 노트 · 최대 120 BPM · MISS마다 +1초. 줄넘기: 회차마다 바뀌는 개인별 키 · 120초 동안 성공한 점프마다 1점. 박 체력: 팀 인원 × 300, 바는 중앙에서 가속합니다.</p><p>각 조는 순서대로 경기하며 미로는 3회 순환하고 줄넘기는 2분간 진행합니다. 미로는 순위별 100/80/60/40/20점, 계주는 120점에서 추가 소요 초만큼 감점, 줄넘기는 성공 점프 수로 채점합니다. 미완주 팀은 진행률로 순위를 정합니다. 동률은 공동 순위, 동일 점수입니다. 인원 차이 보정은 시험용이며 미로의 소통 난도 차이는 남습니다.</p><p>랜덤 섞기는 온라인 참가자 전원을 배정합니다. 서버 재시작 시 경기 기록은 초기화됩니다.</p></div></details>`,
  );
  if (focus === "pin") {
    const input = document.querySelector<HTMLInputElement>("#pin");
    input?.focus();
  }
}
function match() {
  selectedTeam = S.active_team;
  const own = S.teams.find((t) => t.id === S.my_team);
  mount(
    `<div class="row between"><div><div class="eyebrow">${S.phase === "results" ? "STAGE RESULTS" : "LIVE MATCH"} / ${S.stage + 1} OF 4</div><h1>${titles[S.stage]}</h1></div><div class="row">${S.host ? `<button data-action="resetConfirm" id="resetButton">대기실로</button>${S.phase === "playing" ? `<button data-action="pause">${S.paused ? "▶ 재개" : "Ⅱ 일시정지"}</button>` : S.stage < 3 ? '<button class="primary" data-action="start">다음 스테이지 →</button>' : ""}` : ""}</div></div><div class="stages">${titles.map((n, i) => `<span class="${i === S.stage ? "on" : ""}">0${i + 1} ${n}</span>`).join("")}</div><div class="layout"><aside class="sidebar">${S.teams.map((t) => `<section class="status ${selectedTeam === t.id ? "active" : ""}" style="--team:var(--c${t.id})"><div class="row between"><h3>${t.id + 1}조 ${S.my_team === t.id ? "· MY TEAM" : ""}</h3><strong>${t.score}점</strong></div><ul>${t.members.map((p) => `<li><span>${e(p.name)}${p.ai ? " · AI" : ""}${p.me ? " · 나" : ""}</span><span class="${p.online ? "" : "offline"}">${p.online ? "접속" : "끊김"}</span></li>`).join("")}</ul><div class="progress"><i style="width:${Math.round(t.progress * 100)}%"></i></div><div class="small muted">${t.status === "waiting" ? "순서 대기" : t.completed ? (t.finish !== null ? "완주 " + t.finish.toFixed(1) + "초" : "시간 종료 · " + Math.round(t.progress * 100) + "%") : Math.round(t.progress * 100) + "% 진행"}</div><div class="small">${e(t.feedback)}</div></section>`).join("")}</aside><section><div class="arena"><div class="arenahead"><div><strong>${S.phase === "results" ? "경기 결과" : S.active_team! + 1 + "조 경기 중계"}</strong><div class="small muted">${S.phase === "results" ? "순위와 누적 점수를 확인하세요." : desc[S.stage]}</div></div><div class="clock" id="clock"></div></div><div class="stagebody">${S.phase === "results" ? results() : arena()}</div><div class="controller">${S.phase === "results" ? '<p class="muted">' + (S.stage < 3 ? "사회자가 다음 경기를 시작하면 자동으로 이동합니다." : "모든 경기가 끝났습니다. 수고하셨습니다!") + "</p>" : controller(own)}</div></div></section></div>`,
  );
  animate(S, serverNow());
}
function selectTeam(id: number) {
  selectedTeam = id;
  match();
}
function arena() {
  const t = S.teams.find((t) => t.id === S.active_team);
  if (!t) return "";
  const next = S.teams.find((q) => q.status === "waiting");
  return `<div class="turn-banner"><strong>${t.id + 1}조 차례</strong> · ${S.teams.findIndex((q) => q.id === t.id) + 1} / ${S.teams.length}번째 경기 <span class="small">${next ? "다음: " + (next.id + 1) + "조" : "마지막 조입니다"}</span></div><div class="stagegrid"><section class="pane" style="--team:var(--c${t.id})"><div class="row between"><h3>${t.id + 1}조</h3><span class="badge">LIVE</span></div>${S.stage === 0 ? maze(t) : S.stage === 1 ? relay(t) : S.stage === 2 ? rope(t, S) : gourd(t, S)}</section></div>`;
}
function controller(t: Team | undefined) {
  if (S.host && !t)
    return `<div class="notice"><strong>현재 관전 중입니다.</strong> ${S.teams.some((q) => !q.completed && q.members.some((p) => p.ai)) ? `<button class="primary" data-action="take_ai">AI 자리로 플레이 참가</button>` : "대기실로 돌아가 조에 참여한 뒤 시작해 주세요."}</div>`;
  if (!t)
    return '<p class="muted">관전 중입니다. 다음 경기 편성은 대기실에서 참여할 수 있습니다.</p>';
  if (t.status !== "active")
    return `<div class="notice">${t.completed ? "우리 조 경기가 끝났습니다." : "우리 조 순서를 기다려 주세요."} 현재 ${S.active_team! + 1}조 경기 중입니다.</div>`;
  let role =
    S.stage === 0
      ? (t.members.length === 1
          ? [["U", "D", "L", "R"]]
          : t.members.length === 2
            ? [
                ["U", "D"],
                ["L", "R"],
              ]
            : t.members.length === 3
              ? [["U", "D"], ["L"], ["R"]]
              : [["U"], ["D"], ["L"], ["R"]])[S.my_slot!]
      : S.stage === 1
        ? [t.relay_keys[S.my_slot!]]
        : S.stage === 2
          ? [t.rope_keys[S.my_slot!]]
          : ["S"];
  let label =
    S.stage === 0
      ? "내 담당 방향: " + role.map((k) => arrows[k]).join(" ")
      : S.stage === 1
        ? "내 고정 키: " + arrows[role[0]]
        : S.stage === 2
          ? "이번 점프: " + (role[0] === "S" ? "SPACE" : arrows[role[0]])
          : "중앙에 맞춰 던지기";
  return `<div class="row between"><strong>${t.id + 1}조 · ${e(t.members[S.my_slot!].name)}</strong><span class="badge">${label}</span></div>${S.stage === 3 ? `<div class="targetbar"><i class="zone"></i><i class="bull"></i><i class="needle" id="needle"></i></div><div class="small muted">중앙 30 · 안쪽 20 · 가장자리 10 · 중앙 가속 ×1.5 · 회전당 한 번</div>` : ""}<div class="controls">${role.map((k) => `<button class="key ${k === "S" ? "space primary" : ""}" data-key="${k}">${k === "S" ? "SPACE / 누르기" : arrows[k]}</button>`).join("")}</div><div class="small muted" style="text-align:center;margin-top:10px">${S.stage === 2 ? "매 회차 새 키 · 잘못 누르면 해당 회차 실패 · " : ""}길게 누르기·키 자동 반복은 입력되지 않습니다.</div>`;
}
function results() {
  const ordered = [...S.teams].sort((a, b) => a.rank - b.rank);
  return `<table><thead><tr><th>순위</th><th>팀</th><th>기록</th><th>획득</th><th>합계</th></tr></thead><tbody>${ordered.map((t) => `<tr><td>${t.rank}위</td><td>${t.id + 1}조</td><td>${S.stage === 2 ? t.jump_count + "회 성공" : t.finish !== null ? t.finish.toFixed(1) + "초" : Math.round(t.progress * 100) + "% · 미완주"}</td><td>+${t.points}</td><td>${t.score}</td></tr>`).join("")}</tbody></table>${
    S.stage === 3
      ? `<div class="notice"><strong>종합 우승: ${S.teams
          .filter((t) => t.score === Math.max(...S.teams.map((q) => q.score)))
          .map((t) => `${t.id + 1}조`)
          .join(
            ", ",
          )}!</strong><br>4개 스테이지 누적 점수 기준입니다. 동점은 공동 우승입니다.</div>`
      : ""
  }`;
}
let lastInput = 0;
function sendKey(key: Key) {
  if (
    !online ||
    !S ||
    S.phase !== "playing" ||
    S.paused ||
    S.my_team !== S.active_team ||
    serverNow() < S.start
  )
    return;
  if (performance.now() - lastInput < 65) return;
  lastInput = performance.now();
  act("input", { key, round: S.round });
}
const landingSources = new Map<string, LandingRole>();
const landingKeyMap: Record<string, LandingRole> = {
  KeyA: "left",
  ArrowLeft: "left",
  KeyL: "right",
  ArrowRight: "right",
  KeyU: "up",
  ArrowUp: "up",
  KeyD: "down",
  ArrowDown: "down",
};
function transmitLanding(role: LandingRole, pressed: boolean) {
  if (!S || S.phase !== "tutorial") return;
  void postAction(token, "landing_input", {
    role,
    pressed,
    round: S.round,
  }).catch(() => {});
}
function pressLanding(source: string, role: LandingRole) {
  if (
    !online ||
    S?.phase !== "tutorial" ||
    S.paused ||
    S.my_team !== S.active_team ||
    !S.landing_roles.includes(role) ||
    landingSources.has(source)
  )
    return;
  landingSources.set(source, role);
  transmitLanding(role, true);
}
function releaseLanding(source: string) {
  const role = landingSources.get(source);
  landingSources.delete(source);
  if (role && ![...landingSources.values()].includes(role))
    transmitLanding(role, false);
}
function clearLandingInputs() {
  const held = new Set(landingSources.values());
  landingSources.clear();
  held.forEach((role) => transmitLanding(role, false));
}
setInterval(() => {
  if (online)
    new Set(landingSources.values()).forEach((role) =>
      transmitLanding(role, true),
    );
}, 180);
document.addEventListener("keyup", (ev) => releaseLanding("key-" + ev.code));
window.addEventListener("blur", clearLandingInputs);
document.addEventListener("visibilitychange", () => {
  if (document.hidden) clearLandingInputs();
});
app.addEventListener("pointerdown", (ev) => {
  const button = (ev.target as Element).closest<HTMLButtonElement>(
    "[data-landing-role]",
  );
  if (!button || button.disabled) return;
  ev.preventDefault();
  button.setPointerCapture(ev.pointerId);
  pressLanding(
    "pointer-" + ev.pointerId,
    button.dataset.landingRole as LandingRole,
  );
});
for (const name of [
  "pointerup",
  "pointercancel",
  "lostpointercapture",
] as const) {
  app.addEventListener(name, (ev) => releaseLanding("pointer-" + ev.pointerId));
}
document.addEventListener("keydown", (ev) => {
  if (
    ["INPUT", "SELECT", "TEXTAREA"].includes((ev.target as HTMLElement).tagName)
  )
    return;
  if (S?.phase === "tutorial") {
    const role = landingKeyMap[ev.code];
    if (role) {
      ev.preventDefault();
      pressLanding("key-" + ev.code, role);
    }
    return;
  }
  const k =
    (
      {
        ArrowUp: "U",
        ArrowDown: "D",
        ArrowLeft: "L",
        ArrowRight: "R",
        Space: "S",
      } as Record<string, Key>
    )[ev.code] ||
    (
      {
        ArrowUp: "U",
        ArrowDown: "D",
        ArrowLeft: "L",
        ArrowRight: "R",
        " ": "S",
        Spacebar: "S",
      } as Record<string, Key>
    )[ev.key];
  if (k && S?.phase === "playing") {
    ev.preventDefault();
    if (!ev.repeat) sendKey(k);
  }
});
let lastSound = "";
function frame() {
  requestAnimationFrame(frame);
  animate(S, serverNow());
  if (S?.phase === "tutorial") animateLanding(S, serverNow());
  updateAudio(S);
  if (!S || S.paused || S.phase !== "playing" || serverNow() < S.start) return;
  const n = serverNow(),
    t = S.teams.find((t) => t.id === S.active_team);
  if (!t || t.finish !== null) return;
  let cue = null;
  if (S.stage === 2) {
    const timing = ropeClock(t, n);
    if (Math.abs(n - timing.beat) < 0.06)
      cue = `rope-${S.round}-${t.id}-` + timing.index;
    else if (timing.index > 0 && Math.abs(n - timing.previous) < 0.06)
      cue = `rope-${S.round}-${t.id}-` + (timing.index - 1);
  }
  if (S.stage === 1) {
    const note = t.relay_notes.find((note) => Math.abs(n - note.at) < 0.06);
    if (note) cue = `relay-${S.round}-${t.id}-${note.id}`;
  }
  if (cue && cue !== lastSound) {
    lastSound = cue;
    beep();
  }
}
requestAnimationFrame(frame);
setInterval(poll, 180);
poll();
if (location.protocol === "file:") {
  mount(
    '<div class="card join"><h1>서버 주소로 접속해 주세요</h1><p>HTML 파일을 직접 여는 방식이 아닙니다. 같은 폴더에서 <code>python server.py</code>를 실행하고 표시된 <code>http://서버IP:8000</code> 주소를 열어주세요.</p></div>',
  );
}
function mount(html: string) {
  patchMount((S?.game_test && S.host ? testPanel() : "") + html);
}

app.addEventListener("click", (event) => {
  const button = (event.target as Element).closest<HTMLButtonElement>(
    "button[data-action]",
  );
  if (!button || button.disabled) return;
  const action = button.dataset.action!;
  if (action === "resetConfirm") {
    if (confirm("모든 경기 점수를 초기화하고 대기실로 돌아갈까요?"))
      void act("reset");
    return;
  }
  const data: Record<string, unknown> = {};
  if (button.dataset.team !== undefined)
    data.team = Number(button.dataset.team);
  if (action === "test_stage") {
    data.stage = Number(button.dataset.stage);
    data.bots = testBots;
  }
  if (action === "host") data.pin = element<HTMLInputElement>("pin").value;
  void act(action as ActionName, data);
});
app.addEventListener("change", (event) => {
  const select = event.target as HTMLSelectElement;
  if (select.matches("[data-test-bots]")) testBots = Number(select.value);
  if (select.matches("[data-team-count]"))
    void act("count", { count: Number(select.value) });
});
app.addEventListener("pointerdown", (event) => {
  const button = (event.target as Element).closest<HTMLButtonElement>(
    "button[data-key]",
  );
  if (!button || button.disabled) return;
  event.preventDefault();
  sendKey(button.dataset.key as Key);
});
