import type { Team, GameState } from "./types";
import { e, arrows } from "./ui";
export function maze(t: Team) {
  return `<div class="maze" style="grid-template-columns:repeat(${t.maze.length},1fr)">${t.maze.map((row, y) => row.map((v, x) => `<div class="cell ${v ? "wall" : ""} ${x === t.goal[0] && y === t.goal[1] ? "exit" : x === t.maze_start[0] && y === t.maze_start[1] ? "maze-start" : ""}">${t.pos[0] === x && t.pos[1] === y ? '<i class="avatar"></i>' : ""}</div>`).join("")).join("")}</div><p class="small muted">${t.id + 1}조 · 미로 ${t.maze_lap}/3 · ${t.maze.length}×${t.maze.length} · 파란 칸이 출발점, 녹색 칸이 출구입니다. 매 회차 출발 모서리가 바뀝니다. 최단 ${t.path_length}칸.</p>`;
}
function noteIcon(key: string) {
  if (key === "S") return '<span class="note-space">SPACE</span>';
  const rotation: Record<string, number> = { U: 0, R: 90, D: 180, L: 270 };
  return `<svg class="note-arrow" viewBox="0 0 32 32" aria-hidden="true"><path transform="rotate(${rotation[key]} 16 16)" d="M16 3 2 17h9v12h10V17h9Z"/></svg>`;
}
export function relay(t: Team) {
  if (t.finish !== null) return '<div class="big">완주!</div>';
  const keys = ["L", "D", "U", "R"];
  return `<div class="row">${t.members.map((p, i) => `<span class="badge">${e(p.name)} · ${arrows[t.relay_keys[i]]}</span>`).join("")}</div><div data-relay="${t.id}">준비</div><div class="runner-race" aria-label="60초 달리기"><div class="runner-finish">FINISH</div><div class="relay-runner" data-runner="${t.id}">🏃</div></div><p>기본 60초 · HIT ${t.relay_hit_count}회 · MISS ${t.relay_misses}회 · +${t.relay_misses}초</p><div class="relay-track" aria-label="속도가 다른 노트가 노란 판정선에 닿을 때 담당 키를 누르세요">${keys.map((k, i) => `<div class="relay-lane" style="top:${i * 25}%">${k === "S" ? "SPACE" : arrows[k]}</div>`).join("")}<div class="relay-line"></div>${t.relay_notes.map((note) => `<div id="relay-note-${t.id}-${note.id}" class="relay-note" aria-label="${arrows[note.key]}" style="top:calc(${keys.indexOf(note.key) * 25}% + 3px);transform:translateX(10000px)" data-note="${t.id}-${note.id}">${noteIcon(note.key)}</div>`).join("")}</div><div class="small muted">각자 고정 키 하나 · 노트별 무작위 속도 · 추월 가능 · 최대 120 BPM · 완주까지 연속 생성</div><div>달리기 ${Math.round(t.progress * 100)}%</div>`;
}
export function rope(t: Team, S: GameState) {
  return `<div class="big">${t.jump_count}<span class="small muted">회 성공 · 120초 도전</span></div><svg class="rope-scene" viewBox="0 0 600 260" role="img" aria-label="박자에 맞춰 회전하는 줄과 참가자의 점프"><path d="M35 225H565 M35 235H565" stroke="#c2a77b" stroke-width="2"/><path class="rope-cord" data-rope-back="${t.id}"/><g>${t.members
    .map((p, i) => {
      const x = 130 + i * (340 / Math.max(1, t.members.length - 1));
      return `<ellipse cx="${x}" cy="218" rx="23" ry="5" fill="#76532c" opacity=".15"/><g transform="translate(${x},0)"><g class="jumper" data-jumper="${t.id}-${i}"><circle cx="0" cy="127" r="13" fill="#e9b881"/><path d="M-13 118Q0 105 13 118" fill="var(--team)"/><path d="M-14 151Q0 141 14 151L12 180H-12Z"/><path class="limb" d="M-13 153L-26 170M13 153L26 170M-7 180L-10 211M7 180L10 211"/></g></g><text x="${x}" y="250" text-anchor="middle" font-size="12" fill="#70573b">${e(p.name)} · ${t.rope_keys[i] === "S" ? "SPACE" : arrows[t.rope_keys[i]]}</text>`;
    })
    .join(
      "",
    )}</g><path class="rope-cord" data-rope-front="${t.id}"/><g class="rope-impact" data-rope-impact="${t.id}" opacity="0" aria-hidden="true"><ellipse cx="300" cy="225" rx="110" ry="6"/><path d="M170 211l-18-14m75 12-8-23m81 22v-28m81 29 8-23m41 25 18-14"/><text x="300" y="185" text-anchor="middle">JUMP!</text></g><circle cx="55" cy="155" r="7" fill="#815333"/><circle cx="545" cy="155" r="7" fill="#815333"/></svg><p class="rope-hint small">줄이 발밑의 선에 닿을 때 이번 회차의 내 키 · 캐릭터는 실제 입력에 맞춰 점프합니다</p><div class="rope-pattern" aria-label="조별 8박 패턴">${t.rope_pattern.map((seconds, i) => `<span class="badge ${i === t.beat_index % 8 ? "on" : ""}" data-rope-note="${i}">${Math.round(60 / seconds)}<small> BPM</small></span>`).join("")}</div><div class="row between"><strong>${t.bpm} BPM</strong><span class="small muted">${t.change_in <= 2 ? `${t.change_in}박 후 ${t.next_bpm} BPM` : "리듬을 맞추세요"}</span></div>`;
}
export function gourd(t: Team, S: GameState) {
  return `<div class="gourd">${t.health === 0 ? "POP!" : Math.ceil((t.health / (S.rules.gourd_hp * t.members.length)) * 100) + "%"}</div><div class="progress"><i style="width:${100 * (1 - t.progress)}%"></i></div><div class="small muted">남은 체력 ${t.health} / ${S.rules.gourd_hp * t.members.length}</div><div class="targetbar" aria-label="첫 번째 주자의 중앙 가속 타겟 바"><i class="zone"></i><i class="bull"></i><i class="needle" data-target-slot="0"></i></div><p class="small muted">첫 번째 주자 바 중계 · 중앙에서 속도 ×1.5</p>`;
}
