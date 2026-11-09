import type { GameState, LandingRole } from "./types";
import { e } from "./ui";

export const landingLabels: Record<LandingRole, string> = {
  left: "A / ← · 왼쪽 추진",
  right: "L / → · 오른쪽 추진",
  up: "U / ↑ · 출력 증가",
  down: "D / ↓ · 출력 감소",
};
export function landingScreen(S: GameState) {
  const s = S.landing!;
  const team = S.teams.find((t) => t.id === S.active_team)!;
  const owns = S.my_team === S.active_team;
  const roles = owns ? S.landing_roles : [];
  const done = s.status === "landed" || s.status === "crashed";
  return `<section class="card"><div class="eyebrow">필수 협동 튜토리얼 · 1스테이지 전</div><div class="row between"><h1>깡통 착륙</h1>${S.host ? `<div class="row"><button data-action="pause">${S.paused ? "▶ 재개" : "Ⅱ 일시정지"}</button><button data-action="resetConfirm">대기실로</button></div>` : ""}</div><p>${team.id + 1}조 차례 · ${S.teams.filter((t) => t.completed).length}/${S.teams.length}개 조 체험 완료 · 전 팀 비행 후 미로가 자동 시작됩니다.</p><div class="row">${S.teams.map((t) => `<span class="badge">${t.id + 1}조 · ${t.completed ? "체험 완료" : t.id === S.active_team ? "비행 중" : "대기"}</span>`).join("")}</div><p class="muted">네 조작을 나눠 맡으세요. 연료 50 · U+D는 출력 유지 · 둘 다 놓으면 추력 0 · 실패해도 다음 순서로 진행 · 연습 점수는 본경기에 미반영</p><div class="row">${team.members
    .map(
      (p, i) =>
        `<span class="badge">${e(p.name)} · ${rolesForSize(team.members.length)
          [i].map((r) => landingLabels[r])
          .join(" / ")}</span>`,
    )
    .join(
      "",
    )}</div><div class="row landing-hud" aria-live="off"><strong>연료 ${s.fuel.toFixed(1)}</strong><strong>출력 ${Math.round(s.throttle * 100)}%</strong><span>고도 ${s.y.toFixed(1)}m</span><span>하강 ${Math.max(0, -s.vy).toFixed(1)}m/s</span><span>바람 ${s.wind >= 0 ? "→" : "←"} ${Math.abs(s.wind).toFixed(1)}</span><span id="landing-clock"></span></div><svg class="landing-scene" viewBox="0 0 1000 550" role="img" aria-label="바람에 밀리는 깡통과 좁은 중앙 착륙장"><rect width="1000" height="550" fill="#101e33"/><path d="M0 490H1000V550H0Z" fill="#344251"/><path d="M442.625 487H557.375" stroke="#7be5b9" stroke-width="8"/><path d="M500 475V495" stroke="#ffdc79" stroke-width="4"/><text x="500" y="530" text-anchor="middle" fill="white">LANDING ZONE · 중앙 100점</text><g id="landing-can"><path d="M-12 -5L0 ${8 + s.throttle * 35}L12 -5Z" fill="#ffc568" opacity="${s.throttle > 0 && s.fuel > 0 && !done ? 1 : 0}"/><rect x="-20" y="-56" width="40" height="49" rx="5" fill="#cbd9e3"/><rect x="-12" y="-44" width="24" height="18" fill="#527589"/><path d="M-15 -9L-27 0H-34M15 -9L27 0H34" fill="none" stroke="#dceaf2" stroke-width="4"/><path d="M22 -20L50 -13L22 -6Z" fill="#74dcff" opacity="${s.active.includes("left") && s.fuel > 0 && !done ? 1 : 0}"/><path d="M-22 -20L-50 -13L-22 -6Z" fill="#74dcff" opacity="${s.active.includes("right") && s.fuel > 0 && !done ? 1 : 0}"/></g></svg><div class="notice" role="status">${done ? `${e(s.reason)} · 연습 ${s.score}점 · 3초 후 자동 진행` : S.paused ? "일시정지" : s.status === "ready" ? "준비 · 시작하면 바로 낙하합니다" : "중앙에 안전하게 착륙하세요. 수직 5m/s · 수평 3m/s 이하"}</div>${owns ? `<p><strong>내 담당: ${roles.map((r) => landingLabels[r]).join(" / ")}</strong></p><div class="controls">${roles.map((role) => `<button class="key ${s.active.includes(role) ? "primary" : ""}" data-landing-role="${role}" ${done ? "disabled" : ""}>${landingLabels[role]}</button>`).join("")}</div>` : `<p class="muted">${S.my_team === null ? "관전 중입니다." : "우리 조 순서를 기다리세요."}</p>`}<p class="small muted">키 또는 화면 버튼을 누르고 있으세요. 4인 팀은 한 사람당 한 조작. 1~3인 팀은 남는 조작을 묶어서 담당합니다.</p></section>`;
}
function rolesForSize(n: number): LandingRole[][] {
  if (n === 1) return [["left", "right", "up", "down"]];
  if (n === 2)
    return [
      ["left", "right"],
      ["up", "down"],
    ];
  if (n === 3) return [["left"], ["right"], ["up", "down"]];
  return [["left"], ["right"], ["up"], ["down"]];
}
export function animateLanding(S: GameState, now: number) {
  const s = S.landing;
  if (S.phase !== "tutorial" || !s) return;
  const dt =
    !S.paused && s.status === "playing"
      ? Math.max(0, Math.min(0.2, now - S.now))
      : 0;
  const x = 500 + (s.x + s.vx * dt) * 7.65;
  const y = 475 - Math.max(0, s.y + s.vy * dt) * 2.9;
  document
    .getElementById("landing-can")
    ?.setAttribute("transform", `translate(${x} ${y})`);
  const clock = document.getElementById("landing-clock");
  if (clock)
    clock.textContent = S.paused
      ? "PAUSED"
      : now < S.start
        ? `시작 ${Math.ceil(S.start - now)}`
        : `${Math.max(0, 60 - s.elapsed).toFixed(1)}초`;
}
